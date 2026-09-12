import logging
from typing import Optional

from app.core.circuit_id import generate_circuit_id
from app.drivers.factory import DriverFactory
from app.models.hateoas import Link
from app.models.onu_inventory import (
    ONUInventoryItem,
    ONUMigrationEvent,
    ReconcileFieldEventRequest,
    ReconcileFieldEventResponse,
)
from app.models.provision import ProvisionRequest
from app.services.webhook_dispatcher import WebhookDispatcher
from app.storage.olt_repository import OLTRepository
from app.storage.onu_repository import ONUInventoryRepository

logger = logging.getLogger(__name__)


class ONUReconciliationService:
    """
    Serviço inteligente de Auto-Recuperação e Conciliação Física de ONUs.
    Resolve cenários de campo onde ocorrem fusões invertidas, mudanças de endereço
    ou migração física de cordoalhas ópticas em janelas de manutenção de POP.
    """

    def __init__(
        self,
        olt_repo: OLTRepository,
        onu_repo: ONUInventoryRepository,
        webhook_dispatcher: Optional[WebhookDispatcher] = None,
    ):
        self.olt_repo = olt_repo
        self.onu_repo = onu_repo
        self.webhook_dispatcher = webhook_dispatcher

    def reconcile_field_event(self, req: ReconcileFieldEventRequest) -> ReconcileFieldEventResponse:
        item = self.onu_repo.get_by_serial(req.serial)

        # 1. Serial não registrado no inventário
        if not item:
            return ReconcileFieldEventResponse(
                success=False,
                action_taken="onu_not_found",
                serial=req.serial,
                message=f"ONU com serial '{req.serial}' não localizada no inventário do OLTAPI. Trate-a como dispositivo virgem.",
            )

        # 2. Contrato Inativo ou Equipamento em Estoque (Proteção contra herança de dados antigos)
        if item.contract_status in ["IN_STOCK", "CANCELLED"]:
            return ReconcileFieldEventResponse(
                success=False,
                action_taken="rejected_in_stock_onu",
                serial=req.serial,
                contract_id=item.contract_id,
                subscriber_name=item.subscriber_name,
                message=(
                    f"A ONU {req.serial} está com status '{item.contract_status}' (estoque/cancelada). "
                    "Por segurança, a herança de VLAN e perfil do assinante anterior foi bloqueada. "
                    "Associe a um novo contrato ativo no ERP antes de ativar."
                ),
                links={
                    "inventory": Link(
                        href=f"/api/v1/onus/{req.serial}",
                        method="GET",
                        description="Consultar cadastro de estoque da ONU",
                    )
                },
            )

        # 3. Contrato ATIVO: Auto-Recuperação e Migração Física
        detected_olt = self.olt_repo.get_by_id(req.detected_olt_id)
        if not detected_olt:
            raise ValueError(f"OLT de destino detectada '{req.detected_olt_id}' não encontrada.")

        target_driver = DriverFactory.get_driver(detected_olt)

        # Determina o ONU ID na nova porta
        target_onu_id = req.detected_onu_id
        if not target_onu_id:
            try:
                port_onus = target_driver.get_port_onus(detected_olt, req.detected_port)
                used_ids = {onu.onu_id for onu in port_onus}
                target_onu_id = 1
                for cand in range(1, 129):
                    if cand not in used_ids:
                        target_onu_id = cand
                        break
            except Exception:
                target_onu_id = 1

        # A) Provisiona na nova posição física (onde a luz acendeu)
        prov_req = ProvisionRequest(
            port=req.detected_port,
            serial=req.serial,
            vlan=item.vlan,
            profile=item.profile,
            description=item.subscriber_name or item.description or "Cliente",
        )
        target_driver.provision_onu(detected_olt, prov_req)
        logger.info(f"ONU {req.serial} provisionada na nova OLT/porta {detected_olt.name} {req.detected_port}.")

        old_olt_id = item.current_olt_id
        old_port = item.current_port
        old_onu_id = item.current_onu_id
        old_circuit_id = item.circuit_id or ""

        # B) Se houve deslocamento físico de porta ou OLT: limpa a posição antiga fantasma
        if old_olt_id != req.detected_olt_id or old_port != req.detected_port:
            old_olt = self.olt_repo.get_by_id(old_olt_id)
            if old_olt:
                try:
                    old_driver = DriverFactory.get_driver(old_olt)
                    old_driver.deprovision_onu(old_olt, req.serial, port=old_port, onu_id=old_onu_id)
                    logger.info(f"ONU fantasma {req.serial} desprovisionada da posição antiga {old_olt.name} {old_port}.")
                except Exception as e:
                    logger.warning(f"Aviso ao limpar posição antiga da ONU {req.serial} na OLT {old_olt.name}: {e}")

        # C) Recalcula o Circuit ID oficial Broadband Forum TR-101
        new_circuit_id = generate_circuit_id(detected_olt.name, req.detected_port, target_onu_id, item.vlan)

        # D) Atualiza coordenadas geográficas se fornecidas
        if req.latitude is not None:
            item.latitude = req.latitude
        if req.longitude is not None:
            item.longitude = req.longitude

        # E) Atualiza dados no inventário
        item.current_olt_id = req.detected_olt_id
        item.current_port = req.detected_port
        item.current_onu_id = target_onu_id
        item.circuit_id = new_circuit_id
        self.onu_repo.upsert(item)

        # F) Registra evento cronológico imutável para a Timeline do NOC
        old_olt = self.olt_repo.get_by_id(old_olt_id)
        old_olt_name = old_olt.name if old_olt else old_olt_id

        migration_event = ONUMigrationEvent(
            serial=req.serial,
            contract_id=item.contract_id,
            subscriber_name=item.subscriber_name,
            reason=req.reason or "field_event_auto_reconciliation",
            from_olt_id=old_olt_id,
            from_olt_name=old_olt_name,
            from_port=old_port,
            from_onu_id=old_onu_id,
            from_circuit_id=old_circuit_id,
            to_olt_id=req.detected_olt_id,
            to_olt_name=detected_olt.name,
            to_port=req.detected_port,
            to_onu_id=target_onu_id,
            to_circuit_id=new_circuit_id,
            status="success",
            details="ONU detectada em nova posição física com contrato ativo. Migração e limpeza executadas com sucesso.",
        )
        self.onu_repo.add_history_event(migration_event)

        is_cross_olt = bool(old_olt_id and old_olt_id != req.detected_olt_id)
        action_name = "reconciled_cross_olt" if is_cross_olt else "reconciled_intra_olt"

        # Dispara evento webhook para o ERP (se despachante configurado)
        if self.webhook_dispatcher:
            event_data = {
                "serial": req.serial,
                "contract_id": item.contract_id,
                "subscriber_name": item.subscriber_name,
                "action_taken": action_name,
                "old_olt_id": old_olt_id,
                "old_olt_name": old_olt_name,
                "old_port": old_port,
                "old_onu_id": old_onu_id,
                "old_circuit_id": old_circuit_id,
                "new_olt_id": req.detected_olt_id,
                "new_olt_name": detected_olt.name,
                "new_port": req.detected_port,
                "new_onu_id": target_onu_id,
                "new_circuit_id": new_circuit_id,
                "vlan": item.vlan,
                "profile": item.profile,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "reason": req.reason or "field_event_auto_reconciliation",
            }
            try:
                self.webhook_dispatcher.dispatch("onu.reconciled", event_data)
            except Exception as e:
                logger.warning(f"Falha ao despachar webhook onu.reconciled para {req.serial}: {e}")

        # G) Retorna resposta detalhada com links HATEOAS
        return ReconcileFieldEventResponse(
            success=True,
            action_taken=action_name,
            serial=req.serial,
            contract_id=item.contract_id,
            subscriber_name=item.subscriber_name,
            from_olt_id=old_olt_id,
            to_olt_id=req.detected_olt_id,
            from_port=old_port,
            to_port=req.detected_port,
            old_olt_id=old_olt_id,
            new_olt_id=req.detected_olt_id,
            old_port=old_port,
            new_port=req.detected_port,
            old_onu_id=old_onu_id,
            new_onu_id=target_onu_id,
            old_circuit_id=old_circuit_id,
            new_circuit_id=new_circuit_id,
            message=(
                f"ONU {req.serial} do assinante '{item.subscriber_name}' (Contrato {item.contract_id}) "
                f"auto-recuperada com sucesso. Posição atualizada para {detected_olt.name} porta {req.detected_port}. "
                f"Novo Circuit ID: {new_circuit_id}."
            ),
            links={
                "details": Link(
                    href=f"/api/v1/onus/{req.serial}",
                    method="GET",
                    description="Consultar cadastro e localização atualizada da ONU",
                ),
                "history": Link(
                    href=f"/api/v1/onus/{req.serial}/history",
                    method="GET",
                    description="Consultar histórico de movimentações desta ONU",
                ),
                "target_port_onus": Link(
                    href=f"/api/v1/olts/{req.detected_olt_id}/ports/{req.detected_port}/onus",
                    method="GET",
                    description="Listar todas as ONUs da nova porta PON",
                ),
            },
        )
