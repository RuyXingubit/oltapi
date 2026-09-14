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



