from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_security_context
from app.core.rbac import SecurityContext
from app.core.uuid import generate_uuid7
from app.db.models import OLTModel, TenantModel, TenantVLANAllocationModel
from app.db.session import get_db
from app.models.tenant import (
    TenantCreateRequest,
    TenantResponse,
    TenantVLANAllocationCreate,
    TenantVLANAllocationResponse,
)

router = APIRouter(prefix="/tenants", tags=["Gestão de Inquilinos & Rede Neutra"])


def _format_tenant(tenant: TenantModel, db: Session) -> TenantResponse:
    allocs = (
        db.query(TenantVLANAllocationModel)
        .filter(TenantVLANAllocationModel.tenant_id == tenant.id)
        .all()
    )
    vlan_responses = [
        TenantVLANAllocationResponse(
            id=a.id,
            tenant_id=a.tenant_id,
            olt_id=a.olt_id,
            vlan_id=a.vlan_id,
            description=a.description,
            created_at=a.created_at,
        )
        for a in allocs
    ]
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        type=tenant.type,  # type: ignore[arg-type]
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        vlans=vlan_responses,
    )


@router.get("", response_model=List[TenantResponse])
def list_tenants(
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Lista todos os inquilinos cadastrados (apenas SUPER_ADMIN)."""
    if not ctx.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: apenas administradores podem listar inquilinos.",
        )
    tenants = db.query(TenantModel).order_by(TenantModel.created_at.desc()).all()
    return [_format_tenant(t, db) for t in tenants]


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    req: TenantCreateRequest,
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Cadastra um novo Inquilino / Operadora de Rede Neutra (apenas SUPER_ADMIN)."""
    if not ctx.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: apenas administradores podem criar novos inquilinos.",
        )

    existing = db.query(TenantModel).filter(TenantModel.name == req.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inquilino com nome '{req.name}' já cadastrado.",
        )

    tenant = TenantModel(
        id=generate_uuid7(),
        name=req.name,
        type=req.type.value,
        is_active=req.is_active,
        created_at=datetime.now(timezone.utc),
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return _format_tenant(tenant, db)


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant_by_id(
    tenant_id: str,
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Consulta detalhes de um inquilino e suas VLANs alocadas."""
    if not ctx.is_super_admin and ctx.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: você não tem permissão para visualizar este inquilino.",
        )

    tenant = db.query(TenantModel).filter(TenantModel.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inquilino não encontrado.")

    return _format_tenant(tenant, db)


@router.post("/{tenant_id}/vlans", response_model=TenantVLANAllocationResponse, status_code=status.HTTP_201_CREATED)
def allocate_vlan(
    tenant_id: str,
    req: TenantVLANAllocationCreate,
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Aloca uma VLAN para a operadora de rede neutra em uma OLT específica (apenas SUPER_ADMIN)."""
    if not ctx.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: apenas administradores podem alocar VLANs.",
        )

    tenant = db.query(TenantModel).filter(TenantModel.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inquilino não encontrado.")

    olt = db.query(OLTModel).filter(OLTModel.id == req.olt_id).first()
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OLT especificada não encontrada.")

    existing = (
        db.query(TenantVLANAllocationModel)
        .filter(
            TenantVLANAllocationModel.tenant_id == tenant_id,
            TenantVLANAllocationModel.olt_id == req.olt_id,
            TenantVLANAllocationModel.vlan_id == req.vlan_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"VLAN {req.vlan_id} já está alocada para este inquilino nesta OLT.",
        )

    allocation = TenantVLANAllocationModel(
        id=generate_uuid7(),
        tenant_id=tenant_id,
        olt_id=req.olt_id,
        vlan_id=req.vlan_id,
        description=req.description,
        created_at=datetime.now(timezone.utc),
    )
    db.add(allocation)
    db.commit()
    db.refresh(allocation)

    return TenantVLANAllocationResponse(
        id=allocation.id,
        tenant_id=allocation.tenant_id,
        olt_id=allocation.olt_id,
        vlan_id=allocation.vlan_id,
        description=allocation.description,
        created_at=allocation.created_at,
    )


@router.delete("/{tenant_id}/vlans/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
def deallocate_vlan(
    tenant_id: str,
    allocation_id: str,
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Remove a alocação de VLAN de uma operadora (apenas SUPER_ADMIN)."""
    if not ctx.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: apenas administradores podem remover alocações de VLAN.",
        )

    allocation = (
        db.query(TenantVLANAllocationModel)
        .filter(
            TenantVLANAllocationModel.id == allocation_id,
            TenantVLANAllocationModel.tenant_id == tenant_id,
        )
        .first()
    )
    if not allocation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alocação de VLAN não encontrada.")

    db.delete(allocation)
    db.commit()
    return None
