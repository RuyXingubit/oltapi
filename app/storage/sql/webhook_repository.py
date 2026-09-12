import json
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.uuid import generate_uuid7
from app.db.models import WebhookDeliveryModel, WebhookSubscriptionModel
from app.db.session import SessionLocal
from app.models.webhook import WebhookDeliveryLog, WebhookSubscription

logger = logging.getLogger(__name__)


class SQLWebhookRepository:
    """Repositório de Assinaturas e Entregas de Webhooks via SQLAlchemy."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def _to_sub(self, m: WebhookSubscriptionModel) -> WebhookSubscription:
        events_list = json.loads(m.events) if m.events.startswith("[") else [e.strip() for e in m.events.split(",")]
        return WebhookSubscription(
            id=m.id,
            url=m.url,
            secret=m.secret,
            events=events_list,
            is_active=m.is_active,
            description=m.description,
            created_at=m.created_at,
        )

    def _to_log(self, m: WebhookDeliveryModel) -> WebhookDeliveryLog:
        return WebhookDeliveryLog(
            id=m.id,
            subscription_id=m.subscription_id,
            event=m.event,
            url=m.url,
            status_code=m.status_code,
            success=m.success,
            duration_ms=m.duration_ms,
            error_message=m.error_message,
            timestamp=m.timestamp,
        )

    def get_by_id(self, subscription_id: str) -> Optional[WebhookSubscription]:
        with self.session_factory() as db:
            m = db.query(WebhookSubscriptionModel).filter(WebhookSubscriptionModel.id == subscription_id).first()
            return self._to_sub(m) if m else None

    def list_all(self, active_only: bool = False) -> List[WebhookSubscription]:
        with self.session_factory() as db:
            q = db.query(WebhookSubscriptionModel)
            if active_only:
                q = q.filter(WebhookSubscriptionModel.is_active.is_(True))
            models = q.order_by(WebhookSubscriptionModel.created_at.asc()).all()
            return [self._to_sub(m) for m in models]

    def create(self, subscription: WebhookSubscription) -> WebhookSubscription:
        with self.session_factory() as db:
            events_json = json.dumps(subscription.events)
            m = WebhookSubscriptionModel(
                id=subscription.id or generate_uuid7(),
                url=subscription.url,
                secret=subscription.secret,
                events=events_json,
                is_active=subscription.is_active,
                description=subscription.description,
                created_at=subscription.created_at,
            )
            db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_sub(m)

    def update(self, subscription: WebhookSubscription) -> WebhookSubscription:
        with self.session_factory() as db:
            m = db.query(WebhookSubscriptionModel).filter(WebhookSubscriptionModel.id == subscription.id).first()
            if m:
                m.url = subscription.url
                m.secret = subscription.secret
                m.events = json.dumps(subscription.events)
                m.is_active = subscription.is_active
                m.description = subscription.description
                db.commit()
                db.refresh(m)
                return self._to_sub(m)
            return subscription

    def delete(self, subscription_id: str) -> bool:
        with self.session_factory() as db:
            m = db.query(WebhookSubscriptionModel).filter(WebhookSubscriptionModel.id == subscription_id).first()
            if m:
                db.delete(m)
                db.commit()
                return True
            return False

    def add_delivery_log(self, log: WebhookDeliveryLog) -> WebhookDeliveryLog:
        with self.session_factory() as db:
            m = WebhookDeliveryModel(
                id=log.id or generate_uuid7(),
                subscription_id=log.subscription_id,
                event=log.event,
                url=log.url,
                status_code=log.status_code,
                success=log.success,
                duration_ms=log.duration_ms,
                error_message=log.error_message,
                timestamp=log.timestamp,
            )
            db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_log(m)

    def list_deliveries(self, subscription_id: Optional[str] = None, limit: int = 50) -> List[WebhookDeliveryLog]:
        with self.session_factory() as db:
            q = db.query(WebhookDeliveryModel)
            if subscription_id:
                q = q.filter(WebhookDeliveryModel.subscription_id == subscription_id)
            models = q.order_by(WebhookDeliveryModel.timestamp.desc()).limit(limit).all()
            return [self._to_log(m) for m in models]
