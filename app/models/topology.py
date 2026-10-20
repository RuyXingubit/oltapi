from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.uuid import generate_uuid7
from app.models.hateoas import Link


class NetworkZoneCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, description="Nome da Zona / Bairro")
    sector: Optional[str] = Field(default=None, max_length=64, description="Setor ou Região")
    city: Optional[str] = Field(default=None, max_length=64, description="Município")
    description: Optional[str] = Field(default=None, max_length=256, description="Descrição da área de atendimento")


class NetworkZoneItem(BaseModel):
    id: str = Field(default_factory=generate_uuid7, description="Identificador único UUIDv7")
    name: str
    sector: Optional[str] = None
    city: Optional[str] = None
    description: Optional[str] = None
    odb_count: int = 0
    onu_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class OpticalDistributionBoxCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=32, description="Código identificador da CTO/ODB (ex: CTO-CEN-01)")
    name: str = Field(..., min_length=2, max_length=64, description="Nome descritivo da caixa")
    zone_id: Optional[str] = Field(default=None, description="ID da Zona de Rede")
    olt_id: Optional[str] = Field(default=None, description="ID da OLT associada")
    pon_port: Optional[str] = Field(default=None, description="Porta PON que alimenta a CTO")
    splitter_capacity: int = Field(default=16, ge=2, le=128, description="Capacidade do splitter (ex: 8, 16, 32)")
    latitude: Optional[float] = Field(default=None, description="Latitude geográfica da CTO")
    longitude: Optional[float] = Field(default=None, description="Longitude geográfica da CTO")
    address: Optional[str] = Field(default=None, max_length=256, description="Endereço ou poste de referência")
    notes: Optional[str] = Field(default=None, description="Observações de fusão / sangria")


class OpticalDistributionBoxItem(BaseModel):
    id: str = Field(default_factory=generate_uuid7, description="Identificador único UUIDv7")
    code: str
    name: str
    zone_id: Optional[str] = None
    olt_id: Optional[str] = None
    pon_port: Optional[str] = None
    splitter_capacity: int = 16
    used_ports: int = 0
    available_ports: int = 16
    occupied_splitter_ports: List[int] = Field(default_factory=list)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class ONUTopologyAssignRequest(BaseModel):
    zone_id: Optional[str] = Field(default=None, description="ID da Zona FTTH")
    odb_id: Optional[str] = Field(default=None, description="ID da CTO / ODB")
    odb_splitter_port: Optional[int] = Field(default=None, ge=1, le=128, description="Porta física do splitter na CTO")
    latitude: Optional[float] = Field(default=None, description="Latitude da instalação")
    longitude: Optional[float] = Field(default=None, description="Longitude da instalação")


class ODBHealthNode(BaseModel):
    odb_id: str
    code: str
    name: str
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    olt_id: Optional[str] = None
    pon_port: Optional[str] = None
    splitter_capacity: int = 16
    total_onus: int = 0
    online_onus: int = 0
    dying_gasp_onus: int = 0
    los_onus: int = 0
    degraded_onus: int = 0
    health_status: str = Field(
        default="healthy",
        description="Estado operacional inferido: healthy, degraded, power_outage, fiber_cut",
    )
    diagnosis_summary: str = Field(default="Operação normal", description="Diagnóstico automático da CTO")
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class TopologyHealthMapResponse(BaseModel):
    total_zones: int = 0
    total_odbs: int = 0
    healthy_odbs: int = 0
    degraded_odbs: int = 0
    power_outage_odbs: int = 0
    fiber_cut_odbs: int = 0
    nodes: List[ODBHealthNode] = Field(default_factory=list)
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}
