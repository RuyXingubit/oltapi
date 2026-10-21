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
    mode: Optional[str] = Field(default="bridge", description="Modo de operação: 'bridge' ou 'router'")
    pppoe_user: Optional[str] = Field(default=None, description="Usuário PPPoE para modo router")
    pppoe_password: Optional[str] = Field(default=None, description="Senha PPPoE para modo router")
    onu_id: Optional[int] = Field(default=None, description="ID da ONU na porta PON (auto-calculado se omitido)")


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
    action: str = Field(description="Tipo de ação: deprovision, reboot, suspend, resume, change_vlan, move_port")
    olt_id: str
    serial: str
    port: Optional[str] = None
    onu_id: Optional[int] = None
    message: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class ONUChangeVLANRequest(BaseModel):
    vlan: int = Field(..., ge=1, le=4094, description="Nova VLAN de serviço da ONU", json_schema_extra={"example": 621})
    port: Optional[str] = Field(default=None, description="Porta PON atual da ONU (detectada automaticamente se omitida)")
    onu_id: Optional[int] = Field(default=None, description="ID numérico da ONU na porta PON (detectado automaticamente se omitido)")
    mode: Optional[str] = Field(default="bridge", description="Modo de operação: 'bridge' ou 'router'")


class ONUMovePortRequest(BaseModel):
    target_port: str = Field(..., description="Nova porta PON de destino (ex: 0/1/2)", json_schema_extra={"example": "0/1/2"})
    target_onu_id: Optional[int] = Field(default=None, description="ID numérico na nova porta PON (auto-alocado se omitido)")
    vlan: Optional[int] = Field(default=None, ge=1, le=4094, description="VLAN de serviço na nova porta (mantém a VLAN atual se omitida)")
    mode: Optional[str] = Field(default="bridge", description="Modo de operação: 'bridge' ou 'router'")
    description: Optional[str] = Field(default=None, description="Descrição/nome do cliente (mantém a descrição atual se omitida)")



