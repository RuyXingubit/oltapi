import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.hateoas import Link


class PonPolicyCreateOrUpdate(BaseModel):
    port: str = Field(..., description="Porta PON (ex: 0/1 ou 1)", json_schema_extra={"example": "0/1"})
    default_vlan: int = Field(..., ge=1, le=4094, description="VLAN de serviço padrão", json_schema_extra={"example": 300})
    default_mode: str = Field(default="transparent", description="Modo padrão: transparent, bridge ou router")
    default_line_profile: Optional[str] = Field(default=None, description="Perfil de linha (DBA) padrão")
    default_srv_profile: Optional[str] = Field(default=None, description="Perfil de serviço padrão")
    vendor_parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parâmetros específicos do fabricante")
    auto_authorize_enabled: bool = Field(default=False, description="Habilitar auto-autorização contínua nesta porta")


class PonPolicyItem(BaseModel):
    id: str
    olt_id: str
    port: str
    default_vlan: int
    default_mode: str = "transparent"
    default_line_profile: Optional[str] = None
    default_srv_profile: Optional[str] = None
    vendor_parameters: Dict[str, Any] = Field(default_factory=dict)
    auto_authorize_enabled: bool = False
    created_at: datetime
    updated_at: datetime
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class AutoProvisionTaskCreate(BaseModel):
    pon_port: str = Field(default="ALL", description="Porta PON alvo ou 'ALL' para todas as portas")
    target_vlan: Optional[int] = Field(default=None, ge=1, le=4094, description="VLAN alvo (se omitido, herda da política da PON)")
    duration_minutes: int = Field(default=120, ge=5, le=1440, description="Duração da janela em minutos (5min a 24h)")
    default_mode: str = Field(default="transparent", description="Modo de operação: transparent, bridge ou router")
    default_line_profile: Optional[str] = Field(default=None, description="Perfil de linha padrão")
    default_srv_profile: Optional[str] = Field(default=None, description="Perfil de serviço padrão")
    vendor_parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_by: Optional[str] = Field(default=None, description="Operador ou técnico responsável")


class AutoProvisionTaskItem(BaseModel):
    id: str
    olt_id: str
    pon_port: str
    target_vlan: int
    default_mode: str = "transparent"
    default_line_profile: Optional[str] = None
    default_srv_profile: Optional[str] = None
    vendor_parameters: Dict[str, Any] = Field(default_factory=dict)
    status: str = "RUNNING"  # RUNNING, COMPLETED, CANCELLED
    starts_at: datetime
    expires_at: datetime
    remaining_seconds: int = 0
    provisioned_count: int = 0
    created_by: Optional[str] = None
    created_at: datetime
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class ProvisioningSchemaField(BaseModel):
    key: str
    label: str
    type: str  # "int", "text", "select"
    required: bool = False
    default_value: Optional[Any] = None
    options: List[Dict[str, Any]] = Field(default_factory=list)


class ProvisioningSchemaResponse(BaseModel):
    olt_id: str
    vendor: str
    model: str
    ports: List[str] = Field(default_factory=list)
    fields: List[ProvisioningSchemaField] = Field(default_factory=list)
    available_vlans: List[Dict[str, Any]] = Field(default_factory=list)
    available_profiles: List[Dict[str, Any]] = Field(default_factory=list)
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}
