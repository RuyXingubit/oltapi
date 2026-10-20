from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.uuid import generate_uuid7
from app.models.hateoas import Link


class OpticalTelemetrySample(BaseModel):
    id: str = Field(default_factory=generate_uuid7, description="Identificador único da amostra UUIDv7")
    serial: str = Field(..., description="Serial da ONU")
    olt_id: str = Field(..., description="ID da OLT")
    port: Optional[str] = Field(default=None, description="Porta PON")
    onu_id: Optional[int] = Field(default=None, description="Índice ONU ID")
    rx_power_dbm: Optional[float] = Field(default=None, description="Potência óptica Rx da ONU (dBm)")
    tx_power_dbm: Optional[float] = Field(default=None, description="Potência óptica Tx da ONU (dBm)")
    olt_rx_power_dbm: Optional[float] = Field(default=None, description="Potência óptica Rx na OLT (dBm)")
    status: str = Field(default="online", description="Estado operacional: online, offline, los, dying_gasp")
    last_down_cause: Optional[str] = Field(default=None, description="Causa da última queda normalizada")
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp da coleta")


class OpticalTelemetryHistoryResponse(BaseModel):
    serial: str = Field(..., description="Serial da ONU")
    olt_id: Optional[str] = Field(default=None, description="ID da OLT atual")
    port: Optional[str] = Field(default=None, description="Porta PON atual")
    current_rx_power_dbm: Optional[float] = Field(default=None, description="Leitura mais recente de Rx (dBm)")
    baseline_rx_power_dbm: Optional[float] = Field(default=None, description="Média histórica / baseline de Rx (dBm)")
    drift_db: Optional[float] = Field(
        default=None,
        description="Variação em dB entre o sinal atual e a linha de base (negativo indica atenuação/degradação)",
    )
    is_degraded: bool = Field(default=False, description="Indica se a ONU apresenta atenuação crítica ou deriva excessiva")
    degradation_reasons: List[str] = Field(default_factory=list, description="Motivos técnicos do alerta de degradação")
    samples: List[OpticalTelemetrySample] = Field(default_factory=list, description="Série temporal de amostras ópticas")
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class DegradedONUReportItem(BaseModel):
    serial: str = Field(..., description="Serial da ONU")
    subscriber_name: Optional[str] = Field(default=None, description="Nome do assinante")
    olt_id: Optional[str] = Field(default=None, description="ID da OLT")
    port: Optional[str] = Field(default=None, description="Porta PON")
    onu_id: Optional[int] = Field(default=None, description="Índice ONU ID")
    rx_power_dbm: Optional[float] = Field(default=None, description="Última potência óptica Rx (dBm)")
    baseline_rx_power_dbm: Optional[float] = Field(default=None, description="Média histórica de Rx (dBm)")
    drift_db: Optional[float] = Field(default=None, description="Deriva acumulada (dB)")
    last_down_cause: Optional[str] = Field(default=None, description="Última causa de queda")
    severity: str = Field(default="warning", description="Severidade: warning ou critical")
    reasons: List[str] = Field(default_factory=list, description="Motivos de classificação no radar")
    last_telemetry_at: Optional[datetime] = Field(default=None, description="Timestamp da última leitura")
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class OpticalCollectionSummaryResponse(BaseModel):
    olt_id: str
    olt_name: str
    collected_count: int
    degraded_count: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}
