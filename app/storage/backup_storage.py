import hashlib
import json
import logging
from datetime import datetime, timezone
import difflib
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import settings
from app.core.uuid import generate_uuid7, is_valid_uuid7
from app.models.backup import (
    BackupAuditReport,
    BackupDiffResult,
    BackupMetadata,
    PurgeResult,
)

logger = logging.getLogger(__name__)


class BackupStorage:
    """Gerenciador de armazenamento seguro e integridade de backups das OLTs."""

    def __init__(self, base_dir: Optional[Path] = None, data_file: Optional[Path] = None):
        self.base_dir = base_dir or settings.BACKUP_DIR
        self.data_file = data_file or (settings.DATA_DIR / "backups.json")
        self._backups: Dict[str, BackupMetadata] = {}
        self._load()

    def _load(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        meta = BackupMetadata(**item)
                        self._backups[meta.backup_id] = meta
            except Exception as e:
                logger.error(f"Erro ao carregar índice de backups: {e}")

    def _save(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json_data = [b.model_dump(mode="json") for b in self._backups.values()]
                json.dump(json_data, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar índice de backups: {e}")

    def save_backup(self, olt_id: str, content: str) -> BackupMetadata:
        """Salva o conteúdo textual do backup em disco, calcula SHA-256 e registra metadados."""
        olt_backup_dir = self.base_dir / olt_id
        olt_backup_dir.mkdir(parents=True, exist_ok=True)

        backup_id = generate_uuid7()
        filename = f"backup_{backup_id}.cfg"
        file_path = olt_backup_dir / filename

        raw_bytes = content.encode("utf-8")
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

        with open(file_path, "wb") as f:
            f.write(raw_bytes)

        metadata = BackupMetadata(
            backup_id=backup_id,
            olt_id=olt_id,
            size_bytes=len(raw_bytes),
            sha256_hash=sha256_hash,
            filename=filename,
        )

        self._backups[backup_id] = metadata
        self._save()
        return metadata

    def list_by_olt(self, olt_id: str) -> List[BackupMetadata]:
        """Lista os backups ordenados por data de criação decrescente."""
        items = [b for b in self._backups.values() if b.olt_id == olt_id]
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items

    def get_backup_path(self, olt_id: str, backup_id: str) -> Optional[Path]:
        """Retorna o caminho seguro do arquivo de backup com proteção rigorosa contra Path Traversal."""
        if not is_valid_uuid7(backup_id) or not is_valid_uuid7(olt_id):
            return None

        metadata = self._backups.get(backup_id)
        if not metadata or metadata.olt_id != olt_id:
            return None

        expected_dir = (self.base_dir / olt_id).resolve()
        target_file = (expected_dir / metadata.filename).resolve()

        # Verifica se o arquivo está estritamente contido dentro do diretório autorizado da OLT
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

        # Se nenhum backup for especificado, compara o mais recente (target) com o imediatamente anterior (base)
        if not base_backup_id and not target_backup_id:
            if len(all_backups) < 2:
                # Com apenas 1 backup, comparamos consigo mesmo (idêntico)
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
            base = self._backups.get(base_backup_id or "")
            target = self._backups.get(target_backup_id or "")
            if not base or not target:
                return None
            if base.olt_id != olt_id or target.olt_id != olt_id:
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
        """Exclui com segurança um arquivo de backup em disco e remove do índice."""
        file_path = self.get_backup_path(olt_id=olt_id, backup_id=backup_id)
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Erro ao excluir arquivo físico de backup {file_path}: {e}")

        if backup_id in self._backups and self._backups[backup_id].olt_id == olt_id:
            del self._backups[backup_id]
            self._save()
            return True
        return False

    def purge_backups(
        self,
        olt_id: Optional[str] = None,
        max_backups_per_olt: int = 30,
        max_age_days: Optional[int] = None,
    ) -> PurgeResult:
        """Aplica política de retenção e expurgo de backups obsoletos por quantidade ou idade."""

        target_olt_ids = [olt_id] if olt_id else list({b.olt_id for b in self._backups.values()})
        deleted_count = 0
        freed_bytes = 0
        now = datetime.now(timezone.utc)

        for current_olt in target_olt_ids:
            backups = self.list_by_olt(current_olt)
            to_delete: List[BackupMetadata] = []

            # 1. Filtro por quantidade excedente
            if len(backups) > max_backups_per_olt:
                to_delete.extend(backups[max_backups_per_olt:])

            # 2. Filtro por idade máxima (preservando sempre pelo menos o backup mais recente)
            if max_age_days is not None:
                for b in backups[:max_backups_per_olt]:
                    if b == backups[0]:
                        # Preserva sempre o mais recente para garantir recuperação em caso de desastre
                        continue
                    age = (now - b.created_at).total_seconds() / 86400.0
                    if age > max_age_days and b not in to_delete:
                        to_delete.append(b)

            for b in to_delete:
                if self.delete_backup(current_olt, b.backup_id):
                    deleted_count += 1
                    freed_bytes += b.size_bytes

        remaining = len([b for b in self._backups.values() if not olt_id or b.olt_id == olt_id])
        return PurgeResult(
            olt_id=olt_id,
            deleted_count=deleted_count,
            freed_bytes=freed_bytes,
            remaining_count=remaining,
        )

