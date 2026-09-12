import logging
from typing import List, Optional
from app.drivers.factory import DriverFactory
from app.models.backup import BackupAuditReport, BackupMetadata, BatchBackupResult, PurgeResult
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository

logger = logging.getLogger(__name__)


class BackupService:
    """Serviço de orquestração de backups em lote, auditoria de integridade e políticas de expurgo."""

    def __init__(self, olt_repo: OLTRepository, storage: BackupStorage):
        self.olt_repo = olt_repo
        self.storage = storage

    def create_backup(self, olt_id: str, notes: Optional[str] = None) -> BackupMetadata:
        """Cria e persiste backup individual da OLT especificada."""
        olt = self.olt_repo.get_by_id(olt_id)
        if not olt:
            raise ValueError(f"OLT '{olt_id}' não encontrada.")
        driver = DriverFactory.get_driver(olt)
        content = driver.backup_config(olt)
        return self.storage.save_backup(olt_id=olt.id, content=content)

    def run_all_backups(
        self,
        purge_after: bool = True,
        max_backups_per_olt: int = 30,
        max_age_days: Optional[int] = None,
    ) -> BatchBackupResult:
        """Executa rotina de coleta de backup em todas as OLTs ativas cadastradas."""
        olts = self.olt_repo.list_all()
        result = BatchBackupResult(
            total_olts=len(olts),
            successful=0,
            failed=0,
            backups=[],
            errors=[],
        )

        for olt in olts:
            try:
                driver = DriverFactory.get_driver(olt)
                content = driver.backup_config(olt)
                meta = self.storage.save_backup(olt_id=olt.id, content=content)
                result.backups.append(meta)
                result.successful += 1
                logger.info(f"Backup concluído com sucesso para OLT '{olt.name}' ({olt.id}): {meta.backup_id}")
            except Exception as e:
                result.failed += 1
                error_item = {"olt_id": olt.id, "olt_name": olt.name, "error": str(e)}
                result.errors.append(error_item)
                logger.error(f"Falha ao realizar backup da OLT '{olt.name}' ({olt.id}): {e}")

        if purge_after:
            try:
                self.storage.purge_backups(
                    olt_id=None,
                    max_backups_per_olt=max_backups_per_olt,
                    max_age_days=max_age_days,
                )
            except Exception as e:
                logger.error(f"Erro ao executar expurgo pós-backup em lote: {e}")

        return result

    def audit_all_olts(self) -> List[BackupAuditReport]:
        """Compila relatório consolidado de integridade e auditoria de todo o parque de OLTs."""
        olts = self.olt_repo.list_all()
        reports: List[BackupAuditReport] = []
        for olt in olts:
            reports.append(self.storage.audit_olt(olt_id=olt.id, olt_name=olt.name))
        return reports

    def purge_all(
        self,
        max_backups_per_olt: int = 30,
        max_age_days: Optional[int] = None,
    ) -> PurgeResult:
        """Aplica política de expurgo global em todas as OLTs."""
        return self.storage.purge_backups(
            olt_id=None,
            max_backups_per_olt=max_backups_per_olt,
            max_age_days=max_age_days,
        )
