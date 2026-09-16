import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

from app.core.config import settings
from app.main import app
from app.models.olt import OLTCreateRequest, OLTInDB, OLTVendor, OLTProtocol
from app.storage.sql.olt_repository import SQLOLTRepository
from app.storage.sql.onu_repository import SQLONUInventoryRepository
from app.storage.sql.webhook_repository import SQLWebhookRepository
from app.storage.sql.backup_storage import SQLBackupStorage
from app.storage.sql.ftp_repository import SQLFTPRepository
from app.services.webhook_dispatcher import WebhookDispatcher
from app.services.onu_reconciliation_service import ONUReconciliationService
from app.services.autofind_scanner import AutofindScannerService
from app.api import deps


@pytest.fixture(scope="session")
def postgres_container():
    """
    Sobe container PostgreSQL 16 oficial via Testcontainers.
    Executa as migrações do Alembic (alembic upgrade head).
    Fallback automático para SQLite caso o daemon do Docker esteja inacessível.
    """
    try:
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:
        from testcontainers.postgres import PostgresContainer

    try:
        postgres = PostgresContainer("postgres:16-alpine")
        postgres.start()
        db_url = postgres.get_connection_url()

        # Executa migrações canônicas do Alembic no Postgres real
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(db_url, pool_pre_ping=True)
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        yield {
            "postgres": postgres,
            "engine": engine,
            "session_factory": session_factory,
            "url": db_url,
            "type": "postgres",
        }

        postgres.stop()
    except Exception as e:
        # Fallback gracioso para SQLite WAL se Docker estiver indisponível
        temp_db = Path(tempfile.mkdtemp()) / "test_fallback.db"
        sqlite_url = f"sqlite:///{temp_db}"
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", sqlite_url)
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        yield {
            "postgres": None,
            "engine": engine,
            "session_factory": session_factory,
            "url": sqlite_url,
            "type": "sqlite",
        }


@pytest.fixture(scope="session", autouse=True)
def setup_test_env(postgres_container):
    temp_dir = Path(tempfile.mkdtemp())
    test_backup_dir = temp_dir / "backups"
    test_backup_dir.mkdir(parents=True, exist_ok=True)

    session_factory = postgres_container["session_factory"]

    test_olt_repo = SQLOLTRepository(session_factory=session_factory)
    test_backup_storage = SQLBackupStorage(session_factory=session_factory, base_dir=test_backup_dir)
    test_onu_repo = SQLONUInventoryRepository(session_factory=session_factory)
    test_webhook_repo = SQLWebhookRepository(session_factory=session_factory)
    test_ftp_repo = SQLFTPRepository(session_factory=session_factory)
    test_webhook_dispatcher = WebhookDispatcher(repo=test_webhook_repo)

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
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()


    app.dependency_overrides[deps.get_db] = override_get_db
    app.dependency_overrides[deps.get_olt_repo] = lambda: test_olt_repo
    app.dependency_overrides[deps.get_backup_storage] = lambda: test_backup_storage
    app.dependency_overrides[deps.get_onu_repo] = lambda: test_onu_repo
    app.dependency_overrides[deps.get_webhook_repo] = lambda: test_webhook_repo
    app.dependency_overrides[deps.get_ftp_repo] = lambda: test_ftp_repo
    app.dependency_overrides[deps.get_webhook_dispatcher] = lambda: test_webhook_dispatcher
    app.dependency_overrides[deps.get_reconciliation_service] = lambda: test_reconciliation_service
    app.dependency_overrides[deps.get_scanner_service] = lambda: test_scanner_service

    yield {
        "repo": test_olt_repo,
        "storage": test_backup_storage,
        "onu_repo": test_onu_repo,
        "webhook_repo": test_webhook_repo,
        "ftp_repo": test_ftp_repo,
        "webhook_dispatcher": test_webhook_dispatcher,
        "reconciliation_service": test_reconciliation_service,
        "scanner_service": test_scanner_service,
        "session_factory": session_factory,
        "temp_dir": temp_dir,
    }

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
    repo: SQLOLTRepository = setup_test_env["repo"]
    for existing in repo.list_all():
        if existing.name == "OLT-TESTE-8820":
            return existing
    req = OLTCreateRequest(
        name="OLT-TESTE-8820",
        vendor=OLTVendor.VSOL,
        model="V1600GT",
        host="192.168.1.200",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="admin_secret_password",
    )
    return repo.create(req)
