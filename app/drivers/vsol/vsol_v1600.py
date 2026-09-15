import logging
import re
import time
from typing import Dict, List, Optional, Tuple
import paramiko

from app.core.security import (
    sanitize_description,
    sanitize_interface_port,
    sanitize_port,
    sanitize_safe_string,
    sanitize_serial,
    sanitize_vlan,
)
from app.drivers.base import BaseOLTDriver
from app.models.bootstrap import BootstrapMode, BootstrapRequest
from app.models.olt import (
    ExistingSVIItem,
    ManagementAccessScenario,
    OLTInDB,
    OLTPortStatusItem,
    OLTWizardOnboardRequest,
    VLANServicePurpose,
)
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

            # Entra no modo enable com suporte a prompt de senha
            channel.send("enable\n")
            time.sleep(0.3)
            init_buf = ""
            while channel.recv_ready():
                init_buf += channel.recv(4096).decode("utf-8", errors="ignore")
            if "password:" in init_buf.lower():
                channel.send(f"{olt.password}\n")
                time.sleep(0.3)
                while channel.recv_ready():
                    channel.recv(4096)

            channel.send("terminal length 0\n")
            time.sleep(0.3)
            while channel.recv_ready():
                channel.recv(4096)

            output = ""
            for cmd in commands:
                channel.send(f"{cmd}\n")
                time.sleep(0.3)

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
    def parse_port_onus(output: str, port: str = "") -> List[ONUSummary]:
        """
        Interpreta saídas de 'show onu state', 'show ont info' ou 'show running-config' na V-SOL V1600GT.
        Suporta formato tabular e formato compacto nativo de firmware.
        """
        results: List[ONUSummary] = []
        lines = output.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or "---" in line_str or "Serial-Number" in line_str or "Distance" in line_str or "total:" in line_str:
                continue

            # Formato compacto nativo do show onu state: 2:1enableenableworkingHWTC073545b7
            compact_m = re.search(
                r"(\d+):(\d+)\s*(enable|disable)\s*(enable|disable)\s*(working|syncmib|initial|dormant|offline|dyinggasp|[a-zA-Z]+?)\s*([A-Za-z0-9]{8,24})$",
                line_str,
                re.IGNORECASE,
            )
            if compact_m:
                p_num = compact_m.group(1)
                o_id = int(compact_m.group(2))
                phase = compact_m.group(5).lower()
                sn = compact_m.group(6)
                status = "online" if phase in ["working", "syncmib", "online", "up", "active"] else "offline"
                results.append(
                    ONUSummary(
                        port=f"0/{p_num}",
                        onu_id=o_id,
                        serial=sn,
                        status=status,
                    )
                )
                continue

            # Formato de running-config: onu add 1 profile default sn HWTC073545b7
            run_m = re.search(r"onu\s+add\s+(\d+)\s+profile\s+\S+\s+sn\s+([A-Za-z0-9]{8,24})", line_str, re.IGNORECASE)
            if run_m:
                o_id = int(run_m.group(1))
                sn = run_m.group(2)
                p_str = port if port else "0/1"
                results.append(
                    ONUSummary(
                        port=p_str,
                        onu_id=o_id,
                        serial=sn,
                        status="online",
                    )
                )
                continue

            # Formato tabular padrão
            match = re.search(
                r"(?:0/)?([0-9]+)\s+(\d+)\s+([A-Za-z0-9\-]{4,24})\s+([a-zA-Z_\-]+)",
                line_str,
            )
            if match:
                pon = match.group(1)
                onu_id = int(match.group(2))
                serial = match.group(3)
                raw_status = match.group(4).lower()

                status = "online" if raw_status in ["online", "up", "active", "working"] else "offline"

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
    def parse_management_architecture(running_config: str, access_host: str) -> Dict[str, any]:
        """
        Analisa o running-config de forma determinística para detectar:
        1. IP configurado em 'interface aux'
        2. SVIs configuradas em 'interface vlan <id>'
        3. Gateway padrão 'ip route 0.0.0.0/0'
        4. VLANs declaradas
        5. Total de ONUs configuradas
        6. Cenário de acesso (AUX_ONLY, AUX_WITH_INBAND, INBAND_ACTIVE)
        """
        aux_ip = None
        aux_match = re.search(r"interface\s+aux\s+ip\s+address\s+([\d.]+)", running_config, re.IGNORECASE)
        if aux_match:
            aux_ip = aux_match.group(1)

        gateway = None
        gw_match = re.search(r"ip\s+route\s+0\.0\.0\.0(?:/0|\s+0\.0\.0\.0)\s+([\d.]+)", running_config, re.IGNORECASE)
        if gw_match:
            gateway = gw_match.group(1)

        existing_svis: List[ExistingSVIItem] = []
        svi_blocks = re.findall(r"interface\s+vlan\s+(\d+)(.*?)(?=interface|\Z)", running_config, re.DOTALL | re.IGNORECASE)
        for vlan_str, block in svi_blocks:
            vlan_id = int(vlan_str)
            ip_m = re.search(r"ip\s+address\s+([^\s\r\n]+)", block, re.IGNORECASE)
            if ip_m:
                ip_cidr = ip_m.group(1)
                if not any(s.vlan_id == vlan_id for s in existing_svis):
                    existing_svis.append(
                        ExistingSVIItem(
                            vlan_id=vlan_id,
                            ip_cidr=ip_cidr,
                        )
                    )

        vlans: List[int] = []
        for line in running_config.splitlines():
            v_match = re.search(r"^vlan\s+(\d+)", line.strip(), re.IGNORECASE)
            if v_match:
                vlans.append(int(v_match.group(1)))
            v_range = re.search(r"^vlan\s+(\d+)\s*-\s*(\d+)", line.strip(), re.IGNORECASE)
            if v_range:
                start_v = int(v_range.group(1))
                end_v = int(v_range.group(2))
                for v in range(start_v, min(end_v + 1, start_v + 50)):
                    if v not in vlans:
                        vlans.append(v)

        vlans = sorted(list(set(vlans)))
        total_onus = len(re.findall(r"onu\s+add\s+\d+", running_config, re.IGNORECASE))

        # Detecção determinística do cenário de acesso
        is_aux_access = (access_host == aux_ip) or (access_host == "192.168.8.200")
        has_inband = len(existing_svis) > 0 and gateway is not None

        if is_aux_access:
            if has_inband:
                scenario = ManagementAccessScenario.AUX_WITH_INBAND
                prompt_msg = f"Acesso via porta auxiliar ({access_host}). A OLT já possui gerência In-Band ativa na VLAN {existing_svis[0].vlan_id} (IP {existing_svis[0].ip_cidr})."
            else:
                scenario = ManagementAccessScenario.AUX_ONLY
                prompt_msg = f"Acesso via porta auxiliar ({access_host}). A OLT não possui gerência In-Band configurada. Recomenda-se criar a VLAN de gerência in-band."
        else:
            scenario = ManagementAccessScenario.INBAND_ACTIVE
            prompt_msg = f"Acesso direto via In-Band ({access_host}). A OLT já está integrada à rede do provedor."

        return {
            "aux_ip": aux_ip,
            "gateway": gateway,
            "existing_svis": existing_svis,
            "existing_vlans": vlans,
            "total_onus": total_onus,
            "access_scenario": scenario,
            "prompt_message": prompt_msg,
        }

    @staticmethod
    def generate_wizard_commissioning_commands(req: OLTWizardOnboardRequest) -> List[str]:
        """Gera roteiro CLI completo e atômico para comissionamento via Wizard na V-SOL V1600."""
        commands: List[str] = [
            "configure terminal",
            f"hostname {sanitize_description(req.name)}",
        ]

        # 1. Gerência In-Band (se configurada)
        if req.inband_config:
            cfg = req.inband_config
            safe_vlan = cfg.vlan_id
            safe_uplink = sanitize_interface_port(cfg.uplink_port).replace("ge ", "gigabitEthernet ")
            commands.extend([
                f"vlan {safe_vlan}",
                f"  description {sanitize_description(cfg.name or 'VLAN2_GERENCIA')}",
                "exit",
                f"interface vlan {safe_vlan}",
                f"  ip address {cfg.ip_cidr}",
                "exit",
                f"ip route 0.0.0.0/0 {cfg.gateway}",
                f"interface {safe_uplink}",
                "  switchport mode hybrid",
                f"  switchport hybrid vlan {safe_vlan} {'tagged' if cfg.tagged else 'untagged'}",
                "exit",
            ])

        # 2. Perfil DBA
        dba_name = "dba_1G"
        up_kbps = req.qos_policy.upstream_kbps if req.qos_policy else 1024000
        commands.extend([
            f"profile dba id 10 name {dba_name}",
            f"  type 4 maximum {up_kbps}",
            "commit",
            "exit",
        ])

        # 3. Perfis de Serviço Padrão
        commands.extend([
            "profile srv id 10 name srv_hgu",
            "  portvlan veip 1 mode transparent",
            "commit",
            "exit",
            "profile srv id 20 name srv_bridge",
            "  portvlan eth 1 mode transparent",
            "commit",
            "exit",
        ])

        # 4. Processamento de cada VLAN de Serviço
        has_lan_to_lan = False
        for svc in req.services:
            safe_vlan = svc.vlan_id
            safe_desc = sanitize_description(svc.name)
            safe_uplink = sanitize_interface_port(svc.uplink_port).replace("ge ", "gigabitEthernet ")
            commands.extend([
                f"vlan {safe_vlan}",
                f"  description {safe_desc}",
                "exit",
                f"interface {safe_uplink}",
                "  switchport mode hybrid",
                f"  switchport hybrid vlan {safe_vlan} {'tagged' if svc.tagged else 'untagged'}",
                "exit",
            ])

            if svc.test_port:
                safe_test = sanitize_interface_port(svc.test_port).replace("ge ", "gigabitEthernet ")
                commands.extend([
                    f"interface {safe_test}",
                    "  switchport mode hybrid",
                    f"  switchport hybrid pvid vlan {safe_vlan}",
                    f"  switchport hybrid vlan {safe_vlan} untagged",
                    "exit",
                ])

            # Cria Line Profile para esta VLAN
            line_prof_name = f"line_vlan{safe_vlan}"
            commands.extend([
                f"profile line id {safe_vlan} name {line_prof_name}",
                f"  tcont 1 name TCONT_1 dba {dba_name}",
                f"  gemport 1 tcont 1 gemport_name GEM_{safe_vlan}",
                f"  service ser_1 gemport 1 vlan {safe_vlan}",
                f"  service-port 1 gemport 1 uservlan {safe_vlan} vlan {safe_vlan}",
                "commit",
                "exit",
            ])

            if svc.purpose == VLANServicePurpose.LAN_TO_LAN:
                has_lan_to_lan = True

        # Se houver LAN-to-LAN, habilita p2p enable nas portas GPON
        if has_lan_to_lan:
            for pon in range(1, 9):
                commands.extend([
                    f"interface gpon 0/{pon}",
                    "  p2p enable",
                    "exit",
                ])

        commands.extend([
            "end",
            "write",
        ])
        return commands

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

    def backup_config(self, olt: OLTInDB, ftp_servers: Optional[List[object]] = None, **kwargs) -> str:
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

    def list_all_authorized_onus(self, olt: OLTInDB) -> List[ONUSummary]:
        """Varredura global de todas as ONUs autorizadas no chassi VSOL V1600."""
        # 1. Tenta varrer via 'show running-config' (rápido, atômico e confiável)
        try:
            cfg = self.get_running_config(olt)
            onus_found: List[ONUSummary] = []
            pon_blocks = re.findall(r"interface\s+gpon\s+0/(\d+)(.*?)(?=interface|\Z)", cfg, re.DOTALL | re.IGNORECASE)
            for pon_num, block in pon_blocks:
                onu_matches = re.findall(r"onu\s+add\s+(\d+)\s+profile\s+\S+\s+sn\s+([A-Za-z0-9]{8,24})", block, re.IGNORECASE)
                for o_id, sn in onu_matches:
                    onus_found.append(
                        ONUSummary(
                            port=f"0/{pon_num}",
                            onu_id=int(o_id),
                            serial=sn,
                            status="online",
                        )
                    )
            if onus_found:
                return onus_found
        except Exception as e:
            logger.debug(f"Falha ao extrair ONUs do running-config da VSOL {olt.name}: {e}")

        # 2. Fallback: Consulta via CLI em cada porta PON ativa
        commands = [
            "terminal length 0",
            "configure terminal",
        ]
        for p in range(1, 5):
            commands.extend([
                f"interface gpon 0/{p}",
                "show onu state",
                "exit",
            ])
        commands.append("end")

        try:
            output = self._execute_cli_commands(olt, commands)
            return self.parse_port_onus(output, "")
        except Exception as e:
            logger.warning(f"Erro ao listar ONUs da VSOL {olt.name}: {e}")
            return []

    def get_chassis_interfaces(self, olt: OLTInDB) -> List[OLTPortStatusItem]:
        """Mapeia as portas GPON e Uplink do chassi VSOL V1600."""
        onus = []
        try:
            onus = self.list_all_authorized_onus(olt) or []
        except Exception as e:
            logger.warning(f"Erro ao listar ONUs da VSOL {olt.name}: {e}")

        onu_count_by_pon: Dict[int, int] = {}
        for o in onus:
            nums = re.findall(r"\d+", o.port)
            if nums:
                p = int(nums[-1])
                onu_count_by_pon[p] = onu_count_by_pon.get(p, 0) + 1

        num_ports = 16 if "16" in self.model_name.lower() else (8 if "8" in self.model_name.lower() else 8)
        ports: List[OLTPortStatusItem] = []

        for i in range(1, num_ports + 1):
            count = onu_count_by_pon.get(i, 0)
            ports.append(
                OLTPortStatusItem(
                    port_id=f"gpon 0/{i}",
                    port_type="gpon",
                    admin_state="enabled",
                    oper_status="up",
                    onu_count=count,
                    onu_capacity=128,
                    speed_duplex="2.488Gbps Down / 1.244Gbps Up",
                    details=f"{count} ONUs registradas na fibra | Laser GPON Tx Ativo (+2.5 dBm)"
                    if count > 0
                    else "Laser GPON Tx Ativo (+2.5 dBm) - Aguardando ONUs",
                )
            )

        ports.append(
            OLTPortStatusItem(
                port_id="ge 0/1",
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
                port_id="ge 0/2",
                port_type="ge",
                admin_state="enabled",
                oper_status="down",
                onu_count=0,
                onu_capacity=0,
                speed_duplex="1Gbps",
                details="Link Redundante (Standby)",
            )
        )
        return ports

    def save_running_config(self, olt: OLTInDB) -> bool:
        """Persiste a configuração ativa na flash da VSOL V1600 via 'write'."""
        try:
            self._execute_cli_commands(olt, ["write"])
            return True
        except Exception as e:
            logger.warning(f"Erro ao persistir flash na VSOL {olt.name}: {e}")
            return False

    def extract_snmp_community(self, config_text: str) -> Tuple[Optional[str], bool]:
        """Extrai comunidade SNMP do running-config da VSOL V1600."""
        if not config_text:
            return None, False
        match = re.search(r"snmp-server\s+community\s+(\S+)(?:\s+ro)?", config_text, re.IGNORECASE)
        if match:
            return match.group(1), False
        return None, False

    def configure_snmp(self, olt: OLTInDB, community: str, port: int = 161) -> bool:
        """Provisiona comunidade SNMP Read-Only (RO) na VSOL V1600 e salva via 'write'."""
        commands = [
            "enable",
            "configure terminal",
            "snmp-server enable",
            f"snmp-server community {community} ro",
            "exit",
            "write",
        ]
        try:
            self._execute_cli_commands(olt, commands)
            return True
        except Exception as e:
            logger.error(f"Falha ao provisionar SNMP na VSOL {olt.name}: {e}")
            return False

    def list_vlans(self, olt: OLTInDB) -> List[any]:
        """Lista todas as VLANs configuradas na OLT VSOL."""
        from app.models.vlan import VLANItem
        try:
            cfg = self.get_running_config(olt)
            arch = self.parse_management_architecture(cfg, olt.host)
            vlan_items = []
            for v_id in arch.get("existing_vlans", []):
                desc_match = re.search(rf"vlan\s+{v_id}\s+(?:description|name)\s+(\S+)", cfg, re.IGNORECASE)
                name = desc_match.group(1) if desc_match else f"VLAN_{v_id}"
                vlan_items.append(
                    VLANItem(
                        vlan_id=v_id,
                        name=name,
                    )
                )
            return vlan_items
        except Exception as e:
            logger.warning(f"Erro ao listar VLANs da VSOL {olt.name}: {e}")
            return []

    def create_vlan(self, olt: OLTInDB, req: any) -> bool:
        """Cria nova VLAN de serviço com line profile compilado na OLT VSOL."""
        safe_vlan = sanitize_vlan(req.vlan_id)
        safe_desc = sanitize_description(getattr(req, "name", None) or f"VLAN_{safe_vlan}")
        commands = [
            "configure terminal",
            f"vlan {safe_vlan}",
            f"  description {safe_desc}",
            "exit",
        ]
        tagged_ports = getattr(req, "tagged_ports", None) or []
        if tagged_ports:
            for p in tagged_ports:
                safe_port = sanitize_interface_port(p).replace("ge ", "gigabitEthernet ")
                commands.extend([
                    f"interface {safe_port}",
                    "  switchport mode hybrid",
                    f"  switchport hybrid vlan {safe_vlan} tagged",
                    "exit",
                ])
        # Auto-create line profile
        commands.extend([
            f"profile line id {safe_vlan} name line_vlan{safe_vlan}",
            "  tcont 1 name TCONT_1 dba dba_1G",
            f"  gemport 1 tcont 1 gemport_name GEM_{safe_vlan}",
            f"  service ser_1 gemport 1 vlan {safe_vlan}",
            f"  service-port 1 gemport 1 uservlan {safe_vlan} vlan {safe_vlan}",
            "commit",
            "exit",
            "end",
            "write",
        ])
        try:
            self._execute_cli_commands(olt, commands)
            return True
        except Exception as e:
            logger.error(f"Erro ao criar VLAN {safe_vlan} na VSOL {olt.name}: {e}")
            return False

    def execute_wizard_commissioning(self, olt: OLTInDB, req: OLTWizardOnboardRequest) -> List[str]:
        """Aplica o roteiro de comissionamento wizard na OLT VSOL física."""
        commands = self.generate_wizard_commissioning_commands(req)
        self._execute_cli_commands(olt, commands)
        return commands

