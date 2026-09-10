from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.uuid import is_valid_uuid7
from app.models.onu import ONUDetails, ONUSummary, UnauthorizedONU
from app.models.provision import ProvisionResponse


def test_healthcheck_is_public(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_auth_required_for_protected_endpoints(client: TestClient):
    # Sem header X-API-Key
    response = client.get("/api/v1/olts")
    assert response.status_code == 401

    # Com chave inválida
    response = client.get("/api/v1/olts", headers={"X-API-Key": "invalid_key"})
    assert response.status_code == 401


def test_create_and_list_olts(client: TestClient, auth_headers):
    payload = {
        "name": "OLT-CENTRAL-01",
        "vendor": "intelbras",
        "model": "8820",
        "host": "192.168.10.1",
        "port": 22,
        "protocol": "ssh",
        "username": "admin",
        "password": "super_secret_password",
    }
    response = client.post("/api/v1/olts", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()

    # Validações estruturais e de segurança
    assert is_valid_uuid7(data["id"]) is True
    assert data["name"] == "OLT-CENTRAL-01"
    assert "password" not in data  # SEGURANÇA: Senha nunca deve ser vazada na resposta

    # Listar OLTs
    list_response = client.get("/api/v1/olts", headers=auth_headers)
    assert list_response.status_code == 200
    items = list_response.json()
    assert any(item["id"] == data["id"] for item in items)


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_get_olt_config(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.get_running_config.return_value = "! Intelbras 8820 running-config\ninterface gpon-olt_1/1\nexit\n"
    mock_get_driver.return_value = mock_driver

    response = client.get(f"/api/v1/olts/{sample_olt_8820.id}/config", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["olt_id"] == sample_olt_8820.id
    assert "Intelbras 8820 running-config" in data["config_text"]


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_backup_flow_create_list_download(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.backup_config.return_value = "system-config backup data content..."
    mock_get_driver.return_value = mock_driver

    # 1. Disparar backup
    backup_res = client.post(f"/api/v1/olts/{sample_olt_8820.id}/backups", headers=auth_headers)
    assert backup_res.status_code == 201
    meta = backup_res.json()

    assert is_valid_uuid7(meta["backup_id"]) is True
    assert meta["olt_id"] == sample_olt_8820.id
    assert len(meta["sha256_hash"]) == 64
    assert meta["size_bytes"] > 0

    backup_id = meta["backup_id"]

    # 2. Listar backups
    list_res = client.get(f"/api/v1/olts/{sample_olt_8820.id}/backups", headers=auth_headers)
    assert list_res.status_code == 200
    assert any(b["backup_id"] == backup_id for b in list_res.json())

    # 3. Download do arquivo
    down_res = client.get(f"/api/v1/olts/{sample_olt_8820.id}/backups/{backup_id}/download", headers=auth_headers)
    assert down_res.status_code == 200
    assert down_res.content == b"system-config backup data content..."


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_list_port_onus(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.get_port_onus.return_value = [
        ONUSummary(port="1/1", onu_id=1, serial="INCL12345678", status="online", name="Cliente_01")
    ]
    mock_get_driver.return_value = mock_driver

    response = client.get(f"/api/v1/olts/{sample_olt_8820.id}/ports/1/1/onus", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["serial"] == "INCL12345678"
    assert data[0]["status"] == "online"


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_get_onu_details(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.get_onu_details.return_value = ONUDetails(
        port="1/1",
        onu_id=1,
        serial="INCL12345678",
        status="online",
        rx_power_dbm=-19.45,
        tx_power_dbm=2.10,
        vlan=100,
    )
    mock_get_driver.return_value = mock_driver

    response = client.get(f"/api/v1/olts/{sample_olt_8820.id}/onus/INCL12345678", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["rx_power_dbm"] == -19.45
    assert data["status"] == "online"


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_list_unauthorized_onus(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.list_unauthorized_onus.return_value = [
        UnauthorizedONU(port="1/2", serial="INCL88990011", model="110B")
    ]
    mock_get_driver.return_value = mock_driver

    response = client.get(f"/api/v1/olts/{sample_olt_8820.id}/unauthorized", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["serial"] == "INCL88990011"


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_provision_onu_success(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.provision_onu.return_value = ProvisionResponse(
        success=True,
        port="1/1",
        onu_id=5,
        serial="INCL12345678",
        message="ONU provisionada e salva com sucesso na memória da OLT Intelbras 8820.",
    )
    mock_get_driver.return_value = mock_driver

    payload = {
        "port": "1/1",
        "serial": "INCL12345678",
        "vlan": 100,
        "profile": "PLAN_100M",
        "description": "Cliente_Joao_Silva",
    }
    response = client.post(f"/api/v1/olts/{sample_olt_8820.id}/onus", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["onu_id"] == 5


def test_provision_onu_rejects_injection(client: TestClient, auth_headers, sample_olt_8820):
    # Tentativa de injeção no serial
    payload = {
        "port": "1/1",
        "serial": "INCL; reboot;",
        "vlan": 100,
    }
    response = client.post(f"/api/v1/olts/{sample_olt_8820.id}/onus", json=payload, headers=auth_headers)
    # Validação do FastAPI / Pydantic ou Security deve rejeitar com 400/422
    assert response.status_code in [400, 422]
