import logging
import re
import time
from typing import List, Optional, Tuple
import paramiko

from app.core.security import sanitize_description, sanitize_port, sanitize_safe_string, sanitize_serial, sanitize_vlan
from app.drivers.base import BaseOLTDriver
from app.models.bootstrap import BootstrapMode, BootstrapRequest, DefaultONUMode
from app.models.olt import OLTInDB
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ProvisionRequest, ProvisionResponse

logger = logging.getLogger(__name__)


class IntelbrasGSeriesDriver(BaseOLTDriver):
    """
    Driver especializado para OLTs da família Intelbras G-Series (G08 e G16).
    - G08: 8 portas GPON (0/1 a 0/8)
    - G16: 16 portas GPON (0/1 a 0/16)
    """

    def __init__(self, total_pons: int = 16, model_name: str = "G16", timeout: int = 15):
        self.total_pons = total_pons
        self.model_name = model_name
        self.timeout = timeout

    # ----------------------------------------------------------------------
    # Comunicação SSH com o Concentrador G-Series
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

            # Desabilita paginação no terminal
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
            logger.error(f"Erro de comunicação SSH com OLT G-Series {olt.name} ({olt.host}): {e}")
            raise ConnectionError(f"Falha ao conectar na OLT {olt.name}: {str(e)}")
        finally:
            client.close()

    # ----------------------------------------------------------------------
    # Parsers Puros (Testáveis Unitariamente)
    # ----------------------------------------------------------------------

    @staticmethod
    def parse_unauthorized_onus(output: str) -> List[UnauthorizedONU]:
        """
        Interpreta saídas de 'show ont autofind all' ou 'show ont unassigned'.
        Exemplo:
        0/1       INCL12345678    110B          GPON            --
        0/15      HWTC99887766    auto          GPON            --
        """
        results: List[UnauthorizedONU] = []
        lines = output.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or "---" in line_str or "Ont-find" in line_str or "Port" in line_str and "SN" in line_str:
                continue

            # Busca porta no formato 0/X e serial alfanumérico
            match = re.search(r"\b(0/[0-9]+)\s+([A-Za-z0-9]{4,20})(?:\s+([A-Za-z0-9_\-]+))?", line_str)
            if match:
                port = match.group(1)
                serial = match.group(2)
                model = match.group(3) if match.group(3) else "auto"
                results.append(UnauthorizedONU(port=port, serial=serial, model=model))

        return results

    @staticmethod
    def parse_port_onus(output: str, port: str) -> List[ONUSummary]:
        """
        Interpreta saídas de 'show ont info {port} all'.
        Exemplo:
        0/1     1      INCL12345678    online    -19.50        Cliente_01
        0/1     2      INCL87654321    offline   --            Cliente_02
        """
        results: List[ONUSummary] = []
        lines = output.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or "---" in line_str or "OntId" in line_str or "RxPower" in line_str:
                continue

            match = re.search(r"\b([0-9]+/[0-9]+)\s+([0-9]+)\s+([A-Za-z0-9]{4,20})\s+([a-zA-Z_\-]+)", line_str)
            if match:
                detected_port = match.group(1)
                onu_id = int(match.group(2))
                serial = match.group(3)
                status = match.group(4).lower()

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
        Interpreta níveis de potência óptica na OLT G08 / G16.
        Exemplo:
        Rx optical power(dBm): -19.50
        Tx optical power(dBm): 2.30
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
    # Implementação dos Métodos da Interface BaseOLTDriver
    # ----------------------------------------------------------------------

    def get_running_config(self, olt: OLTInDB) -> str:
        commands = [
            "enable",
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
        commands = [
            "enable",
            f"show ont info {safe_port} all",
        ]
        output = self._execute_cli_commands(olt, commands)
        return self.parse_port_onus(output, safe_port)

    def get_onu_details(self, olt: OLTInDB, serial_or_id: str) -> ONUDetails:
        safe_id = sanitize_safe_string(serial_or_id, "identificador da onu")
        commands = [
            "enable",
            f"show ont optical-info {safe_id}",
        ]
        output = self._execute_cli_commands(olt, commands)
        rx, tx = self.parse_optical_info(output)

        status = "unknown"
        if "online" in output.lower():
            status = "online"
        elif "offline" in output.lower():
            status = "offline"

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

        commands = [
            "enable",
            f"ont add {safe_port} sn {safe_serial} vlan {safe_vlan} name {safe_desc}",
            "write",
        ]
        self._execute_cli_commands(olt, commands)

        return ProvisionResponse(
            success=True,
            port=safe_port,
            onu_id=1,
            serial=safe_serial,
            message=f"ONU provisionada com sucesso na OLT {self.model_name}.",
        )

    # ----------------------------------------------------------------------
    # Assistente de Bootstrap Oficial para G08 e G16
    # ----------------------------------------------------------------------

    def generate_bootstrap_commands(self, req: BootstrapRequest) -> List[str]:
        """
        Gera o script oficial da ferramenta Intelbras autoconfig para OLTs G08 (8 PONs) ou G16 (16 PONs).
        """
        commands: List[str] = [
            "enable",
            "deploy profile dba",
            "aim 1 name DBA-DEFAULT",
            "type 4 max 1200000",
            "active",
            "exit",
        ]

        is_router = (req.default_onu_mode == DefaultONUMode.ROUTER)

        if req.mode == BootstrapMode.SINGLE_VLAN:
            safe_vlan = sanitize_vlan(req.vlan or 100)

            # Profile VLAN
            commands.extend([
                "deploy profile vlan",
                f"aim 1 name VLAN-{safe_vlan}",
                f"translate old-vlan {safe_vlan} new-vlan {safe_vlan}",
                "active",
                "exit",
            ])

            # Profile Line
            if is_router:
                commands.extend([
                    "deploy profile line",
                    f"aim 1 name ROUTER_{safe_vlan}",
                    "device type auto",
                    "tcont 1 profile dba 1",
                    "gemport 1 tcont 1 vlan-profile 1",
                    "mapping mode port-vlan",
                    f"mapping 1 port veip vlan {safe_vlan} gemport 1",
                    f"flow 1 port veip vlan {safe_vlan} keep",
                    "active",
                    "exit",
                ])
            else:
                commands.extend([
                    "deploy profile line",
                    f"aim 1 name BRIDGE_{safe_vlan}",
                    "device type auto",
                    "tcont 1 profile dba 1",
                    "gemport 1 tcont 1 vlan-profile 1",
                    "mapping mode port-vlan",
                    f"mapping 1 port eth 1 vlan {safe_vlan} gemport 1",
                    f"flow 1 port eth 1 default vlan {safe_vlan}",
                    "active",
                    "exit",
                ])

            # Auto-Config em todas as portas PON do equipamento (1 a 8 para G08, 1 a 16 para G16)
            commands.extend([
                "ont auto-config",
                "ont-find interface gpon all",
                "ont-find list-age time 60 interface gpon all",
            ])

            for pon in range(1, self.total_pons + 1):
                commands.append(
                    f"ont auto-config name ROUTER-VLAN-{safe_vlan} line 1 interface gpon 0/{pon}"
                )
                commands.append(
                    f"ont auto-config name TERCEIROS-{pon} all-ont line 1 interface gpon 0/{pon}"
                )

        elif req.mode == BootstrapMode.VLAN_PER_PON:
            vlan_map = req.vlan_per_pon or {}

            commands.extend([
                "ont auto-config",
                "ont-find interface gpon all",
                "ont-find list-age time 60 interface gpon all",
            ])

            for pon in range(1, self.total_pons + 1):
                raw_vlan = vlan_map.get(str(pon), 100 + pon)
                safe_vlan = sanitize_vlan(raw_vlan)

                # Deploy profile vlan por PON
                commands.extend([
                    "deploy profile vlan",
                    f"aim {pon} name VLAN-{safe_vlan}",
                    f"translate old-vlan {safe_vlan} new-vlan {safe_vlan}",
                    "active",
                    "exit",
                ])

                # Deploy profile line por PON
                if is_router:
                    commands.extend([
                    "deploy profile line",
                    f"aim {pon} name ROUTER_{safe_vlan}",
                    "device type auto",
                    "tcont 1 profile dba 1",
                    f"gemport 1 tcont 1 vlan-profile {pon}",
                    "mapping mode port-vlan",
                    f"mapping 1 port veip vlan {safe_vlan} gemport 1",
                    f"flow 1 port veip vlan {safe_vlan} keep",
                    "active",
                    "exit",
                    ])
                else:
                    commands.extend([
                    "deploy profile line",
                    f"aim {pon} name BRIDGE_{safe_vlan}",
                    "device type auto",
                    "tcont 1 profile dba 1",
                    f"gemport 1 tcont 1 vlan-profile {pon}",
                    "mapping mode port-vlan",
                    f"mapping 1 port eth 1 vlan {safe_vlan} gemport 1",
                    f"flow 1 port eth 1 default vlan {safe_vlan}",
                    "active",
                    "exit",
                    ])

                commands.append(
                    f"ont auto-config name ROUTER-VLAN-{safe_vlan} line {pon} interface gpon 0/{pon}"
                )
                commands.append(
                    f"ont auto-config name TERCEIROS-{pon} all-ont line {pon} interface gpon 0/{pon}"
                )

        commands.append("write")
        return commands

    def apply_bootstrap(self, olt: OLTInDB, req: BootstrapRequest) -> int:
        commands = self.generate_bootstrap_commands(req)
        self._execute_cli_commands(olt, commands)
        return len(commands)
