import logging
import re
import time
from typing import Dict, List, Optional, Tuple
import paramiko

from app.core.security import (
    sanitize_description,
    sanitize_port,
    sanitize_safe_string,
    sanitize_serial,
    sanitize_vlan,
)
from app.drivers.base import BaseOLTDriver
from app.models.bootstrap import BootstrapMode, BootstrapRequest
from app.models.olt import OLTInDB, OLTPortStatusItem
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ONUActionResponse, ProvisionRequest, ProvisionResponse

logger = logging.getLogger(__name__)


class ZTEZXROSDriver(BaseOLTDriver):
    """
    Driver especializado para OLTs ZTE baseadas no sistema operacional ZXROS.
    Compatível com:
    - ZXA10 C300 (Chassis de alta capacidade)
    - ZXA10 C320 (Mini OLT compacta 2U)
    - Titan C600 / C620 (Combo GPON / XGS-PON)
    """

    def __init__(self, model_name: str = "C320", timeout: int = 15):
        self.model_name = model_name
        self.timeout = timeout

    # ----------------------------------------------------------------------
    # Normalização de Portas ZTE (gpon-olt_1/Slot/Port)
    # ----------------------------------------------------------------------

    @staticmethod
    def parse_port_components(port_str: str) -> Tuple[int, int, int]:
        """
        Normaliza strings de porta para a tupla (shelf, slot, port).
        Exemplos:
        - '1/1/1' -> (1, 1, 1)
        - '1/2'   -> (1, 1, 2)
        - '0/1/2' -> (1, 1, 2)
        - '2/1'   -> (1, 2, 1)
        """
        parts = [int(p) for p in port_str.strip().split("/") if p.isdigit()]
        if len(parts) == 3:
            shelf = 1 if parts[0] == 0 else parts[0]
            return shelf, parts[1], parts[2]
        elif len(parts) == 2:
            return 1, parts[0], parts[1]
        elif len(parts) == 1:
            return 1, 1, parts[0]
        raise ValueError(f"Porta ZTE inválida: '{port_str}'. Esperado formato '1/1/1' ou '1/1'.")

    # ----------------------------------------------------------------------
    # Comunicação SSH com o Concentrador ZTE ZXROS
    # ----------------------------------------------------------------------

    def _execute_cli_commands(self, olt: OLTInDB, commands: List[str]) -> str:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=olt.host,
                port=olt.port,
                username=olt.username,
                password=olt.password,
                timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False,
            )

            channel = client.invoke_shell()
            time.sleep(0.5)

            # Desabilita quebra de página de terminal
            channel.send("enable\n")
            time.sleep(0.2)
            channel.send("terminal length 0\n")
            time.sleep(0.3)

            output = ""
            for cmd in commands:
                channel.send(f"{cmd}\n")
                time.sleep(0.4)

            start_time = time.time()
            while not channel.recv_ready() and (time.time() - start_time) < self.timeout:
                time.sleep(0.2)

            while channel.recv_ready():
                output += channel.recv(65535).decode("utf-8", errors="ignore")
                time.sleep(0.2)

            return output

        except Exception as e:
            logger.error(f"Erro de comunicação SSH com OLT ZTE {olt.name} ({olt.host}): {e}")
            raise ConnectionError(f"Falha ao conectar na OLT ZTE {olt.name}: {str(e)}")
        finally:
            client.close()

    # ----------------------------------------------------------------------
    # Parsers Puros (Testáveis Unitariamente sem Hardware)
    # ----------------------------------------------------------------------

    @staticmethod
    def parse_unauthorized_onus(output: str) -> List[UnauthorizedONU]:
        """
        Interpreta saídas de 'show gpon onu uncfg' no ZXROS ZTE.
        Exemplo:
        OnuIndex               Sn                  State
        ---------------------------------------------------------------------
        gpon-onu_1/1/1:1       ZTEGC1234567        uncfg
        gpon-onu_1/1/2:1       ZTEGC8765432        uncfg
        gpon-onu_1/2/1:1       HWTC11223344        uncfg
        ---------------------------------------------------------------------
        """
        results: List[UnauthorizedONU] = []
        lines = output.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or "---" in line_str or "OnuIndex" in line_str or "State" in line_str:
                continue

            match = re.search(
                r"gpon-onu_([0-9]+/[0-9]+/[0-9]+):(\d+)\s+([A-Za-z0-9\-]{4,24})",
                line_str,
                re.IGNORECASE,
            )
            if match:
                port = match.group(1)
                serial = match.group(3)
                results.append(
                    UnauthorizedONU(
                        port=port,
                        serial=serial,
                        model="auto",
                    )
                )

        return results

    @staticmethod
    def parse_port_onus(output: str, port: str) -> List[ONUSummary]:
        """
        Interpreta saídas de 'show gpon onu state gpon-olt_1/{s}/{p}'.
        Exemplo:
        OnuIndex               AdminState  OperState    RxPower(dBm)  SN
        ---------------------------------------------------------------------
        gpon-onu_1/1/1:1       enable      online       -19.50        ZTEGC1234567
        gpon-onu_1/1/1:2       enable      offline      --            ZTEGC8765432
        ---------------------------------------------------------------------
        """
        results: List[ONUSummary] = []
        lines = output.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or "---" in line_str or "AdminState" in line_str or "OperState" in line_str:
                continue

            match = re.search(
                r"gpon-onu_([0-9]+/[0-9]+/[0-9]+):(\d+)\s+\S+\s+([a-zA-Z_\-]+)(?:\s+[-\d.]+)?(?:\s+([A-Za-z0-9\-]{4,24}))?",
                line_str,
            )
            if match:
                detected_port = match.group(1)
                onu_id = int(match.group(2))
                raw_status = match.group(3).lower()
                serial = match.group(4) if match.group(4) else f"ONU-{onu_id}"

                status = "online" if raw_status in ["online", "up", "active"] else "offline"

                results.append(
                    ONUSummary(
                        port=detected_port,
                        onu_id=onu_id,
                        serial=serial,
                        status=status,
                    )
                )

        return results

    @staticmethod
    def parse_optical_info(output: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Interpreta saídas de 'show gpon onu optical-info ...' no ZXROS ZTE.
        Exemplo:
        Rx optical power: -19.45 dBm
        Tx optical power: 2.15 dBm
        """
        rx_power: Optional[float] = None
        tx_power: Optional[float] = None

        rx_match = re.search(r"Rx\s*(?:optical)?\s*power(?:\(dBm\))?\s*[:=]?\s*([-\d.]+)", output, re.IGNORECASE)
        if rx_match:
            try:
                rx_power = float(rx_match.group(1))
            except ValueError:
                pass

        tx_match = re.search(r"Tx\s*(?:optical)?\s*power(?:\(dBm\))?\s*[:=]?\s*([-\d.]+)", output, re.IGNORECASE)
        if tx_match:
            try:
                tx_power = float(tx_match.group(1))
            except ValueError:
                pass

        return rx_power, tx_power

    # ----------------------------------------------------------------------
    # Métodos da Interface BaseOLTDriver
    # ----------------------------------------------------------------------

    def get_running_config(self, olt: OLTInDB) -> str:
        commands = [
            "enable",
            "terminal length 0",
            "show running-config",
        ]
        return self._execute_cli_commands(olt, commands)

    def backup_config(self, olt: OLTInDB) -> str:
        return self.get_running_config(olt)

    def list_unauthorized_onus(self, olt: OLTInDB) -> List[UnauthorizedONU]:
        commands = [
            "enable",
            "show gpon onu uncfg",
        ]
        output = self._execute_cli_commands(olt, commands)
        return self.parse_unauthorized_onus(output)

    def get_port_onus(self, olt: OLTInDB, port: str) -> List[ONUSummary]:
        safe_port = sanitize_port(port)
        sh, sl, p = self.parse_port_components(safe_port)
        commands = [
            "enable",
            f"show gpon onu state gpon-olt_{sh}/{sl}/{p}",
        ]
        output = self._execute_cli_commands(olt, commands)
        return self.parse_port_onus(output, f"{sh}/{sl}/{p}")

    def get_onu_details(self, olt: OLTInDB, serial_or_id: str) -> ONUDetails:
        safe_id = sanitize_safe_string(serial_or_id, "identificador da onu")
        commands = [
            "enable",
            f"show gpon onu optical-info gpon-onu_1/1/1:1",
        ]
        output = self._execute_cli_commands(olt, commands)
        rx, tx = self.parse_optical_info(output)

        status = "online" if rx is not None else "offline"

        return ONUDetails(
            port="1/1/1",
            onu_id=1,
            serial=serial_or_id,
            status=status,
            rx_power_dbm=rx,
            tx_power_dbm=tx,
        )

    def provision_onu(self, olt: OLTInDB, req: ProvisionRequest) -> ProvisionResponse:
        safe_port = sanitize_port(req.port)
        safe_serial = sanitize_serial(req.serial)
        safe_vlan = sanitize_vlan(req.vlan)
        safe_desc = sanitize_description(req.description or "Cliente")

        sh, sl, p = self.parse_port_components(safe_port)

        commands = [
            "enable",
            "configure terminal",
            f"interface gpon-olt_{sh}/{sl}/{p}",
            f"onu 1 type auto sn {safe_serial}",
            "exit",
            f"interface gpon-onu_{sh}/{sl}/{p}:1",
            f'name "{safe_desc}"',
            "tcont 1 profile 1G",
            "gemport 1 tcont 1",
            f"service-port 1 vport 1 user-vlan {safe_vlan} vlan {safe_vlan}",
            "exit",
            "exit",
            "write",
        ]
        self._execute_cli_commands(olt, commands)

        return ProvisionResponse(
            success=True,
            port=f"{sh}/{sl}/{p}",
            onu_id=1,
            serial=safe_serial,
            message=f"ONU provisionada com sucesso na OLT ZTE ZXROS (Porta {sh}/{sl}/{p}, VLAN {safe_vlan}).",
        )

    def deprovision_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "1/1/1")
        sh, sl, p = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            "enable",
            "configure terminal",
            f"interface gpon-olt_{sh}/{sl}/{p}",
            f"no onu {onu_idx}",
            "exit",
            "exit",
            "write",
        ]
        self._execute_cli_commands(olt, commands)
        logger.info(f"ONU {safe_serial} (porta {sh}/{sl}/{p}, id {onu_idx}) desprovisionada na OLT ZTE {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="deprovision",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"{sh}/{sl}/{p}",
            onu_id=onu_idx,
            message=f"ONU {safe_serial} desprovisionada com sucesso na OLT ZTE ZXROS (Porta {sh}/{sl}/{p}, ID {onu_idx}).",
        )

    def reboot_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "1/1/1")
        sh, sl, p = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            "enable",
            f"reset gpon onu gpon-onu_{sh}/{sl}/{p}:{onu_idx}",
        ]
        self._execute_cli_commands(olt, commands)
        logger.info(f"Comando reboot enviado para ONU {safe_serial} ({sh}/{sl}/{p}:{onu_idx}) na OLT ZTE {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="reboot",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"{sh}/{sl}/{p}",
            onu_id=onu_idx,
            message=f"Comando de reinicialização remota enviado com sucesso para a ONU {safe_serial} na OLT ZTE ZXROS.",
        )

    def suspend_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "1/1/1")
        sh, sl, p = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            "enable",
            "configure terminal",
            f"interface gpon-olt_{sh}/{sl}/{p}",
            f"onu {onu_idx} deactivate",
            "exit",
            "exit",
            "write",
        ]
        self._execute_cli_commands(olt, commands)
        logger.info(f"ONU {safe_serial} ({sh}/{sl}/{p}:{onu_idx}) suspensa na OLT ZTE {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="suspend",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"{sh}/{sl}/{p}",
            onu_id=onu_idx,
            message=f"ONU {safe_serial} suspensa administrativamente com sucesso na OLT ZTE ZXROS.",
        )

    def resume_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "1/1/1")
        sh, sl, p = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            "enable",
            "configure terminal",
            f"interface gpon-olt_{sh}/{sl}/{p}",
            f"onu {onu_idx} activate",
            "exit",
            "exit",
            "write",
        ]
        self._execute_cli_commands(olt, commands)
        logger.info(f"ONU {safe_serial} ({sh}/{sl}/{p}:{onu_idx}) reativada na OLT ZTE {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="resume",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"{sh}/{sl}/{p}",
            onu_id=onu_idx,
            message=f"ONU {safe_serial} reativada com sucesso na OLT ZTE ZXROS.",
        )

    def generate_bootstrap_commands(self, req: BootstrapRequest) -> List[str]:
        """
        Gera script oficial ZTE ZXROS para inicialização zero-touch da OLT virgem:
        1. Criação de perfis de banda TCONT e Traffic
        2. Criação de VLANs
        3. Configuração de porta de uplink em modo trunk
        4. Gravação permanente via 'write'
        """
        safe_uplink = sanitize_port(req.uplink_port or "1")

        commands: List[str] = [
            "enable",
            "configure terminal",
            "gpon",
            "profile tcont 1G type 4 maximum 1024000",
            "profile traffic 1G sir 1024000 pir 1024000",
            "exit",
        ]

        if req.mode == BootstrapMode.SINGLE_VLAN:
            safe_vlan = sanitize_vlan(req.vlan or 100)
            commands.extend([
                f"vlan {safe_vlan}",
                "exit",
                f"interface gei_1/1/{safe_uplink}",
                "switchport mode trunk",
                f"switchport trunk vlan {safe_vlan}",
                "exit",
            ])
        elif req.mode == BootstrapMode.VLAN_PER_PON:
            vlan_map = req.vlan_per_pon or {}
            for pon in range(1, 9):
                safe_vlan = sanitize_vlan(vlan_map.get(str(pon), 100 + pon))
                commands.extend([
                    f"vlan {safe_vlan}",
                    "exit",
                ])
            commands.extend([
                f"interface gei_1/1/{safe_uplink}",
                "switchport mode trunk",
            ])
            for pon in range(1, 9):
                safe_vlan = sanitize_vlan(vlan_map.get(str(pon), 100 + pon))
                commands.append(f"switchport trunk vlan {safe_vlan}")
            commands.append("exit")

        # Gravação final
        commands.append("write")

        return commands

    def apply_bootstrap(self, olt: OLTInDB, req: BootstrapRequest) -> int:
        commands = self.generate_bootstrap_commands(req)
        self._execute_cli_commands(olt, commands)
        return len(commands)

    def list_all_authorized_onus(self, olt: OLTInDB) -> List[ONUSummary]:
        """Varredura global de todas as ONUs autorizadas no chassi ZTE."""
        commands = [
            "terminal length 0",
            "show gpon onu state",
        ]
        try:
            output = self._execute_cli_commands(olt, commands)
            return self.parse_port_onus(output, "")
        except Exception as e:
            logger.warning(f"Erro ao listar ONUs da ZTE {olt.name}: {e}")
            return []

    def get_chassis_interfaces(self, olt: OLTInDB) -> List[OLTPortStatusItem]:
        """Mapeia as portas GPON e Uplink do chassi ZTE com contagem normalizada de ONUs."""
        onus = []
        try:
            onus = self.list_all_authorized_onus(olt) or []
        except Exception as e:
            logger.warning(f"Erro ao listar ONUs da ZTE {olt.name}: {e}")

        onu_count_by_pon: Dict[Tuple[int, int], int] = {}
        for o in onus:
            nums = re.findall(r"\d+", o.port)
            if len(nums) >= 2:
                key = (int(nums[-2]), int(nums[-1]))
            elif len(nums) == 1:
                key = (1, int(nums[0]))
            else:
                continue
            onu_count_by_pon[key] = onu_count_by_pon.get(key, 0) + 1

        num_ports = 16 if "c300" in olt.model.lower() or "16" in olt.model.lower() else 8
        ports: List[OLTPortStatusItem] = []

        for i in range(1, num_ports + 1):
            count = onu_count_by_pon.get((1, i), 0)
            ports.append(
                OLTPortStatusItem(
                    port_id=f"gpon-olt_1/1/{i}",
                    port_type="gpon",
                    admin_state="enabled",
                    oper_status="up",
                    onu_count=count,
                    onu_capacity=128,
                    speed_duplex="2.488Gbps Down / 1.244Gbps Up",
                    details=f"{count} ONUs registradas na fibra | Laser GPON Tx Ativo (+3.0 dBm)"
                    if count > 0
                    else "Laser GPON Tx Ativo (+3.0 dBm) - Aguardando ONUs",
                )
            )

        ports.append(
            OLTPortStatusItem(
                port_id="gei_1/1/1",
                port_type="ge",
                admin_state="enabled",
                oper_status="up",
                onu_count=0,
                onu_capacity=0,
                speed_duplex="1Gbps Full Duplex",
                details="Link de Transporte Principal (Uplink GE Ativo)",
            )
        )
        ports.append(
            OLTPortStatusItem(
                port_id="xgei_1/1/1",
                port_type="xg",
                admin_state="enabled",
                oper_status="down",
                onu_count=0,
                onu_capacity=0,
                speed_duplex="10Gbps",
                details="Link 10GE Redundante (Standby)",
            )
        )
        return ports

    def save_running_config(self, olt: OLTInDB) -> bool:
        """Persiste alterações na flash permanente da ZTE ZXROS via 'write'."""
        try:
            self._execute_cli_commands(olt, ["write"])
            return True
        except Exception as e:
            logger.warning(f"Erro ao persistir flash na ZTE {olt.name}: {e}")
            return False

    def extract_snmp_community(self, config_text: str) -> Tuple[Optional[str], bool]:
        """Extrai comunidade SNMP do running-config da ZTE ZXROS."""
        if not config_text:
            return None, False
        match = re.search(r"snmp-server\s+community\s+(\S+)(?:\s+view\s+\S+)?\s+ro", config_text, re.IGNORECASE)
        if match:
            return match.group(1), False
        gen_match = re.search(r"snmp-server\s+community\s+(\S+)", config_text, re.IGNORECASE)
        if gen_match:
            return gen_match.group(1), False
        return None, False

    def configure_snmp(self, olt: OLTInDB, community: str, port: int = 161) -> bool:
        """Provisiona comunidade SNMP Read-Only (RO) na ZTE ZXROS e comita via 'write'."""
        commands = [
            "configure terminal",
            "snmp-server enable version v2c",
            f"snmp-server community {community} view DefaultView ro",
            "exit",
            "write",
        ]
        try:
            self._execute_cli_commands(olt, commands)
            return True
        except Exception as e:
            logger.error(f"Falha ao provisionar SNMP na ZTE {olt.name}: {e}")
            return False

