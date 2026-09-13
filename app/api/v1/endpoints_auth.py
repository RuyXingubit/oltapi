from datetime import timedelta
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_security_context
from app.core.config import settings
from app.core.rbac import SecurityContext
from app.core.security import create_access_token, verify_password
from app.db.models import TenantModel, TenantVLANAllocationModel, UserModel, UserOLTPermissionModel
from app.db.session import get_db
from app.models.user import TokenResponse, UserLoginRequest, UserProfileResponse

router = APIRouter(prefix="/auth", tags=["Autenticação & Sessões Web"])


@router.post("/login", response_model=TokenResponse)
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    """Autentica usuário e senha para acesso à futura interface Web gerando token JWT."""
    user = db.query(UserModel).filter(UserModel.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas. Verifique seu e-mail e senha.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário desativado pelo administrador do sistema.",
        )

    tenant = db.query(TenantModel).filter(TenantModel.id == user.tenant_id).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inquilino/Organização desativado pelo administrador.",
        )

    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": user.id,
        "role": user.role,
        "tenant_id": user.tenant_id,
    }
    token = create_access_token(token_data, expires_delta=expires_delta)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        role=user.role,  # type: ignore[arg-type]
        tenant_id=user.tenant_id,
    )


@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Retorna dados do usuário autenticado, suas permissões de OLT e VLANs autorizadas."""
    if ctx.caller_type == "MASTER_KEY":
        return UserProfileResponse(
            id="00000000-0000-7000-0000-000000000000",
            tenant_id="00000000-0000-7000-0000-000000000000",
            tenant_name=ctx.tenant_name or "Provedor Matriz",
            tenant_type="PROVIDER_OWNER",
            name="Super Admin (.env)",
            email="admin@oltapi.local",
            role="SUPER_ADMIN",  # type: ignore[arg-type]
            allowed_olt_ids=[],
            allowed_vlans={},
        )

    user = db.query(UserModel).filter(UserModel.id == ctx.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    tenant = db.query(TenantModel).filter(TenantModel.id == user.tenant_id).first()

    perms = db.query(UserOLTPermissionModel).filter(UserOLTPermissionModel.user_id == user.id).all()
    allowed_olts = [p.olt_id for p in perms]

    allowed_vlans_dict: Dict[str, List[int]] = {}
    if tenant and tenant.type == "NEUTRAL_OPERATOR":
        allocs = db.query(TenantVLANAllocationModel).filter(TenantVLANAllocationModel.tenant_id == tenant.id).all()
        for al in allocs:
            allowed_vlans_dict.setdefault(al.olt_id, []).append(al.vlan_id)

    return UserProfileResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        tenant_name=tenant.name if tenant else "Desconhecido",
        tenant_type=tenant.type if tenant else "PROVIDER_OWNER",
        name=user.name,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
        allowed_olt_ids=allowed_olts,
        allowed_vlans=allowed_vlans_dict,
    )
