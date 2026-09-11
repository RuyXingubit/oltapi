from typing import List, Optional
from fastapi import APIRouter, Depends
from app.api.deps import get_backup_service, require_api_key
from app.models.backup import BackupAuditReport, BatchBackupResult, PurgePolicy, PurgeResult
from app.services.backup_service import BackupService

router = APIRouter(prefix="/backups", tags=["Backups & Disaster Recovery"], dependencies=[Depends(require_api_key)])


@router.post("/run-all", response_model=BatchBackupResult)
def run_all_backups(
    purge_after: bool = True,
    policy: Optional[PurgePolicy] = None,
    service: BackupService = Depends(get_backup_service),
):
    """Dispara a rotina de backup em lote para todas as OLTs cadastradas com expurgo automático."""
    p = policy or PurgePolicy()
    return service.run_all_backups(
        purge_after=purge_after,
        max_backups_per_olt=p.max_backups_per_olt,
        max_age_days=p.max_age_days,
    )


@router.get("/audit-all", response_model=List[BackupAuditReport])
def audit_all_backups(
    service: BackupService = Depends(get_backup_service),
):
    """Retorna relatório consolidado de integridade, contagem e status de drift de todas as OLTs."""
    return service.audit_all_olts()


@router.post("/purge-all", response_model=PurgeResult)
def purge_all_backups(
    policy: Optional[PurgePolicy] = None,
    service: BackupService = Depends(get_backup_service),
):
    """Executa a política de expurgo e retenção de backups para todo o inventário de OLTs."""
    p = policy or PurgePolicy()
    return service.purge_all(
        max_backups_per_olt=p.max_backups_per_olt,
        max_age_days=p.max_age_days,
    )
