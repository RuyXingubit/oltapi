from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.hateoas import Link


class ScannerOLTSummary(BaseModel):
    olt_id: str
    olt_name: str
    status: str = Field(description="Status da varredura na OLT: 'success' ou 'error'")
    detected_onus_count: int = 0
    reconciled_serials: List[str] = Field(default_factory=list)
    virgin_serials: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class ScannerRunResult(BaseModel):
    cycle_id: str = Field(description="Identificador único do ciclo de varredura (UUIDv7)")
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    olts_scanned: int
    detected_onus_count: int
    reconciled_onus_count: int
    virgin_onus_count: int
    errors_count: int
    olt_results: List[ScannerOLTSummary] = Field(default_factory=list)
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class ScannerStatus(BaseModel):
    is_running: bool
    interval_seconds: int
    last_run_at: Optional[datetime] = None
    last_run_duration_ms: Optional[float] = None
    last_cycle_id: Optional[str] = None
    total_cycles: int = 0
    total_onus_detected: int = 0
    total_onus_reconciled: int = 0
    total_virgin_onus: int = 0
    total_errors: int = 0
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class ScannerIntervalUpdateRequest(BaseModel):
    interval_seconds: int = Field(
        ...,
        ge=10,
        le=86400,
        description="Novo intervalo de varredura periódica em segundos (mínimo defensivo: 10s)",
        json_schema_extra={"example": 60},
    )
