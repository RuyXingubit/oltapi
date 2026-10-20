from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_preset_repo, get_security_context, require_api_key
from app.core.rbac import SecurityContext
from app.models.hateoas import Link
from app.models.presets import ProvisioningPresetCreate, ProvisioningPresetItem
from app.storage.sql.preset_repository import SQLPresetRepository

router = APIRouter(
    prefix="/presets",
    tags=["Presets Universais de Provisionamento (Fase 3)"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=List[ProvisioningPresetItem])
def list_presets(
    repo: SQLPresetRepository = Depends(get_preset_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Lista os templates universais de provisionamento (VLAN, modo e perfis) disponíveis para autorização 1-clique."""
    ctx.enforce_scope("onus:read")
    tenant_filter = ctx.tenant_id if ctx.tenant_type == "NEUTRAL_OPERATOR" else None
    items = repo.list_presets(tenant_id=tenant_filter)
    for item in items:
        item.links = {
            "delete": Link(
                href=f"/api/v1/presets/{item.id}",
                method="DELETE",
                description="Remover este Preset de provisionamento",
            )
        }
    return items


@router.post("", response_model=ProvisioningPresetItem, status_code=status.HTTP_201_CREATED)
def create_preset(
    req: ProvisioningPresetCreate,
    response: Response,
    repo: SQLPresetRepository = Depends(get_preset_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Cria um novo Preset reutilizável de provisionamento."""
    ctx.enforce_scope("onus:provision")
    try:
        item = repo.create_preset(req)
        response.headers["Location"] = f"/api/v1/presets/{item.id}"
        item.links = {
            "delete": Link(
                href=f"/api/v1/presets/{item.id}",
                method="DELETE",
                description="Remover este Preset",
            )
        }
        return item
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preset(
    preset_id: str,
    repo: SQLPresetRepository = Depends(get_preset_repo),
    ctx: SecurityContext = Depends(get_security_context),
):
    """Remove um Preset de provisionamento pelo seu UUIDv7."""
    ctx.enforce_scope("onus:provision")
    deleted = repo.delete_preset(preset_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Preset '{preset_id}' não encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
