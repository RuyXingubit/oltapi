from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from app.models.bootstrap import BootstrapRequest
from app.models.olt import OLTInDB, OLTPortStatusItem
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ONUActionResponse, ProvisionRequest, ProvisionResponse
from app.models.vlan import VLANItem, VLANCreateRequest, ProfileItem


class BaseOLTDriver(ABC):
    """Interface abstrata base para drivers de OLT de todos os fabricantes."""

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
