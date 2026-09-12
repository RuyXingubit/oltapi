import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.uuid import is_valid_uuid7
from app.db.init_db import migrate_legacy_json_data, run_migrations
from app.db.models import Base, OLTModel, ONUInventoryModel
from app.models.olt import OLTCreateRequest, OLTVendor, OLTProtocol
from app.models.onu_inventory import ONUInventoryItem, ONUMigrationEvent
from app.models.webhook import WebhookSubscription, WebhookDeliveryLog
from app.storage.sql.olt_repository import SQLOLTRepository
from app.storage.sql.onu_repository import SQLONUInventoryRepository
from app.storage.sql.webhook_repository import SQLWebhookRepository
from app.storage.sql.backup_storage import SQLBackupStorage


@pytest.fixture
def sql_session_factory(tmp_path):
    """Cria engine SQLite isolada para testes com foreign keys e WAL ativados."""
    db_path = tmp_path / "test_sql.db"
    db_url = f"sqlite:///{db_path}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    return factory


def test_sql_olt_repository_crud(sql_session_factory):
    repo = SQLOLTRepository(session_factory=sql_session_factory)

    # 1. Criação
    req = OLTCreateRequest(
        name="OLT-SQL-TEST",
        vendor=OLTVendor.INTELBRAS,
        model="8820",
        host="10.0.0.1",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="secret_password",
    )
    olt = repo.create(req)
    assert is_valid_uuid7(olt.id)
    assert olt.name == "OLT-SQL-TEST"

    # 2. Consulta por ID
    fetched = repo.get_by_id(olt.id)
    assert fetched is not None
    assert fetched.id == olt.id
    assert fetched.password == "secret_password"

    # 3. Listagem
    all_olts = repo.list_all()
    assert len(all_olts) == 1
    assert all_olts[0].name == "OLT-SQL-TEST"

    # 4. Exclusão
    deleted = repo.delete(olt.id)
    assert deleted is True
    assert repo.get_by_id(olt.id) is None
    assert len(repo.list_all()) == 0


def test_sql_onu_inventory_repository_crud(sql_session_factory):
    olt_repo = SQLOLTRepository(session_factory=sql_session_factory)
    onu_repo = SQLONUInventoryRepository(session_factory=sql_session_factory)

    olt = olt_repo.create(
        OLTCreateRequest(
            name="OLT-ONU-TEST",
            vendor=OLTVendor.HUAWEI,
            model="MA5800",
            host="10.0.0.2",
            port=22,
            protocol=OLTProtocol.SSH,
            username="root",
            password="pwd",
        )
    )

    # 1. Criação / Upsert de ONU
    item = ONUInventoryItem(
        serial="HWTC12345678",
        contract_id="CTR-9900",
        subscriber_name="Assinante Fibra SQL",
        contract_status="ACTIVE",
        current_olt_id=olt.id,
        current_port="0/1/1",
        current_onu_id=3,
        circuit_id=f"{olt.name} eth 0/1/1:3:100",
        vlan=100,
        profile="PLAN_300M",
        latitude=-23.5505,
        longitude=-46.6333,
        description="Instalação aprovada",
    )
    saved = onu_repo.upsert(item)
    assert is_valid_uuid7(saved.id)
    assert saved.serial == "HWTC12345678"

    # 2. Busca por serial e por id
    by_serial = onu_repo.get_by_serial("HWTC12345678")
    assert by_serial is not None
    assert by_serial.subscriber_name == "Assinante Fibra SQL"
    assert by_serial.latitude == -23.5505
    assert by_serial.description == "Instalação aprovada"

    by_id = onu_repo.get_by_id(saved.id)
    assert by_id is not None
    assert by_id.serial == "HWTC12345678"

    # 3. Atualização (Mudança de status e porta)
    by_serial.current_port = "0/1/2"
    by_serial.contract_status = "SUSPENDED"
    updated = onu_repo.upsert(by_serial)
    assert updated.current_port == "0/1/2"
    assert updated.contract_status == "SUSPENDED"

    # 4. Listagem com filtros
    assert len(onu_repo.list_all(contract_status="SUSPENDED")) == 1
    assert len(onu_repo.list_all(contract_status="ACTIVE")) == 0
    assert len(onu_repo.list_all(olt_id=olt.id)) == 1
    assert len(onu_repo.list_all(port="0/1/2")) == 1

    # 5. Deleção
    assert onu_repo.delete("HWTC12345678") is True
    assert onu_repo.get_by_serial("HWTC12345678") is None


def test_sql_onu_history_and_timeline(sql_session_factory):
    onu_repo = SQLONUInventoryRepository(session_factory=sql_session_factory)

    ev1 = ONUMigrationEvent(
        serial="SN001",
        contract_id="CTR-1",
        subscriber_name="Cliente 1",
        reason="manutencao_pop",
        from_olt_id="olt-a",
        from_olt_name="OLT-A",
        to_olt_id="olt-b",
        to_olt_name="OLT-B",
        from_port="1/1",
        to_port="1/2",
        from_onu_id=1,
        to_onu_id=5,
        from_circuit_id="OLT-A eth 1/1:1:100",
        to_circuit_id="OLT-B eth 1/2:5:100",
        status="success",
    )
    ev2 = ONUMigrationEvent(
        serial="SN001",
        contract_id="CTR-1",
        subscriber_name="Cliente 1",
        reason="correcao_fusao",
        from_olt_id="olt-b",
        from_olt_name="OLT-B",
        to_olt_id="olt-b",
        to_olt_name="OLT-B",
        from_port="1/2",
        to_port="1/3",
        from_onu_id=5,
        to_onu_id=2,
        from_circuit_id="OLT-B eth 1/2:5:100",
        to_circuit_id="OLT-B eth 1/3:2:100",
        status="success",
    )
    onu_repo.add_history_event(ev1)
    onu_repo.add_history_event(ev2)

    # Linha do tempo reversa (mais recente primeiro)
    history = onu_repo.list_history(serial="SN001")
    assert len(history) == 2
    assert history[0].reason == "correcao_fusao"
    assert history[1].reason == "manutencao_pop"


def test_sql_webhook_repository(sql_session_factory):
    repo = SQLWebhookRepository(session_factory=sql_session_factory)

    # 1. Cria assinatura
    sub = WebhookSubscription(
        url="https://erp.exemplo.com.br/webhook",
        secret="secret123456",
        events=["onu.reconciled", "onu.detected"],
        description="ERP MK-Auth Principal",
    )
    created = repo.create(sub)
    assert is_valid_uuid7(created.id)
    assert created.is_active is True
    assert "onu.reconciled" in created.events

    # 2. Consulta e atualização
    fetched = repo.get_by_id(created.id)
    assert fetched is not None
    fetched.is_active = False
    repo.update(fetched)
    assert repo.get_by_id(created.id).is_active is False

    # 3. Registro de entrega
    log = WebhookDeliveryLog(
        subscription_id=created.id,
        event="onu.reconciled",
        url=created.url,
        status_code=200,
        success=True,
        duration_ms=35.5,
    )
    repo.add_delivery_log(log)

    deliveries = repo.list_deliveries(subscription_id=created.id)
    assert len(deliveries) == 1
    assert deliveries[0].status_code == 200
    assert deliveries[0].success is True

    # 4. Deleção (em cascata)
    assert repo.delete(created.id) is True
    assert repo.get_by_id(created.id) is None
    assert len(repo.list_deliveries(subscription_id=created.id)) == 0


def test_sql_backup_storage(tmp_path, sql_session_factory):
    storage = SQLBackupStorage(base_dir=tmp_path / "backups", session_factory=sql_session_factory)
    olt_id = "0191e4f2-51a8-7d84-a12b-3456789abcde"

    # 1. Salvar backup
    content_v1 = "hostname OLT-CENTRAL\ninterface gpon 1/1\n"
    meta_v1 = storage.save_backup(olt_id, content_v1)
    assert is_valid_uuid7(meta_v1.backup_id)
    assert meta_v1.size_bytes == len(content_v1.encode("utf-8"))

    # 2. Listar
    backups = storage.list_by_olt(olt_id)
    assert len(backups) == 1
    assert backups[0].backup_id == meta_v1.backup_id

    # 3. Leitura segura
    read_content = storage.get_backup_content(olt_id, meta_v1.backup_id)
    assert read_content == content_v1

    # 4. Comparador de backups
    content_v2 = "hostname OLT-CENTRAL\ninterface gpon 1/1\n ont add 1\n"
    meta_v2 = storage.save_backup(olt_id, content_v2)

    diff_res = storage.compare_backups(olt_id, meta_v1.backup_id, meta_v2.backup_id)
    assert diff_res is not None
    assert diff_res.identical is False
    assert diff_res.additions_count >= 1

    # 5. Auditoria
    audit = storage.audit_olt(olt_id, "OLT-CENTRAL")
    assert audit.total_backups == 2
    assert audit.has_changed is True

    # 6. Expurgo
    purge = storage.purge_backups(olt_id=olt_id, max_backups_per_olt=1)
    assert purge.deleted_count == 1
    assert purge.remaining_count == 1


def test_legacy_json_data_migration(tmp_path, sql_session_factory):
    """Valida a migração transparente e idempotente de arquivos JSON legados para SQL."""
    data_dir = tmp_path / "legacy_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Cria olts.json legado
    olts_json = data_dir / "olts.json"
    olts_json.write_text(
        json.dumps(
            [
                {
                    "id": "0191e4f2-1111-7000-8000-000000000001",
                    "name": "OLT-LEGACY-01",
                    "vendor": "intelbras",
                    "model": "8820",
                    "host": "192.168.1.1",
                    "port": 22,
                    "protocol": "ssh",
                    "username": "admin",
                    "password": "legacy_password",
                }
            ]
        ),
        encoding="utf-8",
    )

    # Cria onus_inventory.json legado
    onus_json = data_dir / "onus_inventory.json"
    onus_json.write_text(
        json.dumps(
            [
                {
                    "id": "0191e4f2-2222-7000-8000-000000000002",
                    "serial": "LEGACY123456",
                    "contract_id": "CTR-LEGACY-10",
                    "subscriber_name": "Assinante Legado",
                    "contract_status": "ACTIVE",
                    "current_olt_id": "0191e4f2-1111-7000-8000-000000000001",
                    "current_port": "1/1",
                    "current_onu_id": 2,
                    "circuit_id": "OLT-LEGACY-01 eth 1/1:2:100",
                    "vlan": 100,
                }
            ]
        ),
        encoding="utf-8",
    )

    from app.core.config import settings
    orig_data_dir = settings.DATA_DIR
    settings.DATA_DIR = data_dir

    try:
        with sql_session_factory() as db:
            migrate_legacy_json_data(db)

            # Valida que os dados foram importados nas tabelas SQL
            olt = db.query(OLTModel).filter(OLTModel.id == "0191e4f2-1111-7000-8000-000000000001").first()
            assert olt is not None
            assert olt.name == "OLT-LEGACY-01"

            onu = db.query(ONUInventoryModel).filter(ONUInventoryModel.serial == "LEGACY123456").first()
            assert onu is not None
            assert onu.subscriber_name == "Assinante Legado"
            assert onu.contract_id == "CTR-LEGACY-10"

            # Segunda execução não duplica (idempotência)
            migrate_legacy_json_data(db)
            assert db.query(OLTModel).count() == 1
            assert db.query(ONUInventoryModel).count() == 1
    finally:
        settings.DATA_DIR = orig_data_dir
