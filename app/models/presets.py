from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.uuid import generate_uuid7
from app.models.hateoas import Link


class ProvisioningPresetCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, description="Nome do Preset (ex: Residencial 500M Bridge)")
    description: Optional[str] = Field(default=None, max_length=256, description="Descrição operacional do template")
    vlan: int = Field(..., ge=1, le=4094, description="VLAN de serviço padrão")
    mode: str = Field(default="transparent", description="Modo de operação: transparent, tag, translate, trunk")
    line_profile: Optional[str] = Field(default="DEFAULT", description="Line profile padrão na OLT")
    srv_profile: Optional[str] = Field(default="DEFAULT", description="Service profile padrão na OLT")
    tenant_id: Optional[str] = Field(default=None, description="ID do Tenant proprietário (opcional)")
    is_default: bool = Field(default=False, description="Define se é o preset padrão sugerido na tela de autofind")


class ProvisioningPresetItem(BaseModel):
    id: str = Field(default_factory=generate_uuid7, description="Identificador único UUIDv7")
    name: str
    description: Optional[str] = None
    vlan: int
    mode: str = "transparent"
    line_profile: Optional[str] = "DEFAULT"
    srv_profile: Optional[str] = "DEFAULT"
    tenant_id: Optional[str] = None
    is_default: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class PreProvisionONURequest(BaseModel):
    serial: str = Field(..., description="Serial alfanumérico da ONU enviada a campo")
    subscriber_name: str = Field(..., min_length=2, max_length=128, description="Nome do assinante")
    contract_id: Optional[str] = Field(default=None, description="Código do contrato no ERP")
    preset_id: Optional[str] = Field(default=None, description="ID do Preset de provisionamento a aplicar")
    vlan: Optional[int] = Field(default=None, ge=1, le=4094, description="VLAN de serviço (sobrescreve o preset se informado)")
    profile: Optional[str] = Field(default=None, description="Perfil de tráfego (sobrescreve o preset se informado)")
    olt_id: Optional[str] = Field(default=None, description="OLT esperada (opcional; se omitido, ativa em qualquer OLT onde acender)")
    port: Optional[str] = Field(default=None, description="Porta PON esperada (opcional)")
    zone_id: Optional[str] = Field(default=None, description="ID da Zona FTTH")
    odb_id: Optional[str] = Field(default=None, description="ID da CTO / ODB")
    odb_splitter_port: Optional[int] = Field(default=None, ge=1, le=128, description="Porta do splitter na CTO")
    description: Optional[str] = Field(default=None, description="Observações da Ordem de Serviço")


class BatchONUActionTarget(BaseModel):
    serial: str = Field(..., description="Serial da ONU")
    port: Optional[str] = Field(default=None, description="Porta PON da ONU")
    onu_id: Optional[int] = Field(default=None, description="Índice numérico da ONU na porta")


class BatchONUActionRequest(BaseModel):
    action: str = Field(
        ...,
        description="Ação em lote: reboot, suspend, resume, deprovision, change_vlan",
    )
    targets: List[BatchONUActionTarget] = Field(..., min_length=1, max_length=128, description="Lista de ONUs alvo")
    target_vlan: Optional[int] = Field(default=None, ge=1, le=4094, description="Nova VLAN (obrigatório quando action='change_vlan')")


class BatchONUActionItemResult(BaseModel):
    serial: str
    port: Optional[str] = None
    onu_id: Optional[int] = None
    success: bool
    message: str


class BatchONUActionResponse(BaseModel):
    olt_id: str
    action: str
    total: int
    succeeded: int
    failed: int
    results: List[BatchONUActionItemResult] = Field(default_factory=list)
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}
