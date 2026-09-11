from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.uuid import generate_uuid7


class BackupMetadata(BaseModel):
    backup_id: str = Field(default_factory=generate_uuid7, description="UUIDv7 identificador único")
    olt_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    size_bytes: int
    sha256_hash: str
    filename: str


class BackupDiffResult(BaseModel):
    olt_id: str
    base_backup_id: str
    target_backup_id: str
    identical: bool = Field(description="Verdadeiro se os hashes SHA-256 forem idênticos (sem config drift)")
    base_sha256: str
    target_sha256: str
    diff_lines: List[str] = Field(default_factory=list, description="Linhas no formato unified_diff")
    additions_count: int = 0
    deletions_count: int = 0


class BackupAuditReport(BaseModel):
    olt_id: str
    olt_name: str
    total_backups: int
    total_bytes: int
    latest_backup: Optional[BackupMetadata] = None
    previous_backup: Optional[BackupMetadata] = None
    has_changed: bool = Field(description="Verdadeiro se o último backup divergir do penúltimo")
    last_backup_at: Optional[datetime] = None


class PurgePolicy(BaseModel):
    max_backups_per_olt: int = Field(default=30, ge=1, description="Máximo de backups retidos por OLT")
    max_age_days: Optional[int] = Field(default=None, ge=1, description="Idade máxima em dias para retenção")


class PurgeResult(BaseModel):
    olt_id: Optional[str] = None
    deleted_count: int
    freed_bytes: int
    remaining_count: int


class BatchBackupResult(BaseModel):
    total_olts: int
    successful: int
    failed: int
    backups: List[BackupMetadata] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)

