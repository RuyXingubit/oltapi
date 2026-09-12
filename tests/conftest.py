import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.olt import OLTCreateRequest, OLTInDB, OLTVendor, OLTProtocol
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository
from app.storage.onu_repository import ONUInventoryRepository
from app.storage.webhook_repository import WebhookRepository
from app.services.webhook_dispatcher import WebhookDispatcher
from app.api import deps


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    # Cria diretório temporário para testes
    temp_dir = Path(tempfile.mkdtemp())
    test_backup_dir = temp_dir / "backups"
    test_data_dir = temp_dir / "data"

    test_backup_dir.mkdir(parents=True, exist_ok=True)
    test_data_dir.mkdir(parents=True, exist_ok=True)

    test_olt_repo = OLTRepository(data_file=test_data_dir / "olts.json")
    test_backup_storage = BackupStorage(base_dir=test_backup_dir, data_file=test_data_dir / "backups.json")
    test_onu_repo = ONUInventoryRepository(
        inventory_file=test_data_dir / "onus_inventory.json",
        history_file=test_data_dir / "onus_history.json",
    )
    test_webhook_repo = WebhookRepository(
        subscriptions_file=test_data_dir / "webhooks.json",
        deliveries_file=test_data_dir / "webhook_deliveries.json",
    )
    test_webhook_dispatcher = WebhookDispatcher(repo=test_webhook_repo)
    
    from app.services.onu_reconciliation_service import ONUReconciliationService
    from app.services.autofind_scanner import AutofindScannerService

    test_reconciliation_service = ONUReconciliationService(
        olt_repo=test_olt_repo,
        onu_repo=test_onu_repo,
        webhook_dispatcher=test_webhook_dispatcher,
    )
    test_scanner_service = AutofindScannerService(
        olt_repo=test_olt_repo,
        onu_repo=test_onu_repo,
        reconciliation_service=test_reconciliation_service,
        webhook_dispatcher=test_webhook_dispatcher,
    )

    # Override das dependências FastAPI
    app.dependency_overrides[deps.get_olt_repo] = lambda: test_olt_repo
    app.dependency_overrides[deps.get_backup_storage] = lambda: test_backup_storage
    app.dependency_overrides[deps.get_onu_repo] = lambda: test_onu_repo
    app.dependency_overrides[deps.get_webhook_repo] = lambda: test_webhook_repo
    app.dependency_overrides[deps.get_webhook_dispatcher] = lambda: test_webhook_dispatcher
    app.dependency_overrides[deps.get_reconciliation_service] = lambda: test_reconciliation_service
    app.dependency_overrides[deps.get_scanner_service] = lambda: test_scanner_service

    yield {
        "repo": test_olt_repo,
        "storage": test_backup_storage,
        "onu_repo": test_onu_repo,
        "webhook_repo": test_webhook_repo,
        "webhook_dispatcher": test_webhook_dispatcher,
        "reconciliation_service": test_reconciliation_service,
        "scanner_service": test_scanner_service,
        "temp_dir": temp_dir,
    }

    # Limpeza
    shutil.rmtree(temp_dir, ignore_errors=True)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"X-API-Key": settings.API_KEY}


@pytest.fixture
def sample_olt_8820(setup_test_env) -> OLTInDB:
    repo: OLTRepository = setup_test_env["repo"]
    for existing in repo.list_all():
        if existing.name == "OLT-TESTE-8820":
            return existing
    req = OLTCreateRequest(
        name="OLT-TESTE-8820",
        vendor=OLTVendor.INTELBRAS,
        model="8820",
        host="192.168.1.200",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="admin_secret_password",
    )
    return repo.create(req)
