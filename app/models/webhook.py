from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.uuid import generate_uuid7
from app.models.hateoas import Link


class WebhookSubscription(BaseModel):
    id: str = Field(default_factory=generate_uuid7, description="Identificador único da assinatura UUIDv7")
    url: str = Field(..., description="URL de endpoint HTTP/HTTPS do ERP que receberá o evento")
    secret: str = Field(..., description="Chave secreta compartilhada para cálculo do HMAC SHA-256")
    events: List[str] = Field(default_factory=lambda: ["*"], description="Lista de eventos inscritos (ex: ['onu.reconciled', 'onu.detected'] ou ['*'])")
    is_active: bool = Field(default=True, description="Se a assinatura está ativa e recebendo despachos")
    description: Optional[str] = Field(default=None, description="Identificação do ERP de destino (ex: 'IXC Soft Matriz')")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")

    model_config = {"populate_by_name": True}


class WebhookCreateRequest(BaseModel):
    url: str = Field(..., description="URL de destino do webhook no ERP (ex: https://erp.provedor.com.br/api/webhooks/oltapi)")
    secret: Optional[str] = Field(default=None, description="Chave secreta para assinatura HMAC (opcional, gerada automaticamente se omitida)")
    events: Optional[List[str]] = Field(default_factory=lambda: ["*"], description="Eventos desejados (default: ['*'])")
    is_active: Optional[bool] = Field(default=True, description="Ativar webhook imediatamente")
    description: Optional[str] = Field(default=None, description="Descrição amigável do sistema receptor")


class WebhookDeliveryLog(BaseModel):
    id: str = Field(default_factory=generate_uuid7, description="ID único da entrega UUIDv7")
    subscription_id: str
    event: str
    url: str
    status_code: Optional[int] = None
    success: bool
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WebhookPayload(BaseModel):
    id: str = Field(default_factory=generate_uuid7, description="ID do evento UUIDv7 para idempotência no ERP")
    event: str = Field(..., description="Nome do evento (ex: onu.reconciled, onu.detected, webhook.ping)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = Field(default_factory=dict, description="Dados estruturados do evento de telecom")
