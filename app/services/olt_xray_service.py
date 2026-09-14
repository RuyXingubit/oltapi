"""
Serviço de Diagnóstico e Telemetria de Chassi de OLTs (Compatibilidade Retroativa).
Delega a execução para OLTTelemetryService.
"""

from app.models.olt import OLTXRayResponse
from app.services.olt_telemetry_service import OLTTelemetryService
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository
from app.storage.onu_repository import ONUInventoryRepository


class OLTXRayService:
    """Wrapper de compatibilidade retroativa para OLTTelemetryService."""

    def __init__(
        self,
        olt_repo: OLTRepository,
        onu_repo: ONUInventoryRepository,
        storage: BackupStorage,
    ):
        self._telemetry = OLTTelemetryService(olt_repo, onu_repo, storage)

    def inspect_olt(self, olt_id: str) -> OLTXRayResponse:
        """Executa a inspeção de telemetria de chassi."""
        return self._telemetry.inspect_chassis(olt_id)
