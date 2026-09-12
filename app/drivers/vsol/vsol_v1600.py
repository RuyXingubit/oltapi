import logging
import re
import time
from typing import List, Optional, Tuple
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
from app.models.olt import OLTInDB
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ONUActionResponse, ProvisionRequest, ProvisionResponse

logger = logging.getLogger(__name__)


class VSOLV1600Driver(BaseOLTDriver):
    """
    Driver especializado para OLTs V-SOL da família V1600 (especificamente V1600GT e V1600G GPON).
    Compatível com chassis standalone de 4, 8 e 16 portas GPON com uplinks 10GE (xe / tg / 10ge) e GE.
    """

    def __init__(self, model_name: str = "V1600GT", timeout: int = 15):
        self.model_name = model_name
        self.timeout = timeout

    # ----------------------------------------------------------------------
    # Normalização de Portas V-SOL (GPON 0/X)
    # ----------------------------------------------------------------------

    @staticmethod
    def parse_port_components(port_str: str) -> Tuple[int, int]:
        """
        Normaliza strings de porta para a tupla (slot, pon).
        Exemplos:
        - '0/1'   -> (0, 1)
        - '1'     -> (0, 1)
        - '0/1/2' -> (0, 2)
        """
        parts = [int(p) for p in port_str.strip().split("/") if p.isdigit()]
        if len(parts) >= 2:
            return parts[0], parts[1]
        elif len(parts) == 1:
            return 0, parts[0]
        raise ValueError(f"Porta V-SOL inválida: '{port_str}'. Esperado formato '0/1' ou '1'.")

    # ----------------------------------------------------------------------
    # Comunicação SSH com o Concentrador V-SOL V1600GT
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
            logger.error(f"Erro de comunicação SSH com OLT V-SOL {olt.name} ({olt.host}): {e}")
            raise ConnectionError(f"Falha ao conectar na OLT V-SOL {olt.name}: {str(e)}")
        finally:
            client.close()

    # ----------------------------------------------------------------------
    # Parsers Puros (Testáveis Unitariamente sem Hardware)
    # ----------------------------------------------------------------------

    @staticmethod
    def parse_unauthorized_onus(output: str) -> List[UnauthorizedONU]:
        """
        Interpreta saídas de 'show ont autofind all' ou 'show ont unauth' na V-SOL V1600GT.
        Exemplo:
        -----------------------------------------------------------------------------
        Port       ONT-SN            Vendor     Model           Time
        -----------------------------------------------------------------------------
        gpon 0/1   VSOL12345678      VSOL       V2801SG         2026-09-11 10:15:30
        gpon 0/1   HWTC88776655      HWTC       EG8145V5        2026-09-11 10:18:22
        gpon 0/2   INCL99887766      INCL       110B            2026-09-11 10:20:05
        -----------------------------------------------------------------------------
        """
        results: List[UnauthorizedONU] = []
        lines = output.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or "---" in line_str or "ONT-SN" in line_str or "Port" in line_str and "Vendor" in line_str:
                continue

            match = re.search(
                r"(?:gpon\s+)?([0-9]+/[0-9]+)\s+([A-Za-z0-9\-]{4,24})(?:\s+([A-Za-z0-9_\-]+))?(?:\s+([A-Za-z0-9_\-]+))?",
                line_str,
                re.IGNORECASE,
            )
            if match:
                port = match.group(1)
                serial = match.group(2)
                vendor = match.group(3) or ""
                model = match.group(4) or vendor or "auto"

                results.append(
                    UnauthorizedONU(
                        port=port,
                        serial=serial,
                        model=model,
                    )
                )

        return results

    @staticmethod
    def parse_port_onus(output: str, port: str) -> List[ONUSummary]:
        """
        Interpreta saídas de 'show ont info 0/{pon} all' na V-SOL V1600GT.
        Exemplo:
        -----------------------------------------------------------------------------
        Port    ONT-ID  Serial-Number     Status    Distance(m)  RxPower(dBm)  Description
        -----------------------------------------------------------------------------
        0/1     1       VSOL12345678      online    450          -19.50        Cliente_01
        0/1     2       VSOL87654321      offline   --           --            Cliente_02
        -----------------------------------------------------------------------------
        """
        results: List[ONUSummary] = []
        lines = output.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or "---" in line_str or "Serial-Number" in line_str or "Distance" in line_str:
                continue

            match = re.search(
                r"(?:0/)?([0-9]+)\s+(\d+)\s+([A-Za-z0-9\-]{4,24})\s+([a-zA-Z_\-]+)",
                line_str,
            )
            if match:
                pon = match.group(1)
                onu_id = int(match.group(2))
                serial = match.group(3)
                raw_status = match.group(4).lower()

                status = "online" if raw_status in ["online", "up", "active"] else "offline"

                results.append(
                    ONUSummary(
                        port=f"0/{pon}",
                        onu_id=onu_id,
                        serial=serial,
                        status=status,
                    )
                )

        return results

    @staticmethod
    def parse_optical_info(output: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Interpreta saídas de 'show ont optical-info 0/{pon} {id}' na V-SOL V1600GT.
        Exemplo:
        Rx optical power(dBm)                 : -19.45
        Tx optical power(dBm)                 : 2.15
        OLT Rx optical power(dBm)             : -20.10
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
            "show ont autofind all",
        ]
        output = self._execute_cli_commands(olt, commands)
        return self.parse_unauthorized_onus(output)

    def get_port_onus(self, olt: OLTInDB, port: str) -> List[ONUSummary]:
        safe_port = sanitize_port(port)
        slot, pon = self.parse_port_components(safe_port)
        commands = [
            "enable",
            f"show ont info 0/{pon} all",
        ]
        output = self._execute_cli_commands(olt, commands)
        return self.parse_port_onus(output, f"0/{pon}")

    def get_onu_details(self, olt: OLTInDB, serial_or_id: str) -> ONUDetails:
        safe_id = sanitize_safe_string(serial_or_id, "identificador da onu")
        commands = [
            "enable",
            f"show ont optical-info 0/1 {safe_id}",
        ]
        output = self._execute_cli_commands(olt, commands)
        rx, tx = self.parse_optical_info(output)

        status = "online" if rx is not None else "offline"

        return ONUDetails(
            port="0/1",
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

        slot, pon = self.parse_port_components(safe_port)

        commands = [
            "enable",
            "configure terminal",
            f"interface gpon 0/{pon}",
            f'ont add 1 sn-auth {safe_serial} vlan {safe_vlan} desc "{safe_desc}"',
            "exit",
            "exit",
            "write",
        ]
        self._execute_cli_commands(olt, commands)

        return ProvisionResponse(
            success=True,
            port=f"0/{pon}",
            onu_id=1,
            serial=safe_serial,
            message=f"ONU provisionada com sucesso na OLT V-SOL V1600GT (Porta 0/{pon}, VLAN {safe_vlan}).",
        )

    def deprovision_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "0/1")
        slot, pon = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            "enable",
            "configure terminal",
            f"interface gpon 0/{pon}",
            f"no ont {onu_idx}",
            "exit",
            "exit",
            "write",
        ]
        self._execute_cli_commands(olt, commands)
        logger.info(f"ONU {safe_serial} (porta 0/{pon}, id {onu_idx}) desprovisionada na OLT V-SOL {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="deprovision",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"0/{pon}",
            onu_id=onu_idx,
            message=f"ONU {safe_serial} desprovisionada com sucesso na OLT V-SOL (Porta 0/{pon}, ID {onu_idx}).",
        )

    def reboot_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "0/1")
        slot, pon = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            "enable",
            "configure terminal",
            f"interface gpon 0/{pon}",
            f"ont reset {onu_idx}",
            "exit",
            "exit",
        ]
        self._execute_cli_commands(olt, commands)
        logger.info(f"Comando reboot enviado para ONU {safe_serial} (0/{pon}:{onu_idx}) na OLT V-SOL {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="reboot",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"0/{pon}",
            onu_id=onu_idx,
            message=f"Comando de reinicialização remota enviado com sucesso para a ONU {safe_serial} na OLT V-SOL.",
        )

    def suspend_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "0/1")
        slot, pon = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            "enable",
            "configure terminal",
            f"interface gpon 0/{pon}",
            f"ont deactivate {onu_idx}",
            "exit",
            "exit",
            "write",
        ]
        self._execute_cli_commands(olt, commands)
        logger.info(f"ONU {safe_serial} (0/{pon}:{onu_idx}) suspensa na OLT V-SOL {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="suspend",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"0/{pon}",
            onu_id=onu_idx,
            message=f"ONU {safe_serial} suspensa administrativamente com sucesso na OLT V-SOL.",
        )

    def resume_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "0/1")
        slot, pon = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            "enable",
            "configure terminal",
            f"interface gpon 0/{pon}",
            f"ont activate {onu_idx}",
            "exit",
            "exit",
            "write",
        ]
        self._execute_cli_commands(olt, commands)
        logger.info(f"ONU {safe_serial} (0/{pon}:{onu_idx}) reativada na OLT V-SOL {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="resume",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"0/{pon}",
            onu_id=onu_idx,
            message=f"ONU {safe_serial} reativada com sucesso na OLT V-SOL.",
        )

    def generate_bootstrap_commands(self, req: BootstrapRequest) -> List[str]:
        """
        Gera script oficial V-SOL V1600GT para inicialização zero-touch da OLT virgem:
        1. Criação de perfis DBA e Line Profile
        2. Configuração de VLAN de serviço
        3. Configuração de porta de uplink (10GE / GE)
        4. Habilitação de autofind nas portas GPON
        5. Gravação permanente na flash via 'write'
        """
        safe_uplink = sanitize_port(req.uplink_port or "1")

        commands: List[str] = [
            "enable",
            "configure terminal",
            # DBA Profile
            "profile dba 1 dba-name DBA-DEFAULT type 4 max 1024000",
            # Line Profile
            "profile line 1 line-name LINE-DEFAULT",
            "tcont 1 dba-id 1",
            "gem add 1 tcont 1",
        ]

        if req.mode == BootstrapMode.SINGLE_VLAN:
            safe_vlan = sanitize_vlan(req.vlan or 100)
            commands.extend([
                f"gem mapping 1 1 vlan {safe_vlan}",
                "exit",
                f"vlan {safe_vlan}",
                "exit",
                # Configuração da porta de uplink
                f"interface ge 0/{safe_uplink}",
                "switchport mode trunk",
                f"switchport trunk allowed vlan add {safe_vlan}",
                "exit",
            ])
        elif req.mode == BootstrapMode.VLAN_PER_PON:
            vlan_map = req.vlan_per_pon or {}
            commands.append("exit")
            for pon in range(1, 9):
                safe_vlan = sanitize_vlan(vlan_map.get(str(pon), 100 + pon))
                commands.extend([
                    f"vlan {safe_vlan}",
                    "exit",
                ])
            commands.extend([
                f"interface ge 0/{safe_uplink}",
                "switchport mode trunk",
            ])
            for pon in range(1, 9):
                safe_vlan = sanitize_vlan(vlan_map.get(str(pon), 100 + pon))
                commands.append(f"switchport trunk allowed vlan add {safe_vlan}")
            commands.append("exit")

        # Habilita autofind nas portas GPON
        for pon in range(1, 9):
            commands.extend([
                f"interface gpon 0/{pon}",
                "ont-autofind enable",
                "exit",
            ])

        # Gravação final
        commands.append("write")

        return commands

    def apply_bootstrap(self, olt: OLTInDB, req: BootstrapRequest) -> int:
        commands = self.generate_bootstrap_commands(req)
        self._execute_cli_commands(olt, commands)
        return len(commands)
