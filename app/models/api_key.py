from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, description="Nome identificador da chave (ex: ERP IXC)")
    scopes: List[str] = Field(..., min_length=1, description="Lista de escopos granulares permitidos")
    expires_in_days: Optional[int] = Field(None, ge=1, le=3650, description="Validade em dias (opcional)")


class APIKeyCreatedResponse(BaseModel):
    id: str
    name: str
    key: str = Field(..., description="Chave de API em texto puro. ATENÇÃO: exibida apenas uma vez!")
    key_prefix: str
    scopes: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None


class APIKeyResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    name: str
    key_prefix: str
    scopes: List[str]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
