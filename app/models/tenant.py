from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from app.core.uuid import generate_uuid7


class TenantType(str, Enum):
    PROVIDER_OWNER = "PROVIDER_OWNER"
    NEUTRAL_OPERATOR = "NEUTRAL_OPERATOR"


class TenantVLANAllocationBase(BaseModel):
    olt_id: str = Field(..., description="ID da OLT onde a VLAN está autorizada")
    vlan_id: int = Field(..., ge=1, le=4094, description="ID numérico da VLAN IEEE 802.1Q")
    description: Optional[str] = Field(None, max_length=128, description="Identificação da VLAN")


class TenantVLANAllocationCreate(TenantVLANAllocationBase):
    pass


class TenantVLANAllocationResponse(TenantVLANAllocationBase):
    id: str
    tenant_id: str
    created_at: datetime


class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, description="Nome do Inquilino / Operadora")
    type: TenantType = Field(default=TenantType.NEUTRAL_OPERATOR, description="Tipo da organização")
    is_active: bool = Field(default=True, description="Status de ativação")


class TenantResponse(BaseModel):
    id: str
    name: str
    type: TenantType
    is_active: bool
    created_at: datetime
    vlans: List[TenantVLANAllocationResponse] = []
