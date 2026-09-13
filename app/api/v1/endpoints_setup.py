from datetime import datetime, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException, Security, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import get_password_hash, API_KEY_HEADER
from app.core.uuid import generate_uuid7
from app.db.models import TenantModel, UserModel, ONUInventoryModel
from app.models.setup import SetupInitRequest, SetupInitResponse, SetupStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status", response_model=SetupStatusResponse, summary="Verifica status de inicialização do sistema")
def get_setup_status(db: Session = Depends(get_db)):
    """
    Retorna se o sistema já foi configurado com a empresa matriz (Provider Owner) e admin.
    Endpoint público para orientar a interface web / clientes API.
    """
    provider = db.query(TenantModel).filter(TenantModel.type == "PROVIDER_OWNER").first()
    if provider:
        return SetupStatusResponse(
            is_configured=True,
            provider_name=provider.name,
            message="Sistema já inicializado e operacional.",
        )
    return SetupStatusResponse(
        is_configured=False,
        provider_name=None,
        message="Sistema aguardando setup inicial. Utilize a Master API Key para configurar.",
    )


@router.post(
    "/init",
    response_model=SetupInitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Executa o setup inicial do sistema (First-Run Wizard)",
)
def initialize_system(
    req: SetupInitRequest,
    api_key: str = Security(API_KEY_HEADER),
    db: Session = Depends(get_db),
):
    """
    Inicializa o sistema com a empresa matriz e a conta de Super Administrador real.
    - Exige a Master API Key configurada no .env via header 'X-API-Key'.
    - Bloqueia permanentemente após o primeiro uso (retorna 403 Forbidden).
    - Não utiliza nenhum dado falso ou senha padrão hardcoded.
    """
    # 1. Valida Master API Key do .env
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso não autorizado. O setup inicial requer a Master API Key configurada no .env.",
        )

    # 2. Bloqueio permanente se já configurado
    existing_provider = db.query(TenantModel).filter(TenantModel.type == "PROVIDER_OWNER").first()
    if existing_provider:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"O sistema já está configurado para '{existing_provider.name}'. Re-inicialização bloqueada por segurança.",
        )

    # 3. Criação do Tenant do Provedor Proprietário com UUIDv7
    tenant_id = generate_uuid7()
    tenant = TenantModel(
        id=tenant_id,
        name=req.provider_name.strip(),
        type="PROVIDER_OWNER",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(tenant)
    db.flush()

    # 4. Criação do Usuário Super Admin com UUIDv7 e Bcrypt
    user_id = generate_uuid7()
    admin_user = UserModel(
        id=user_id,
        tenant_id=tenant.id,
        name=req.admin_name.strip(),
        email=req.admin_email.strip().lower(),
        password_hash=get_password_hash(req.admin_password),
        role="SUPER_ADMIN",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(admin_user)

    # 5. Vincula quaisquer ONUs legadas sem tenant à empresa recém-criada
    unassigned_onus = db.query(ONUInventoryModel).filter(ONUInventoryModel.tenant_id.is_(None)).all()
    for onu in unassigned_onus:
        onu.tenant_id = tenant.id

    db.commit()

    logger.info(
        f"Setup inicial concluído com sucesso: Tenant '{tenant.name}' ({tenant.id}), Admin '{admin_user.email}' ({admin_user.id})"
    )

    return SetupInitResponse(
        status="success",
        message="Setup inicial concluído com sucesso. O sistema agora está pronto para operação.",
        tenant_id=tenant.id,
        admin_user_id=admin_user.id,
        admin_email=admin_user.email,
    )
