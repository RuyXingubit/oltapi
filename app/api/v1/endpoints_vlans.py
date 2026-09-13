import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_olt_repo, require_api_key
from app.drivers.factory import DriverFactory
from app.models.hateoas import Link
from app.models.vlan import ProfileItem, VLANCreateRequest, VLANItem
from app.storage.olt_repository import OLTRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/olts/{olt_id}",
    tags=["VLANs & Serviços de Rede"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/vlans", response_model=List[VLANItem])
def list_olt_vlans(
    olt_id: str,
    olt_repo: OLTRepository = Depends(get_olt_repo),
):
    """Lista todas as VLANs configuradas na OLT com links HATEOAS contextuais."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        vlans = driver.list_vlans(olt)
        for v in vlans:
            v.links = {
                "self": Link(href=f"/api/v1/olts/{olt_id}/vlans", method="GET", description="Listar VLANs da OLT"),
                "olt": Link(href=f"/api/v1/olts/{olt_id}", method="GET", description="Dados da OLT"),
            }
        return vlans
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao consultar VLANs da OLT: {str(e)}")


@router.post("/vlans", status_code=status.HTTP_201_CREATED)
def create_olt_vlan(
    olt_id: str,
    req: VLANCreateRequest,
    olt_repo: OLTRepository = Depends(get_olt_repo),
):
    """Cria uma nova VLAN de serviço na OLT física e comita na memória permanente."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        success = driver.create_vlan(olt, req)
        # Salva na memória flash/NVRAM da OLT
        driver.save_running_config(olt)

        return {
            "success": success,
            "olt_id": olt_id,
            "vlan_id": req.vlan_id,
            "name": req.name,
            "message": f"VLAN {req.vlan_id} criada e gravada na flash com sucesso na OLT {olt.name}.",
            "_links": {
                "vlans": {"href": f"/api/v1/olts/{olt_id}/vlans", "method": "GET"},
                "olt": {"href": f"/api/v1/olts/{olt_id}", "method": "GET"},
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar VLAN na OLT: {str(e)}")


@router.get("/profiles", response_model=List[ProfileItem])
def list_olt_profiles(
    olt_id: str,
    olt_repo: OLTRepository = Depends(get_olt_repo),
):
    """Lista os perfis de tráfego, linha e DBA configurados na OLT."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        profiles = driver.list_profiles(olt)
        for p in profiles:
            p.links = {
                "olt": Link(href=f"/api/v1/olts/{olt_id}", method="GET", description="Dados da OLT"),
            }
        return profiles
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao listar perfis da OLT: {str(e)}")
