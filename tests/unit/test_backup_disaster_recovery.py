from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.uuid import generate_uuid7
from app.models.backup import PurgePolicy
from app.models.olt import OLTCreateRequest, OLTVendor
from app.services.backup_service import BackupService
from app.storage.backup_storage import BackupStorage
from app.storage.olt_repository import OLTRepository



@pytest.fixture
def temp_backup_env(tmp_path: Path):
    backup_dir = tmp_path / "backups"
    data_file = tmp_path / "backups.json"
    storage = BackupStorage(base_dir=backup_dir, data_file=data_file)
    return storage


def test_backup_storage_compare_identical(temp_backup_env: BackupStorage):
    storage = temp_backup_env
    olt_id = generate_uuid7()
    content = "hostname OLT-CORE\nvlan 100\ninterface gpon 1/1\n"

    b1 = storage.save_backup(olt_id=olt_id, content=content)
    b2 = storage.save_backup(olt_id=olt_id, content=content)

    diff_res = storage.compare_backups(olt_id=olt_id, base_backup_id=b1.backup_id, target_backup_id=b2.backup_id)
    assert diff_res is not None
    assert diff_res.identical is True
    assert diff_res.base_sha256 == diff_res.target_sha256
    assert diff_res.diff_lines == []
    assert diff_res.additions_count == 0
    assert diff_res.deletions_count == 0


def test_backup_storage_compare_drift_unified_diff(temp_backup_env: BackupStorage):
    storage = temp_backup_env
    olt_id = generate_uuid7()

    base_cfg = "hostname OLT-CORE\nvlan 100\ninterface gpon 1/1\n"
    target_cfg = "hostname OLT-CORE\nvlan 100\nvlan 200\ninterface gpon 1/1\n description Uplink\n"

    b_base = storage.save_backup(olt_id=olt_id, content=base_cfg)
    b_target = storage.save_backup(olt_id=olt_id, content=target_cfg)

    # Compara sem passar IDs (deve comparar automaticamente o mais recente contra o penúltimo)
    diff_res = storage.compare_backups(olt_id=olt_id)
    assert diff_res is not None
    assert diff_res.identical is False
    assert diff_res.base_sha256 != diff_res.target_sha256
    assert diff_res.additions_count == 2
    assert any("+vlan 200" in line for line in diff_res.diff_lines)
    assert any("+ description Uplink" in line for line in diff_res.diff_lines)


def test_backup_storage_audit_olt(temp_backup_env: BackupStorage):
    storage = temp_backup_env
    olt_id = generate_uuid7()

    b1 = storage.save_backup(olt_id=olt_id, content="vlan 10\n")
    b2 = storage.save_backup(olt_id=olt_id, content="vlan 20\n")

    report = storage.audit_olt(olt_id=olt_id, olt_name="OLT Central")
    assert report.olt_id == olt_id
    assert report.olt_name == "OLT Central"
    assert report.total_backups == 2
    assert report.total_bytes == (b1.size_bytes + b2.size_bytes)
    assert report.has_changed is True
    assert report.latest_backup is not None
    assert report.latest_backup.backup_id == b2.backup_id
    assert report.previous_backup is not None
    assert report.previous_backup.backup_id == b1.backup_id


def test_backup_storage_purge_by_max_count(temp_backup_env: BackupStorage):
    storage = temp_backup_env
    olt_id = generate_uuid7()

    for i in range(5):
        storage.save_backup(olt_id=olt_id, content=f"config version {i}\n")

    assert len(storage.list_by_olt(olt_id)) == 5

    purge_res = storage.purge_backups(olt_id=olt_id, max_backups_per_olt=2)
    assert purge_res.deleted_count == 3
    assert purge_res.freed_bytes > 0
    assert purge_res.remaining_count == 2
    assert len(storage.list_by_olt(olt_id)) == 2


def test_backup_storage_purge_preserves_newest_even_if_old(temp_backup_env: BackupStorage):
    storage = temp_backup_env
    olt_id = generate_uuid7()

    storage.save_backup(olt_id=olt_id, content="only config\n")

    # Força max_age_days=0
    purge_res = storage.purge_backups(olt_id=olt_id, max_backups_per_olt=10, max_age_days=0)
    assert purge_res.deleted_count == 0
    assert purge_res.remaining_count == 1


from unittest.mock import MagicMock, patch


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_backup_service_run_all_and_audit_all(mock_get_driver, tmp_path: Path):
    mock_driver = MagicMock()
    mock_driver.backup_config.return_value = "system-config backup data content..."
    mock_get_driver.return_value = mock_driver

    backup_dir = tmp_path / "backups_svc"
    data_file = tmp_path / "backups_svc.json"
    storage = BackupStorage(base_dir=backup_dir, data_file=data_file)
    olt_repo = OLTRepository(data_file=tmp_path / "olts.json")

    olt = olt_repo.create(
        OLTCreateRequest(
            name="OLT Teste Service",
            host="127.0.0.1",
            vendor=OLTVendor.INTELBRAS,
            model="8820i",
            username="admin",
            password="secretpassword",
        )
    )

    svc = BackupService(olt_repo=olt_repo, storage=storage)
    batch_res = svc.run_all_backups(purge_after=True, max_backups_per_olt=5)

    assert batch_res.total_olts >= 1
    assert batch_res.successful >= 1
    assert len(batch_res.backups) >= 1

    audits = svc.audit_all_olts()
    assert len(audits) >= 1
    assert any(a.olt_id == olt.id for a in audits)


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_api_backups_dr_endpoints(mock_get_driver, client: TestClient):
    mock_driver = MagicMock()
    mock_driver.backup_config.return_value = "system-config backup data content..."
    mock_get_driver.return_value = mock_driver

    headers = {"X-API-Key": settings.API_KEY}

    # 1. Cria OLT
    res_olt = client.post(
        "/api/v1/olts",
        headers=headers,
        json={
            "name": "OLT DR Unit Test",
            "host": "10.10.10.50",
            "vendor": "intelbras",
            "model": "8820i",
            "username": "admin",
            "password": "secretpassword",
        },
    )
    assert res_olt.status_code == 201
    olt_id = res_olt.json()["id"]

    # 2. Dispara dois backups via API
    res_b1 = client.post(f"/api/v1/olts/{olt_id}/backups", headers=headers)
    assert res_b1.status_code == 201
    b1_id = res_b1.json()["backup_id"]

    res_b2 = client.post(f"/api/v1/olts/{olt_id}/backups", headers=headers)
    assert res_b2.status_code == 201
    b2_id = res_b2.json()["backup_id"]

    # 3. GET /{olt_id}/backups/audit
    res_audit = client.get(f"/api/v1/olts/{olt_id}/backups/audit", headers=headers)
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert audit_data["olt_id"] == olt_id
    assert audit_data["total_backups"] >= 2
    assert audit_data["latest_backup"]["backup_id"] == b2_id

    # 4. GET /{olt_id}/backups/compare
    res_diff = client.get(
        f"/api/v1/olts/{olt_id}/backups/compare?base_id={b1_id}&target_id={b2_id}",
        headers=headers,
    )
    assert res_diff.status_code == 200
    diff_data = res_diff.json()
    assert diff_data["identical"] is True
    assert diff_data["base_sha256"] == diff_data["target_sha256"]

    # 5. POST /{olt_id}/backups/purge
    res_purge = client.post(
        f"/api/v1/olts/{olt_id}/backups/purge",
        headers=headers,
        json={"max_backups_per_olt": 1},
    )
    assert res_purge.status_code == 200
    purge_data = res_purge.json()
    assert purge_data["deleted_count"] >= 1

    # 6. Global Endpoints
    res_run_all = client.post("/api/v1/backups/run-all", headers=headers)
    assert res_run_all.status_code == 200
    assert res_run_all.json()["successful"] >= 1

    res_audit_all = client.get("/api/v1/backups/audit-all", headers=headers)
    assert res_audit_all.status_code == 200
    assert isinstance(res_audit_all.json(), list)

    res_purge_all = client.post("/api/v1/backups/purge-all", headers=headers, json={"max_backups_per_olt": 5})
    assert res_purge_all.status_code == 200
    assert "deleted_count" in res_purge_all.json()

