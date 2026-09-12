import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.uuid import generate_uuid7
from app.db.models import ONUInventoryModel, ONUMigrationHistoryModel
from app.db.session import SessionLocal
from app.models.onu_inventory import ONUInventoryItem, ONUMigrationEvent

logger = logging.getLogger(__name__)


class SQLONUInventoryRepository:
    """Repositório de Inventário de ONUs e Histórico do NOC via SQLAlchemy."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def _to_item(self, m: ONUInventoryModel) -> ONUInventoryItem:
        return ONUInventoryItem(
            id=m.id,
            serial=m.serial,
            contract_id=m.contract_id,
            subscriber_name=m.subscriber_name,
            contract_status=m.contract_status,
            current_olt_id=m.current_olt_id,
            current_port=m.current_port,
            current_onu_id=m.current_onu_id,
            circuit_id=m.circuit_id,
            vlan=m.vlan,
            profile=m.profile,
            latitude=m.latitude,
            longitude=m.longitude,
            description=m.description,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def _to_event(self, m: ONUMigrationHistoryModel) -> ONUMigrationEvent:
        return ONUMigrationEvent(
            id=m.id,
            serial=m.serial,
            contract_id=m.contract_id,
            subscriber_name=m.subscriber_name,
            reason=m.reason,
            from_olt_id=m.from_olt_id,
            from_olt_name=m.from_olt_name,
            from_port=m.from_port,
            from_onu_id=m.from_onu_id,
            from_circuit_id=m.from_circuit_id,
            to_olt_id=m.to_olt_id,
            to_olt_name=m.to_olt_name,
            to_port=m.to_port,
            to_onu_id=m.to_onu_id,
            to_circuit_id=m.to_circuit_id,
            status=m.status,
            details=m.details,
            timestamp=m.timestamp,
        )

    def get_by_serial(self, serial: str) -> Optional[ONUInventoryItem]:
        with self.session_factory() as db:
            m = db.query(ONUInventoryModel).filter(ONUInventoryModel.serial == serial).first()
            return self._to_item(m) if m else None

    def get_by_id(self, onu_id: str) -> Optional[ONUInventoryItem]:
        with self.session_factory() as db:
            m = db.query(ONUInventoryModel).filter(ONUInventoryModel.id == onu_id).first()
            return self._to_item(m) if m else None

    def upsert(self, item: ONUInventoryItem) -> ONUInventoryItem:
        with self.session_factory() as db:
            now = datetime.now(timezone.utc)
            item.updated_at = now
            m = db.query(ONUInventoryModel).filter(ONUInventoryModel.serial == item.serial).first()
            if m:
                m.contract_id = item.contract_id
                m.subscriber_name = item.subscriber_name
                m.contract_status = item.contract_status
                m.current_olt_id = item.current_olt_id
                m.current_port = item.current_port
                m.current_onu_id = item.current_onu_id
                m.circuit_id = item.circuit_id
                m.vlan = item.vlan
                m.profile = item.profile
                m.latitude = item.latitude
                m.longitude = item.longitude
                m.description = item.description
                m.updated_at = now
            else:
                m = ONUInventoryModel(
                    id=item.id or generate_uuid7(),
                    serial=item.serial,
                    contract_id=item.contract_id,
                    subscriber_name=item.subscriber_name,
                    contract_status=item.contract_status,
                    current_olt_id=item.current_olt_id,
                    current_port=item.current_port,
                    current_onu_id=item.current_onu_id,
                    circuit_id=item.circuit_id,
                    vlan=item.vlan,
                    profile=item.profile,
                    latitude=item.latitude,
                    longitude=item.longitude,
                    description=item.description,
                    created_at=item.created_at or now,
                    updated_at=now,
                )
                db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_item(m)

    def delete(self, serial: str) -> bool:
        with self.session_factory() as db:
            m = db.query(ONUInventoryModel).filter(ONUInventoryModel.serial == serial).first()
            if m:
                db.delete(m)
                db.commit()
                return True
            return False

    def list_all(
        self,
        olt_id: Optional[str] = None,
        port: Optional[str] = None,
        contract_status: Optional[str] = None,
        contract_id: Optional[str] = None,
    ) -> List[ONUInventoryItem]:
        with self.session_factory() as db:
            q = db.query(ONUInventoryModel)
            if olt_id:
                q = q.filter(ONUInventoryModel.current_olt_id == olt_id)
            if port:
                q = q.filter(ONUInventoryModel.current_port == port)
            if contract_status:
                q = q.filter(ONUInventoryModel.contract_status == contract_status)
            if contract_id:
                q = q.filter(ONUInventoryModel.contract_id == contract_id)
            models = q.order_by(ONUInventoryModel.serial.asc()).all()
            return [self._to_item(m) for m in models]

    def add_history_event(self, event: ONUMigrationEvent) -> ONUMigrationEvent:
        with self.session_factory() as db:
            m = ONUMigrationHistoryModel(
                id=event.id or generate_uuid7(),
                serial=event.serial,
                contract_id=event.contract_id,
                subscriber_name=event.subscriber_name,
                reason=event.reason,
                from_olt_id=event.from_olt_id,
                from_olt_name=event.from_olt_name,
                from_port=event.from_port,
                from_onu_id=event.from_onu_id,
                from_circuit_id=event.from_circuit_id,
                to_olt_id=event.to_olt_id,
                to_olt_name=event.to_olt_name,
                to_port=event.to_port,
                to_onu_id=event.to_onu_id,
                to_circuit_id=event.to_circuit_id,
                status=event.status,
                details=event.details,
                timestamp=event.timestamp or datetime.now(timezone.utc),
            )
            db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_event(m)

    def list_history(
        self,
        serial: Optional[str] = None,
        from_olt_id: Optional[str] = None,
        to_olt_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ONUMigrationEvent]:
        with self.session_factory() as db:
            q = db.query(ONUMigrationHistoryModel)
            if serial:
                q = q.filter(ONUMigrationHistoryModel.serial == serial)
            if from_olt_id:
                q = q.filter(ONUMigrationHistoryModel.from_olt_id == from_olt_id)
            if to_olt_id:
                q = q.filter(ONUMigrationHistoryModel.to_olt_id == to_olt_id)
            models = q.order_by(ONUMigrationHistoryModel.timestamp.desc()).limit(limit).all()
            return [self._to_event(m) for m in models]
