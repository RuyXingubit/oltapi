from typing import Union
from fastapi import Depends
from app.core.security import verify_api_key
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

# Instâncias singleton padrão (persistência relacional via SQLAlchemy)
_olt_repo = SQLOLTRepository()
_backup_storage = SQLBackupStorage()
_onu_repo = SQLONUInventoryRepository()
_webhook_repo = SQLWebhookRepository()


def get_olt_repo() -> Union[SQLOLTRepository, OLTRepository]:
    return _olt_repo


def get_onu_repo() -> Union[SQLONUInventoryRepository, ONUInventoryRepository]:
    return _onu_repo


def get_webhook_repo() -> Union[SQLWebhookRepository, WebhookRepository]:
    return _webhook_repo


def get_webhook_dispatcher(
    repo: Union[SQLWebhookRepository, WebhookRepository] = Depends(get_webhook_repo),
) -> WebhookDispatcher:
    return WebhookDispatcher(repo=repo)


def get_backup_storage() -> Union[SQLBackupStorage, BackupStorage]:
    return _backup_storage


def get_backup_service(
    repo: Union[SQLOLTRepository, OLTRepository] = Depends(get_olt_repo),
    storage: Union[SQLBackupStorage, BackupStorage] = Depends(get_backup_storage),
) -> BackupService:
    return BackupService(olt_repo=repo, storage=storage)


# Instâncias dos serviços compartilhados
_reconciliation_service = ONUReconciliationService(
    olt_repo=_olt_repo,
    onu_repo=_onu_repo,
    webhook_dispatcher=get_webhook_dispatcher(_webhook_repo),
)

_scanner_service = None


def get_reconciliation_service() -> ONUReconciliationService:
    return _reconciliation_service


def get_scanner_service() -> "AutofindScannerService":
    global _scanner_service
    if _scanner_service is None:
        from app.services.autofind_scanner import AutofindScannerService
        _scanner_service = AutofindScannerService(
            olt_repo=_olt_repo,
            onu_repo=_onu_repo,
            reconciliation_service=_reconciliation_service,
            webhook_dispatcher=get_webhook_dispatcher(_webhook_repo),
        )
    return _scanner_service


def require_api_key(api_key: str = Depends(verify_api_key)) -> str:
    return api_key


