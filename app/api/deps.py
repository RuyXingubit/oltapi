from datetime import datetime, timezone
import hmac
import json
from typing import Optional, Union
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import SecurityContext
from app.core.security import API_KEY_HEADER, decode_access_token, hash_api_key, verify_api_key
from app.db.models import (
    APIKeyModel,
    TenantModel,
    TenantVLANAllocationModel,
    UserModel,
    UserOLTPermissionModel,
)
from app.db.session import get_db
from app.services.backup_service import BackupService
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository
from app.storage.onu_repository import ONUInventoryRepository
from app.storage.webhook_repository import WebhookRepository
from app.storage.sql.olt_repository import SQLOLTRepository
from app.storage.sql.onu_repository import SQLONUInventoryRepository
from app.storage.sql.webhook_repository import SQLWebhookRepository
from app.storage.sql.backup_storage import SQLBackupStorage
from app.services.webhook_dispatcher import WebhookDispatcher
from app.services.onu_reconciliation_service import ONUReconciliationService
from app.services.autofind_scanner import AutofindScannerService
from app.services.olt_sync_service import OLTSyncService
from app.services.olt_xray_service import OLTXRayService
from app.services.olt_onboarding_service import OLTOnboardingService
from app.services.onu_enrichment_service import ONUEnrichmentService
from app.storage.sql.ftp_repository import SQLFTPRepository

# Instâncias singleton padrão (persistência relacional via SQLAlchemy)
_olt_repo = SQLOLTRepository()
_backup_storage = SQLBackupStorage()
_onu_repo = SQLONUInventoryRepository()
_webhook_repo = SQLWebhookRepository()
_ftp_repo = SQLFTPRepository()


def get_olt_repo() -> Union[SQLOLTRepository, OLTRepository]:
    return _olt_repo


def get_onu_repo() -> Union[SQLONUInventoryRepository, ONUInventoryRepository]:
    return _onu_repo


def get_webhook_repo() -> Union[SQLWebhookRepository, WebhookRepository]:
    return _webhook_repo


def get_ftp_repo() -> SQLFTPRepository:
    return _ftp_repo


def get_webhook_dispatcher(
    repo: Union[SQLWebhookRepository, WebhookRepository] = Depends(get_webhook_repo),
) -> WebhookDispatcher:
    return WebhookDispatcher(repo=repo)


def get_backup_storage() -> Union[SQLBackupStorage, BackupStorage]:
    return _backup_storage


def get_backup_service(
    repo: Union[SQLOLTRepository, OLTRepository] = Depends(get_olt_repo),
    storage: Union[SQLBackupStorage, BackupStorage] = Depends(get_backup_storage),
    ftp_repo: SQLFTPRepository = Depends(get_ftp_repo),
) -> BackupService:
    return BackupService(olt_repo=repo, storage=storage, ftp_repo=ftp_repo)


# Instâncias dos serviços compartilhados
_reconciliation_service = ONUReconciliationService(
    olt_repo=_olt_repo,
    onu_repo=_onu_repo,
    webhook_dispatcher=get_webhook_dispatcher(_webhook_repo),
)

_scanner_service = None


def get_reconciliation_service() -> ONUReconciliationService:
    return _reconciliation_service


def get_scanner_service() -> AutofindScannerService:
    global _scanner_service
    if _scanner_service is None:
        _scanner_service = AutofindScannerService(
            olt_repo=_olt_repo,
            onu_repo=_onu_repo,
            reconciliation_service=_reconciliation_service,
            webhook_dispatcher=get_webhook_dispatcher(_webhook_repo),
        )
    return _scanner_service


http_bearer = HTTPBearer(auto_error=False)


ROLE_DEFAULT_SCOPES = {
    "SUPER_ADMIN": {"*"},
    "TENANT_ADMIN": {
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
    },
    "NOC": {
        "olts:read",
        "onus:read",
        "onus:discover",
        "onus:provision",
        "onus:actions",
        "diagnostics:read",
        "backups:read",
        "vlans:read",
    },
    "FIELD_TECH": {
        "olts:read",
        "onus:read",
        "onus:discover",
        "onus:provision",
        "onus:actions",
        "diagnostics:read",
    },
    "TENANT_TECH": {
        "olts:read",
        "onus:read",
        "onus:discover",
        "onus:provision",
        "onus:actions",
        "diagnostics:read",
    },
}


def get_security_context(
    api_key: Optional[str] = Security(API_KEY_HEADER),
    auth_cred: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
    db: Session = Depends(get_db),
) -> SecurityContext:
    """
    Dependência central de autorização. Resolve a identidade e escopos do chamador
    a partir de cabeçalho X-API-Key (mestra ou dinâmica) ou Authorization: Bearer <JWT>.
    """
    # 1. Autenticação via Chave de API (X-API-Key)
    if api_key:
        # 1.1 Chave mestra do .env (Super Admin com bypass total)
        if hmac.compare_digest(api_key, settings.API_KEY):
            return SecurityContext(
                caller_type="MASTER_KEY",
                role="SUPER_ADMIN",
                scopes={"*"},
                user_name="Super Admin (.env)",
                tenant_name="Provedor Matriz",
                tenant_type="PROVIDER_OWNER",
                allowed_olt_ids=None,
                allowed_vlans=None,
            )

        # 1.2 Chave dinâmica persistida no banco
        k_hash = hash_api_key(api_key)
        key_record = (
            db.query(APIKeyModel)
            .filter(APIKeyModel.key_hash == k_hash)
            .first()
        )
        if not key_record or not key_record.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Chave de API ausente, inválida ou revogada.",
            )

        if key_record.expires_at and key_record.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Chave de API expirada.",
            )

        # Atualiza timestamp de uso
        key_record.last_used_at = datetime.now(timezone.utc)
        db.commit()

        tenant = db.query(TenantModel).filter(TenantModel.id == key_record.tenant_id).first()
        if not tenant or not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inquilino/Organização associado a esta chave está inativo.",
            )

        user = db.query(UserModel).filter(UserModel.id == key_record.user_id).first()

        try:
            scopes = set(json.loads(key_record.scopes))
        except Exception:
            scopes = set()

        # Restrições de OLT (se aplicável ao perfil)
        allowed_olts = None
        user_role = user.role if user else "TENANT_ADMIN"
        if user_role in ["FIELD_TECH", "TENANT_ADMIN", "TENANT_TECH"] and user:
            perms = (
                db.query(UserOLTPermissionModel)
                .filter(UserOLTPermissionModel.user_id == user.id)
                .all()
            )
            allowed_olts = {p.olt_id for p in perms}

        # Restrições de VLAN por OLT para Operadoras Neutras
        allowed_vlans = None
        if tenant.type == "NEUTRAL_OPERATOR":
            allocs = (
                db.query(TenantVLANAllocationModel)
                .filter(TenantVLANAllocationModel.tenant_id == tenant.id)
                .all()
            )
            allowed_vlans = {}
            for al in allocs:
                allowed_vlans.setdefault(al.olt_id, set()).add(al.vlan_id)

        return SecurityContext(
            caller_type="DYNAMIC_API_KEY",
            role=user_role,
            scopes=scopes,
            user_id=user.id if user else None,
            user_name=user.name if user else key_record.name,
            user_email=user.email if user else None,
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            tenant_type=tenant.type,
            allowed_olt_ids=allowed_olts,
            allowed_vlans=allowed_vlans,
        )

    # 2. Autenticação via Token JWT (Authorization: Bearer <token>)
    if auth_cred and auth_cred.credentials:
        token = auth_cred.credentials
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de acesso inválido ou expirado.",
            )

        user_id = payload["sub"]
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário associado ao token está inativo ou não existe.",
            )

        tenant = db.query(TenantModel).filter(TenantModel.id == user.tenant_id).first()
        if not tenant or not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inquilino associado a este usuário está inativo.",
            )

        allowed_olts = None
        if user.role in ["FIELD_TECH", "TENANT_ADMIN", "TENANT_TECH"]:
            perms = (
                db.query(UserOLTPermissionModel)
                .filter(UserOLTPermissionModel.user_id == user.id)
                .all()
            )
            allowed_olts = {p.olt_id for p in perms}

        allowed_vlans = None
        if tenant.type == "NEUTRAL_OPERATOR":
            allocs = (
                db.query(TenantVLANAllocationModel)
                .filter(TenantVLANAllocationModel.tenant_id == tenant.id)
                .all()
            )
            allowed_vlans = {}
            for al in allocs:
                allowed_vlans.setdefault(al.olt_id, set()).add(al.vlan_id)

        user_role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        role_scopes = set(ROLE_DEFAULT_SCOPES.get(user_role_str, {"olts:read", "onus:read"}))

        return SecurityContext(
            caller_type="USER_JWT",
            role=user_role_str,
            scopes=role_scopes,
            user_id=user.id,
            user_name=user.name,
            user_email=user.email,
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            tenant_type=tenant.type,
            allowed_olt_ids=allowed_olts,
            allowed_vlans=allowed_vlans,
        )

    # 3. Nenhuma credencial fornecida
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autenticação obrigatória. Forneça o cabeçalho 'X-API-Key' ou 'Authorization: Bearer <token>'.",
    )


def require_api_key(ctx: SecurityContext = Depends(get_security_context)) -> SecurityContext:
    """Compatibilidade retroativa: valida que a requisição possui credenciais válidas e ativas."""
    return ctx


def get_sync_service(
    olt_repo: Union[SQLOLTRepository, OLTRepository] = Depends(get_olt_repo),
    onu_repo: Union[SQLONUInventoryRepository, ONUInventoryRepository] = Depends(get_onu_repo),
    backup_service: BackupService = Depends(get_backup_service),
) -> OLTSyncService:
    return OLTSyncService(olt_repo=olt_repo, onu_repo=onu_repo, backup_service=backup_service)


def get_xray_service(
    olt_repo: Union[SQLOLTRepository, OLTRepository] = Depends(get_olt_repo),
    onu_repo: Union[SQLONUInventoryRepository, ONUInventoryRepository] = Depends(get_onu_repo),
    storage: BackupStorage = Depends(get_backup_storage),
) -> OLTXRayService:
    return OLTXRayService(olt_repo=olt_repo, onu_repo=onu_repo, storage=storage)


def get_onboarding_service(
    olt_repo: Union[SQLOLTRepository, OLTRepository] = Depends(get_olt_repo),
    backup_service: BackupService = Depends(get_backup_service),
    sync_service: OLTSyncService = Depends(get_sync_service),
    telemetry_service: OLTXRayService = Depends(get_xray_service),
) -> OLTOnboardingService:
    return OLTOnboardingService(
        olt_repo=olt_repo,
        backup_service=backup_service,
        sync_service=sync_service,
        telemetry_service=telemetry_service,
    )


def get_enrichment_service(
    olt_repo: Union[SQLOLTRepository, OLTRepository] = Depends(get_olt_repo),
    onu_repo: Union[SQLONUInventoryRepository, ONUInventoryRepository] = Depends(get_onu_repo),
) -> ONUEnrichmentService:
    actual_olt_repo = _olt_repo if hasattr(olt_repo, "dependency") else olt_repo
    actual_onu_repo = _onu_repo if hasattr(onu_repo, "dependency") else onu_repo
    return ONUEnrichmentService(olt_repo=actual_olt_repo, onu_repo=actual_onu_repo)




