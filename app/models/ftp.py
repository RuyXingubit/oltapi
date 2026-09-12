from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.uuid import generate_uuid7
from app.models.hateoas import Link


class FTPServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="Nome identificador do servidor FTP")
    host: str = Field(..., min_length=1, max_length=128, description="IP ou Hostname do servidor FTP")
    port: int = Field(default=21, ge=1, le=65535, description="Porta de conexão FTP")
    username: str = Field(..., min_length=1, max_length=64, description="Usuário de autenticação FTP")
    base_path: str = Field(default="/", max_length=128, description="Caminho base no servidor FTP")
    is_global_default: bool = Field(default=False, description="Se True, todas as OLTs salvarão uma cópia aqui por padrão")
    is_active: bool = Field(default=True, description="Status de ativação do servidor")


class FTPServerCreate(FTPServerBase):
    password: str = Field(..., min_length=1, max_length=256, description="Senha do servidor FTP")


class FTPServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    host: Optional[str] = Field(None, min_length=1, max_length=128)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, min_length=1, max_length=64)
    password: Optional[str] = Field(None, min_length=1, max_length=256)
    base_path: Optional[str] = Field(None, max_length=128)
    is_global_default: Optional[bool] = None
    is_active: Optional[bool] = None


class FTPServerResponse(FTPServerBase):
    id: str = Field(default_factory=generate_uuid7, description="UUIDv7 identificador único")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True, "from_attributes": True}


class OLTFTPBindingRequest(BaseModel):
    ftp_server_ids: List[str] = Field(..., description="Lista de UUIDv7 dos servidores FTP a serem vinculados")


class OLTFTPDestinationResponse(BaseModel):
    olt_id: str
    specific_destinations: List[FTPServerResponse]
    global_destinations: List[FTPServerResponse]
    effective_destinations: List[FTPServerResponse]
