from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.models.olt import OLTCreateRequest, OLTVendor, OLTProtocol


def test_create_ftp_server_success(client: TestClient, auth_headers):
    payload = {
        "name": "FTP-PROD-01",
        "host": "192.168.100.50",
        "port": 21,
        "username": "ftpuser",
        "password": "secret_password_123",
        "base_path": "/backups/olts",
        "is_global_default": False,
        "is_active": True,
    }
    response = client.post("/api/v1/ftp-servers", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "FTP-PROD-01"
    assert data["host"] == "192.168.100.50"
    assert data["port"] == 21
    assert data["username"] == "ftpuser"
    assert data["base_path"] == "/backups/olts"
    assert data["is_global_default"] is False
    assert data["is_active"] is True
    assert "id" in data
    assert len(data["id"]) == 36  # UUIDv7 length
    # Garante que a senha NUNCA é retornada na resposta pública
    assert "password" not in data
    assert "Location" in response.headers
    assert response.headers["Location"] == f"/api/v1/ftp-servers/{data['id']}"
    assert "_links" in data
    assert "self" in data["_links"]
    assert "test" in data["_links"]


def test_create_ftp_server_duplicate_name(client: TestClient, auth_headers):
    payload = {
        "name": "FTP-DUPLICATE-TEST",
        "host": "192.168.100.51",
        "username": "user1",
        "password": "pass",
    }
    resp1 = client.post("/api/v1/ftp-servers", json=payload, headers=auth_headers)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/ftp-servers", json=payload, headers=auth_headers)
    assert resp2.status_code == 409
    assert "já cadastrado" in resp2.json()["detail"]


def test_list_ftp_servers(client: TestClient, auth_headers):
    response = client.get("/api/v1/ftp-servers", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all("password" not in item for item in data)
    assert all("_links" in item for item in data)


def test_get_and_update_and_delete_ftp_server(client: TestClient, auth_headers):
    # 1. Cria
    create_payload = {
        "name": "FTP-CRUD-TEST",
        "host": "10.0.0.10",
        "username": "tempuser",
        "password": "temppassword",
    }
    c_resp = client.post("/api/v1/ftp-servers", json=create_payload, headers=auth_headers)
    assert c_resp.status_code == 201
    ftp_id = c_resp.json()["id"]

    # 2. Get
    g_resp = client.get(f"/api/v1/ftp-servers/{ftp_id}", headers=auth_headers)
    assert g_resp.status_code == 200
    assert g_resp.json()["name"] == "FTP-CRUD-TEST"

    # 3. Update
    u_resp = client.put(
        f"/api/v1/ftp-servers/{ftp_id}",
        json={"name": "FTP-CRUD-UPDATED", "is_global_default": True},
        headers=auth_headers,
    )
    assert u_resp.status_code == 200
    assert u_resp.json()["name"] == "FTP-CRUD-UPDATED"
    assert u_resp.json()["is_global_default"] is True

    # 4. Delete
    d_resp = client.delete(f"/api/v1/ftp-servers/{ftp_id}", headers=auth_headers)
    assert d_resp.status_code == 204

    # 5. Get após delete retorna 404
    g2_resp = client.get(f"/api/v1/ftp-servers/{ftp_id}", headers=auth_headers)
    assert g2_resp.status_code == 404


def test_bind_olt_to_ftp_and_resolve_destinations(client: TestClient, auth_headers, setup_test_env):
    olt_repo = setup_test_env["repo"]
    olt = olt_repo.create(
        OLTCreateRequest(
            name="OLT-MULTI-FTP",
            vendor=OLTVendor.FIBERHOME,
            model="AN5516-01",
            host="172.16.0.10",
            port=23,
            protocol=OLTProtocol.TELNET,
            username="noc",
            password="pwd",
        )
    )

    # 1. Cria FTP Específico
    ftp_spec = client.post(
        "/api/v1/ftp-servers",
        json={
            "name": "FTP-ESPECIFICO-OLT",
            "host": "10.10.10.1",
            "username": "user_spec",
            "password": "pwd",
            "is_global_default": False,
        },
        headers=auth_headers,
    ).json()

    # 2. Cria FTP Global
    ftp_glob = client.post(
        "/api/v1/ftp-servers",
        json={
            "name": "FTP-GLOBAL-DEFAULT",
            "host": "10.10.10.2",
            "username": "user_glob",
            "password": "pwd",
            "is_global_default": True,
        },
        headers=auth_headers,
    ).json()

    # 3. Vincula o FTP específico à OLT
    bind_resp = client.post(
        f"/api/v1/olts/{olt.id}/ftp-servers",
        json={"ftp_server_ids": [ftp_spec["id"]]},
        headers=auth_headers,
    )
    assert bind_resp.status_code == 200
    data = bind_resp.json()

    assert data["olt_id"] == olt.id
    # Destinos específicos contém o FTP específico
    spec_ids = [s["id"] for s in data["specific_destinations"]]
    assert ftp_spec["id"] in spec_ids

    # Destinos globais contém o FTP global
    glob_ids = [s["id"] for s in data["global_destinations"]]
    assert ftp_glob["id"] in glob_ids

    # Destinos efetivos contém AMBOS
    eff_ids = [s["id"] for s in data["effective_destinations"]]
    assert ftp_spec["id"] in eff_ids
    assert ftp_glob["id"] in eff_ids
    assert len(eff_ids) >= 2


def test_test_ftp_server_connection_mock(client: TestClient, auth_headers):
    # Cria servidor para teste
    c_resp = client.post(
        "/api/v1/ftp-servers",
        json={
            "name": "FTP-MOCK-TEST",
            "host": "10.0.0.99",
            "port": 21,
            "username": "testuser",
            "password": "secretpassword",
        },
        headers=auth_headers,
    )
    ftp_id = c_resp.json()["id"]

    # Caso Sucesso Mockado
    with patch("ftplib.FTP") as mock_ftp_class:
        mock_ftp = MagicMock()
        mock_ftp.getwelcome.return_value = "220 Proserv FTP Ready"
        mock_ftp.pwd.return_value = "/backups"
        mock_ftp_class.return_value = mock_ftp

        test_resp = client.post(f"/api/v1/ftp-servers/{ftp_id}/test", headers=auth_headers)
        assert test_resp.status_code == 200
        res = test_resp.json()
        assert res["success"] is True
        assert res["banner"] == "220 Proserv FTP Ready"
        assert res["working_directory"] == "/backups"
        assert "latency_ms" in res

    # Caso Falha de Conexão Mockado
    with patch("ftplib.FTP") as mock_ftp_class:
        mock_ftp = MagicMock()
        mock_ftp.connect.side_effect = ConnectionRefusedError("Connection refused by peer")
        mock_ftp_class.return_value = mock_ftp

        test_resp = client.post(f"/api/v1/ftp-servers/{ftp_id}/test", headers=auth_headers)
        assert test_resp.status_code == 200
        res = test_resp.json()
        assert res["success"] is False
        assert "Connection refused" in res["message"]
