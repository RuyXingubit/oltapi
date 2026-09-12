import difflib
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.uuid import generate_uuid7, is_valid_uuid7
from app.db.models import BackupMetadataModel
from app.db.session import SessionLocal
from app.models.backup import BackupAuditReport, BackupDiffResult, BackupMetadata, PurgeResult

logger = logging.getLogger(__name__)


class SQLBackupStorage:
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

            expected_dir = (self.base_dir / olt_id).resolve()
            target_file = (expected_dir / m.filename).resolve()

            if not str(target_file).startswith(str(expected_dir)):
                logger.warning(f"Tentativa de Path Traversal bloqueada: {target_file}")
                return None

            if not target_file.exists():
                return None

            return target_file

    def get_backup_content(self, olt_id: str, backup_id: str) -> Optional[str]:
        """Retorna o conteúdo textual do backup especificado com leitura segura."""
        file_path = self.get_backup_path(olt_id=olt_id, backup_id=backup_id)
        if not file_path:
            return None
        try:
            return file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.error(f"Erro ao ler arquivo de backup {file_path}: {e}")
            return None

    def compare_backups(
        self,
        olt_id: str,
        base_backup_id: Optional[str] = None,
        target_backup_id: Optional[str] = None,
    ) -> Optional[BackupDiffResult]:
        """Compara dois backups por hash SHA-256 e gera diff unificado linha a linha."""
        all_backups = self.list_by_olt(olt_id)
        if not all_backups:
            return None

        if not base_backup_id and not target_backup_id:
            if len(all_backups) < 2:
                single = all_backups[0]
                return BackupDiffResult(
                    olt_id=olt_id,
                    base_backup_id=single.backup_id,
                    target_backup_id=single.backup_id,
                    identical=True,
                    base_sha256=single.sha256_hash,
                    target_sha256=single.sha256_hash,
                    diff_lines=[],
                    additions_count=0,
                    deletions_count=0,
                )
            target = all_backups[0]
            base = all_backups[1]
        else:
            backups_map = {b.backup_id: b for b in all_backups}
            base = backups_map.get(base_backup_id or "")
            target = backups_map.get(target_backup_id or "")
            if not base or not target:
                return None

        identical = base.sha256_hash == target.sha256_hash
        diff_lines: List[str] = []
        additions = 0
        deletions = 0

        if not identical:
            base_content = self.get_backup_content(olt_id, base.backup_id) or ""
            target_content = self.get_backup_content(olt_id, target.backup_id) or ""

            base_lines = base_content.splitlines(keepends=True)
            target_lines = target_content.splitlines(keepends=True)

            raw_diff = list(
                difflib.unified_diff(
                    base_lines,
                    target_lines,
                    fromfile=f"backup_{base.backup_id}.cfg",
                    tofile=f"backup_{target.backup_id}.cfg",
                    lineterm="",
                )
            )
            for line in raw_diff:
                diff_lines.append(line.rstrip("\r\n"))
                if line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1

        return BackupDiffResult(
            olt_id=olt_id,
            base_backup_id=base.backup_id,
            target_backup_id=target.backup_id,
            identical=identical,
            base_sha256=base.sha256_hash,
            target_sha256=target.sha256_hash,
            diff_lines=diff_lines,
            additions_count=additions,
            deletions_count=deletions,
        )

    def audit_olt(self, olt_id: str, olt_name: str) -> BackupAuditReport:
        """Gera relatório de integridade e auditoria de backups para a OLT."""
        backups = self.list_by_olt(olt_id)
        total_backups = len(backups)
        total_bytes = sum(b.size_bytes for b in backups)
        latest = backups[0] if backups else None
        previous = backups[1] if len(backups) > 1 else None

        has_changed = False
        if latest and previous:
            has_changed = latest.sha256_hash != previous.sha256_hash

        return BackupAuditReport(
            olt_id=olt_id,
            olt_name=olt_name,
            total_backups=total_backups,
            total_bytes=total_bytes,
            latest_backup=latest,
            previous_backup=previous,
            has_changed=has_changed,
            last_backup_at=latest.created_at if latest else None,
        )

    def delete_backup(self, olt_id: str, backup_id: str) -> bool:
        """Exclui com segurança um arquivo de backup em disco e remove do banco relacional."""
        file_path = self.get_backup_path(olt_id=olt_id, backup_id=backup_id)
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Erro ao excluir arquivo físico de backup {file_path}: {e}")

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

        deleted_count = 0
        freed_bytes = 0
        now = datetime.now(timezone.utc)

        for current_olt in target_olt_ids:
            backups = self.list_by_olt(current_olt)
            to_delete: List[BackupMetadata] = []

            if len(backups) > max_backups_per_olt:
                to_delete.extend(backups[max_backups_per_olt:])

            if max_age_days is not None:
                for b in backups[:max_backups_per_olt]:
                    if b == backups[0]:
                        continue
                    age = (now - b.created_at).total_seconds() / 86400.0
                    if age > max_age_days and b not in to_delete:
                        to_delete.append(b)

            for b in to_delete:
                if self.delete_backup(current_olt, b.backup_id):
                    deleted_count += 1
                    freed_bytes += b.size_bytes

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
