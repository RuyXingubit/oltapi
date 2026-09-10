from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import get_backup_storage, get_olt_repo, require_api_key
from app.drivers.factory import DriverFactory
from app.models.backup import BackupMetadata
from app.models.olt import OLTConfigResponse, OLTCreateRequest, OLTResponse
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository

router = APIRouter(prefix="/olts", tags=["OLTs & Backups"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=List[OLTResponse])
def list_olts(repo: OLTRepository = Depends(get_olt_repo)):
    """Lista todas as OLTs cadastradas."""
    olts = repo.list_all()
    return [
        OLTResponse(
            id=o.id,
            name=o.name,
            vendor=o.vendor,
            model=o.model,
            host=o.host,
            port=o.port,
            protocol=o.protocol,
            created_at=o.created_at,
        )
        for o in olts
    ]


@router.post("", response_model=OLTResponse, status_code=status.HTTP_201_CREATED)
def create_olt(req: OLTCreateRequest, repo: OLTRepository = Depends(get_olt_repo)):
    """Cadastra uma nova OLT no inventário."""
    olt = repo.create(req)
    return OLTResponse(
        id=olt.id,
        name=olt.name,
        vendor=olt.vendor,
        model=olt.model,
        host=olt.host,
        port=olt.port,
        protocol=olt.protocol,
        created_at=olt.created_at,
    )


@router.get("/{olt_id}/config", response_model=OLTConfigResponse)
def get_olt_config(olt_id: str, repo: OLTRepository = Depends(get_olt_repo)):
    """Coleta e visualiza o running-config completo da OLT."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        config_text = driver.get_running_config(olt)
        return OLTConfigResponse(olt_id=olt.id, config_text=config_text)
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao obter configuração: {str(e)}")


@router.get("/{olt_id}/backups", response_model=List[BackupMetadata])
def list_backups(
    olt_id: str,
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
):
    """Lista o histórico de backups realizados para a OLT."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")
    return storage.list_by_olt(olt_id)


@router.post("/{olt_id}/backups", response_model=BackupMetadata, status_code=status.HTTP_201_CREATED)
def trigger_backup(
    olt_id: str,
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
):
    """Dispara a rotina de backup na OLT, salva em disco e retorna os metadados com UUIDv7 e hash SHA-256."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    try:
        driver = DriverFactory.get_driver(olt)
        content = driver.backup_config(olt)
        metadata = storage.save_backup(olt_id=olt.id, content=content)
        return metadata
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao realizar backup: {str(e)}")


@router.get("/{olt_id}/backups/{backup_id}/download")
def download_backup(
    olt_id: str,
    backup_id: str,
    repo: OLTRepository = Depends(get_olt_repo),
    storage: BackupStorage = Depends(get_backup_storage),
):
    """Entrega o arquivo bruto de backup para download seguro pelo ERP ou técnico."""
    olt = repo.get_by_id(olt_id)
    if not olt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"OLT '{olt_id}' não encontrada.")

    file_path = storage.get_backup_path(olt_id=olt_id, backup_id=backup_id)
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Backup '{backup_id}' não encontrado ou inválido.")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )
