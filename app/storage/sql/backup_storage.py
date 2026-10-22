import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.core.config import settings
from app.core.uuid import generate_uuid7, is_valid_uuid7
from app.db.models import BackupMetadataModel
from app.db.session import SessionLocal
from app.models.backup import BackupMetadata, PurgeResult
from app.storage.backup_storage import BackupStorage

logger = logging.getLogger(__name__)


class SQLBackupStorage(BackupStorage):
    """
    Gerenciador de armazenamento seguro e integridade de backups das OLTs via banco relacional.
    Armazena os arquivos físicos `.cfg` no sistema de arquivos seguro e o índice/metadados no banco.
    """

    def __init__(self, base_dir: Optional[Path] = None, session_factory=SessionLocal):
        self.base_dir = base_dir or settings.BACKUP_DIR
        self.session_factory = session_factory
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _to_model(self, m: BackupMetadataModel) -> BackupMetadata:
        return BackupMetadata(
            backup_id=m.backup_id,
            olt_id=m.olt_id,
            size_bytes=m.size_bytes,
            sha256_hash=m.sha256,
            filename=m.filename,
            created_at=m.created_at,
        )

    def save_backup(self, olt_id: str, content: str) -> BackupMetadata:
        """Salva o conteúdo textual do backup em disco, calcula SHA-256 e grava no banco relacional."""
        olt_backup_dir = self.base_dir / olt_id
        olt_backup_dir.mkdir(parents=True, exist_ok=True)

        backup_id = generate_uuid7()
        filename = f"backup_{backup_id}.cfg"
        file_path = olt_backup_dir / filename

        raw_bytes = content.encode("utf-8")
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

        with open(file_path, "wb") as f:
            f.write(raw_bytes)

        now = datetime.now(timezone.utc)
        with self.session_factory() as db:
            m = BackupMetadataModel(
                backup_id=backup_id,
                olt_id=olt_id,
                olt_name=olt_id,
                filename=filename,
                size_bytes=len(raw_bytes),
                sha256=sha256_hash,
                created_at=now,
            )
            db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_model(m)

    def list_by_olt(self, olt_id: str) -> List[BackupMetadata]:
        """Lista os backups ordenados por data de criação decrescente."""
        with self.session_factory() as db:
            models = (
                db.query(BackupMetadataModel)
                .filter(BackupMetadataModel.olt_id == olt_id)
                .order_by(BackupMetadataModel.created_at.desc())
                .all()
            )
            return [self._to_model(m) for m in models]

    def get_backup_path(self, olt_id: str, backup_id: str) -> Optional[Path]:
        """Retorna o caminho seguro do arquivo de backup com proteção rigorosa contra Path Traversal."""
        if not is_valid_uuid7(backup_id) or not is_valid_uuid7(olt_id):
            return None

        with self.session_factory() as db:
            m = (
                db.query(BackupMetadataModel)
                .filter(
                    BackupMetadataModel.backup_id == backup_id,
                    BackupMetadataModel.olt_id == olt_id,
                )
                .first()
            )
            if not m:
                return None

            return self._resolve_safe_file(olt_id, m.filename)

    def delete_backup(self, olt_id: str, backup_id: str) -> bool:
        """Exclui com segurança um arquivo de backup em disco e remove do banco relacional."""
        self._unlink_backup_file(olt_id, backup_id)

        with self.session_factory() as db:
            m = (
                db.query(BackupMetadataModel)
                .filter(
                    BackupMetadataModel.backup_id == backup_id,
                    BackupMetadataModel.olt_id == olt_id,
                )
                .first()
            )
            if m:
                db.delete(m)
                db.commit()
                return True
            return False

    def purge_backups(
        self,
        olt_id: Optional[str] = None,
        max_backups_per_olt: int = 30,
        max_age_days: Optional[int] = None,
    ) -> PurgeResult:
        """Aplica política de retenção e expurgo de backups obsoletos por quantidade ou idade."""
        with self.session_factory() as db:
            if olt_id:
                target_olt_ids = [olt_id]
            else:
                rows = db.query(BackupMetadataModel.olt_id).distinct().all()
                target_olt_ids = [r[0] for r in rows]

        deleted_count, freed_bytes = self._purge_olt_list(target_olt_ids, max_backups_per_olt, max_age_days)

        with self.session_factory() as db:
            q = db.query(BackupMetadataModel)
            if olt_id:
                q = q.filter(BackupMetadataModel.olt_id == olt_id)
            remaining = q.count()

        return PurgeResult(
            olt_id=olt_id,
            deleted_count=deleted_count,
            freed_bytes=freed_bytes,
            remaining_count=remaining,
        )
