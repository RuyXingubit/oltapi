import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.models.onu_inventory import ONUInventoryItem, ONUMigrationEvent
from app.models.optical_telemetry import (
    DegradedONUReportItem,
    OpticalTelemetryHistoryResponse,
    OpticalTelemetrySample,
)

logger = logging.getLogger(__name__)


class ONUInventoryRepository:
    """
    Repositório de persistência para inventário permanente de ONUs e
    registro cronológico de histórico de manobras / auto-recuperações (NOC Timeline).
    """

    def __init__(
        self,
        inventory_file: Optional[Path] = None,
        history_file: Optional[Path] = None,
    ):
        self.inventory_file = inventory_file or (settings.DATA_DIR / "onus_inventory.json")
        self.history_file = history_file or (settings.DATA_DIR / "onus_history.json")
        self._items: Dict[str, ONUInventoryItem] = {}  # indexado por serial
        self._history: List[ONUMigrationEvent] = []
        self._optical_samples: Dict[str, List[OpticalTelemetrySample]] = {}
        self._load()

    def _load(self):
        # Carrega Inventário de ONUs
        if self.inventory_file.exists():
            try:
                with open(self.inventory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for raw in data:
                        item = ONUInventoryItem(**raw)
                        self._items[item.serial] = item
            except Exception as e:
                logger.error(f"Erro ao carregar inventário de ONUs de {self.inventory_file}: {e}")

        # Carrega Histórico / Audit Trail
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    hist_data = json.load(f)
                    for raw in hist_data:
                        ev = ONUMigrationEvent(**raw)
                        self._history.append(ev)
            except Exception as e:
                logger.error(f"Erro ao carregar histórico de ONUs de {self.history_file}: {e}")

    def _save_inventory(self):
        try:
            with open(self.inventory_file, "w", encoding="utf-8") as f:
                json_data = [item.model_dump(mode="json") for item in self._items.values()]
                json.dump(json_data, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar inventário de ONUs em {self.inventory_file}: {e}")

    def _save_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json_data = [ev.model_dump(mode="json") for ev in self._history]
                json.dump(json_data, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar histórico de ONUs em {self.history_file}: {e}")

    # -----------------------------------------------------------------------
    # Operações de Inventário
    # -----------------------------------------------------------------------

    def get_by_serial(self, serial: str) -> Optional[ONUInventoryItem]:
        return self._items.get(serial)

    def get_by_id(self, onu_id: str) -> Optional[ONUInventoryItem]:
        for item in self._items.values():
            if item.id == onu_id:
                return item
        return None

    def upsert(self, item: ONUInventoryItem) -> ONUInventoryItem:
        item.updated_at = datetime.now(timezone.utc)
        self._items[item.serial] = item
        self._save_inventory()
        return item

    def delete(self, serial: str) -> bool:
        if serial in self._items:
            del self._items[serial]
            self._save_inventory()
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
        results = list(self._items.values())
        if olt_id:
            results = [item for item in results if item.current_olt_id == olt_id]
        if port:
            results = [item for item in results if item.current_port == port]
        if contract_status:
            results = [item for item in results if item.contract_status == contract_status]
        if contract_id:
            results = [item for item in results if item.contract_id == contract_id]
        if zone_id:
            results = [item for item in results if item.zone_id == zone_id]
        if odb_id:
            results = [item for item in results if item.odb_id == odb_id]
        return results

    # -----------------------------------------------------------------------
    # Operações de Histórico / Linha do Tempo (NOC Timeline)
    # -----------------------------------------------------------------------

    def add_history_event(self, event: ONUMigrationEvent) -> ONUMigrationEvent:
        self._history.append(event)
        self._save_history()
        return event

    def list_history(
        self,
        serial: Optional[str] = None,
        from_olt_id: Optional[str] = None,
        to_olt_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ONUMigrationEvent]:
        events = list(reversed(self._history))
        if serial:
            events = [ev for ev in events if ev.serial == serial]
        if from_olt_id:
            events = [ev for ev in events if ev.from_olt_id == from_olt_id]
        if to_olt_id:
            events = [ev for ev in events if ev.to_olt_id == to_olt_id]
        return events[:limit]

    # -----------------------------------------------------------------------
    # Fase 2: Série Temporal de Potência Óptica (In-Memory / JSON Fallback)
    # -----------------------------------------------------------------------

    def record_optical_sample(
        self,
        sample: OpticalTelemetrySample,
        last_down_time: Optional[str] = None,
    ) -> OpticalTelemetrySample:
        self._optical_samples.setdefault(sample.serial, []).append(sample)
        inv = self._items.get(sample.serial)
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
            inv.last_telemetry_at = sample.recorded_at
            self.upsert(inv)
        return sample

    def get_optical_history(
        self,
        serial: str,
        limit: int = 100,
    ) -> OpticalTelemetryHistoryResponse:
        samples = self._optical_samples.get(serial, [])[-limit:]
        inv = self._items.get(serial)
        rx_values = [s.rx_power_dbm for s in samples if s.rx_power_dbm is not None]
        current_rx = rx_values[-1] if rx_values else (inv.last_rx_power_dbm if inv else None)
        baseline_rx = None
        drift_db = None
        if rx_values:
            baseline_slice = rx_values[: min(5, max(1, len(rx_values) // 2 or 1))]
            baseline_rx = round(sum(baseline_slice) / len(baseline_slice), 2)
            if current_rx is not None:
                drift_db = round(current_rx - baseline_rx, 2)

        reasons: List[str] = []
        if current_rx is not None:
            if current_rx <= -27.0:
                reasons.append(f"Sinal óptico crítico ({current_rx:.2f} dBm <= -27.0 dBm)")
            elif current_rx <= -25.5:
                reasons.append(f"Sinal óptico em atenção ({current_rx:.2f} dBm <= -25.5 dBm)")
        if drift_db is not None and drift_db <= -2.5:
            reasons.append(f"Deriva óptica acentuada ({drift_db:+.2f} dB em relação à linha de base {baseline_rx:.2f} dBm)")

        return OpticalTelemetryHistoryResponse(
            serial=serial,
            olt_id=inv.current_olt_id if inv else (samples[-1].olt_id if samples else None),
            port=inv.current_port if inv else (samples[-1].port if samples else None),
            current_rx_power_dbm=current_rx,
            baseline_rx_power_dbm=baseline_rx,
            drift_db=drift_db,
            is_degraded=len(reasons) > 0,
            degradation_reasons=reasons,
            samples=samples,
        )

    def list_degraded_onus(
        self,
        olt_id: Optional[str] = None,
        threshold_dbm: float = -25.5,
        drift_threshold_db: float = -2.5,
    ) -> List[DegradedONUReportItem]:
        invs = self.list_all(olt_id=olt_id)
        degraded_list: List[DegradedONUReportItem] = []
        for inv in invs:
            hist = self.get_optical_history(inv.serial, limit=50)
            rx = hist.current_rx_power_dbm if hist.current_rx_power_dbm is not None else inv.last_rx_power_dbm
            drift = hist.drift_db
            reasons = list(hist.degradation_reasons)
            if rx is not None and rx <= threshold_dbm and not any("Sinal óptico" in r for r in reasons):
                reasons.append(f"Sinal óptico abaixo do limiar ({rx:.2f} dBm <= {threshold_dbm:.2f} dBm)")
            if drift is not None and drift <= drift_threshold_db and not any("Deriva óptica" in r for r in reasons):
                reasons.append(f"Deriva óptica ({drift:+.2f} dB <= {drift_threshold_db:+.2f} dB)")
            if inv.last_down_cause in ("los", "lofi"):
                reasons.append(f"Alarme físico ativo: {inv.last_down_cause.upper()}")
            if not reasons:
                continue
            severity = "warning"
            if (
                (rx is not None and rx <= -27.0)
                or (drift is not None and drift <= -4.0)
                or inv.last_down_cause in ("los", "lofi")
            ):
                severity = "critical"
            degraded_list.append(
                DegradedONUReportItem(
                    serial=inv.serial,
                    subscriber_name=inv.subscriber_name,
                    olt_id=inv.current_olt_id,
                    port=inv.current_port,
                    onu_id=inv.current_onu_id,
                    rx_power_dbm=rx,
                    baseline_rx_power_dbm=hist.baseline_rx_power_dbm,
                    drift_db=drift,
                    last_down_cause=inv.last_down_cause,
                    severity=severity,
                    reasons=reasons,
                    last_telemetry_at=inv.last_telemetry_at,
                )
            )
        degraded_list.sort(key=lambda x: (x.rx_power_dbm if x.rx_power_dbm is not None else -99.0))
        return degraded_list

