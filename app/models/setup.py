from typing import Optional
from pydantic import BaseModel, Field


class SetupStatusResponse(BaseModel):
    is_configured: bool = Field(..., description="Indica se o sistema já teve seu setup inicial concluído")
    provider_name: Optional[str] = Field(None, description="Nome do provedor cadastrado se já configurado")
    message: str = Field(..., description="Mensagem de status do setup")


class SetupInitRequest(BaseModel):
    provider_name: str = Field(..., min_length=2, max_length=128, description="Nome / Razão Social da Empresa ou Provedor")
    admin_name: str = Field(..., min_length=2, max_length=128, description="Nome completo do Administrador Geral")
    admin_email: str = Field(..., min_length=5, max_length=128, description="E-mail de acesso do Administrador")
    admin_password: str = Field(..., min_length=8, max_length=128, description="Senha de acesso do Administrador (mínimo 8 caracteres)")


class SetupInitResponse(BaseModel):
    status: str = "success"
    message: str
    tenant_id: str
    admin_user_id: str
    admin_email: str
