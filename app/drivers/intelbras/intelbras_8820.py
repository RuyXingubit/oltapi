import logging
import re
import time
from typing import List, Optional, Tuple
import paramiko

from app.core.security import sanitize_description, sanitize_port, sanitize_safe_string, sanitize_serial, sanitize_vlan
from app.drivers.base import BaseOLTDriver
from app.models.olt import OLTInDB
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ProvisionRequest, ProvisionResponse

logger = logging.getLogger(__name__)


class Intelbras8820Driver(BaseOLTDriver):
    """
    Driver de comunicação e provisionamento para OLT Intelbras 8820 (GPON).
    Suporta SSH com desativação de paginação e parsers resilientes.
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    # ----------------------------------------------------------------------
    # Métodos de Comunicação SSH
    # ----------------------------------------------------------------------

    def _execute_cli_commands(self, olt: OLTInDB, commands: List[str]) -> str:
        """Conecta via SSH, executa uma lista sequencial de comandos e retorna a saída acumulada."""
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

            # Desabilita paginação
            channel.send("terminal length 0\n")
            time.sleep(0.3)

            output = ""
            for cmd in commands:
                channel.send(f"{cmd}\n")
                time.sleep(0.4)

            # Aguarda a conclusão dos comandos
            start_time = time.time()
            while not channel.recv_ready() and (time.time() - start_time) < self.timeout:
                time.sleep(0.2)

            while channel.recv_ready():
                output += channel.recv(65535).decode("utf-8", errors="ignore")
                time.sleep(0.2)

            return output

        except Exception as e:
            logger.error(f"Erro de comunicação SSH com OLT {olt.name} ({olt.host}): {e}")
            raise ConnectionError(f"Falha ao conectar na OLT {olt.name}: {str(e)}")
        finally:
            client.close()

    # ----------------------------------------------------------------------
    # Parsers Puros (Testáveis Unitariamente)
    # ----------------------------------------------------------------------

    @staticmethod
    def parse_unauthorized_onus(output: str) -> List[UnauthorizedONU]:
        """
        Interpreta saídas de 'show gpon onu uncfg' ou 'show gpon uncfg-onu'.
        Exemplos de linhas suportadas:
        - gpon-onu_1/1:1  INCL12345678  discovering
        - 1/1  INCL12345678  110B
        """
        results: List[UnauthorizedONU] = []
        lines = output.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or "---" in line_str or "OnuIndex" in line_str or "Sn" in line_str:
                continue

            # Padrão formato: gpon-onu_1/2:1  INCL12345678 ...
            match_onu_idx = re.search(r"gpon-onu_([0-9]+/[0-9]+)(?::[0-9]+)?\s+([A-Za-z0-9]+)(?:\s+([A-Za-z0-9_\-]+))?", line_str)
            if match_onu_idx:
                port = match_onu_idx.group(1)
                serial = match_onu_idx.group(2)
                model = match_onu_idx.group(3) if match_onu_idx.group(3) else "auto"
                results.append(UnauthorizedONU(port=port, serial=serial, model=model))
                continue

            # Padrão formato simplificado: 1/1  INCL12345678  110B
            parts = line_str.split()
            if len(parts) >= 2 and re.match(r"^[0-9]+/[0-9]+$", parts[0]) and re.match(r"^[A-Za-z0-9]{4,20}$", parts[1]):
                port = parts[0]
                serial = parts[1]
                model = parts[2] if len(parts) > 2 else "auto"
                results.append(UnauthorizedONU(port=port, serial=serial, model=model))

        return results

    @staticmethod
    def parse_port_onus(output: str, port: str) -> List[ONUSummary]:
        """
        Interpreta saídas de 'show gpon onu state gpon-olt_{port}'.
        Exemplo:
        gpon-onu_1/1:1  enable  online  -19.45  INCL12345678
        gpon-onu_1/1:2  enable  offline  --     INCL87654321
        """
        results: List[ONUSummary] = []
        lines = output.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or "---" in line_str or "OperState" in line_str or "OnuIndex" in line_str:
                continue

            # Extrai índice gpon-onu_X/X:Y
            match = re.search(r"gpon-onu_([0-9]+/[0-9]+):([0-9]+)\s+(?:enable|disable)?\s*([a-zA-Z_\-]+)", line_str)
            if match:
                detected_port = match.group(1)
                onu_id = int(match.group(2))
                status = match.group(3).lower()

                # Busca serial na mesma linha se existir
                serial_match = re.search(r"\b([A-Za-z]{4}[0-9A-Za-z]{8,12})\b", line_str)
                serial = serial_match.group(1) if serial_match else f"ONU-{onu_id}"

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
        Interpreta potências ópticas Rx/Tx de comandos 'show gpon onu optical-info'.
        Exemplo:
        Rx optical power: -19.45 dBm
        Tx optical power: 2.10 dBm
        """
        rx_power: Optional[float] = None
        tx_power: Optional[float] = None

        rx_match = re.search(r"Rx\s*(?:optical)?\s*power\s*[:=]?\s*([-\d.]+)", output, re.IGNORECASE)
        if rx_match:
            try:
                rx_power = float(rx_match.group(1))
            except ValueError:
                pass

        tx_match = re.search(r"Tx\s*(?:optical)?\s*power\s*[:=]?\s*([-\d.]+)", output, re.IGNORECASE)
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
        """Gera e retorna a configuração integral para backup."""
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
        commands = [
            "enable",
            f"show gpon onu state gpon-olt_{safe_port}",
        ]
        output = self._execute_cli_commands(olt, commands)
        return self.parse_port_onus(output, safe_port)

    def get_onu_details(self, olt: OLTInDB, serial_or_id: str) -> ONUDetails:
        safe_identifier = sanitize_safe_string(serial_or_id, "identificador da onu")
        commands = [
            "enable",
            f"show gpon onu detail-info {safe_identifier}",
            f"show gpon onu optical-info {safe_identifier}",
        ]
        output = self._execute_cli_commands(olt, commands)
        rx, tx = self.parse_optical_info(output)

        # Detecta status
        status = "unknown"
        if "online" in output.lower():
            status = "online"
        elif "offline" in output.lower():
            status = "offline"

        # Extrai porta ou ONU ID
        port_match = re.search(r"([0-9]+/[0-9]+)", output)
        port = port_match.group(1) if port_match else "1/1"

        return ONUDetails(
            port=port,
            onu_id=1,
            serial=serial_or_id,
            status=status,
            rx_power_dbm=rx,
            tx_power_dbm=tx,
        )

    def provision_onu(self, olt: OLTInDB, req: ProvisionRequest) -> ProvisionResponse:
        """
        Executa os comandos de autorização na Intelbras 8820:
        1. Identifica o próximo ONU ID livre na porta ou utiliza o fornecido.
        2. Configura a interface gpon-olt e gpon-onu.
        3. Grava as alterações na memória não-volátil (write memory).
        """
        safe_port = sanitize_port(req.port)
        safe_serial = sanitize_serial(req.serial)
        safe_vlan = sanitize_vlan(req.vlan)
        safe_desc = sanitize_safe_string(req.description or "Cliente", "descrição")

        # Procura um ONU ID livre (ou padrão 1)
        onu_id = 1
        existing_onus = self.get_port_onus(olt, safe_port)
        used_ids = {onu.onu_id for onu in existing_onus}
        for candidate_id in range(1, 129):
            if candidate_id not in used_ids:
                onu_id = candidate_id
                break

        commands = [
            "enable",
            "config",
            f"interface gpon-olt_{safe_port}",
            f"onu {onu_id} type auto sn {safe_serial}",
            "exit",
            f"interface gpon-onu_{safe_port}:{onu_id}",
            f"name {safe_desc}",
            f"vlan {safe_vlan}",
            "exit",
            "write memory",
        ]

        output = self._execute_cli_commands(olt, commands)
        logger.info(f"Provisionamento de ONU {safe_serial} concluído na OLT {olt.name}. Output: {output[:100]}...")

        return ProvisionResponse(
            success=True,
            port=safe_port,
            onu_id=onu_id,
            serial=safe_serial,
            message="ONU provisionada e salva com sucesso na memória da OLT Intelbras 8820.",
        )
