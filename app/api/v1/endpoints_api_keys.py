from datetime import datetime, timedelta, timezone
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_security_context
from app.core.rbac import SecurityContext
from app.core.security import generate_api_key
from app.core.uuid import generate_uuid7
from app.db.models import APIKeyModel
from app.db.session import get_db
from app.models.api_key import APIKeyCreatedResponse, APIKeyCreateRequest, APIKeyResponse

router = APIRouter(prefix="/api-keys", tags=["Gestão de Chaves de API Secundárias"])

VALID_SCOPES = {
    "*",
    "olts:read",
    "olts:admin",
    "onus:read",
    "onus:discover",
    "onus:provision",
    "onus:deprovision",
    "onus:actions",
    "diagnostics:read",
    "backups:read",
    "backups:create",
    "vlans:read",
    "api_keys:manage",
}


def _format_key(k: APIKeyModel) -> APIKeyResponse:
    try:
        scopes = json.loads(k.scopes)
    except Exception:
        scopes = []
    return APIKeyResponse(
        id=k.id,
        tenant_id=k.tenant_id,
        user_id=k.user_id,
        name=k.name,
        key_prefix=k.key_prefix,
        scopes=scopes,
        is_active=k.is_active,
        created_at=k.created_at,
        last_used_at=k.last_used_at,
        expires_at=k.expires_at,
    )


@router.get("", response_model=List[APIKeyResponse])
def list_api_keys(
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Lista as chaves de API dinâmicas ativas/revogadas do inquilino do chamador."""
    if ctx.is_super_admin:
        keys = db.query(APIKeyModel).order_by(APIKeyModel.created_at.desc()).all()
    else:
        keys = (
            db.query(APIKeyModel)
            .filter(APIKeyModel.tenant_id == ctx.tenant_id)
            .order_by(APIKeyModel.created_at.desc())
            .all()
        )
    return [_format_key(k) for k in keys]


@router.post("", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_dynamic_api_key(
    req: APIKeyCreateRequest,
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """
    Gera uma nova chave de API com escopos granulares.
    ATENÇÃO: A chave secreta em texto puro é retornada apenas uma única vez na criação.
    """
    # Validação de escopos
    invalid_scopes = [s for s in req.scopes if s not in VALID_SCOPES]
    if invalid_scopes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Escopo(s) inválido(s): {invalid_scopes}. Escopos válidos: {sorted(list(VALID_SCOPES))}",
        )

    # Inquilino de rede neutra não pode solicitar escopos de administração global
    if ctx.tenant_type == "NEUTRAL_OPERATOR":
        forbidden_scopes = {"*", "olts:admin", "backups:create"}
        requested_forbidden = set(req.scopes).intersection(forbidden_scopes)
        if requested_forbidden:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Seu perfil não tem permissão para emitir chaves com escopos: {list(requested_forbidden)}",
            )

    full_key, prefix, key_hash = generate_api_key("live")

    expires_at = None
    if req.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_in_days)

    target_tenant_id = ctx.tenant_id
    target_user_id = ctx.user_id

    if not target_tenant_id or not target_user_id:
        from app.db.models import TenantModel, UserModel
        matriz = db.query(TenantModel).filter(TenantModel.type == "PROVIDER_OWNER").first()
        if matriz:
            target_tenant_id = target_tenant_id or matriz.id
            admin_user = db.query(UserModel).filter(UserModel.tenant_id == matriz.id).first()
            if admin_user:
                target_user_id = target_user_id or admin_user.id

    target_tenant_id = target_tenant_id or "00000000-0000-7000-0000-000000000000"
    target_user_id = target_user_id or "00000000-0000-7000-0000-000000000000"

    api_key_record = APIKeyModel(
        id=generate_uuid7(),
        tenant_id=target_tenant_id,
        user_id=target_user_id,
        name=req.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=json.dumps(req.scopes),
        is_active=True,
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(api_key_record)
    db.commit()
    db.refresh(api_key_record)

    return APIKeyCreatedResponse(
        id=api_key_record.id,
        name=api_key_record.name,
        key=full_key,
        key_prefix=api_key_record.key_prefix,
        scopes=req.scopes,
        created_at=api_key_record.created_at,
        expires_at=api_key_record.expires_at,
    )


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    api_key_id: str,
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Revoga imediatamente uma chave de API dinâmica."""
    key_record = db.query(APIKeyModel).filter(APIKeyModel.id == api_key_id).first()
    if not key_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chave de API não encontrada.")

    if not ctx.is_super_admin and ctx.tenant_id != key_record.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para revogar esta chave.",
        )

    key_record.is_active = False
    db.commit()
    return None
