from abc import ABC, abstractmethod
import re
from typing import List, Optional, Tuple
from app.models.bootstrap import BootstrapRequest
from app.models.olt import OLTInDB, OLTPortStatusItem
from app.models.onu import ONUMacEntry, ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ONUActionResponse, ProvisionRequest, ProvisionResponse
from app.models.vlan import VLANItem, VLANCreateRequest, ProfileItem


class BaseOLTDriver(ABC):
    """Interface abstrata base para drivers de OLT de todos os fabricantes."""

    @staticmethod
    def normalize_down_cause(raw_cause: Optional[str]) -> Optional[str]:
        """
        Normaliza strings brutas de causa de desconexão da CLI de diferentes fabricantes
        para o vocabulário canônico do OLTAPI:
        - 'dying_gasp': Queda de energia elétrica na CPE do assinante
        - 'los': Perda de sinal óptico (rompimento de fibra / conector solto)
        - 'lofi': Perda de quadro óptico / atenuação severa
        - 'admin_down': Bloqueio administrativo / blacklist / disable
        - 'power_off': Desligamento de energia reportado
        - 'unknown': Desconhecido
        """
        if not raw_cause:
            return None
        cleaned = raw_cause.strip().lower().replace("-", "_").replace(" ", "_")
        if not cleaned or cleaned in ("none", "null", "n/a", "--", "up", "online", "working", "active", "syncmib"):
            return None
        if any(k in cleaned for k in ("dying", "dgasp", "dying_gasp", "dyinggasp", "power_down")):
            return "dying_gasp"
        if any(k in cleaned for k in ("lofi", "lof", "loami")):
            return "lofi"
        if any(k in cleaned for k in ("los", "loss_of_signal", "optical_los", "link_down")):
            return "los"
        if any(k in cleaned for k in ("admin", "disable", "blacklist", "suspend", "deactive")):
            return "admin_down"
        if any(k in cleaned for k in ("pwr", "power_off", "poweroff")):
            return "power_off"
        if cleaned in ("offline", "down", "inactive", "dormant", "initial"):
            return "unknown"
        return "unknown"

    @staticmethod
    def format_canonical_mac(raw_mac: str) -> Optional[str]:
        """Normaliza qualquer representação de MAC (XX:XX..., XX-XX..., XXXX.XXXX.XXXX) para AA:BB:CC:DD:EE:FF."""
        hex_only = re.sub(r"[^0-9A-Fa-f]", "", raw_mac or "")
        if len(hex_only) != 12:
            return None
        upper_hex = hex_only.upper()
        return ":".join(upper_hex[i : i + 2] for i in range(0, 12, 2))

    @classmethod
    def parse_mac_table_generic(cls, output: str, default_port: Optional[str] = None) -> List[ONUMacEntry]:
        """
        Extrai entradas FDB/MAC de saídas CLI de OLTs (formatos XX:XX:XX:XX:XX:XX,
        XX-XX-XX-XX-XX-XX ou XXXX.XXXX.XXXX), capturando VLAN e porta quando disponíveis.
        """
        entries: List[ONUMacEntry] = []
        seen = set()
        mac_regex = re.compile(
            r"(?:[0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}|(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}"
        )
        for line in (output or "").splitlines():
            line_s = line.strip()
            if not line_s or line_s.startswith("---") or "mac address" in line_s.lower() and "vlan" in line_s.lower():
                continue
            m = mac_regex.search(line_s)
            if not m:
                continue
            canonical_mac = cls.format_canonical_mac(m.group(0))
            if not canonical_mac or canonical_mac in seen:
                continue
            seen.add(canonical_mac)

            # Remove o MAC da linha para procurar VLAN (1..4094) e porta
            remainder = (line_s[: m.start()] + " " + line_s[m.end() :]).strip()
            vlan_val: Optional[int] = None
            vlan_m = re.search(r"\b(?:vlan\s*[:=]?\s*)?(\d{1,4})\b", remainder, re.IGNORECASE)
            if vlan_m:
                cand = int(vlan_m.group(1))
                if 1 <= cand <= 4094:
                    vlan_val = cand

            port_val = default_port
            port_m = re.search(
                r"\b((?:eth|uni|veip|gemport|gpon|pon|fe|ge)[_\-\s/]*\d+(?:/\d+(?::\d+)?)?)\b",
                remainder,
                re.IGNORECASE,
            )
            if port_m:
                port_val = port_m.group(1).strip()

            entries.append(
                ONUMacEntry(
                    mac_address=canonical_mac,
                    vlan=vlan_val,
                    port=port_val,
                )
            )
        return entries

    @abstractmethod
    def get_running_config(self, olt: OLTInDB) -> str:
        """Coleta o running-config completo da OLT."""
        pass

    @abstractmethod
    def backup_config(self, olt: OLTInDB, ftp_servers: Optional[List[object]] = None) -> str:
        """Gera o backup da configuração e retorna o conteúdo textual."""
        pass

    @abstractmethod
    def list_unauthorized_onus(self, olt: OLTInDB) -> List[UnauthorizedONU]:
        """Lista todas as ONUs pendentes de autorização (autofind / unconfigured)."""
        pass

    @abstractmethod
    def get_port_onus(self, olt: OLTInDB, port: str) -> List[ONUSummary]:
        """Lista todas as ONUs cadastradas/ativas em uma porta PON específica."""
        pass

    @abstractmethod
    def get_onu_details(self, olt: OLTInDB, serial_or_id: str) -> ONUDetails:
        """Obtém diagnóstico detalhado e níveis de potência óptica (dBm) de uma ONU."""
        pass

    def get_onu_mac_table(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> List[ONUMacEntry]:
        """Obtém a tabela de endereços MAC aprendidos nas portas da ONU."""
        return []

    @abstractmethod
    def provision_onu(self, olt: OLTInDB, req: ProvisionRequest) -> ProvisionResponse:
        """Provisiona a ONU na OLT atribuindo porta, serial, vlan e perfil."""
        pass

    @abstractmethod
    def deprovision_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        """Remove a ONU da OLT e libera a porta PON e recursos."""
        pass

    @abstractmethod
    def reboot_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        """Reinicia a ONU remotamente através da OLT."""
        pass

    @abstractmethod
    def suspend_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        """Suspende administrativamente o serviço da ONU (bloqueio por inadimplência)."""
        pass

    @abstractmethod
    def resume_onu(
        self,
        olt: OLTInDB,
        serial_or_id: str,
        port: Optional[str] = None,
        onu_id: Optional[int] = None,
    ) -> ONUActionResponse:
        """Reativa o serviço da ONU na OLT."""
        pass

    @abstractmethod
    def generate_bootstrap_commands(self, req: BootstrapRequest) -> List[str]:
        """Gera a sequência de comandos CLI para configuração inicial da OLT virgem."""
        pass

    @abstractmethod
    def apply_bootstrap(self, olt: OLTInDB, req: BootstrapRequest) -> int:
        """Executa a configuração inicial na OLT física e retorna a quantidade de comandos aplicados."""
        pass

    def list_vlans(self, olt: OLTInDB) -> List["VLANItem"]:
        """Lista todas as VLANs configuradas na OLT."""
        return []

    def create_vlan(self, olt: OLTInDB, req: "VLANCreateRequest") -> bool:
        """Cria uma nova VLAN de serviço na OLT."""
        return True

    def list_profiles(self, olt: OLTInDB) -> List["ProfileItem"]:
        """Lista os profiles de linha e tráfego configurados na OLT."""
        return []

    def list_all_authorized_onus(self, olt: OLTInDB) -> List[ONUSummary]:
        """Varredura global de todas as ONUs autorizadas no chassi da OLT."""
        return []

    def save_running_config(self, olt: OLTInDB) -> bool:
        """Grava as configurações ativas na memória não-volátil/flash da OLT (write/save)."""
        return True

    def get_chassis_interfaces(self, olt: OLTInDB) -> List[OLTPortStatusItem]:
        """Mapeia as interfaces físicas (PON e Uplink) do chassi com seus nomes canônicos e estados operacionais."""
        return []

    def get_chassis_uptime(self, olt: OLTInDB) -> Optional[int]:
        """Retorna o tempo de atividade do chassi em segundos."""
        return None

    def extract_snmp_community(self, config_text: str) -> Tuple[Optional[str], bool]:
        """
        Extrai a comunidade SNMP do running-config ou backup do equipamento.
        Retorna:
            (community_em_texto_claro_ou_None, is_cipher_flag)
        """
        return None, False

    def configure_snmp(self, olt: OLTInDB, community: str, port: int = 161) -> bool:
        """
        Configura comunidade SNMP somente-leitura (RO) via CLI do equipamento
        e grava permanentemente na flash (save/write).
        """
        return False

    def get_snmp_community_live(self, olt: OLTInDB) -> Tuple[Optional[str], bool]:
        """
        Consulta a comunidade SNMP diretamente no chassi físico via CLI ativa.
        Implementado por drivers específicos com suporte a leitura direta.
        Retorna (community, is_cipher).
        """
        return None, False

    handles_primary_ftp_upload: bool = False
    """Indica se o próprio driver realiza upload direto ao primeiro servidor FTP primário."""

    def inspect_management_arch(self, olt: OLTInDB, running_cfg: str, access_host: str) -> dict:
        """
        Inspeciona a arquitetura de gerência e acesso da OLT (SVIs, porta auxiliar e cenário).
        Implementação padrão agnóstica para OLTs em produção.
        """
        protocol_str = olt.protocol.value.upper() if hasattr(olt.protocol, "value") else str(olt.protocol).upper()
        vendor_str = olt.vendor.value.upper() if hasattr(olt.vendor, "value") else str(olt.vendor).upper()
        return {
            "aux_ip": None,
            "gateway": None,
            "existing_svis": [],
            "existing_vlans": [],
            "total_onus": 0,
            "access_scenario": "inband_active",
            "prompt_message": f"Conectado à OLT {vendor_str} {olt.model.upper()} via {protocol_str}.",
        }

    def execute_wizard_commissioning(self, olt: OLTInDB, req: object) -> List[str]:
        """
        Aplica o comissionamento assistido na OLT e grava permanentemente na flash.
        Retorna a lista de comandos CLI executados.
        """
        return []

    def get_provisioning_schema(self, olt: OLTInDB) -> dict:
        """
        Retorna a especificação dinâmica de parâmetros de provisionamento aceitos pelo concentrador,
        incluindo portas detectadas, campos aceitos e listas de VLANs e perfis configurados.
        """
        vlans = []
        try:
            vlans = [{"id": getattr(v, "vlan_id", v), "name": getattr(v, "name", f"VLAN_{v}")} for v in self.list_vlans(olt)]
        except Exception:
            vlans = []

        profiles = []
        try:
            profiles = [{"name": getattr(p, "name", str(p)), "type": getattr(p, "type", "generic")} for p in self.list_profiles(olt)]
        except Exception:
            profiles = []
        
        # Mapeia portas PON
        pon_ports = []
        try:
            interfaces = self.get_chassis_interfaces(olt)
            pon_ports = [iface.port for iface in interfaces if "gpon" in iface.port.lower() or "pon" in iface.port.lower()]
        except Exception:
            pon_ports = []

        if not pon_ports:
            pon_ports = ["0/1", "0/2", "0/3", "0/4"]

        vendor_str = olt.vendor.value.upper() if hasattr(olt.vendor, "value") else str(olt.vendor).upper()
        return {
            "olt_id": olt.id,
            "vendor": vendor_str,
            "model": olt.model,
            "ports": pon_ports,
            "fields": [
                {
                    "key": "vlan",
                    "label": "VLAN de Serviço",
                    "type": "int",
                    "required": True,
                    "default_value": vlans[0]["id"] if vlans else 100,
                    "options": [{"label": f"VLAN {v['id']} ({v['name']})", "value": v["id"]} for v in vlans],
                },
                {
                    "key": "mode",
                    "label": "Modo de Operação",
                    "type": "select",
                    "required": True,
                    "default_value": "transparent",
                    "options": [
                        {"label": "Transparente (Bridge/HGU)", "value": "transparent"},
                        {"label": "Bridge (SFU)", "value": "bridge"},
                        {"label": "Router (PPPoE/IPoE)", "value": "router"},
                    ],
                },
                {
                    "key": "line_profile",
                    "label": "Perfil de Linha (DBA)",
                    "type": "select",
                    "required": False,
                    "default_value": "DEFAULT",
                    "options": [{"label": p["name"], "value": p["name"]} for p in profiles if "line" in p.get("type", "").lower() or "dba" in p.get("type", "").lower()] or [{"label": "DEFAULT", "value": "DEFAULT"}],
                },
                {
                    "key": "srv_profile",
                    "label": "Perfil de Serviço",
                    "type": "select",
                    "required": False,
                    "default_value": "DEFAULT",
                    "options": [{"label": p["name"], "value": p["name"]} for p in profiles if "srv" in p.get("type", "").lower() or "service" in p.get("type", "").lower()] or [{"label": "DEFAULT", "value": "DEFAULT"}],
                },
            ],
            "available_vlans": vlans,
            "available_profiles": profiles,
        }
