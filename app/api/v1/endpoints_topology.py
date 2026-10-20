from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_security_context, get_topology_repo, require_api_key
from app.core.rbac import SecurityContext
from app.models.hateoas import Link
from app.models.topology import (
    NetworkZoneCreate,
    NetworkZoneItem,
    OpticalDistributionBoxCreate,
    OpticalDistributionBoxItem,
    TopologyHealthMapResponse,
)
from app.storage.sql.topology_repository import SQLTopologyRepository

router = APIRouter(
    prefix="/topology",
    tags=["Topologia Passiva FTTH, CTOs/ODBs & Mapa de Saúde (Fase 4)"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/zones", response_model=List[NetworkZoneItem])
def list_network_zones(
    repo: SQLTopologyRepository = Depends(get_topology_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Lista todas as Zonas de Rede FTTH (Bairros/Setores) com contagem de CTOs e ONUs vinculadas."""
    ctx.enforce_scope("onus:read")
    items = repo.list_zones()
    for item in items:
        item.links = {
            "odbs": Link(
                href=f"/api/v1/topology/odbs?zone_id={item.id}",
                method="GET",
                description="Listar CTOs/ODBs desta Zona",
            ),
            "delete": Link(
                href=f"/api/v1/topology/zones/{item.id}",
                method="DELETE",
                description="Remover Zona de Rede",
            ),
        }
    return items


@router.post("/zones", response_model=NetworkZoneItem, status_code=status.HTTP_201_CREATED)
def create_network_zone(
    req: NetworkZoneCreate,
    response: Response,
    repo: SQLTopologyRepository = Depends(get_topology_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Cadastra uma nova Zona de Rede FTTH (Bairro / Setor / Cidade)."""
    ctx.enforce_scope("onus:provision")
    try:
        item = repo.create_zone(req)
        response.headers["Location"] = f"/api/v1/topology/zones/{item.id}"
        item.links = {
            "odbs": Link(
                href=f"/api/v1/topology/odbs?zone_id={item.id}",
                method="GET",
                description="Listar CTOs/ODBs desta Zona",
            )
        }
        return item
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_network_zone(
    zone_id: str,
    repo: SQLTopologyRepository = Depends(get_topology_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Remove uma Zona de Rede FTTH."""
    ctx.enforce_scope("onus:provision")
    if not repo.delete_zone(zone_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Zona '{zone_id}' não encontrada.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/odbs", response_model=List[OpticalDistributionBoxItem])
def list_odbs(
    zone_id: Optional[str] = Query(default=None, description="Filtrar por Zona FTTH"),
    olt_id: Optional[str] = Query(default=None, description="Filtrar por OLT"),
    repo: SQLTopologyRepository = Depends(get_topology_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Lista todas as Caixas de Terminação Óptica (CTOs / ODBs) com lotação e portas ocupadas do splitter."""
    ctx.enforce_scope("onus:read")
    items = repo.list_odbs(zone_id=zone_id, olt_id=olt_id)
    for item in items:
        item.links = {
            "health_map": Link(
                href="/api/v1/topology/health-map",
                method="GET",
                description="Ver diagnóstico de saúde óptica desta CTO",
            ),
            "delete": Link(
                href=f"/api/v1/topology/odbs/{item.id}",
                method="DELETE",
                description="Remover CTO/ODB",
            ),
        }
    return items


@router.post("/odbs", response_model=OpticalDistributionBoxItem, status_code=status.HTTP_201_CREATED)
def create_odb(
    req: OpticalDistributionBoxCreate,
    response: Response,
    repo: SQLTopologyRepository = Depends(get_topology_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Cadastra uma nova Caixa de Terminação Óptica (CTO / ODB) com capacidade de splitter e coordenadas GPS."""
    ctx.enforce_scope("onus:provision")
    try:
        item = repo.create_odb(req)
        response.headers["Location"] = f"/api/v1/topology/odbs/{item.id}"
        item.links = {
            "health_map": Link(
                href="/api/v1/topology/health-map",
                method="GET",
                description="Mapa de saúde das CTOs",
            )
        }
        return item
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/odbs/{odb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_odb(
    odb_id: str,
    repo: SQLTopologyRepository = Depends(get_topology_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Remove uma CTO/ODB do inventário passivo."""
    ctx.enforce_scope("onus:provision")
    if not repo.delete_odb(odb_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"CTO/ODB '{odb_id}' não encontrada.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/health-map", response_model=TopologyHealthMapResponse)
def get_topology_health_map(
    olt_id: Optional[str] = Query(default=None, description="Filtrar por OLT"),
    zone_id: Optional[str] = Query(default=None, description="Filtrar por Zona FTTH"),
    repo: SQLTopologyRepository = Depends(get_topology_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """
    Mapa de Saúde de Rede Passiva (Fase 4).
    Correlaciona alarmes Dying Gasp e LoS das ONUs por CTO/ODB para distinguir instantaneamente:
    - Queda de Energia Elétrica Coletiva ('power_outage')
    - Rompimento de Fibra / Drop Troncal ('fiber_cut')
    - Atenuação / Degradação ('degraded')
    - Operação Normal ('healthy')
    """
    ctx.enforce_scope("onus:read")
    res = repo.get_topology_health_map(olt_id=olt_id, zone_id=zone_id)
    res.links = {
        "zones": Link(href="/api/v1/topology/zones", method="GET", description="Listar Zonas de Rede"),
        "odbs": Link(href="/api/v1/topology/odbs", method="GET", description="Listar CTOs/ODBs"),
    }
    return res
