from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.uuid import generate_uuid7
from app.models.hateoas import Link


class OLTVendor(str, Enum):
    INTELBRAS = "intelbras"
    HUAWEI = "huawei"
    FIBERHOME = "fiberhome"
    VSOL = "vsol"
    ZTE = "zte"
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
    snmp_community: Optional[str] = Field(default="public", description="Comunidade SNMP v2c para telemetria de chassi")
    snmp_port: Optional[int] = Field(default=161, ge=1, le=65535, description="Porta UDP do serviço SNMP")
    snmp_version: Optional[str] = Field(default="v2c", description="Versão do protocolo SNMP (v2c)")


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
    snmp_community: Optional[str] = "public"
    snmp_port: Optional[int] = 161
    snmp_version: Optional[str] = "v2c"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OLTResponse(BaseModel):
    id: str
    name: str
    vendor: OLTVendor
    model: str
    host: str
    port: int
    protocol: OLTProtocol
    snmp_community: Optional[str] = "public"
    snmp_port: Optional[int] = 161
    snmp_version: Optional[str] = "v2c"
    status: Optional[str] = Field(default="online", description="Status de conectividade (online, unreachable)")
    connection_message: Optional[str] = Field(default=None, description="Diagnóstico de conectividade inicial")
    created_at: datetime
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class OLTCredentialsResponse(BaseModel):
    olt_id: str
    olt_name: str
    host: str
    port: int
    protocol: str
    username: str
    password: str
    revealed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    audit_warning: str = Field(
        default="A visualização de credenciais de hardware foi registrada na trilha de auditoria de segurança.",
        description="Aviso de conformidade e auditoria",
    )


class ConnectionTestResult(BaseModel):
    olt_id: str
    host: str
    port: int
    reachable: bool
    latency_ms: Optional[float] = None
    message: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class OLTConfigResponse(BaseModel):
    olt_id: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    config_text: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class OLTPortStatusItem(BaseModel):
    port_id: str = Field(..., description="Identificador da porta (ex: gpon 0/1/1 ou xg 0/0/1)")
    port_type: str = Field(..., description="Tipo da porta: gpon, epon, ge, xg, 100ge")
    admin_state: str = Field(default="enabled", description="Estado administrativo: enabled, disabled")
    oper_status: str = Field(..., description="Estado operacional: up, down, loss_of_signal")
    onu_count: int = Field(default=0, description="Quantidade de ONUs ativas na porta")
    onu_capacity: int = Field(default=128, description="Capacidade máxima de ONUs na porta")
    speed_duplex: Optional[str] = Field(default=None, description="Velocidade e modo para portas uplink (ex: 10Gbps Full Duplex)")
    details: Optional[str] = Field(default=None, description="Informações adicionais do laser/SFP")


class OLTXRayResponse(BaseModel):
    olt_id: str
    olt_name: str
    vendor: OLTVendor
    model: str
    host: str
    uptime_seconds: int = Field(..., description="Tempo de uptime da OLT em segundos")
    uptime_human: str = Field(..., description="Tempo de uptime legível (ex: 142 dias, 8 horas, 12 min)")
    firmware_version: str = Field(..., description="Versão do software/firmware em execução")
    cpu_usage_pct: Optional[float] = Field(default=None, description="Percentual de uso de CPU")
    memory_usage_pct: Optional[float] = Field(default=None, description="Percentual de uso de memória")
    temperature_celsius: Optional[float] = Field(default=None, description="Temperatura média das placas em °C")
    ports: List[OLTPortStatusItem] = Field(default_factory=list, description="Lista completa de todas as portas PON e Uplink e seus estados")
    total_onus_detected: int = Field(default=0, description="Total de ONUs detectadas no chassi físico")
    total_vlans_detected: int = Field(default=0, description="Total de VLANs configuradas na OLT")
    vlans: List[int] = Field(default_factory=list, description="Lista de IDs de VLANs detectadas")
    running_config_preview: str = Field(default="", description="Prévia do arquivo de configuração vivo")
    is_onboarded: bool = Field(default=False, description="Se a OLT já passou pelo processo de sync / onboarding")
    baseline_backup_id: Optional[str] = Field(default=None, description="ID do backup baseline v0 se já sincronizado")
    snmp_active: bool = Field(default=False, description="Indica se a telemetria SNMP respondeu via UDP 161")
    snmp_status: str = Field(default="inactive", description="Status SNMP: active, unreachable, cipher_detected, not_configured")
    snmp_community: Optional[str] = Field(default=None, description="Comunidade SNMP em uso ou auto-descoberta")
    snmp_message: Optional[str] = Field(default=None, description="Diagnóstico detalhado da telemetria SNMP")
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


# Alias formal para resposta de telemetria de chassi
OLTTelemetryResponse = OLTXRayResponse


class SNMPTestRequest(BaseModel):
    community: Optional[str] = Field(default=None, description="Comunidade SNMP a testar. Se omitida, usa a cadastrada na OLT")
    port: Optional[int] = Field(default=161, ge=1, le=65535, description="Porta UDP do agente SNMP (padrão 161)")
    save_if_successful: bool = Field(default=False, description="Se True e o teste for bem-sucedido, adota esta comunidade no cadastro da OLT")


class SNMPTestResponse(BaseModel):
    olt_id: str
    host: str
    port: int
    community: str
    reachable: bool
    latency_ms: Optional[float] = None
    uptime_seconds: Optional[int] = None
    saved_to_db: bool = False
    message: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class SNMPConfigureRequest(BaseModel):
    community: str = Field(..., min_length=3, max_length=64, description="Nova comunidade SNMP somente-leitura (RO) a ser gravada na OLT")
    port: Optional[int] = Field(default=161, ge=1, le=65535, description="Porta UDP do agente SNMP")


class SNMPConfigureResponse(BaseModel):
    olt_id: str
    host: str
    community: str
    configured_in_cli: bool
    saved_to_flash: bool
    tested_ok: bool
    uptime_seconds: Optional[int] = None
    message: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class OLTOnboardRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, description="Nome identificador da OLT")
    host: str = Field(..., min_length=4, max_length=255, description="Endereço IP ou hostname da OLT")
    username: str = Field(..., min_length=1, max_length=64, description="Usuário de acesso à CLI")
    password: str = Field(..., min_length=1, max_length=128, description="Senha de acesso à CLI")
    custom_port: Optional[int] = Field(default=None, ge=1, le=65535, description="Porta de acesso customizada (opcional)")


class OnboardingStepItem(BaseModel):
    step_key: str = Field(..., description="Chave identificadora da etapa")
    title: str = Field(..., description="Título da etapa")
    status: str = Field(..., description="Estado: pending, running, success, warning, error")
    details: Optional[str] = Field(default=None, description="Mensagem de detalhe ou diagnóstico")


class OLTOnboardResponse(BaseModel):
    olt_id: str
    name: str
    vendor: OLTVendor
    model: str
    host: str
    port: int
    protocol: OLTProtocol
    baseline_backup_id: str
    snmp_community: str
    snmp_active: bool
    total_ports: int
    active_ports: int
    total_onus_detected: int
    new_onus_registered: int
    firmware_version: Optional[str] = None
    uptime_human: Optional[str] = None
    steps: List[OnboardingStepItem] = Field(default_factory=list, description="Histórico de execução do pipeline")
    message: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


# =============================================================================
# Modelos para o Wizard de Onboarding & Comissionamento Dinâmico (V-SOL / Multi-Vendor)
# =============================================================================

class ManagementAccessScenario(str, Enum):
    AUX_ONLY = "aux_only"
    AUX_WITH_INBAND = "aux_with_inband"
    INBAND_ACTIVE = "inband_active"


class VLANServicePurpose(str, Enum):
    PPPOE_ROUTER = "pppoe_router"
    PPPOE_BRIDGE = "pppoe_bridge"
    IPOE = "ipoe"
    REDE_NEUTRA = "rede_neutra"
    LAN_TO_LAN = "lan_to_lan"


class InBandManagementConfig(BaseModel):
    vlan_id: int = Field(default=2, ge=1, le=4094, description="ID da VLAN de gerência in-band")
    uplink_port: str = Field(default="ge 0/1", description="Porta física de uplink para a gerência (ex: ge 0/1)")
    ip_cidr: str = Field(..., description="Endereço IP com máscara CIDR para a SVI (ex: 172.16.251.60/24)")
    gateway: str = Field(..., description="Gateway padrão da rede de gerência (ex: 172.16.251.1)")
    tagged: bool = Field(default=True, description="Se a VLAN deve ser tagged na porta de uplink")
    name: Optional[str] = Field(default="VLAN2_GERENCIA", description="Descrição/nome da VLAN de gerência")


class VLANServiceItem(BaseModel):
    vlan_id: int = Field(..., ge=1, le=4094, description="ID da VLAN de serviço")
    name: str = Field(..., min_length=1, max_length=64, description="Nome identificador da VLAN")
    purpose: VLANServicePurpose = Field(..., description="Propósito operacional do serviço")
    uplink_port: str = Field(default="ge 0/1", description="Porta de saída uplink (ex: ge 0/1 ou ge 0/2 para rede neutra)")
    tagged: bool = Field(default=True, description="Se a VLAN sai tagged na porta de uplink")
    test_port: Optional[str] = Field(default=None, description="Porta física de bancada para saída untagged (ex: ge 0/4)")


class BandwidthPolicyType(str, Enum):
    TRANSPARENT_1G = "transparent_1g"
    CUSTOM_LIMITS = "custom_limits"


class BandwidthQoSPolicy(BaseModel):
    policy_type: BandwidthPolicyType = Field(default=BandwidthPolicyType.TRANSPARENT_1G)
    upstream_kbps: int = Field(default=1024000, ge=1024, description="Limite de upload no DBA Profile (kbps)")
    downstream_kbps: int = Field(default=1024000, ge=1024, description="Limite de download no GEM Port Traffic-Limit (kbps)")


class OLTInspectRequest(BaseModel):
    host: str = Field(..., min_length=4, max_length=255, description="Endereço IP ou hostname da OLT")
    username: str = Field(..., min_length=1, max_length=64, description="Usuário de acesso à CLI")
    password: str = Field(..., min_length=1, max_length=128, description="Senha de acesso à CLI")
    custom_port: Optional[int] = Field(default=None, ge=1, le=65535, description="Porta customizada de conexão")


class ExistingSVIItem(BaseModel):
    vlan_id: int
    name: Optional[str] = None
    ip_cidr: Optional[str] = None
    tagged_ports: List[str] = Field(default_factory=list)
    untagged_ports: List[str] = Field(default_factory=list)


class OLTInspectResponse(BaseModel):
    host: str
    vendor: OLTVendor
    model: str
    access_scenario: ManagementAccessScenario
    aux_ip: Optional[str] = None
    existing_svis: List[ExistingSVIItem] = Field(default_factory=list)
    existing_vlans: List[int] = Field(default_factory=list)
    gateway: Optional[str] = None
    total_onus_detected: int = 0
    prompt_message: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class OLTWizardOnboardRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, description="Nome de identificação da OLT")
    host: str = Field(..., min_length=4, max_length=255, description="Endereço IP ou hostname de acesso")
    username: str = Field(..., min_length=1, max_length=64, description="Usuário de acesso à CLI")
    password: str = Field(..., min_length=1, max_length=128, description="Senha de acesso à CLI")
    custom_port: Optional[int] = Field(default=None, ge=1, le=65535, description="Porta customizada de conexão")
    inband_config: Optional[InBandManagementConfig] = Field(default=None, description="Configuração de gerência in-band opcional")
    services: List[VLANServiceItem] = Field(default_factory=list, description="Lista de VLANs de serviço com propósitos")
    qos_policy: BandwidthQoSPolicy = Field(default_factory=BandwidthQoSPolicy, description="Política de controle de banda")

