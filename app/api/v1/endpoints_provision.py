from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_olt_repo, require_api_key
from app.drivers.factory import DriverFactory
from app.models.onu import UnauthorizedONU
from app.models.provision import ProvisionRequest, ProvisionResponse
from app.storage.olt_repository import OLTRepository

router = APIRouter(prefix="/olts", tags=["Provisionamento & Descoberta"], dependencies=[Depends(require_api_key)])


@router.get("/{olt_id}/unauthorized", response_model=List[UnauthorizedONU])
def list_unauthorized_onus(olt_id: str, repo: OLTRepository = Depends(get_olt_repo)):
    """Lista as ONUs conectadas fisicamente que aguardam autorização (autofind / unconfigured)."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        return driver.list_unauthorized_onus(olt)
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao listar ONUs descobertas: {str(e)}")


@router.post("/{olt_id}/onus", response_model=ProvisionResponse, status_code=status.HTTP_201_CREATED)
def provision_onu(olt_id: str, req: ProvisionRequest, repo: OLTRepository = Depends(get_olt_repo)):
    """Provisiona e autoriza uma ONU na porta informada aplicando VLAN, perfil e descrição."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        result = driver.provision_onu(olt, req)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao provisionar ONU: {str(e)}")
