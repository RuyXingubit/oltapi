import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.uuid import generate_uuid7
from app.db.models import (
    ONUInventoryModel,
    ONUMigrationHistoryModel,
    ONUOpticalTelemetryHistoryModel,
)
from app.db.session import SessionLocal
from app.models.onu_inventory import ONUInventoryItem, ONUMigrationEvent
from app.models.optical_telemetry import (
    DegradedONUReportItem,
    OpticalTelemetryHistoryResponse,
    OpticalTelemetrySample,
)

logger = logging.getLogger(__name__)


class SQLONUInventoryRepository:
    """Repositório de Inventário de ONUs, Série Temporal Óptica e Histórico do NOC via SQLAlchemy."""

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
            profile=m.profile or "DEFAULT",
            latitude=m.latitude,
            longitude=m.longitude,
            description=m.description,
            last_rx_power_dbm=m.last_rx_power_dbm,
            last_tx_power_dbm=m.last_tx_power_dbm,
            last_olt_rx_power_dbm=m.last_olt_rx_power_dbm,
            last_down_cause=m.last_down_cause,
            last_down_time=m.last_down_time,
            last_telemetry_at=m.last_telemetry_at,
            zone_id=m.zone_id,
            odb_id=m.odb_id,
            odb_splitter_port=m.odb_splitter_port,
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

    def _to_optical_sample(self, m: ONUOpticalTelemetryHistoryModel) -> OpticalTelemetrySample:
        return OpticalTelemetrySample(
            id=m.id,
            serial=m.serial,
            olt_id=m.olt_id,
            port=m.port,
            onu_id=m.onu_id,
            rx_power_dbm=m.rx_power_dbm,
            tx_power_dbm=m.tx_power_dbm,
            olt_rx_power_dbm=m.olt_rx_power_dbm,
            status=m.status,
            last_down_cause=m.last_down_cause,
            recorded_at=m.recorded_at,
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
                if item.last_rx_power_dbm is not None:
                    m.last_rx_power_dbm = item.last_rx_power_dbm
                if item.last_tx_power_dbm is not None:
                    m.last_tx_power_dbm = item.last_tx_power_dbm
                if item.last_olt_rx_power_dbm is not None:
                    m.last_olt_rx_power_dbm = item.last_olt_rx_power_dbm
                if item.last_down_cause is not None:
                    m.last_down_cause = item.last_down_cause
                if item.last_down_time is not None:
                    m.last_down_time = item.last_down_time
                if item.last_telemetry_at is not None:
                    m.last_telemetry_at = item.last_telemetry_at
                m.zone_id = item.zone_id
                m.odb_id = item.odb_id
                m.odb_splitter_port = item.odb_splitter_port
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
                    last_rx_power_dbm=item.last_rx_power_dbm,
                    last_tx_power_dbm=item.last_tx_power_dbm,
                    last_olt_rx_power_dbm=item.last_olt_rx_power_dbm,
                    last_down_cause=item.last_down_cause,
                    last_down_time=item.last_down_time,
                    last_telemetry_at=item.last_telemetry_at,
                    zone_id=item.zone_id,
                    odb_id=item.odb_id,
                    odb_splitter_port=item.odb_splitter_port,
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
        zone_id: Optional[str] = None,
        odb_id: Optional[str] = None,
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
            if zone_id:
                q = q.filter(ONUInventoryModel.zone_id == zone_id)
            if odb_id:
                q = q.filter(ONUInventoryModel.odb_id == odb_id)
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

    # -----------------------------------------------------------------------
    # Fase 2: Série Temporal de Potência Óptica e Radar de Degradação
    # -----------------------------------------------------------------------

    def record_optical_sample(
        self,
        sample: OpticalTelemetrySample,
        last_down_time: Optional[str] = None,
    ) -> OpticalTelemetrySample:
        with self.session_factory() as db:
            now = sample.recorded_at or datetime.now(timezone.utc)
            m = ONUOpticalTelemetryHistoryModel(
                id=sample.id or generate_uuid7(),
                serial=sample.serial,
                olt_id=sample.olt_id,
                port=sample.port,
                onu_id=sample.onu_id,
                rx_power_dbm=sample.rx_power_dbm,
                tx_power_dbm=sample.tx_power_dbm,
                olt_rx_power_dbm=sample.olt_rx_power_dbm,
                status=sample.status or "online",
                last_down_cause=sample.last_down_cause,
                recorded_at=now,
            )
            db.add(m)

            # Atualiza cache de última leitura no inventário se a ONU existir
            inv = db.query(ONUInventoryModel).filter(ONUInventoryModel.serial == sample.serial).first()
            if inv:
                if sample.rx_power_dbm is not None:
                    inv.last_rx_power_dbm = sample.rx_power_dbm
                if sample.tx_power_dbm is not None:
                    inv.last_tx_power_dbm = sample.tx_power_dbm
                if sample.olt_rx_power_dbm is not None:
                    inv.last_olt_rx_power_dbm = sample.olt_rx_power_dbm
                if sample.last_down_cause is not None:
                    inv.last_down_cause = sample.last_down_cause
                if last_down_time is not None:
                    inv.last_down_time = last_down_time
                inv.last_telemetry_at = now
                inv.updated_at = now

            db.commit()
            db.refresh(m)
            return self._to_optical_sample(m)

    def get_optical_history(
        self,
        serial: str,
        limit: int = 100,
    ) -> OpticalTelemetryHistoryResponse:
        with self.session_factory() as db:
            rows = (
                db.query(ONUOpticalTelemetryHistoryModel)
                .filter(ONUOpticalTelemetryHistoryModel.serial == serial)
                .order_by(ONUOpticalTelemetryHistoryModel.recorded_at.desc())
                .limit(limit)
                .all()
            )
            inv = db.query(ONUInventoryModel).filter(ONUInventoryModel.serial == serial).first()

            # Ordena em ordem cronológica (mais antiga -> mais recente) para gráficos
            samples = [self._to_optical_sample(r) for r in reversed(rows)]
            from app.storage.onu_repository import ONUInventoryRepository

            return ONUInventoryRepository.build_optical_history_response(serial, samples, inv)

    def list_degraded_onus(
        self,
        olt_id: Optional[str] = None,
        threshold_dbm: float = -25.5,
        drift_threshold_db: float = -2.5,
    ) -> List[DegradedONUReportItem]:
        with self.session_factory() as db:
            q = db.query(ONUInventoryModel)
            if olt_id:
                q = q.filter(ONUInventoryModel.current_olt_id == olt_id)
            invs = q.all()
            from app.storage.onu_repository import ONUInventoryRepository

            return ONUInventoryRepository.build_degraded_onus_report(
                invs,
                lambda serial, limit: self.get_optical_history(serial, limit=limit),
                threshold_dbm=threshold_dbm,
                drift_threshold_db=drift_threshold_db,
            )

