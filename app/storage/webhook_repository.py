import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.models.webhook import WebhookDeliveryLog, WebhookSubscription

logger = logging.getLogger(__name__)


class WebhookRepository:
    """
    Repositório de persistência atômica para assinaturas de webhooks de ERPs
    e logs de auditoria de entregas realizadas pelo OLTAPI.
    """

    def __init__(
        self,
        subscriptions_file: Optional[Path] = None,
        deliveries_file: Optional[Path] = None,
    ):
        self.subscriptions_file = subscriptions_file or (settings.DATA_DIR / "webhooks.json")
        self.deliveries_file = deliveries_file or (settings.DATA_DIR / "webhook_deliveries.json")
        self._subscriptions: Dict[str, WebhookSubscription] = {}
        self._deliveries: List[WebhookDeliveryLog] = []
        self._load()

    def _load(self):
        if self.subscriptions_file.exists():
            try:
                with open(self.subscriptions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        sub = WebhookSubscription(**item)
                        self._subscriptions[sub.id] = sub
            except Exception as e:
                logger.error(f"Erro ao carregar webhooks de {self.subscriptions_file}: {e}")

        if self.deliveries_file.exists():
            try:
                with open(self.deliveries_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        log = WebhookDeliveryLog(**item)
                        self._deliveries.append(log)
            except Exception as e:
                logger.error(f"Erro ao carregar logs de entrega de webhooks de {self.deliveries_file}: {e}")

    def _save_subscriptions(self):
        try:
            with open(self.subscriptions_file, "w", encoding="utf-8") as f:
                data = [sub.model_dump(mode="json") for sub in self._subscriptions.values()]
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar assinaturas de webhooks em {self.subscriptions_file}: {e}")

    def _save_deliveries(self):
        try:
            with open(self.deliveries_file, "w", encoding="utf-8") as f:
                # Mantém apenas as últimas 200 entregas em disco
                data = [log.model_dump(mode="json") for log in self._deliveries[-200:]]
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar logs de entrega de webhooks em {self.deliveries_file}: {e}")

    # -----------------------------------------------------------------------
    # Assinaturas
    # -----------------------------------------------------------------------

    def get_by_id(self, subscription_id: str) -> Optional[WebhookSubscription]:
        return self._subscriptions.get(subscription_id)

    def list_all(self, active_only: bool = False) -> List[WebhookSubscription]:
        subs = list(self._subscriptions.values())
        if active_only:
            subs = [s for s in subs if s.is_active]
        return subs

    def create(self, subscription: WebhookSubscription) -> WebhookSubscription:
        self._subscriptions[subscription.id] = subscription
        self._save_subscriptions()
        return subscription

    def update(self, subscription: WebhookSubscription) -> WebhookSubscription:
        subscription.updated_at = datetime.now(timezone.utc)
        self._subscriptions[subscription.id] = subscription
        self._save_subscriptions()
        return subscription

    def delete(self, subscription_id: str) -> bool:
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            self._save_subscriptions()
            return True
        return False

    # -----------------------------------------------------------------------
    # Entregas / Logs
    # -----------------------------------------------------------------------

    def add_delivery_log(self, log: WebhookDeliveryLog) -> WebhookDeliveryLog:
        self._deliveries.append(log)
        self._save_deliveries()
        return log

    def list_deliveries(self, subscription_id: Optional[str] = None, limit: int = 50) -> List[WebhookDeliveryLog]:
        logs = list(reversed(self._deliveries))
        if subscription_id:
            logs = [l for l in logs if l.subscription_id == subscription_id]
        return logs[:limit]
