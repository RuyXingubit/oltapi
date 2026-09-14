import logging
import time
from typing import Union
from app.core.circuit_id import generate_circuit_id
from app.core.uuid import generate_uuid7
from app.drivers.factory import DriverFactory
from app.models.onu_inventory import ONUInventoryItem
from app.models.vlan import SyncOLTResponse
from app.services.backup_service import BackupService
from app.storage.olt_repository import OLTRepository
from app.storage.onu_repository import ONUInventoryRepository
from app.storage.sql.olt_repository import SQLOLTRepository
from app.storage.sql.onu_repository import SQLONUInventoryRepository

logger = logging.getLogger(__name__)


class OLTSyncService:
    """
    Serviço de Onboarding & Sincronização Segura de OLT em Produção (Brownfield).
    Executa:
    1. Backup Preventivo Obrigatório (Snapshot v0 Baseline com hash SHA-256).
    2. Varredura e Ingestão de todas as ONUs já ativas na OLT física.
    3. Mapeamento de VLANs existentes.
    4. Cálculo de Circuit ID TR-101 e persistência atômica no banco relacional.
    """

    def __init__(
        self,
        olt_repo: Union[SQLOLTRepository, OLTRepository],
        onu_repo: Union[SQLONUInventoryRepository, ONUInventoryRepository],
        backup_service: BackupService,
    ):
        self.olt_repo = olt_repo
        self.onu_repo = onu_repo
        self.backup_service = backup_service

    def sync_olt(self, olt_id: str) -> SyncOLTResponse:
        olt = self.olt_repo.get_by_id(olt_id)
        if not olt:
            raise ValueError(f"OLT '{olt_id}' não encontrada.")

        start_time = time.perf_counter()

        # 1. Snapshot de Baseline v0 Preventivo (Obrigatório)
        baseline_backup = self.backup_service.create_backup(
            olt_id=olt.id,
            notes="Baseline v0 - Pre-Onboarding Full Discovery",
        )

        # 2. Driver Discovery
        driver = DriverFactory.get_driver(olt)
        onus = driver.list_all_authorized_onus(olt)
        vlans = driver.list_vlans(olt)
        vlan_ids = [v.vlan_id for v in vlans] if vlans else []

        new_count = 0
        updated_count = 0

        # 3. Ingestão no inventário relacional
        for onu in onus:
            existing = self.onu_repo.get_by_serial(onu.serial)
            target_vlan = getattr(onu, "vlan", None) or (vlan_ids[0] if vlan_ids else 100)
            circuit_id = generate_circuit_id(olt.name, onu.port, onu.onu_id, target_vlan)

            if existing:
                existing.current_olt_id = olt.id
                existing.current_port = onu.port
                existing.current_onu_id = onu.onu_id
                existing.circuit_id = circuit_id
                existing.contract_status = "ACTIVE"
                if existing.vlan is None or onu.vlan is not None:
                    existing.vlan = target_vlan
                if onu.name:
                    existing.description = onu.name
                self.onu_repo.upsert(existing)
                updated_count += 1
            else:
                item = ONUInventoryItem(
                    id=generate_uuid7(),
                    serial=onu.serial,
                    subscriber_name=onu.name or f"Assinante {onu.serial}",
                    contract_status="ACTIVE",
                    current_olt_id=olt.id,
                    current_port=onu.port,
                    current_onu_id=onu.onu_id,
                    circuit_id=circuit_id,
                    vlan=target_vlan,
                    description=onu.name or f"Descoberto via Sync {olt.name}",
                )
                self.onu_repo.upsert(item)
                new_count += 1

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return SyncOLTResponse(
            olt_id=olt.id,
            olt_name=olt.name,
            baseline_backup_id=baseline_backup.backup_id,
            total_onus_discovered=len(onus),
            new_onus_registered=new_count,
            existing_onus_updated=updated_count,
            vlans_discovered=vlan_ids,
            duration_ms=duration_ms,
            message=f"Sync concluído com sucesso. {new_count} novas ONUs cadastradas e {updated_count} atualizadas.",
        )
