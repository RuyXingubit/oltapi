from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_webhook_dispatcher, get_webhook_repo, require_api_key
from app.core.webhook_signer import generate_webhook_secret
from app.models.hateoas import Link
from app.models.webhook import (
    WebhookCreateRequest,
    WebhookDeliveryLog,
    WebhookSubscription,
)
from app.services.webhook_dispatcher import WebhookDispatcher
from app.storage.webhook_repository import WebhookRepository

router = APIRouter(prefix="/webhooks", tags=["Webhooks & Notificações ERP"], dependencies=[Depends(require_api_key)])


@router.get("", response_model=List[WebhookSubscription])
def list_webhooks(
    active_only: bool = Query(default=False, description="Listar apenas webhooks ativos"),
    repo: WebhookRepository = Depends(get_webhook_repo),
):
    """Lista todas as assinaturas de webhook cadastradas no OLTAPI."""
    subs = repo.list_all(active_only=active_only)
    for sub in subs:
        sub.links = {
            "self": Link(
                href=f"/api/v1/webhooks/{sub.id}",
                method="GET",
                description="Consultar detalhes desta assinatura",
            ),
            "ping": Link(
                href=f"/api/v1/webhooks/{sub.id}/ping",
                method="POST",
                description="Testar conectividade e assinatura HMAC com o ERP",
            ),
            "deliveries": Link(
                href=f"/api/v1/webhooks/deliveries?subscription_id={sub.id}",
                method="GET",
                description="Ver histórico de entregas deste webhook",
            ),
        }
    return subs


@router.get("/deliveries", response_model=List[WebhookDeliveryLog])
def list_deliveries(
    subscription_id: Optional[str] = Query(default=None, description="Filtrar por ID de assinatura"),
    limit: int = Query(default=50, ge=1, le=200, description="Limite de registros retornados"),
    repo: WebhookRepository = Depends(get_webhook_repo),
):
    """Consulta o histórico e logs de auditoria das tentativas de entrega de webhooks."""
    return repo.list_deliveries(subscription_id=subscription_id, limit=limit)


@router.post("", response_model=WebhookSubscription, status_code=status.HTTP_201_CREATED)
def create_webhook(
    req: WebhookCreateRequest,
    response: Response,
    repo: WebhookRepository = Depends(get_webhook_repo),
):
    """Cadastra um novo webhook para o ERP receber notificações em tempo real assinadas com HMAC SHA-256."""
    secret = req.secret or generate_webhook_secret()
    sub = WebhookSubscription(
        url=str(req.url),
        secret=secret,
        events=req.events or ["*"],
        is_active=True if req.is_active is None else req.is_active,
        description=req.description,
    )
    saved = repo.create(sub)
    response.headers["Location"] = f"/api/v1/webhooks/{saved.id}"
    saved.links = {
        "self": Link(
            href=f"/api/v1/webhooks/{saved.id}",
            method="GET",
            description="Consultar detalhes da assinatura",
        ),
        "ping": Link(
            href=f"/api/v1/webhooks/{saved.id}/ping",
            method="POST",
            description="Testar conectividade e assinatura HMAC com o ERP",
        ),
    }
    return saved


@router.get("/{subscription_id}", response_model=WebhookSubscription)
def get_webhook(
    subscription_id: str,
    repo: WebhookRepository = Depends(get_webhook_repo),
):
    """Consulta uma assinatura de webhook pelo ID."""
    sub = repo.get_by_id(subscription_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Webhook '{subscription_id}' não encontrado.")

    sub.links = {
        "self": Link(
            href=f"/api/v1/webhooks/{sub.id}",
            method="GET",
            description="Consultar detalhes da assinatura",
        ),
        "ping": Link(
            href=f"/api/v1/webhooks/{sub.id}/ping",
            method="POST",
            description="Testar conectividade e assinatura HMAC com o ERP",
        ),
        "deliveries": Link(
            href=f"/api/v1/webhooks/deliveries?subscription_id={sub.id}",
            method="GET",
            description="Ver histórico de entregas deste webhook",
        ),
    }
    return sub


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    subscription_id: str,
    repo: WebhookRepository = Depends(get_webhook_repo),
):
    """Remove uma assinatura de webhook."""
    deleted = repo.delete(subscription_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Webhook '{subscription_id}' não encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{subscription_id}/ping", response_model=WebhookDeliveryLog)
def ping_webhook(
    subscription_id: str,
    repo: WebhookRepository = Depends(get_webhook_repo),
    dispatcher: WebhookDispatcher = Depends(get_webhook_dispatcher),
):
    """Dispara uma mensagem de teste (ping) com assinatura HMAC SHA-256 para validar o endpoint do ERP."""
    sub = repo.get_by_id(subscription_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Webhook '{subscription_id}' não encontrado.")

    ping_data = {
        "message": "Ping de validação de conectividade OLTAPI",
        "subscription_id": sub.id,
        "subscription_description": sub.description,
    }
    return dispatcher.send_webhook(sub, "webhook.ping", ping_data)
