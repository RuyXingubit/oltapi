import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.models.onu_inventory import ONUInventoryItem, ONUMigrationEvent

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
