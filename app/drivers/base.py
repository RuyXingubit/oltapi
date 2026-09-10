from abc import ABC, abstractmethod
from typing import List
from app.models.olt import OLTInDB
from app.models.onu import ONUSummary, ONUDetails, UnauthorizedONU
from app.models.provision import ProvisionRequest, ProvisionResponse


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
