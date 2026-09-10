from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class BootstrapMode(str, Enum):
    SINGLE_VLAN = "single_vlan"
    VLAN_PER_PON = "vlan_per_pon"


class DefaultONUMode(str, Enum):
    ROUTER = "router"
    BRIDGE = "bridge"


class BootstrapRequest(BaseModel):
    mode: BootstrapMode = Field(
        default=BootstrapMode.SINGLE_VLAN,
        description="Modo de configuração: 'single_vlan' (mesma VLAN para todas as PONs) ou 'vlan_per_pon' (uma VLAN por porta PON)",
    )
    uplink_port: str = Field(
        default="1",
        description="Porta física do Uplink (ex: '1', '2' ou 'uplink 1')",
        json_schema_extra={"example": "1"},
    )
    vlan: Optional[int] = Field(
        default=100,
        ge=1,
        le=4094,
        description="VLAN dos clientes para modo 'single_vlan'",
        json_schema_extra={"example": 100},
    )
    vlan_per_pon: Optional[Dict[str, int]] = Field(
        default=None,
        description="Mapeamento de VLANs por porta PON para modo 'vlan_per_pon' (ex: {'1': 101, '2': 102, ...})",
        json_schema_extra={"example": {"1": 101, "2": 102, "3": 103, "4": 104, "5": 105, "6": 106, "7": 107, "8": 108}},
    )
    default_onu_mode: DefaultONUMode = Field(
        default=DefaultONUMode.ROUTER,
        description="Modo padrão de operação das ONUs do cliente ('router' ou 'bridge')",
    )
    force: bool = Field(
        default=False,
        description="Trava de segurança: confirma a aplicação em OLT mesmo que já existam configurações ativas",
    )


class BootstrapPreviewResponse(BaseModel):
    olt_id: str
    mode: BootstrapMode
    commands: List[str]
    script_text: str
    total_commands: int


class BootstrapApplyResponse(BaseModel):
    success: bool = True
    olt_id: str
    backup_id: str
    total_commands_executed: int
    message: str
