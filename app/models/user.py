from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    NOC = "NOC"
    FIELD_TECH = "FIELD_TECH"
    TENANT_ADMIN = "TENANT_ADMIN"
    TENANT_TECH = "TENANT_TECH"


class UserCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128, description="Nome do usuário ou técnico")
    email: str = Field(..., min_length=5, max_length=128, description="Email de login (único)")
    password: str = Field(..., min_length=8, max_length=128, description="Senha de acesso")
    role: UserRole = Field(..., description="Perfil de acesso (RBAC)")
    tenant_id: Optional[str] = Field(None, description="ID do Inquilino/Organização (obrigatório se não for SUPER_ADMIN)")
    allowed_olt_ids: List[str] = Field(default=[], description="Lista de IDs de OLTs autorizadas (ex: VTX)")


class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=128)
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    allowed_olt_ids: Optional[List[str]] = None


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    email: str
    role: UserRole
    is_active: bool
    allowed_olt_ids: List[str] = []
    created_at: datetime


class UserLoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=128, description="Email cadastrado")
    password: str = Field(..., description="Senha de acesso")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    role: UserRole
    tenant_id: str


class UserProfileResponse(BaseModel):
    id: str
    tenant_id: str
    tenant_name: str
    tenant_type: str
    name: str
    email: str
    role: UserRole
    allowed_olt_ids: List[str] = []
    allowed_vlans: Dict[str, List[int]] = {}
