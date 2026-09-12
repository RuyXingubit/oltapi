from abc import ABC, abstractmethod
from typing import List, Optional
from app.models.bootstrap import BootstrapRequest
from app.models.olt import OLTInDB
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ONUActionResponse, ProvisionRequest, ProvisionResponse


class BaseOLTDriver(ABC):
    """Interface abstrata base para drivers de OLT de todos os fabricantes."""

    @abstractmethod
    def get_running_config(self, olt: OLTInDB) -> str:
        """Coleta o running-config completo da OLT."""
        pass

    @abstractmethod
    def backup_config(self, olt: OLTInDB) -> str:
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

