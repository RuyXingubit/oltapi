import logging
from typing import Any, List, Optional
from app.drivers.factory import DriverFactory
from app.models.backup import BackupAuditReport, BackupMetadata, BatchBackupResult, PurgeResult
from app.services.ftp_service import FTPService
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository

logger = logging.getLogger(__name__)


class BackupService:
    """Serviço de orquestração de backups em lote, auditoria de integridade e políticas de expurgo."""

    def __init__(
        self,
        olt_repo: OLTRepository,
        storage: BackupStorage,
        ftp_repo: Optional[Any] = None,
    ):
        self.olt_repo = olt_repo
        self.storage = storage
        self.ftp_repo = ftp_repo

    def _get_effective_ftps(self, olt_id: str) -> List[Any]:
        if not self.ftp_repo:
            return []
        try:
            destinations = self.ftp_repo.get_destinations_for_olt(olt_id)
            raw_ftps = []
            for d in destinations.effective_destinations:
                raw = self.ftp_repo.get_raw_by_id(d.id)
                if raw and raw.is_active:
                    raw_ftps.append(raw)
            return raw_ftps
        except Exception as e:
            logger.warning(f"Erro ao obter destinos FTP para OLT {olt_id}: {e}")
            return []

    def _mirror_backup(self, olt, driver, backup_id: str, content: str, raw_ftps: List[Any]) -> None:
        if not raw_ftps:
            return
        targets_to_mirror = raw_ftps[1:] if getattr(driver, "handles_primary_ftp_upload", False) else raw_ftps
        for target in targets_to_mirror:
            try:
                remote_name = f"backup_{olt.id}_{backup_id}.cfg"
                FTPService.upload_file(
                    host=target.host,
                    port=target.port,
                    username=target.username,
                    password=target.password,
                    remote_filename=remote_name,
                    content=content,
                    base_path=target.base_path or "/",
                )
                logger.info(f"Backup replicado com sucesso para FTP '{target.name}' ({target.host})")
            except Exception as e:
                logger.error(f"Erro ao replicar backup para FTP '{target.name}': {e}")

    def create_backup(self, olt_id: str, notes: Optional[str] = None) -> BackupMetadata:
        """Cria e persiste backup individual da OLT especificada."""
        olt = self.olt_repo.get_by_id(olt_id)
        if not olt:
            raise ValueError(f"OLT '{olt_id}' não encontrada.")
        raw_ftps = self._get_effective_ftps(olt.id)
        driver = DriverFactory.get_driver(olt)
        content = driver.backup_config(olt, ftp_servers=raw_ftps)
        meta = self.storage.save_backup(olt_id=olt.id, content=content)
        self._mirror_backup(olt, driver, meta.backup_id, content, raw_ftps)
        return meta

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
                raw_ftps = self._get_effective_ftps(olt.id)
                driver = DriverFactory.get_driver(olt)
                content = driver.backup_config(olt, ftp_servers=raw_ftps)
                meta = self.storage.save_backup(olt_id=olt.id, content=content)
                self._mirror_backup(olt, driver, meta.backup_id, content, raw_ftps)
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
