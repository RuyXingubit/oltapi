from fastapi import Depends
from app.core.security import verify_api_key
from app.services.backup_service import BackupService
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository
from app.storage.onu_repository import ONUInventoryRepository
from app.storage.webhook_repository import WebhookRepository
from app.services.webhook_dispatcher import WebhookDispatcher

# Instâncias singleton para injeção de dependência
_olt_repo = OLTRepository()
_backup_storage = BackupStorage()
_onu_repo = ONUInventoryRepository()
_webhook_repo = WebhookRepository()


def get_olt_repo() -> OLTRepository:
    return _olt_repo


def get_onu_repo() -> ONUInventoryRepository:
    return _onu_repo


def get_webhook_repo() -> WebhookRepository:
    return _webhook_repo


def get_webhook_dispatcher(
    repo: WebhookRepository = Depends(get_webhook_repo),
) -> WebhookDispatcher:
    return WebhookDispatcher(repo=repo)


def get_backup_storage() -> BackupStorage:
    return _backup_storage


def get_backup_service(
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
) -> BackupService:
    return BackupService(olt_repo=repo, storage=storage)


def require_api_key(api_key: str = Depends(verify_api_key)) -> str:
    return api_key


