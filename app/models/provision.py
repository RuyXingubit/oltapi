from typing import Dict, Optional
from pydantic import BaseModel, Field
from app.models.hateoas import Link


class ProvisionRequest(BaseModel):
    port: str = Field(..., description="Porta PON (ex: 1/1 ou 0/1/1)", json_schema_extra={"example": "1/1"})
    serial: str = Field(..., description="Número de série alfanumérico da ONU", json_schema_extra={"example": "INCL12345678"})
    vlan: int = Field(..., ge=1, le=4094, description="VLAN de serviço", json_schema_extra={"example": 100})
    profile: Optional[str] = Field(default="DEFAULT", description="Perfil de tráfego/linha", json_schema_extra={"example": "PLAN_100M"})
    description: Optional[str] = Field(default="Cliente", description="Identificação do cliente", json_schema_extra={"example": "Cliente_Joao_Silva"})
    onu_model: Optional[str] = Field(default="auto", description="Modelo da ONU ou 'auto'")


class ProvisionResponse(BaseModel):
    success: bool = True
    port: str
    onu_id: int
    serial: str
    message: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class ONUActionResponse(BaseModel):
    success: bool = True
    action: str = Field(description="Tipo de ação: deprovision, reboot, suspend, resume")
    olt_id: str
    serial: str
    port: Optional[str] = None
    onu_id: Optional[int] = None
    message: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


