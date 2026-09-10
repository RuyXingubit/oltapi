from datetime import datetime, timezone
from pydantic import BaseModel, Field
from app.core.uuid import generate_uuid7


class BackupMetadata(BaseModel):
    backup_id: str = Field(default_factory=generate_uuid7, description="UUIDv7 identificador único")
    olt_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    size_bytes: int
    sha256_hash: str
    filename: str
