import logging
import re
import socket
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
from app.drivers.fiberhome.telnet_client import TelnetClient
from app.models.bootstrap import BootstrapMode, BootstrapRequest
from app.models.olt import OLTInDB
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ONUActionResponse, ProvisionRequest, ProvisionResponse
from app.models.vlan import VLANItem, VLANCreateRequest, ProfileItem
from app.services.ftp_service import FTPService

logger = logging.getLogger(__name__)


class FiberhomeTL1Driver(BaseOLTDriver):
    """
    Driver especializado para OLTs Fiberhome utilizando o protocolo oficial TL1 (Bellcore).
    Compatível com:
    - Família AN5516 (AN5516-01, AN5516-04, AN5516-06)
    - Família AN6000 (AN6000-7, AN6000-15, AN6000-17)
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    # ----------------------------------------------------------------------
    # Normalização de Portas Fiberhome (Slot / PON)
    # ----------------------------------------------------------------------

    @staticmethod
    def parse_port_components(port_str: str) -> Tuple[int, int]:
        """
        Normaliza strings de porta para a tupla (slot, pon).
        Exemplos:
        - '1/2'   -> (1, 2)
        - '0/1/2' -> (1, 2)
        - '3'     -> (1, 3)
        """
        parts = [int(p) for p in port_str.strip().split("/") if p.isdigit()]
        if len(parts) == 3:
            # Formato frame/slot/pon (frame tipicamente 0 ou 1)
            return parts[1], parts[2]
        elif len(parts) == 2:
            return parts[0], parts[1]
        elif len(parts) == 1:
            return 1, parts[0]
        raise ValueError(f"Porta Fiberhome inválida: '{port_str}'. Esperado formato 'slot/pon' (ex: '1/2').")

    # ----------------------------------------------------------------------
    # Comunicação TL1 com o Concentrador Fiberhome
    # ----------------------------------------------------------------------

    def _execute_tl1_commands(self, olt: OLTInDB, commands: List[str]) -> str:
        """
        Executa sequência de comandos TL1 conectando via TCP Socket direto (porta padrão 3337)
        ou via SSH (caso configurado na porta 22).
        """
        if olt.port == 22:
            return self._execute_ssh_tl1(olt, commands)
        return self._execute_raw_socket_tl1(olt, commands)

    def _execute_raw_socket_tl1(self, olt: OLTInDB, commands: List[str]) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        try:
            s.connect((olt.host, olt.port))

            # Envia login TL1 Bellcore
            login_cmd = f"LOGIN:::1::UN={olt.username},PWD={olt.password};\r\n"
            s.sendall(login_cmd.encode("utf-8"))
            time.sleep(0.3)

            output = ""
            for cmd in commands:
                formatted_cmd = cmd.strip()
                if not formatted_cmd.endswith(";"):
                    formatted_cmd += ";"
                s.sendall(f"{formatted_cmd}\r\n".encode("utf-8"))
                time.sleep(0.3)

            # Envia logout TL1
            s.sendall(b"LOGOUT:::1::;\r\n")
            time.sleep(0.2)

            while True:
                try:
                    data = s.recv(65535)
                    if not data:
                        break
                    output += data.decode("utf-8", errors="ignore")
                    if ";" in output:
                        # Resposta final TL1 recebida
                        break
                except socket.timeout:
                    break

            return output

        except Exception as e:
            logger.error(f"Erro de comunicação TL1 Socket com OLT Fiberhome {olt.name} ({olt.host}): {e}")
            raise ConnectionError(f"Falha ao conectar na OLT Fiberhome {olt.name}: {str(e)}")
        finally:
            s.close()

    def _execute_ssh_tl1(self, olt: OLTInDB, commands: List[str]) -> str:
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

            output = ""
            for cmd in commands:
                formatted_cmd = cmd.strip()
                if not formatted_cmd.endswith(";"):
                    formatted_cmd += ";"
                channel.send(f"{formatted_cmd}\n")
                time.sleep(0.4)

            start_time = time.time()
            while not channel.recv_ready() and (time.time() - start_time) < self.timeout:
                time.sleep(0.2)

            while channel.recv_ready():
                output += channel.recv(65535).decode("utf-8", errors="ignore")
                time.sleep(0.2)

            return output

        except Exception as e:
            logger.error(f"Erro de comunicação SSH TL1 com OLT Fiberhome {olt.name} ({olt.host}): {e}")
            raise ConnectionError(f"Falha ao conectar via SSH na OLT Fiberhome {olt.name}: {str(e)}")
        finally:
            client.close()

    # ----------------------------------------------------------------------
    # Parsers Puros (Testáveis Unitariamente sem Hardware)
    # ----------------------------------------------------------------------

    @staticmethod
    def parse_unregistered_onus(response: str) -> List[UnauthorizedONU]:
        """
        Interpreta resposta TL1 de 'LST-UNREGONU'.
        Exemplo:
        IP 0
        M  1 COMPLD
        SLOTNO=1  PORTNO=1  ONUID=1  MAC=FHTT12345678  AUTHTYPE=MAC  DEVTYPE=AN5506-01-A
        SLOTNO=1  PORTNO=3  ONUID=1  MAC=FHTT87654321  AUTHTYPE=MAC  DEVTYPE=AN5506-02-B
        SLOTNO=2  PORTNO=1  ONUID=1  MAC=INCL99887766  AUTHTYPE=MAC  DEVTYPE=110B
        ;
        """
        results: List[UnauthorizedONU] = []
        lines = response.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or "COMPLD" in line_str or line_str.startswith(";") or line_str.startswith("IP"):
                continue

            # Captura SLOTNO, PORTNO, MAC/SN e opcionalmente DEVTYPE
            slot_match = re.search(r"SLOTNO[=:](\d+)", line_str, re.IGNORECASE)
            port_match = re.search(r"PORTNO[=:](\d+)", line_str, re.IGNORECASE)
            mac_match = re.search(r"(?:MAC|SN)[=:]([A-Za-z0-9\-]+)", line_str, re.IGNORECASE)
            dev_match = re.search(r"DEVTYPE[=:]([A-Za-z0-9_\-]+)", line_str, re.IGNORECASE)

            if slot_match and port_match and mac_match:
                slot = slot_match.group(1)
                pon = port_match.group(1)
                serial = mac_match.group(1)
                model = dev_match.group(1) if dev_match else "auto"

                results.append(
                    UnauthorizedONU(
                        port=f"{slot}/{pon}",
                        serial=serial,
                        model=model,
                    )
                )

        return results

    @staticmethod
    def parse_port_onus(response: str, port: str) -> List[ONUSummary]:
        """
        Interpreta resposta TL1 de 'LST-ONU'.
        Exemplo:
        IP 0
        M  1 COMPLD
        SLOTNO=1  PORTNO=1  ONUID=1  NAME=Cliente_01  MAC=FHTT12345678  STATUS=up  RX=-19.50
        SLOTNO=1  PORTNO=1  ONUID=2  NAME=Cliente_02  MAC=FHTT87654321  STATUS=down  RX=--
        ;
        """
        results: List[ONUSummary] = []
        lines = response.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str or "COMPLD" in line_str or line_str.startswith(";") or line_str.startswith("IP"):
                continue

            onuid_match = re.search(r"ONUID[=:](\d+)", line_str, re.IGNORECASE)
            mac_match = re.search(r"(?:MAC|SN)[=:]([A-Za-z0-9\-]+)", line_str, re.IGNORECASE)
            status_match = re.search(r"STATUS[=:]([a-zA-Z_\-]+)", line_str, re.IGNORECASE)

            if onuid_match:
                onu_id = int(onuid_match.group(1))
                serial = mac_match.group(1) if mac_match else f"ONU-{onu_id}"
                raw_status = status_match.group(1).lower() if status_match else "unknown"

                status = "online" if raw_status in ["up", "online", "active"] else "offline"

                results.append(
                    ONUSummary(
                        port=port,
                        onu_id=onu_id,
                        serial=serial,
                        status=status,
                    )
                )

        return results

    @staticmethod
    def parse_optical_info(response: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Interpreta resposta TL1 de 'MEAS-OPTICAL'.
        Exemplo:
        IP 0
        M  1 COMPLD
        RX=-19.45  TX=2.15  VOLTAGE=3.30  BIAS=15.00
        ;
        """
        rx_power: Optional[float] = None
        tx_power: Optional[float] = None

        rx_match = re.search(r"RX[=:]([-\d.]+)", response, re.IGNORECASE)
        if rx_match:
            try:
                rx_power = float(rx_match.group(1))
            except ValueError:
                pass

        tx_match = re.search(r"TX[=:]([-\d.]+)", response, re.IGNORECASE)
        if tx_match:
            try:
                tx_power = float(tx_match.group(1))
            except ValueError:
                pass

        return rx_power, tx_power

    @staticmethod
    def parse_all_authorized_onus(response: str) -> List[ONUSummary]:
        """
        Interpreta resposta TL1 de listagem global de ONUs do chassi.
        Suporta formato com chaves TL1 e formato posicional/tabular.
        """
        results: List[ONUSummary] = []
        lines = response.splitlines()
        for line in lines:
            line_str = line.strip()
            if not line_str or "COMPLD" in line_str or line_str.startswith(";") or line_str.startswith("IP") or line_str.startswith("RESPONSE"):
                continue

            # 1. Padrão Chave-Valor TL1
            slot_match = re.search(r"SLOTNO[=:](\d+)", line_str, re.IGNORECASE)
            port_match = re.search(r"PORTNO[=:](\d+)", line_str, re.IGNORECASE)
            onuid_match = re.search(r"ONUID[=:](\d+)", line_str, re.IGNORECASE)
            mac_match = re.search(r"(?:MAC|SN)[=:]([A-Za-z0-9\-]+)", line_str, re.IGNORECASE)
            name_match = re.search(r'NAME[=:](?:"([^"]*)"|([^\s;,]+))', line_str, re.IGNORECASE)
            status_match = re.search(r"STATUS[=:]([a-zA-Z_\-]+)", line_str, re.IGNORECASE)

            if onuid_match and mac_match:
                onu_id = int(onuid_match.group(1))
                slot = slot_match.group(1) if slot_match else "1"
                pon = port_match.group(1) if port_match else "1"
                serial = mac_match.group(1)
                desc = name_match.group(1) or name_match.group(2) if name_match else None
                raw_status = status_match.group(1).lower() if status_match else "unknown"
                status = "online" if raw_status in ["up", "online", "active"] else "offline"

                results.append(
                    ONUSummary(
                        port=f"{slot}/{pon}",
                        onu_id=onu_id,
                        serial=serial,
                        status=status,
                        name=desc,
                    )
                )
                continue

            # 2. Padrão Posicional / Tabular (ex: 1-1-1-1 FHTT12345678 ACTIVE CLIENTE_JOAO_FIBRA)
            pos_match = re.search(
                r"^(\d+)[-/](\d+)[-/](\d+)[-/: ]+(\d+)\s+([A-Za-z0-9\-]+)(?:\s+([a-zA-Z_\-]+))?(?:\s+(.+))?",
                line_str,
            )
            if pos_match:
                frame = pos_match.group(1)
                slot = pos_match.group(2)
                pon = pos_match.group(3)
                onu_id = int(pos_match.group(4))
                serial = pos_match.group(5)
                raw_status = (pos_match.group(6) or "unknown").lower()
                status = "ACTIVE" if raw_status in ["up", "online", "active"] else ("INACTIVE" if raw_status in ["down", "inactive", "offline"] else raw_status)
                desc = pos_match.group(7).strip() if pos_match.group(7) else None

                results.append(
                    ONUSummary(
                        port=f"{frame}/{slot}/{pon}" if frame != "0" and frame != "1" else f"{slot}/{pon}",
                        onu_id=onu_id,
                        serial=serial,
                        status=status,
                        name=desc,
                    )
                )

        return results

    @staticmethod
    def parse_vlans(response: str) -> List[VLANItem]:
        """
        Interpreta resposta TL1 de listagem de VLANs.
        Suporta formato com chaves TL1 e formato posicional/tabular.
        """
        results: List[VLANItem] = []
        lines = response.splitlines()
        for line in lines:
            line_str = line.strip()
            if not line_str or "COMPLD" in line_str or line_str.startswith(";") or line_str.startswith("IP") or line_str.startswith("RESPONSE"):
                continue

            vlan_match = re.search(r"VLANID[=:](\d+)", line_str, re.IGNORECASE)
            name_match = re.search(r"VLANNAME[=:]([^\s;,]+)", line_str, re.IGNORECASE)
            desc_match = re.search(r'DESC[=:](?:"([^"]*)"|([^\s;,]+))', line_str, re.IGNORECASE)

            if vlan_match:
                vid = int(vlan_match.group(1))
                vname = name_match.group(1) if name_match else None
                desc = desc_match.group(1) or desc_match.group(2) if desc_match else None
                results.append(VLANItem(vlan_id=vid, name=vname, description=desc))
                continue

            # Formato alternativo tabular (ex: VLAN 100: INTERNET_PPPOE)
            vlan_alt = re.search(r"VLAN\s+(\d+)(?:\s*:\s*([^\s;]+))?(?:\s+(.+))?", line_str, re.IGNORECASE)
            if vlan_alt:
                vid = int(vlan_alt.group(1))
                vname = vlan_alt.group(2) if vlan_alt.group(2) else None
                desc = vlan_alt.group(3) if vlan_alt.group(3) else None
                results.append(VLANItem(vlan_id=vid, name=vname, description=desc))

        return results

    @staticmethod
    def parse_profiles(response: str) -> List[ProfileItem]:
        """
        Interpreta resposta TL1 de listagem de perfis.
        Suporta formato com chaves TL1 e formato posicional/tabular.
        """
        results: List[ProfileItem] = []
        lines = response.splitlines()
        for line in lines:
            line_str = line.strip()
            if not line_str or "COMPLD" in line_str or line_str.startswith(";") or line_str.startswith("IP") or line_str.startswith("RESPONSE"):
                continue

            name_match = re.search(r'(?:NAME|PROFNAME)[=:](?:"([^"]*)"|([^\s;,]+))', line_str, re.IGNORECASE)
            type_match = re.search(r'(?:TYPE|PROFTYPE)[=:]([^\s;,]+)', line_str, re.IGNORECASE)

            if name_match:
                pname = name_match.group(1) or name_match.group(2)
                ptype = type_match.group(1).lower() if type_match else "line"
                results.append(ProfileItem(name=pname, profile_type=ptype))
                continue

            # Formato alternativo tabular (ex: LINEPROF: 100M_PLAN ou DBAPROF: DBA_DEFAULT)
            prof_alt = re.search(r"(LINEPROF|DBAPROF|TRAFFICPROF)\s*:\s*([^\s;,]+)", line_str, re.IGNORECASE)
            if prof_alt:
                raw_type = prof_alt.group(1).upper()
                ptype = "line" if "LINE" in raw_type else ("dba" if "DBA" in raw_type else "traffic")
                pname = prof_alt.group(2)
                results.append(ProfileItem(name=pname, profile_type=ptype))

        return results

    # ----------------------------------------------------------------------
    # Métodos da Interface BaseOLTDriver
    # ----------------------------------------------------------------------

    def get_running_config(self, olt: OLTInDB) -> str:
        commands = [
            "LST-CFGFILE:::1::TYPE=RUNNING;",
        ]
        return self._execute_tl1_commands(olt, commands)

    def backup_config(self, olt: OLTInDB, ftp_servers: Optional[List[object]] = None) -> str:
        """
        Gera o backup da configuração da OLT Fiberhome.
        Se servidores FTP forem fornecidos e a OLT estiver configurada para Telnet ou porta 23,
        dispara 'upload ftp showrun' no concentrador e baixa o arquivo do servidor FTP.
        """
        if ftp_servers:
            primary_ftp = ftp_servers[0]
            ftp_host = getattr(primary_ftp, "host", None)
            ftp_port = getattr(primary_ftp, "port", 21)
            ftp_user = getattr(primary_ftp, "username", None)
            ftp_pass = getattr(primary_ftp, "password", None)
            base_path = getattr(primary_ftp, "base_path", "/") or "/"

            if ftp_host and ftp_user and ftp_pass:
                return self._backup_via_ftp_telnet(
                    olt=olt,
                    ftp_host=ftp_host,
                    ftp_port=ftp_port,
                    ftp_user=ftp_user,
                    ftp_pass=ftp_pass,
                    base_path=base_path,
                )

        return self.get_running_config(olt)

    def _backup_via_ftp_telnet(
        self,
        olt: OLTInDB,
        ftp_host: str,
        ftp_user: str,
        ftp_pass: str,
        ftp_port: int = 21,
        base_path: str = "/",
    ) -> str:
        logger.info(f"Iniciando backup da OLT Fiberhome '{olt.name}' via FTP {ftp_host}...")
        temp_filename = f"oltbkp_{int(time.time()) % 100000}"

        client = TelnetClient(host=olt.host, port=olt.port, timeout=self.timeout)
        try:
            client.connect()
            client.read_until([b"Login:", b"login:", b"Username:", b"username:"], timeout=8)
            client.write(f"{olt.username}\r\n")

            client.read_until([b"Password:", b"password:"], timeout=8)
            client.write(f"{olt.password}\r\n")

            prompt = client.read_until([b">", b"#"], timeout=10)
            if b">" in prompt:
                client.write("enable\r\n")
                client.read_until([b"Password:", b"password:"], timeout=8)
                client.write(f"{olt.password}\r\n")
                client.read_until([b"#"], timeout=8)

            cmd = f"upload ftp showrun {ftp_host} {ftp_user} {ftp_pass} {temp_filename}\r\n"
            client.write(cmd)

            # Aguarda a OLT compilar as placas e enviar o arquivo (timeout de até 150s)
            resp = client.read_until(
                [
                    b"Finished. You've successfully upload config file.",
                    b"successfully",
                    b"failed",
                    b"Failed",
                ],
                timeout=150,
            )
            resp_text = resp.decode("ascii", errors="ignore")

            try:
                client.write("exit\r\n")
            except Exception:
                pass

            if "fail" in resp_text.lower():
                raise ConnectionError(f"Falha ao executar upload FTP na OLT {olt.name}: {resp_text}")

            logger.info(f"Upload pela OLT '{olt.name}' concluído com sucesso. Baixando '{temp_filename}' do servidor FTP...")
            content = FTPService.download_file(
                host=ftp_host,
                port=ftp_port,
                username=ftp_user,
                password=ftp_pass,
                remote_filename=temp_filename,
                base_path=base_path,
                timeout=30,
            )

            # Limpeza defensiva do arquivo temporário no FTP
            FTPService.delete_file(
                host=ftp_host,
                port=ftp_port,
                username=ftp_user,
                password=ftp_pass,
                remote_filename=temp_filename,
                base_path=base_path,
            )

            return content
        except Exception as e:
            logger.error(f"Erro no fluxo de backup via Telnet/FTP para OLT {olt.name}: {e}")
            raise ConnectionError(f"Erro ao realizar backup via FTP da OLT Fiberhome {olt.name}: {str(e)}")
        finally:
            client.close()

    @staticmethod
    def is_telnet_cli(olt: OLTInDB) -> bool:
        """Determina se a OLT deve ser acessada via Telnet CLI em vez de TL1 Bellcore puro."""
        return olt.port == 23 or getattr(olt, "protocol", "").lower() == "telnet"

    def _open_telnet_session(self, olt: OLTInDB) -> TelnetClient:
        """Estabelece sessão Telnet com login e escalada para enable se necessário."""
        client = TelnetClient(olt.host, olt.port, timeout=self.timeout)
        client.connect()
        client.read_until([b"Login:", b"login:"])
        client.write(f"{olt.username}\r\n")
        client.read_until([b"Password:", b"password:"])
        client.write(f"{olt.password}\r\n")
        buf = client.read_until([b">", b"#"])
        if b">" in buf:
            client.write("enable\r\n")
            client.read_until([b"Password:", b"password:"])
            client.write(f"{olt.password}\r\n")
            client.read_until([b"#"])
        return client

    def _exec_telnet_cmd(self, client: TelnetClient, cmd: str) -> str:
        """Executa comando no CLI Telnet tratando paginação automática."""
        client.write(f"{cmd}\r\n")
        full_buf = bytearray()
        while True:
            buf = client.read_until([b"#", b"--Press any key to continue Ctrl+c to stop--"], timeout=6)
            full_buf.extend(buf)
            if b"--Press any key to continue" in buf:
                client.write(" ")
                time.sleep(0.1)
            elif b"#" in buf:
                break
        return full_buf.decode("ascii", errors="ignore")

    @staticmethod
    def parse_telnet_vlans(output: str) -> List[VLANItem]:
        """Interpreta saída de 'show vlan all' no diretório vlan do CLI Fiberhome."""
        results: List[VLANItem] = []
        seen_vids = set()
        for line in output.splitlines():
            line_clean = line.strip()
            if not line_clean or "vlan count" in line_clean.lower() or line_clean.startswith("Admin"):
                continue
            line_clean = line_clean.rstrip(",")
            parts = [p.strip() for p in line_clean.split(",") if p.strip()]
            for p in parts:
                if "~" in p:
                    v_parts = p.split("~")
                    if len(v_parts) == 2:
                        try:
                            start_v = int(v_parts[0].strip())
                            end_v = int(v_parts[1].strip())
                            for vid in range(start_v, end_v + 1):
                                if vid not in seen_vids:
                                    seen_vids.add(vid)
                                    results.append(VLANItem(vlan_id=vid, name=f"VLAN_{vid}"))
                        except ValueError:
                            pass
                else:
                    try:
                        vid = int(p.strip())
                        if vid not in seen_vids:
                            seen_vids.add(vid)
                            results.append(VLANItem(vlan_id=vid, name=f"VLAN_{vid}"))
                    except ValueError:
                        pass
        return results

    @staticmethod
    def parse_telnet_port_onus(output: str, port: str) -> List[ONUSummary]:
        """Interpreta saída de 'show authorization slot X pon Y' do CLI Fiberhome."""
        results: List[ONUSummary] = []
        for line in output.splitlines():
            line_clean = line.strip()
            m = re.match(
                r"^(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+([APR])\s+(\d+)\s+(up|dn)\s+([A-Za-z0-9\-]+)",
                line_clean,
                re.IGNORECASE,
            )
            if m:
                slot, pon, onu_id, onu_type, _st, _lic, ost, phy_id = m.groups()
                status = "online" if ost.lower() == "up" else "offline"
                results.append(
                    ONUSummary(
                        port=f"{slot}/{pon}",
                        onu_id=int(onu_id),
                        serial=phy_id,
                        status=status,
                        name=onu_type,
                    )
                )
        return results

    @staticmethod
    def parse_telnet_unauth_onus(output: str) -> List[UnauthorizedONU]:
        """Interpreta saída de 'show unauthlist' ou 'show discovery' do CLI Fiberhome."""
        results: List[UnauthorizedONU] = []
        for line in output.splitlines():
            line_clean = line.strip()
            if not line_clean or "unauth table" in line_clean.lower() or line_clean.startswith("---") or line_clean.startswith("No") or "command execute" in line_clean.lower() or line_clean.startswith("Admin"):
                continue
            # Padrão 1: Slot Pon OnuType PhyId (show discovery: 4 colunas)
            m_disc = re.match(r"^(\d+)\s+(\d+)\s+(\S+)\s+([A-Za-z0-9\-]+)", line_clean)
            if m_disc:
                slot, pon, model, serial = m_disc.groups()
                results.append(UnauthorizedONU(port=f"{slot}/{pon}", serial=serial, model=model))
                continue
            # Padrão 2: No OnuType PhyId (show unauthlist: 3 colunas)
            m = re.match(r"^\d+\s+(\S+)\s+([A-Za-z0-9\-]+)", line_clean)
            if m:
                model, serial = m.groups()
                results.append(UnauthorizedONU(port="auto", serial=serial, model=model))
                continue
        return results

    @staticmethod
    def parse_telnet_profiles(output: str) -> List[ProfileItem]:
        """Interpreta saída de 'show servmode profile all' do CLI Fiberhome."""
        results: List[ProfileItem] = []
        for line in output.splitlines():
            m = re.search(r"name\s+([^\s;]+)\s+type\s+([^\s;]+)", line, re.IGNORECASE)
            if m:
                pname, ptype = m.groups()
                results.append(ProfileItem(name=pname, profile_type=ptype.lower()))
        return results

    def list_unauthorized_onus(self, olt: OLTInDB) -> List[UnauthorizedONU]:
        if self.is_telnet_cli(olt):
            client = self._open_telnet_session(olt)
            try:
                client.write("cd onu\r\n")
                time.sleep(0.2)
                client.read_until([b"#"])
                out = self._exec_telnet_cmd(client, "show unauthlist")
                results = self.parse_telnet_unauth_onus(out)
                if not results:
                    for slot in [1, 11]:
                        disc_out = self._exec_telnet_cmd(client, f"show discovery slot {slot} pon all")
                        results.extend(self.parse_telnet_unauth_onus(disc_out))
                return results
            finally:
                client.write("exit\r\n")
                client.close()

        commands = [
            "LST-UNREGONU::DEV=ALL:1::;",
        ]
        output = self._execute_tl1_commands(olt, commands)
        return self.parse_unregistered_onus(output)

    def get_port_onus(self, olt: OLTInDB, port: str) -> List[ONUSummary]:
        safe_port = sanitize_port(port)
        slot, pon = self.parse_port_components(safe_port)

        if self.is_telnet_cli(olt):
            client = self._open_telnet_session(olt)
            try:
                client.write("cd onu\r\n")
                time.sleep(0.2)
                client.read_until([b"#"])
                out = self._exec_telnet_cmd(client, f"show authorization slot {slot} pon {pon}")
                return self.parse_telnet_port_onus(out, f"{slot}/{pon}")
            finally:
                client.write("exit\r\n")
                client.close()

        commands = [
            f"LST-ONU::OLTID={slot},PONID={pon}:1::;",
        ]
        output = self._execute_tl1_commands(olt, commands)
        return self.parse_port_onus(output, f"{slot}/{pon}")

    def get_onu_details(self, olt: OLTInDB, serial_or_id: str) -> ONUDetails:
        if self.is_telnet_cli(olt):
            client = self._open_telnet_session(olt)
            try:
                client.write("cd onu\r\n")
                time.sleep(0.2)
                client.read_until([b"#"])
                out = self._exec_telnet_cmd(client, f"show onu-info by {serial_or_id}")
                m = re.search(r"(\d+)\s+(\d+)\s+(\d+)\s+([A-Za-z]+)", out)
                if m:
                    slot, pon, onu_id, _state = m.groups()
                    auth_out = self._exec_telnet_cmd(client, f"show authorization slot {slot} pon {pon}")
                    status = "online"
                    for line in auth_out.splitlines():
                        if serial_or_id.lower() in line.lower():
                            if " dn " in line.lower():
                                status = "offline"
                            elif " up " in line.lower():
                                status = "online"
                            break
                    return ONUDetails(
                        port=f"{slot}/{pon}",
                        onu_id=int(onu_id),
                        serial=serial_or_id,
                        status=status,
                    )
                return ONUDetails(
                    port="1/1",
                    onu_id=1,
                    serial=serial_or_id,
                    status="offline",
                )
            finally:
                client.write("exit\r\n")
                client.close()

        safe_id = sanitize_safe_string(serial_or_id, "identificador da onu")
        # Medição de potência via TL1
        commands = [
            f"MEAS-OPTICAL::ONUID={safe_id}:1::;",
        ]
        output = self._execute_tl1_commands(olt, commands)
        rx, tx = self.parse_optical_info(output)

        status = "online" if rx is not None else "offline"

        return ONUDetails(
            port="1/1",
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
        line_profile = sanitize_safe_string(req.profile or "LINE-DEFAULT", "line profile")

        slot, pon = self.parse_port_components(safe_port)

        commands = [
            f'ADD-ONU::OLTID={slot},PONID={pon}:1::NAME="{safe_desc}",AUTHTYPE=MAC,MAC={safe_serial},LINEPROF="{line_profile}";',
            f"CFG-LANPORTVLAN::OLTID={slot},PONID={pon},ONUID=1:1::PORT=1,MODE=TAG,VLAN={safe_vlan};",
        ]
        self._execute_tl1_commands(olt, commands)

        return ProvisionResponse(
            success=True,
            port=f"{slot}/{pon}",
            onu_id=1,
            serial=safe_serial,
            message=f"ONU provisionada com sucesso na OLT Fiberhome TL1 (Slot {slot}, PON {pon}, VLAN {safe_vlan}).",
        )

    def deprovision_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "1/1")
        slot, pon = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            f"DEL-ONU::OLTID={slot},PONID={pon},ONUID={onu_idx}:1::;",
        ]
        self._execute_tl1_commands(olt, commands)
        logger.info(f"ONU {safe_serial} (slot {slot}, pon {pon}, id {onu_idx}) desprovisionada via TL1 na OLT {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="deprovision",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"{slot}/{pon}",
            onu_id=onu_idx,
            message=f"ONU {safe_serial} removida com sucesso via TL1 (Slot {slot}, PON {pon}, ONUID {onu_idx}).",
        )

    def reboot_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "1/1")
        slot, pon = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            f"RESET-ONU::OLTID={slot},PONID={pon},ONUID={onu_idx}:1::;",
        ]
        self._execute_tl1_commands(olt, commands)
        logger.info(f"Comando reboot enviado via TL1 para ONU {safe_serial} ({slot}/{pon}:{onu_idx}) na OLT {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="reboot",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"{slot}/{pon}",
            onu_id=onu_idx,
            message=f"Comando de reinicialização remota enviado via TL1 para a ONU {safe_serial}.",
        )

    def suspend_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "1/1")
        slot, pon = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            f"SET-ONU::OLTID={slot},PONID={pon},ONUID={onu_idx}:1::ADMINSTATUS=DOWN;",
        ]
        self._execute_tl1_commands(olt, commands)
        logger.info(f"ONU {safe_serial} ({slot}/{pon}:{onu_idx}) suspensa via TL1 na OLT {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="suspend",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"{slot}/{pon}",
            onu_id=onu_idx,
            message=f"ONU {safe_serial} suspensa administrativamente via TL1.",
        )

    def resume_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        safe_port = sanitize_port(port or "1/1")
        slot, pon = self.parse_port_components(safe_port)
        safe_serial = sanitize_serial(serial_or_id) if re.match(r"^[A-Za-z0-9]{4,20}$", serial_or_id) else sanitize_safe_string(serial_or_id, "identificador da onu")
        onu_idx = onu_id if onu_id is not None else 1

        commands = [
            f"SET-ONU::OLTID={slot},PONID={pon},ONUID={onu_idx}:1::ADMINSTATUS=UP;",
        ]
        self._execute_tl1_commands(olt, commands)
        logger.info(f"ONU {safe_serial} ({slot}/{pon}:{onu_idx}) reativada via TL1 na OLT {olt.name}.")

        return ONUActionResponse(
            success=True,
            action="resume",
            olt_id=str(olt.id),
            serial=safe_serial,
            port=f"{slot}/{pon}",
            onu_id=onu_idx,
            message=f"ONU {safe_serial} reativada com sucesso via TL1.",
        )

    def generate_bootstrap_commands(self, req: BootstrapRequest) -> List[str]:
        """
        Gera sequência oficial de comandos TL1 para inicialização zero-touch da OLT Fiberhome:
        1. Criação de DBA Profile Type 4
        2. Criação de Line Profile
        3. Configuração de VLAN de serviço e uplink
        """
        safe_uplink = sanitize_port(req.uplink_port or "1")

        commands: List[str] = [
            'ADD-DBAPROF:::1::NAME="DBA-DEFAULT",TYPE=4,MAXBW=1024000;',
            'ADD-LINEPROF:::1::NAME="LINE-DEFAULT",DBANAME="DBA-DEFAULT";',
        ]

        if req.mode == BootstrapMode.SINGLE_VLAN:
            safe_vlan = sanitize_vlan(req.vlan or 100)
            commands.extend([
                f"ADD-VLAN:::1::VLANID={safe_vlan},TYPE=SMART;",
                f"ADD-UPLINKPORTVLAN:::1::PORT={safe_uplink},VLANID={safe_vlan};",
            ])
        elif req.mode == BootstrapMode.VLAN_PER_PON:
            vlan_map = req.vlan_per_pon or {}
            for pon in range(1, 9):
                safe_vlan = sanitize_vlan(vlan_map.get(str(pon), 100 + pon))
                commands.extend([
                    f'ADD-LINEPROF:::1::NAME="LINE-PON{pon}",DBANAME="DBA-DEFAULT";',
                    f"ADD-VLAN:::1::VLANID={safe_vlan},TYPE=SMART;",
                    f"ADD-UPLINKPORTVLAN:::1::PORT={safe_uplink},VLANID={safe_vlan};",
                ])

        return commands

    def apply_bootstrap(self, olt: OLTInDB, req: BootstrapRequest) -> int:
        commands = self.generate_bootstrap_commands(req)
        self._execute_tl1_commands(olt, commands)
        return len(commands)

    def list_all_authorized_onus(self, olt: OLTInDB) -> List[ONUSummary]:
        """Varredura de todas as ONUs autorizadas no chassi da Fiberhome."""
        if self.is_telnet_cli(olt):
            client = self._open_telnet_session(olt)
            try:
                client.write("cd onu\r\n")
                time.sleep(0.2)
                client.read_until([b"#"])
                all_onus: List[ONUSummary] = []
                for slot in [1, 11]:
                    out = self._exec_telnet_cmd(client, f"show authorization slot {slot} pon all")
                    all_onus.extend(self.parse_telnet_port_onus(out, f"{slot}/all"))
                return all_onus
            finally:
                client.write("exit\r\n")
                client.close()

        commands = [
            "LST-ONU:::1::;",
        ]
        output = self._execute_tl1_commands(olt, commands)
        return self.parse_all_authorized_onus(output)

    def list_vlans(self, olt: OLTInDB) -> List[VLANItem]:
        """Lista todas as VLANs configuradas no chassi Fiberhome."""
        if self.is_telnet_cli(olt):
            client = self._open_telnet_session(olt)
            try:
                client.write("cd vlan\r\n")
                time.sleep(0.2)
                client.read_until([b"#"])
                out = self._exec_telnet_cmd(client, "show vlan all")
                return self.parse_telnet_vlans(out)
            finally:
                client.write("exit\r\n")
                client.close()

        commands = [
            "LST-VLAN:::1::;",
        ]
        output = self._execute_tl1_commands(olt, commands)
        return self.parse_vlans(output)

    def create_vlan(self, olt: OLTInDB, req: VLANCreateRequest) -> bool:
        """Cria uma nova VLAN de serviço na OLT Fiberhome."""
        safe_id = sanitize_vlan(req.vlan_id)
        safe_name = sanitize_safe_string(req.name or f"VLAN_{safe_id}", "nome da vlan")
        safe_desc = sanitize_description(req.description or "Criada via OLTAPI")
        commands = [
            f'ADD-VLAN:::1::VLANID={safe_id},VLANNAME="{safe_name}",DESC="{safe_desc}";',
        ]
        if req.tagged_uplink_ports:
            for port in req.tagged_uplink_ports:
                clean_port = sanitize_port(port)
                commands.append(f"ADD-UPLINKPORTVLAN:::1::PORT={clean_port},VLANID={safe_id};")

        self._execute_tl1_commands(olt, commands)
        return True

    def list_profiles(self, olt: OLTInDB) -> List[ProfileItem]:
        """Lista os profiles de linha e tráfego na OLT Fiberhome."""
        if self.is_telnet_cli(olt):
            client = self._open_telnet_session(olt)
            try:
                client.write("cd profile\r\n")
                time.sleep(0.2)
                client.read_until([b"#"])
                out = self._exec_telnet_cmd(client, "show servmode profile all")
                return self.parse_telnet_profiles(out)
            finally:
                client.write("exit\r\n")
                client.close()

        commands = [
            "LST-LINEPROF:::1::;",
            "LST-DBAPROF:::1::;",
        ]
        output = self._execute_tl1_commands(olt, commands)
        return self.parse_profiles(output)

    def save_running_config(self, olt: OLTInDB) -> bool:
        """Comita alterações na memória flash permanente da Fiberhome."""
        commands = [
            "SAVE::DEV=ALL:1::;",
        ]
        try:
            self._execute_tl1_commands(olt, commands)
        except Exception as e:
            logger.warning(f"Aviso ao persistir flash na Fiberhome {olt.name}: {e}")
        return True


# Exportações no nível do módulo
parse_all_authorized_onus = FiberhomeTL1Driver.parse_all_authorized_onus
parse_vlans = FiberhomeTL1Driver.parse_vlans
parse_profiles = FiberhomeTL1Driver.parse_profiles
parse_telnet_vlans = FiberhomeTL1Driver.parse_telnet_vlans
parse_telnet_port_onus = FiberhomeTL1Driver.parse_telnet_port_onus
parse_telnet_unauth_onus = FiberhomeTL1Driver.parse_telnet_unauth_onus
parse_telnet_profiles = FiberhomeTL1Driver.parse_telnet_profiles

