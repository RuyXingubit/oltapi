from datetime import datetime, timezone
from typing import Dict, Optional
from pydantic import BaseModel, Field

from app.core.uuid import generate_uuid7
from app.models.hateoas import Link


class ACSServerConfigCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, description="Nome do servidor ACS (ex: GenieACS Principal)")
    nbi_url: str = Field(..., description="URL da Northbound Interface REST do ACS (ex: http://10.0.0.50:7557)")
    username: Optional[str] = Field(default=None, max_length=64, description="Usuário de autenticação NBI")
    password: Optional[str] = Field(default=None, max_length=128, description="Senha NBI (cifrada em repouso via Fernet AES)")
    cwmp_inform_url: Optional[str] = Field(default=None, description="URL CWMP informada às ONUs (ex: http://10.0.0.50:7547)")
    is_active: bool = Field(default=True, description="Define se este servidor ACS está ativo")


class ACSServerConfigItem(BaseModel):
    id: str = Field(default_factory=generate_uuid7, description="Identificador único UUIDv7")
    name: str
    nbi_url: str
    username: Optional[str] = None
    cwmp_inform_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class ACSConnectionTestResponse(BaseModel):
    server_id: str
    server_name: str
    nbi_url: str
    reachable: bool
    status_code: Optional[int] = None
    message: str


class TR069WiFiConfigRequest(BaseModel):
    ssid_24g: Optional[str] = Field(default=None, min_length=1, max_length=32, description="SSID da rede Wi-Fi 2.4GHz")
    password_24g: Optional[str] = Field(default=None, min_length=8, max_length=64, description="Senha WPA2/WPA3 2.4GHz")
    channel_24g: Optional[str] = Field(default="Auto", description="Canal 2.4GHz (Auto ou 1..13)")
    ssid_5g: Optional[str] = Field(default=None, min_length=1, max_length=32, description="SSID da rede Wi-Fi 5GHz")
    password_5g: Optional[str] = Field(default=None, min_length=8, max_length=64, description="Senha WPA2/WPA3 5GHz")
    channel_5g: Optional[str] = Field(default="Auto", description="Canal 5GHz (Auto ou 36..165)")


class TR069WanConfigRequest(BaseModel):
    mode: str = Field(..., description="Modo WAN: pppoe, dhcp, bridge, static")
    pppoe_username: Optional[str] = Field(default=None, max_length=64, description="Usuário PPPoE do assinante")
    pppoe_password: Optional[str] = Field(default=None, max_length=64, description="Senha PPPoE do assinante")
    vlan_id: Optional[int] = Field(default=None, ge=1, le=4094, description="VLAN WAN TR-069")
    ip_version: str = Field(default="dual_stack", description="Pilha IP: ipv4, ipv6, dual_stack")


class TR069FirmwarePushRequest(BaseModel):
    firmware_filename: str = Field(..., min_length=3, max_length=128, description="Nome da imagem de firmware no servidor ACS")
    file_type: str = Field(default="1 Firmware Upgrade Image", description="Tipo de arquivo CWMP")


class TR069DeviceSummary(BaseModel):
    serial: str
    acs_device_id: Optional[str] = None
    registered_in_acs: bool = False
    acs_server_name: Optional[str] = None
    last_inform: Optional[str] = None
    software_version: Optional[str] = None
    hardware_version: Optional[str] = None
    wan_mode: Optional[str] = None
    wan_ip: Optional[str] = None
    pppoe_username: Optional[str] = None
    ssid_24g: Optional[str] = None
    ssid_5g: Optional[str] = None
    connected_hosts_count: int = 0
    message: Optional[str] = None
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class TR069ActionResponse(BaseModel):
    serial: str
    acs_device_id: Optional[str] = None
    task_queued: bool
    action: str
    message: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}
