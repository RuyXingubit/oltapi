from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.models.hateoas import Link
from app.models.olt import ConnectionTestResult
from app.models.onu import UnauthorizedONU
from app.models.provision import ProvisionResponse


def test_hateoas_create_olt_online_flow(client: TestClient, auth_headers):
    """Testa o fluxo guiado quando a OLT é cadastrada e a porta está acessível (status online)."""
    fake_conn = ConnectionTestResult(
        olt_id="0191e4f2-51a8-7d84-a12b-3456789abcde",
        host="192.168.1.1",
        port=22,
        reachable=True,
        latency_ms=12.4,
        message="Porta 22 acessível em 192.168.1.1. Latência de handshake: 12.4ms.",
        links={
            "self": Link(href="/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde", method="GET"),
            "config": Link(href="/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/config", method="GET"),
            "unauthorized_onus": Link(href="/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/unauthorized", method="GET"),
            "backups": Link(href="/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/backups", method="GET"),
        },
    )

    with patch("app.api.v1.endpoints_olts.test_olt_connectivity", new=AsyncMock(return_value=fake_conn)):
        payload = {
            "name": "OLT-POP-HATEOAS-01",
            "vendor": "vsol",
            "model": "v1600gt",
            "host": "192.168.1.1",
            "port": 22,
            "protocol": "ssh",
            "username": "admin",
            "password": "secret_password",
        }

        resp = client.post("/api/v1/olts", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        
        data = resp.json()
        olt_id = data["id"]
        
        # Validação do cabeçalho Location conforme RFC 9110
        assert resp.headers.get("Location") == f"/api/v1/olts/{olt_id}"
        
        # Validação do status e dos links HATEOAS contextuais para OLT online
        assert data["status"] == "online"
        assert "_links" in data
        links = data["_links"]
        assert "self" in links
        assert "config" in links
        assert "unauthorized_onus" in links
        assert "backups" in links


def test_hateoas_create_olt_unreachable_flow(client: TestClient, auth_headers):
    """Testa o fluxo guiado quando a OLT é cadastrada mas a conexão falha (status unreachable)."""
    fake_conn = ConnectionTestResult(
        olt_id="0191e4f2-51a8-7d84-a12b-999999999999",
        host="10.255.255.1",
        port=22,
        reachable=False,
        latency_ms=None,
        message="Timeout (1500ms) ao conectar em 10.255.255.1:22. Verifique firewall ou rota.",
        links={
            "self": Link(href="/api/v1/olts/0191e4f2-51a8-7d84-a12b-999999999999", method="GET"),
            "test_connection": Link(href="/api/v1/olts/0191e4f2-51a8-7d84-a12b-999999999999/test-connection", method="POST"),
            "edit_olt": Link(href="/api/v1/olts/0191e4f2-51a8-7d84-a12b-999999999999", method="PUT"),
        },
    )

    with patch("app.api.v1.endpoints_olts.test_olt_connectivity", new=AsyncMock(return_value=fake_conn)):
        payload = {
            "name": "OLT-POP-OFFLINE-01",
            "vendor": "zte",
            "model": "c300",
            "host": "10.255.255.1",
            "port": 22,
            "protocol": "ssh",
            "username": "admin",
            "password": "wrong_password",
        }

        resp = client.post("/api/v1/olts", json=payload, headers=auth_headers)
        assert resp.status_code == 201

        data = resp.json()
        olt_id = data["id"]
        assert resp.headers.get("Location") == f"/api/v1/olts/{olt_id}"
        assert data["status"] == "unreachable"
        assert "Timeout" in data["connection_message"]

        # O HATEOAS deve guiar para editar ou retestar
        links = data["_links"]
        assert "test_connection" in links
        assert "edit_olt" in links
        assert "config" not in links  # Não sugere ler config se está offline


def test_hateoas_get_olt_by_id(client: TestClient, auth_headers):
    """Testa a consulta da OLT por ID e a presença de links de navegação."""
    fake_conn = ConnectionTestResult(
        olt_id="teste", host="127.0.0.1", port=22, reachable=True, message="OK", links={}
    )
    with patch("app.api.v1.endpoints_olts.test_olt_connectivity", new=AsyncMock(return_value=fake_conn)):
        create_resp = client.post(
            "/api/v1/olts",
            json={
                "name": "OLT-GET-TEST",
                "vendor": "intelbras",
                "model": "8820",
                "host": "192.168.20.1",
                "username": "admin",
                "password": "123",
            },
            headers=auth_headers,
        )
        olt_id = create_resp.json()["id"]

    resp = client.get(f"/api/v1/olts/{olt_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == olt_id
    assert "_links" in data
    links = data["_links"]
    assert links["self"]["href"] == f"/api/v1/olts/{olt_id}"
    assert links["config"]["href"] == f"/api/v1/olts/{olt_id}/config"
    assert links["test_connection"]["href"] == f"/api/v1/olts/{olt_id}/test-connection"


def test_hateoas_test_connection_endpoint(client: TestClient, auth_headers):
    """Testa o endpoint POST /api/v1/olts/{id}/test-connection."""
    fake_conn = ConnectionTestResult(
        olt_id="teste", host="127.0.0.1", port=22, reachable=True, latency_ms=5.2, message="Porta 22 acessível.", links={}
    )
    with patch("app.api.v1.endpoints_olts.test_olt_connectivity", new=AsyncMock(return_value=fake_conn)):
        create_resp = client.post(
            "/api/v1/olts",
            json={
                "name": "OLT-CONN-TEST",
                "vendor": "fiberhome",
                "model": "an5516",
                "host": "10.0.0.1",
                "username": "admin",
                "password": "123",
            },
            headers=auth_headers,
        )
        olt_id = create_resp.json()["id"]

        test_resp = client.post(f"/api/v1/olts/{olt_id}/test-connection", headers=auth_headers)
        assert test_resp.status_code == 200
        res_data = test_resp.json()
        assert res_data["reachable"] is True
        assert res_data["latency_ms"] == 5.2
        assert "_links" in res_data


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_hateoas_unauthorized_onus_has_provision_link(mock_get_driver, client: TestClient, auth_headers):
    """Testa se cada ONU não autorizada vem acompanhada do link direto para provisionamento."""
    mock_driver = MagicMock()
    mock_driver.list_unauthorized_onus.return_value = [
        UnauthorizedONU(port="1/2", serial="VSOL12345678", model="V2801SG")
    ]
    mock_get_driver.return_value = mock_driver

    fake_conn = ConnectionTestResult(
        olt_id="teste", host="127.0.0.1", port=22, reachable=True, message="OK", links={}
    )
    with patch("app.api.v1.endpoints_olts.test_olt_connectivity", new=AsyncMock(return_value=fake_conn)):
        create_resp = client.post(
            "/api/v1/olts",
            json={
                "name": "OLT-UNAUTH-TEST",
                "vendor": "vsol",
                "model": "v1600gt",
                "host": "10.0.0.2",
                "username": "admin",
                "password": "123",
            },
            headers=auth_headers,
        )
        olt_id = create_resp.json()["id"]

    resp = client.get(f"/api/v1/olts/{olt_id}/unauthorized", headers=auth_headers)
    assert resp.status_code == 200
    onus = resp.json()
    assert len(onus) > 0
    for onu in onus:
        assert "_links" in onu
        assert "provision" in onu["_links"]
        assert onu["_links"]["provision"]["href"] == f"/api/v1/olts/{olt_id}/onus"
        assert onu["_links"]["provision"]["method"] == "POST"


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_hateoas_provision_onu_response_and_location(mock_get_driver, client: TestClient, auth_headers):
    """Testa se ao autorizar uma ONU, retorna o header Location e links de diagnóstico da ONU."""
    mock_driver = MagicMock()
    mock_driver.provision_onu.return_value = ProvisionResponse(
        success=True,
        port="1/1/1",
        onu_id=1,
        serial="ZTEG12345678",
        message="ONU provisionada com sucesso",
    )
    mock_get_driver.return_value = mock_driver

    fake_conn = ConnectionTestResult(
        olt_id="teste", host="127.0.0.1", port=22, reachable=True, message="OK", links={}
    )
    with patch("app.api.v1.endpoints_olts.test_olt_connectivity", new=AsyncMock(return_value=fake_conn)):
        create_resp = client.post(
            "/api/v1/olts",
            json={
                "name": "OLT-PROV-TEST",
                "vendor": "zte",
                "model": "c300",
                "host": "10.0.0.3",
                "username": "admin",
                "password": "123",
            },
            headers=auth_headers,
        )
        olt_id = create_resp.json()["id"]

    prov_payload = {
        "port": "1/1/1",
        "serial": "ZTEG12345678",
        "vlan": 100,
        "description": "Cliente_HATEOAS",
    }
    resp = client.post(f"/api/v1/olts/{olt_id}/onus", json=prov_payload, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.headers.get("Location") == f"/api/v1/olts/{olt_id}/onus/ZTEG12345678"
    
    data = resp.json()
    assert data["success"] is True
    assert "_links" in data
    links = data["_links"]
    assert "details" in links
    assert links["details"]["href"] == f"/api/v1/olts/{olt_id}/onus/ZTEG12345678"
    assert "port_onus" in links


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_hateoas_backup_trigger_response_and_location(mock_get_driver, client: TestClient, auth_headers):
    """Testa se a geração de backup retorna o header Location para download e links de diff e audit."""
    mock_driver = MagicMock()
    mock_driver.backup_config.return_value = "system-config backup data content..."
    mock_get_driver.return_value = mock_driver

    fake_conn = ConnectionTestResult(
        olt_id="teste", host="127.0.0.1", port=22, reachable=True, message="OK", links={}
    )
    with patch("app.api.v1.endpoints_olts.test_olt_connectivity", new=AsyncMock(return_value=fake_conn)):
        create_resp = client.post(
            "/api/v1/olts",
            json={
                "name": "OLT-BACKUP-TEST",
                "vendor": "intelbras",
                "model": "8820",
                "host": "10.0.0.4",
                "username": "admin",
                "password": "123",
            },
            headers=auth_headers,
        )
        olt_id = create_resp.json()["id"]

    resp = client.post(f"/api/v1/olts/{olt_id}/backups", headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    backup_id = data["backup_id"]

    assert resp.headers.get("Location") == f"/api/v1/olts/{olt_id}/backups/{backup_id}/download"
    assert "_links" in data
    links = data["_links"]
    assert "download" in links
    assert "compare" in links
    assert "audit" in links
    assert links["download"]["href"] == f"/api/v1/olts/{olt_id}/backups/{backup_id}/download"
