import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import settings
from app.models.olt import OLTCreateRequest, OLTInDB

logger = logging.getLogger(__name__)


class OLTRepository:
    """Repositório de persistência de OLTs com armazenamento seguro em disco JSON."""

    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or (settings.DATA_DIR / "olts.json")
        self._olts: Dict[str, OLTInDB] = {}
        self._load()

    def _load(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        olt = OLTInDB(**item)
                        self._olts[olt.id] = olt
            except Exception as e:
                logger.error(f"Erro ao carregar inventário de OLTs de {self.data_file}: {e}")

    def _save(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json_data = [olt.model_dump(mode="json") for olt in self._olts.values()]
                json.dump(json_data, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao persistir OLTs em {self.data_file}: {e}")

    def list_all(self) -> List[OLTInDB]:
        return list(self._olts.values())

    def get_by_id(self, olt_id: str) -> Optional[OLTInDB]:
        return self._olts.get(olt_id)

    def create(self, req: OLTCreateRequest) -> OLTInDB:
        olt = OLTInDB(
            name=req.name,
            vendor=req.vendor,
            model=req.model,
            host=req.host,
            port=req.port,
            protocol=req.protocol,
            username=req.username,
            password=req.password,
        )
        self._olts[olt.id] = olt
        self._save()
        return olt

    def delete(self, olt_id: str) -> bool:
        if olt_id in self._olts:
            del self._olts[olt_id]
            self._save()
            return True
        return False
