from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_security_context
from app.core.rbac import SecurityContext
from app.core.security import get_password_hash
from app.core.uuid import generate_uuid7
from app.db.models import OLTModel, TenantModel, UserModel, UserOLTPermissionModel
from app.db.session import get_db
from app.models.user import UserCreateRequest, UserResponse, UserRole, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["Gestão de Usuários & Técnicos"])


def _format_user(user: UserModel, db: Session) -> UserResponse:
    perms = (
        db.query(UserOLTPermissionModel)
        .filter(UserOLTPermissionModel.user_id == user.id)
        .all()
    )
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        name=user.name,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
        is_active=user.is_active,
        allowed_olt_ids=[p.olt_id for p in perms],
        created_at=user.created_at,
    )


@router.get("", response_model=List[UserResponse])
def list_users(
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Lista usuários cadastrados no inquilino do chamador ou todos se SUPER_ADMIN."""
    if ctx.is_super_admin:
        users = db.query(UserModel).order_by(UserModel.created_at.desc()).all()
    else:
        users = (
            db.query(UserModel)
            .filter(UserModel.tenant_id == ctx.tenant_id)
            .order_by(UserModel.created_at.desc())
            .all()
        )
    return [_format_user(u, db) for u in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    req: UserCreateRequest,
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Cria um novo usuário ou técnico com suas respectivas permissões de OLT."""
    # Validação de privilégios
    if not ctx.is_super_admin:
        if ctx.role != "TENANT_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: apenas administradores podem cadastrar usuários.",
            )
        # Inquilino neutro só pode criar usuários para seu próprio tenant e papéis TENANT_*
        if req.tenant_id and req.tenant_id != ctx.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você só pode cadastrar usuários dentro da sua própria organização.",
            )
        if req.role in [UserRole.SUPER_ADMIN, UserRole.NOC, UserRole.FIELD_TECH]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para criar usuários com este papel.",
            )

    target_tenant_id = req.tenant_id or ctx.tenant_id
    if not target_tenant_id:
        # Se for super admin e não informou tenant, busca o tenant matriz
        matriz = db.query(TenantModel).filter(TenantModel.type == "PROVIDER_OWNER").first()
        target_tenant_id = matriz.id if matriz else generate_uuid7()

    existing_email = db.query(UserModel).filter(UserModel.email == req.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Já existe um usuário cadastrado com o e-mail '{req.email}'.",
        )

    # Valida se as OLTs passadas existem
    if req.allowed_olt_ids:
        olts_count = db.query(OLTModel).filter(OLTModel.id.in_(req.allowed_olt_ids)).count()
        if olts_count != len(req.allowed_olt_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uma ou mais OLTs informadas na lista de permissões não existem.",
            )

    user = UserModel(
        id=generate_uuid7(),
        tenant_id=target_tenant_id,
        name=req.name,
        email=req.email,
        password_hash=get_password_hash(req.password),
        role=req.role.value,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()

    # Cria as permissões de OLT
    for olt_id in req.allowed_olt_ids:
        perm = UserOLTPermissionModel(
            id=generate_uuid7(),
            user_id=user.id,
            olt_id=olt_id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(perm)

    db.commit()
    db.refresh(user)
    return _format_user(user, db)


@router.get("/{user_id}", response_model=UserResponse)
def get_user_by_id(
    user_id: str,
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Consulta detalhes de um usuário."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    if not ctx.is_super_admin and ctx.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para visualizar este usuário.",
        )

    return _format_user(user, db)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    req: UserUpdateRequest,
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Atualiza dados, senha, perfil ou permissões de OLT de um usuário."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    if not ctx.is_super_admin and ctx.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para alterar este usuário.",
        )

    if req.name is not None:
        user.name = req.name
    if req.password is not None:
        user.password_hash = get_password_hash(req.password)
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.role is not None and ctx.is_super_admin:
        user.role = req.role.value

    if req.allowed_olt_ids is not None:
        # Atualiza a lista de OLTs vinculadas
        db.query(UserOLTPermissionModel).filter(UserOLTPermissionModel.user_id == user.id).delete()
        for olt_id in req.allowed_olt_ids:
            perm = UserOLTPermissionModel(
                id=generate_uuid7(),
                user_id=user.id,
                olt_id=olt_id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(perm)

    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return _format_user(user, db)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    ctx: SecurityContext = Depends(get_security_context),
    db: Session = Depends(get_db),
):
    """Exclui um usuário (apenas SUPER_ADMIN ou TENANT_ADMIN dentro do seu inquilino)."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    if not ctx.is_super_admin and ctx.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para excluir este usuário.",
        )

    db.delete(user)
    db.commit()
    return None
