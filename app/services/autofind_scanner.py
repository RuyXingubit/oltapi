import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.uuid import generate_uuid7
from app.drivers.factory import DriverFactory
from app.models.hateoas import Link
from app.models.onu_inventory import ReconcileFieldEventRequest
from app.models.scanner import (
    ScannerOLTSummary,
    ScannerRunResult,
    ScannerStatus,
)
from app.services.onu_reconciliation_service import ONUReconciliationService
from app.services.webhook_dispatcher import WebhookDispatcher
from app.storage.olt_repository import OLTRepository
from app.storage.onu_repository import ONUInventoryRepository

logger = logging.getLogger(__name__)


class AutofindScannerService:
    """
    Serviço autônomo de varredura periódica de autofind em segundo plano.
    Varre ciclicamente todas as OLTs registradas, detecta ONUs desautorizadas na fibra
    e aciona o roteamento inteligente:
    - Contrato ATIVO em nova porta/OLT: Auto-reconciliação imediata + Webhook 'onu.reconciled'.
    - Serial Virgem (sem inventário): Notificação imediata via Webhook 'onu.detected'.
    - Estoque / Cancelado: Bloqueio de herança e alerta operacional.
    """

    def __init__(
        self,
        olt_repo: OLTRepository,
        onu_repo: ONUInventoryRepository,
        reconciliation_service: ONUReconciliationService,
        webhook_dispatcher: Optional[WebhookDispatcher] = None,
        interval_seconds: Optional[int] = None,
    ):
        self.olt_repo = olt_repo
        self.onu_repo = onu_repo
        self.reconciliation_service = reconciliation_service
        self.webhook_dispatcher = webhook_dispatcher
        self.interval_seconds = max(
            interval_seconds or settings.SCANNER_INTERVAL_SECONDS,
            settings.SCANNER_MIN_INTERVAL_SECONDS,
        )

        self._is_running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()

        # Locks defensivos para evitar sobrecarga de CPU/sessões nas OLTs
        self._olt_locks: Dict[str, asyncio.Lock] = {}
        self._scan_lock: asyncio.Lock = asyncio.Lock()

        # Métricas acumuladas
        self.total_cycles: int = 0
        self.total_onus_detected: int = 0
        self.total_onus_reconciled: int = 0
        self.total_virgin_onus: int = 0
        self.total_errors: int = 0
        self.last_run_at: Optional[datetime] = None
        self.last_run_duration_ms: Optional[float] = None
        self.last_cycle_id: Optional[str] = None

    def _get_olt_lock(self, olt_id: str) -> asyncio.Lock:
        if olt_id not in self._olt_locks:
            self._olt_locks[olt_id] = asyncio.Lock()
        return self._olt_locks[olt_id]

    def set_interval(self, seconds: int) -> int:
        """Atualiza o intervalo de varredura respeitando o limite mínimo defensivo."""
        self.interval_seconds = max(seconds, settings.SCANNER_MIN_INTERVAL_SECONDS)
        logger.info(f"AutofindScanner: intervalo atualizado para {self.interval_seconds}s.")
        return self.interval_seconds

    def start(self) -> bool:
        """Inicia o loop periódico do scanner em background."""
        if self._is_running:
            logger.warning("AutofindScanner já está em execução.")
            return False

        self._is_running = True
        self._stop_event.clear()
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run_loop())
        except RuntimeError:
            logger.warning("Nenhum loop assíncrono em execução para agendar _run_loop().")
        logger.info(f"AutofindScanner iniciado com intervalo de {self.interval_seconds}s.")
        return True

    async def stop(self) -> bool:
        """Interrompe graciosamente o loop do scanner."""
        if not self._is_running:
            return False

        self._is_running = False
        self._stop_event.set()

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("AutofindScanner finalizado com sucesso.")
        return True

    def get_status(self) -> ScannerStatus:
        """Retorna o status operacional atual do scanner com links HATEOAS."""
        return ScannerStatus(
            is_running=self._is_running,
            interval_seconds=self.interval_seconds,
            last_run_at=self.last_run_at,
            last_run_duration_ms=self.last_run_duration_ms,
            last_cycle_id=self.last_cycle_id,
            total_cycles=self.total_cycles,
            total_onus_detected=self.total_onus_detected,
            total_onus_reconciled=self.total_onus_reconciled,
            total_virgin_onus=self.total_virgin_onus,
            total_errors=self.total_errors,
            links={
                "self": Link(href="/api/v1/scanner/status", method="GET", description="Consultar status do scanner"),
                "start": Link(href="/api/v1/scanner/start", method="POST", description="Iniciar worker do scanner"),
                "stop": Link(href="/api/v1/scanner/stop", method="POST", description="Parar worker do scanner"),
                "run_now": Link(href="/api/v1/scanner/run-now", method="POST", description="Forçar varredura imediata"),
                "onus_history": Link(href="/api/v1/onus/history", method="GET", description="Linha do tempo do NOC"),
                "webhooks": Link(href="/api/v1/webhooks", method="GET", description="Gerenciar webhooks ERP"),
            },
        )

    async def run_scan_cycle(self) -> ScannerRunResult:
        """
        Executa um ciclo completo de varredura em todas as OLTs cadastradas.
        Pode ser acionado periodicamente pelo worker ou sob demanda via POST /scanner/run-now.
        """
        async with self._scan_lock:
            cycle_id = generate_uuid7()
            started_at = datetime.now(timezone.utc)
            olts = self.olt_repo.list_all()

            cycle_detected = 0
            cycle_reconciled = 0
            cycle_virgin = 0
            cycle_errors = 0
            olt_results: List[ScannerOLTSummary] = []

            for olt in olts:
                olt_lock = self._get_olt_lock(olt.id)
                summary = ScannerOLTSummary(olt_id=olt.id, olt_name=olt.name, status="success")

                async with olt_lock:
                    try:
                        driver = DriverFactory.get_driver(olt)
                        # Executa em threadpool assíncrona para não bloquear o loop com I/O de socket/SSH
                        unauth_onus = await asyncio.to_thread(driver.list_unauthorized_onus, olt)
                        summary.detected_onus_count = len(unauth_onus)
                        cycle_detected += len(unauth_onus)

                        for unauth in unauth_onus:
                            inv_item = self.onu_repo.get_by_serial(unauth.serial)

                            # 1. ONU com contrato ativo: reconciliação automática de campo
                            if inv_item and inv_item.contract_status == "ACTIVE":
                                req = ReconcileFieldEventRequest(
                                    serial=unauth.serial,
                                    detected_olt_id=olt.id,
                                    detected_port=unauth.port,
                                    reason="autofind_scanner_auto_reconciliation",
                                )
                                rec_res = await asyncio.to_thread(
                                    self.reconciliation_service.reconcile_field_event, req
                                )
                                if rec_res.success:
                                    cycle_reconciled += 1
                                    summary.reconciled_serials.append(unauth.serial)
                                    logger.info(
                                        f"AutofindScanner: ONU {unauth.serial} auto-reconciliada para {olt.name} {unauth.port}."
                                    )
                                else:
                                    logger.warning(
                                        f"AutofindScanner: falha ao reconciliar ONU {unauth.serial}: {rec_res.message}"
                                    )

                            # 2. ONU Virgem: sem cadastro prévio no inventário
                            elif inv_item is None:
                                cycle_virgin += 1
                                summary.virgin_serials.append(unauth.serial)
                                logger.info(
                                    f"AutofindScanner: ONU virgem {unauth.serial} detectada na OLT {olt.name} porta {unauth.port}."
                                )

                                if self.webhook_dispatcher:
                                    event_data = {
                                        "serial": unauth.serial,
                                        "olt_id": olt.id,
                                        "olt_name": olt.name,
                                        "port": unauth.port,
                                        "model": unauth.model,
                                        "detected_at": unauth.detected_at.isoformat()
                                        if hasattr(unauth, "detected_at") and unauth.detected_at
                                        else datetime.now(timezone.utc).isoformat(),
                                        "cycle_id": cycle_id,
                                    }
                                    try:
                                        self.webhook_dispatcher.dispatch("onu.detected", event_data)
                                    except Exception as we:
                                        logger.warning(f"Erro ao despachar webhook onu.detected para {unauth.serial}: {we}")

                            # 3. ONU em Estoque ou Cancelada: bloqueia herança
                            else:
                                logger.info(
                                    f"AutofindScanner: ONU {unauth.serial} detectada com status '{inv_item.contract_status}'. Herança bloqueada."
                                )

                    except Exception as e:
                        logger.warning(f"AutofindScanner: erro ao varrer OLT {olt.name} ({olt.id}): {e}")
                        summary.status = "error"
                        summary.error_message = str(e)
                        cycle_errors += 1

                olt_results.append(summary)

            completed_at = datetime.now(timezone.utc)
            duration_ms = (completed_at - started_at).total_seconds() * 1000.0

            # Atualização de métricas globais
            self.total_cycles += 1
            self.total_onus_detected += cycle_detected
            self.total_onus_reconciled += cycle_reconciled
            self.total_virgin_onus += cycle_virgin
            self.total_errors += cycle_errors
            self.last_run_at = completed_at
            self.last_run_duration_ms = round(duration_ms, 2)
            self.last_cycle_id = cycle_id

            return ScannerRunResult(
                cycle_id=cycle_id,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=round(duration_ms, 2),
                olts_scanned=len(olts),
                detected_onus_count=cycle_detected,
                reconciled_onus_count=cycle_reconciled,
                virgin_onus_count=cycle_virgin,
                errors_count=cycle_errors,
                olt_results=olt_results,
                links={
                    "status": Link(href="/api/v1/scanner/status", method="GET", description="Consultar status do scanner"),
                    "run_now": Link(href="/api/v1/scanner/run-now", method="POST", description="Forçar nova varredura"),
                },
            )

    async def _run_loop(self):
        """Loop de execução contínua com temporizador e cancelamento limpo."""
        logger.info("AutofindScanner worker loop iniciado.")
        while self._is_running:
            try:
                await self.run_scan_cycle()
            except Exception as e:
                logger.error(f"AutofindScanner: erro inesperado no ciclo periódico: {e}", exc_info=True)

            try:
                # Aguarda o intervalo ou acionamento do stop_event
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
                # Se saiu do wait sem timeout, o evento de parada foi acionado
                break
            except asyncio.TimeoutError:
                # Timeout normal do intervalo: segue para o próximo ciclo
                continue

        logger.info("AutofindScanner worker loop encerrado.")
