import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_olt_repo, require_api_key
from app.db.models import ONUInventoryModel, ONUVLANHistoryModel
from app.drivers.factory import DriverFactory
from app.models.hateoas import Link
from app.models.vlan import (
    ProfileItem,
    VLANCreateRequest,
    VLANHistoryItem,
    VLANItem,
    VLANMetricsItem,
)
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
                "history": Link(href=f"/api/v1/olts/{olt_id}/vlans/{v.vlan_id}/history", method="GET", description="Histórico de seriais"),
            }
        return vlans
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao consultar VLANs da OLT: {str(e)}")


@router.get("/vlans/metrics", response_model=List[VLANMetricsItem])
def get_vlan_metrics(
    olt_id: str,
    olt_repo: OLTRepository = Depends(get_olt_repo),
    db: Session = Depends(get_db),
):
    """Retorna as VLANs da OLT com contagem de ONUs provisionadas e ativas/online."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    driver = DriverFactory.get_driver(olt)
    try:
        vlans = driver.list_vlans(olt)
    except Exception:
        vlans = []

    db_vlans = (
        db.query(ONUInventoryModel.vlan)
        .filter(ONUInventoryModel.current_olt_id == olt_id, ONUInventoryModel.vlan.isnot(None))
        .distinct()
        .all()
    )
    all_vlan_ids = set([v.vlan_id for v in vlans] + [v[0] for v in db_vlans if v[0] is not None])

    vlan_dict = {v.vlan_id: v for v in vlans}
    result = []

    for vid in sorted(list(all_vlan_ids)):
        base_vlan = vlan_dict.get(vid)
        provisioned = (
            db.query(ONUInventoryModel)
            .filter(ONUInventoryModel.current_olt_id == olt_id, ONUInventoryModel.vlan == vid)
            .count()
        )
        active = (
            db.query(ONUInventoryModel)
            .filter(
                ONUInventoryModel.current_olt_id == olt_id,
                ONUInventoryModel.vlan == vid,
                ONUInventoryModel.contract_status == "ACTIVE",
            )
            .count()
        )

        name = base_vlan.name if base_vlan else f"VLAN_{vid}"
        desc = base_vlan.description if base_vlan else "VLAN de Serviço"
        tagged = base_vlan.tagged_ports if base_vlan else ["xg 0/0/1"]
        untagged = base_vlan.untagged_ports if base_vlan else []

        item = VLANMetricsItem(
            vlan_id=vid,
            name=name,
            description=desc,
            tagged_ports=tagged,
            untagged_ports=untagged,
            total_provisioned_onus=provisioned,
            total_active_onus=active,
            links={
                "history": Link(
                    href=f"/api/v1/olts/{olt_id}/vlans/{vid}/history",
                    method="GET",
                    description="Consultar histórico de seriais desta VLAN",
                ),
            },
        )
        result.append(item)

    return result


@router.get("/vlans/{vlan_id}/history", response_model=List[VLANHistoryItem])
def get_vlan_history(
    olt_id: str,
    vlan_id: int,
    olt_repo: OLTRepository = Depends(get_olt_repo),
    db: Session = Depends(get_db),
):
    """Retorna o histórico completo de seriais de ONUs que já utilizaram esta VLAN."""
    olt = olt_repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    history_records = (
        db.query(ONUVLANHistoryModel)
        .filter(ONUVLANHistoryModel.olt_id == olt_id, ONUVLANHistoryModel.vlan_id == vlan_id)
        .order_by(ONUVLANHistoryModel.started_at.desc())
        .all()
    )

    items = []
    seen_serials = set()

    for h in history_records:
        seen_serials.add(h.serial)
        items.append(
            VLANHistoryItem(
                id=h.id,
                serial=h.serial,
                vlan_id=h.vlan_id,
                olt_id=h.olt_id,
                port=h.port,
                contract_id=h.contract_id,
                subscriber_name=h.subscriber_name,
                reason=h.reason,
                started_at=h.started_at,
                ended_at=h.ended_at,
                is_current=(h.ended_at is None),
                links={
                    "onu": Link(href=f"/api/v1/onus/inventory?serial={h.serial}", method="GET", description="Ver ONU"),
                },
            )
        )

    current_onus = (
        db.query(ONUInventoryModel)
        .filter(ONUInventoryModel.current_olt_id == olt_id, ONUInventoryModel.vlan == vlan_id)
        .all()
    )
    for c in current_onus:
        if c.serial not in seen_serials:
            items.append(
                VLANHistoryItem(
                    id=c.id,
                    serial=c.serial,
                    vlan_id=vlan_id,
                    olt_id=olt_id,
                    port=c.current_port,
                    contract_id=c.contract_id,
                    subscriber_name=c.subscriber_name,
                    reason="PROVISIONED_ACTIVE",
                    started_at=c.created_at,
                    ended_at=None,
                    is_current=True,
                    links={
                        "onu": Link(href=f"/api/v1/onus/inventory?serial={c.serial}", method="GET", description="Ver ONU"),
                    },
                )
            )

    return items


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
