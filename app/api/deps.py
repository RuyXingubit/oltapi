from fastapi import Depends
from app.core.security import verify_api_key
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository

# Instâncias singleton para injeção de dependência
_olt_repo = OLTRepository()
_backup_storage = BackupStorage()


def get_olt_repo() -> OLTRepository:
    return _olt_repo


def get_backup_storage() -> BackupStorage:
    return _backup_storage


def require_api_key(api_key: str = Depends(verify_api_key)) -> str:
    return api_key
