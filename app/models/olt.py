from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from app.core.uuid import generate_uuid7


class OLTVendor(str, Enum):
    INTELBRAS = "intelbras"
    HUAWEI = "huawei"
    FIBERHOME = "fiberhome"
    VSOL = "vsol"
    PARKS = "parks"


class OLTProtocol(str, Enum):
    SSH = "ssh"
    TELNET = "telnet"


class OLTCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, description="Nome de identificação da OLT")
    vendor: OLTVendor
    model: str = Field(..., min_length=1, max_length=32, description="Ex: 8820, G16, MA5800-X7")
    host: str = Field(..., description="Endereço IP ou hostname de gerência da OLT")
    port: int = Field(default=22, ge=1, le=65535)
    protocol: OLTProtocol = Field(default=OLTProtocol.SSH)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class OLTInDB(BaseModel):
    id: str = Field(default_factory=generate_uuid7)
    name: str
    vendor: OLTVendor
    model: str
    host: str
    port: int
    protocol: OLTProtocol
    username: str
    password: str  # Armazenada internamente para conexão
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OLTResponse(BaseModel):
    id: str
    name: str
    vendor: OLTVendor
    model: str
    host: str
    port: int
    protocol: OLTProtocol
    created_at: datetime


class OLTConfigResponse(BaseModel):
    olt_id: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    config_text: str
