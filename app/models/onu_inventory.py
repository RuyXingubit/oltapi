from datetime import datetime, timezone
from typing import Dict, Optional
from pydantic import BaseModel, Field

from app.core.uuid import generate_uuid7
from app.models.hateoas import Link


class ONUInventoryItem(BaseModel):
    id: str = Field(default_factory=generate_uuid7, description="Identificador único UUIDv7")
    serial: str = Field(..., description="Serial alfanumérico da ONU (chave de hardware imutável)")
    contract_id: Optional[str] = Field(default=None, description="Número do contrato no ERP")
    subscriber_name: Optional[str] = Field(default=None, description="Nome do assinante")
    contract_status: str = Field(
        default="ACTIVE",
        description="Estado do contrato no ERP: ACTIVE, SUSPENDED, CANCELLED, IN_STOCK",
    )
    vlan: Optional[int] = Field(default=None, ge=1, le=4094, description="VLAN de serviço")
    profile: str = Field(default="DEFAULT", description="Perfil de linha/tráfego")
    description: Optional[str] = Field(default=None, description="Descrição ou anotação do cliente")
    latitude: Optional[float] = Field(default=None, description="Latitude geográfica da instalação da ONU")
    longitude: Optional[float] = Field(default=None, description="Longitude geográfica da instalação da ONU")
    current_olt_id: Optional[str] = Field(default=None, description="ID da OLT onde a ONU está fixada")
    current_port: Optional[str] = Field(default=None, description="Porta PON atual")
    current_onu_id: Optional[int] = Field(default=None, description="Índice ONU ID na porta atual")
    circuit_id: Optional[str] = Field(default=None, description="Identificador de circuito físico Broadband Forum TR-101")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class ONUMigrationEvent(BaseModel):
    id: str = Field(default_factory=generate_uuid7, description="Identificador único do evento UUIDv7")
    serial: str
    contract_id: Optional[str] = None
    subscriber_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = Field(description="Motivo da migração: field_event_auto_reconciliation, address_change, fiber_swap_correction, pop_cutover")
    from_olt_id: Optional[str] = None
    from_olt_name: Optional[str] = None
    from_port: Optional[str] = None
    from_onu_id: Optional[int] = None
    from_circuit_id: Optional[str] = None
    to_olt_id: str
    to_olt_name: str
    to_port: str
    to_onu_id: int
    to_circuit_id: str
    status: str = "success"
    details: Optional[str] = None
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class RegisterONUInventoryRequest(BaseModel):
    serial: str = Field(..., description="Serial alfanumérico da ONU")
    olt_id: Optional[str] = Field(default=None, description="ID da OLT")
    current_olt_id: Optional[str] = Field(default=None, description="Alias para olt_id")
    port: Optional[str] = Field(default=None, description="Porta PON")
    current_port: Optional[str] = Field(default=None, description="Alias para port")
    onu_id: Optional[int] = Field(default=None, description="Índice ONU ID")
    current_onu_id: Optional[int] = Field(default=None, description="Alias para onu_id")
    vlan: Optional[int] = Field(default=None, ge=1, le=4094, description="VLAN de serviço")
    profile: Optional[str] = Field(default="DEFAULT", description="Perfil de tráfego")
    contract_id: Optional[str] = Field(default=None, description="Código do contrato no ERP")
    subscriber_name: Optional[str] = Field(default=None, description="Nome do assinante")
    contract_status: Optional[str] = Field(default="ACTIVE", description="ACTIVE, SUSPENDED, CANCELLED, IN_STOCK")
    description: Optional[str] = Field(default=None, description="Descrição ou notas de campo")
    notes: Optional[str] = Field(default=None, description="Alias para description")
    latitude: Optional[float] = Field(default=None, description="Latitude geográfica")
    longitude: Optional[float] = Field(default=None, description="Longitude geográfica")


class ReconcileFieldEventRequest(BaseModel):
    serial: str = Field(..., description="Serial alfanumérico detectado em campo")
    detected_olt_id: str = Field(..., description="ID da OLT onde a ONU acendeu no autofind")
    detected_port: str = Field(..., description="Porta PON onde a ONU acendeu")
    detected_onu_id: Optional[int] = Field(default=None, description="Índice numérico da ONU (opcional)")
    latitude: Optional[float] = Field(default=None, description="Latitude geográfica atualizada se houver")
    longitude: Optional[float] = Field(default=None, description="Longitude geográfica atualizada se houver")
    reason: Optional[str] = Field(default="field_event_auto_reconciliation", description="Motivo do evento")


class ReconcileFieldEventResponse(BaseModel):
    success: bool
    action_taken: str = Field(description="reconciled_intra_olt, reconciled_cross_olt, rejected_in_stock_onu, onu_not_found")
    serial: str
    contract_id: Optional[str] = None
    subscriber_name: Optional[str] = None
    from_olt_id: Optional[str] = None
    to_olt_id: Optional[str] = None
    from_port: Optional[str] = None
    to_port: Optional[str] = None
    old_olt_id: Optional[str] = None
    new_olt_id: Optional[str] = None
    old_port: Optional[str] = None
    new_port: Optional[str] = None
    old_onu_id: Optional[int] = None
    new_onu_id: Optional[int] = None
    old_circuit_id: Optional[str] = None
    new_circuit_id: Optional[str] = None
    message: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class UpdateONUInventoryRequest(BaseModel):
    subscriber_name: Optional[str] = Field(default=None, description="Nome do assinante")
    description: Optional[str] = Field(default=None, description="Descrição ou anotação do cliente")
    circuit_id: Optional[str] = Field(default=None, description="Identificador do circuito TR-101")
    vlan: Optional[int] = Field(default=None, ge=1, le=4094, description="VLAN de serviço")
    profile: Optional[str] = Field(default=None, description="Perfil de linha/tráfego")
