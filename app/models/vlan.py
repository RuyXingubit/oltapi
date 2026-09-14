from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.hateoas import Link


class VLANItem(BaseModel):
    vlan_id: int = Field(..., ge=1, le=4094, description="ID numérico da VLAN (1-4094)")
    name: Optional[str] = Field(default=None, description="Nome identificador da VLAN")
    description: Optional[str] = Field(default=None, description="Descrição ou propósito da VLAN")
    tagged_ports: List[str] = Field(default_factory=list, description="Portas de uplink/PON marcadas (Tagged)")
    untagged_ports: List[str] = Field(default_factory=list, description="Portas não marcadas (Untagged / Access)")
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class VLANCreateRequest(BaseModel):
    vlan_id: int = Field(..., ge=1, le=4094, description="ID numérico da nova VLAN (1-4094)")
    name: Optional[str] = Field(default=None, max_length=64, description="Nome identificador da VLAN")
    description: Optional[str] = Field(default=None, max_length=128, description="Descrição do propósito da VLAN")
    tagged_uplink_ports: Optional[List[str]] = Field(default=None, description="Lista opcional de portas de uplink para taggear")


class ProfileItem(BaseModel):
    name: str = Field(..., description="Nome do perfil")
    profile_type: str = Field(default="line", description="Tipo do perfil: line, dba, traffic")
    details: Optional[str] = Field(default=None, description="Parâmetros adicionais do perfil")
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class SyncOLTResponse(BaseModel):
    olt_id: str = Field(..., description="Identificador UUIDv7 da OLT")
    olt_name: str = Field(..., description="Nome da OLT")
    baseline_backup_id: str = Field(..., description="UUIDv7 do backup de baseline preventivo (Snapshot v0)")
    total_onus_discovered: int = Field(..., description="Total de ONUs identificadas no chassi")
    new_onus_registered: int = Field(..., description="ONUs novas catalogadas no inventário")
    existing_onus_updated: int = Field(..., description="ONUs preexistentes atualizadas")
    vlans_discovered: List[int] = Field(default_factory=list, description="VLANs identificadas na OLT")
    duration_ms: float = Field(..., description="Tempo de execução do sync em milissegundos")
    message: str = Field(default="Onboarding e sincronização concluídos com sucesso")
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class VLANMetricsItem(BaseModel):
    vlan_id: int = Field(..., description="ID numérico da VLAN")
    name: Optional[str] = Field(default=None, description="Nome identificador da VLAN")
    description: Optional[str] = Field(default=None, description="Descrição ou propósito da VLAN")
    tagged_ports: List[str] = Field(default_factory=list)
    untagged_ports: List[str] = Field(default_factory=list)
    total_provisioned_onus: int = Field(default=0, description="Total de ONUs cadastradas nesta VLAN")
    total_active_onus: int = Field(default=0, description="Total de ONUs com status ACTIVE nesta VLAN")
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class VLANHistoryItem(BaseModel):
    id: str
    serial: str
    vlan_id: int
    olt_id: str
    port: Optional[str] = None
    contract_id: Optional[str] = None
    subscriber_name: Optional[str] = None
    reason: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    is_current: bool = Field(default=True, description="True se a ONU ainda estiver usando esta VLAN")
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}
