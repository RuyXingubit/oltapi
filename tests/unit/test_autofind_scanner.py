from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.uuid import is_valid_uuid7
from app.models.olt import OLTCreateRequest, OLTProtocol, OLTVendor
from app.models.onu import UnauthorizedONU
from app.models.onu_inventory import ONUInventoryItem
from app.models.provision import ProvisionResponse, ONUActionResponse
from app.services.autofind_scanner import AutofindScannerService
from app.services.onu_reconciliation_service import ONUReconciliationService
from app.storage.olt_repository import OLTRepository
from app.storage.onu_repository import ONUInventoryRepository


@pytest.fixture
def isolated_scanner_env(setup_test_env, tmp_path):
    """Cria um ambiente isolado com repositories dedicados em tmp_path para cada teste."""
    test_olt_repo = OLTRepository(data_file=tmp_path / "olts.json")
    test_onu_repo = ONUInventoryRepository(
        inventory_file=tmp_path / "onus_inventory.json",
        history_file=tmp_path / "onus_history.json",
    )
    test_webhook_dispatcher = setup_test_env["webhook_dispatcher"]
    test_reconciliation_service = ONUReconciliationService(
        olt_repo=test_olt_repo,
        onu_repo=test_onu_repo,
        webhook_dispatcher=test_webhook_dispatcher,
    )
    scanner = AutofindScannerService(
        olt_repo=test_olt_repo,
        onu_repo=test_onu_repo,
        reconciliation_service=test_reconciliation_service,
        webhook_dispatcher=test_webhook_dispatcher,
        interval_seconds=60,
    )
    return {
        "scanner": scanner,
        "olt_repo": test_olt_repo,
        "onu_repo": test_onu_repo,
        "webhook_dispatcher": test_webhook_dispatcher,
        "reconciliation_service": test_reconciliation_service,
    }


@pytest.mark.asyncio
async def test_scanner_lifecycle_start_stop_interval(isolated_scanner_env):
    scanner = isolated_scanner_env["scanner"]

    # Status inicial
    status = scanner.get_status()
    assert not status.is_running
    assert status.interval_seconds == 60
    assert "start" in status.links
    assert "stop" in status.links
    assert "run_now" in status.links

    # Inicia
    assert scanner.start() is True
    assert scanner._is_running is True

    # Iniciar novamente deve retornar False (idempotente)
    assert scanner.start() is False

    # Para
    stopped = await scanner.stop()
    assert stopped is True
    assert scanner._is_running is False

    # Parar novamente retorna False
    assert await scanner.stop() is False

    # Ajuste de intervalo
    scanner.set_interval(120)
    assert scanner.interval_seconds == 120

    # Piso defensivo de 10s
    scanner.set_interval(5)
    assert scanner.interval_seconds == 10


@pytest.mark.asyncio
async def test_scanner_run_cycle_active_contract_reconciliation(isolated_scanner_env):
    scanner = isolated_scanner_env["scanner"]
    olt_repo: OLTRepository = isolated_scanner_env["olt_repo"]
    onu_repo: ONUInventoryRepository = isolated_scanner_env["onu_repo"]
    webhook_dispatcher = isolated_scanner_env["webhook_dispatcher"]

    # Cria duas OLTs
    olt_a = olt_repo.create(
        OLTCreateRequest(
            name="OLT-ALPHA-ORIGEM",
            vendor=OLTVendor.INTELBRAS,
            model="8820",
            host="10.10.1.1",
            port=22,
            protocol=OLTProtocol.SSH,
            username="admin",
            password="secret",
        )
    )
    olt_b = olt_repo.create(
        OLTCreateRequest(
            name="OLT-BETA-DESTINO",
            vendor=OLTVendor.INTELBRAS,
            model="8820",
            host="10.10.2.1",
            port=22,
            protocol=OLTProtocol.SSH,
            username="admin",
            password="secret",
        )
    )

    # Cadastra ONU com contrato ativo na OLT A
    onu_item = ONUInventoryItem(
        serial="AUTO11223344",
        contract_id="CTR-AUTO-999",
        subscriber_name="Mercado Central Fibra",
        contract_status="ACTIVE",
        current_olt_id=olt_a.id,
        current_port="1/1",
        current_onu_id=5,
        vlan=220,
        profile="PLAN_500M",
    )
    onu_repo.upsert(onu_item)

    mock_driver_a = MagicMock()
    mock_driver_a.list_unauthorized_onus.return_value = []
    mock_driver_a.deprovision_onu.return_value = ONUActionResponse(
        action="deprovision", olt_id=olt_a.id, serial="AUTO11223344", port="1/1", message="Ghost deleted"
    )

    mock_driver_b = MagicMock()
    mock_driver_b.list_unauthorized_onus.return_value = [
        UnauthorizedONU(port="1/4", serial="AUTO11223344", model="ONT-100")
    ]
    mock_driver_b.get_port_onus.return_value = []
    mock_driver_b.provision_onu.return_value = ProvisionResponse(
        success=True, port="1/4", onu_id=1, serial="AUTO11223344", message="OK"
    )

    def driver_factory_mock(target_olt):
        return mock_driver_a if target_olt.id == olt_a.id else mock_driver_b

    with patch("app.services.autofind_scanner.DriverFactory.get_driver", side_effect=driver_factory_mock), \
         patch("app.services.onu_reconciliation_service.DriverFactory.get_driver", side_effect=driver_factory_mock), \
         patch.object(webhook_dispatcher, "dispatch") as mock_dispatch:

        result = await scanner.run_scan_cycle()

        assert is_valid_uuid7(result.cycle_id)
        assert result.olts_scanned == 2
        assert result.detected_onus_count == 1
        assert result.reconciled_onus_count == 1
        assert result.virgin_onus_count == 0
        assert result.errors_count == 0

        # Verifica se o inventário foi atualizado para a nova OLT e porta
        updated_onu = onu_repo.get_by_serial("AUTO11223344")
        assert updated_onu.current_olt_id == olt_b.id
        assert updated_onu.current_port == "1/4"
        assert updated_onu.circuit_id == "OLT-BETA-DESTINO eth 1/4:1:220"

        # Verifica histórico do NOC gravado
        history = onu_repo.list_history(serial="AUTO11223344")
        assert len(history) >= 1
        assert history[0].from_olt_name == "OLT-ALPHA-ORIGEM"
        assert history[0].to_olt_name == "OLT-BETA-DESTINO"

        # Verifica se o webhook onu.reconciled foi disparado
        mock_dispatch.assert_called_once()
        assert mock_dispatch.call_args[0][0] == "onu.reconciled"


@pytest.mark.asyncio
async def test_scanner_run_cycle_virgin_onu_detected(isolated_scanner_env):
    scanner = isolated_scanner_env["scanner"]
    olt_repo: OLTRepository = isolated_scanner_env["olt_repo"]
    webhook_dispatcher = isolated_scanner_env["webhook_dispatcher"]

    # Cria OLT
    olt = olt_repo.create(
        OLTCreateRequest(
            name="OLT-VIRGIN-TEST",
            vendor=OLTVendor.HUAWEI,
            model="MA5800",
            host="10.20.1.1",
            port=22,
            protocol=OLTProtocol.SSH,
            username="root",
            password="secret",
        )
    )

    mock_driver = MagicMock()
    mock_driver.list_unauthorized_onus.return_value = [
        UnauthorizedONU(port="0/1/2", serial="HWTC99887766", model="EG8145V5")
    ]

    with patch("app.services.autofind_scanner.DriverFactory.get_driver", return_value=mock_driver), \
         patch.object(webhook_dispatcher, "dispatch") as mock_dispatch:

        result = await scanner.run_scan_cycle()

        assert result.olts_scanned == 1
        assert result.detected_onus_count == 1
        assert result.reconciled_onus_count == 0
        assert result.virgin_onus_count == 1

        # Webhook onu.detected deve ser despachado com dados da nova ONU virgem
        mock_dispatch.assert_called_once()
        event_name, event_data = mock_dispatch.call_args[0]
        assert event_name == "onu.detected"
        assert event_data["serial"] == "HWTC99887766"
        assert event_data["olt_id"] == olt.id
        assert event_data["port"] == "0/1/2"
        assert event_data["model"] == "EG8145V5"
        assert is_valid_uuid7(event_data["cycle_id"])


@pytest.mark.asyncio
async def test_scanner_run_cycle_in_stock_onu_blocked(isolated_scanner_env):
    scanner = isolated_scanner_env["scanner"]
    olt_repo: OLTRepository = isolated_scanner_env["olt_repo"]
    onu_repo: ONUInventoryRepository = isolated_scanner_env["onu_repo"]

    olt = olt_repo.create(
        OLTCreateRequest(
            name="OLT-STOCK-TEST",
            vendor=OLTVendor.FIBERHOME,
            model="AN5516",
            host="10.30.1.1",
            port=3337,
            protocol=OLTProtocol.TELNET,
            username="admin",
            password="secret",
        )
    )

    # Cadastra ONU em Estoque
    onu_repo.upsert(
        ONUInventoryItem(
            serial="FHTT44332211",
            contract_id=None,
            subscriber_name=None,
            contract_status="IN_STOCK",
            vlan=100,
        )
    )

    mock_driver = MagicMock()
    mock_driver.list_unauthorized_onus.return_value = [
        UnauthorizedONU(port="1/1/1", serial="FHTT44332211", model="AN5506-04")
    ]

    with patch("app.services.autofind_scanner.DriverFactory.get_driver", return_value=mock_driver):
        result = await scanner.run_scan_cycle()

        assert result.olts_scanned == 1
        assert result.detected_onus_count == 1
        # Não pode herdar nem provisionar automaticamente ONU em estoque
        assert result.reconciled_onus_count == 0
        assert result.virgin_onus_count == 0


@pytest.mark.asyncio
async def test_scanner_fault_tolerance_olt_timeout(isolated_scanner_env):
    scanner = isolated_scanner_env["scanner"]
    olt_repo: OLTRepository = isolated_scanner_env["olt_repo"]

    # Duas OLTs
    olt_down = olt_repo.create(
        OLTCreateRequest(
            name="OLT-TIMEOUT",
            vendor=OLTVendor.ZTE,
            model="C320",
            host="10.99.99.99",
            port=22,
            protocol=OLTProtocol.SSH,
            username="admin",
            password="secret",
        )
    )
    olt_ok = olt_repo.create(
        OLTCreateRequest(
            name="OLT-OK",
            vendor=OLTVendor.VSOL,
            model="V1600G",
            host="10.40.1.1",
            port=22,
            protocol=OLTProtocol.SSH,
            username="admin",
            password="secret",
        )
    )

    mock_driver_down = MagicMock()
    mock_driver_down.list_unauthorized_onus.side_effect = TimeoutError("SSH Connection timed out after 15s")

    mock_driver_ok = MagicMock()
    mock_driver_ok.list_unauthorized_onus.return_value = [
        UnauthorizedONU(port="0/1", serial="VSOL11223344", model="V2801SG")
    ]

    def factory(target_olt):
        return mock_driver_down if target_olt.id == olt_down.id else mock_driver_ok

    with patch("app.services.autofind_scanner.DriverFactory.get_driver", side_effect=factory):
        result = await scanner.run_scan_cycle()

        # O ciclo não quebrou! Contabilizou o erro da OLT down e prosseguiu com a OLT ok
        assert result.olts_scanned == 2
        assert result.errors_count == 1
        assert result.virgin_onus_count == 1
        assert scanner.total_errors == 1


def test_scanner_rest_endpoints(client: TestClient, auth_headers, setup_test_env):
    scanner: AutofindScannerService = setup_test_env["scanner_service"]

    # 1. GET /api/v1/scanner/status
    res = client.get("/api/v1/scanner/status", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "is_running" in data
    assert "_links" in data
    assert "start" in data["_links"]
    assert "run_now" in data["_links"]

    # 2. POST /api/v1/scanner/start
    res = client.post("/api/v1/scanner/start", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["is_running"] is True

    # 3. POST /api/v1/scanner/stop
    res = client.post("/api/v1/scanner/stop", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["is_running"] is False

    # 4. PATCH /api/v1/scanner/interval
    res = client.patch("/api/v1/scanner/interval", json={"interval_seconds": 90}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["interval_seconds"] == 90

    # 5. PATCH /api/v1/scanner/interval inválido (< 10s)
    res = client.patch("/api/v1/scanner/interval", json={"interval_seconds": 3}, headers=auth_headers)
    assert res.status_code == 422

    # 6. POST /api/v1/scanner/run-now
    with patch.object(scanner, "run_scan_cycle") as mock_cycle:
        mock_cycle.return_value = {
            "cycle_id": "018e6a2b-871c-7f51-b753-f72535928d11",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": 45.2,
            "olts_scanned": 1,
            "detected_onus_count": 0,
            "reconciled_onus_count": 0,
            "virgin_onus_count": 0,
            "errors_count": 0,
            "olt_results": [],
            "_links": {},
        }
        res = client.post("/api/v1/scanner/run-now", headers=auth_headers)
        assert res.status_code == 200
        assert is_valid_uuid7(res.json()["cycle_id"])

    # 7. Segurança: Sem API key
    res = client.get("/api/v1/scanner/status")
    assert res.status_code == 401
