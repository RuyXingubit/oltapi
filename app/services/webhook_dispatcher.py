import json
import logging
import time
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks
import httpx

from app.core.webhook_signer import sign_payload
from app.models.webhook import WebhookDeliveryLog, WebhookPayload, WebhookSubscription
from app.storage.webhook_repository import WebhookRepository

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    """
    Despachante assíncrono de Webhooks com assinatura digital HMAC SHA-256.
    Garante entregas não-bloqueantes para ERPs com controle estrito de timeout.
    """

    def __init__(self, repo: WebhookRepository):
        self.repo = repo

    def send_webhook(
        self,
        subscription: WebhookSubscription,
        event: str,
        data: Dict[str, Any],
    ) -> WebhookDeliveryLog:
        """
        Executa uma tentativa síncrona/unária de entrega HTTP POST com assinatura HMAC.
        """
        payload = WebhookPayload(event=event, data=data)
        payload_json = payload.model_dump_json()
        payload_bytes = payload_json.encode("utf-8")
        signature = sign_payload(subscription.secret, payload_bytes)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OLTAPI-Webhook-Dispatcher/1.0",
            "X-OLTAPI-Signature": signature,
            "X-OLTAPI-Event": event,
            "X-OLTAPI-Delivery": payload.id,
            "X-OLTAPI-Timestamp": payload.timestamp.isoformat(),
        }

        start_time = time.perf_counter()
        status_code = None
        success = False
        error_msg = None

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.post(subscription.url, content=payload_bytes, headers=headers)
                status_code = response.status_code
                # Sucesso se o ERP respondeu 2xx
                success = 200 <= response.status_code < 300
                if not success:
                    error_msg = f"ERP respondeu HTTP {status_code}: {response.text[:200]}"
        except httpx.TimeoutException:
            error_msg = "Timeout (5.0s) excedido ao conectar ao ERP."
        except Exception as e:
            error_msg = f"Erro de conexão com o ERP: {str(e)}"

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        delivery_log = WebhookDeliveryLog(
            subscription_id=subscription.id,
            event=event,
            url=subscription.url,
            status_code=status_code,
            success=success,
            duration_ms=duration_ms,
            error_message=error_msg,
        )
        self.repo.add_delivery_log(delivery_log)

        if success:
            logger.info(f"Webhook '{event}' entregue com sucesso para {subscription.url} ({duration_ms}ms).")
        else:
            logger.warning(f"Falha ao entregar webhook '{event}' para {subscription.url}: {error_msg}")

        return delivery_log

    def dispatch(
        self,
        event: str,
        data: Dict[str, Any],
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> List[str]:
        """
        Localiza assinaturas ativas para o evento e despacha via BackgroundTasks (ou síncrono).
        Retorna a lista de IDs de assinaturas acionadas.
        """
        active_subs = self.repo.list_all(active_only=True)
        matched_sub_ids: List[str] = []

        for sub in active_subs:
            # Compatível se escuta wildcard '*' ou o evento específico
            if "*" in sub.events or event in sub.events:
                matched_sub_ids.append(sub.id)
                if background_tasks:
                    background_tasks.add_task(self.send_webhook, sub, event, data)
                else:
                    self.send_webhook(sub, event, data)

        return matched_sub_ids
