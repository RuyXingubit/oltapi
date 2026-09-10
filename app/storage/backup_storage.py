import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import settings
from app.core.uuid import generate_uuid7, is_valid_uuid7
from app.models.backup import BackupMetadata

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
