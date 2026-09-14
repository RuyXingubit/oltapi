"""
Testes unitários para o Raio-X da OLT, Visão Geral de FTP e Métricas de VLANs com Histórico de Seriais.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.core.uuid import generate_uuid7
from app.models.olt import OLTCreateRequest, OLTInDB, OLTProtocol, OLTVendor
from app.models.onu import ONUSummary
from app.models.vlan import VLANItem
from app.storage.sql.olt_repository import SQLOLTRepository


@pytest.fixture
def sample_olt_xray(setup_test_env) -> OLTInDB:
    repo: SQLOLTRepository = setup_test_env["repo"]
    olt_req = OLTCreateRequest(
        name=f"OLT-TEST-XRAY-{generate_uuid7()}",
        vendor=OLTVendor.FIBERHOME,
        model="an5516-01",
        host="192.168.10.1",
        port=23,
        protocol=OLTProtocol.TELNET,
        username="admin",
        password="secretpassword",
    )
    with patch("app.services.connection_service.test_olt_connectivity") as mock_conn:
        mock_conn.return_value = MagicMock(reachable=True, message="Conexão OK", links={})
        return repo.create(olt_req)


def test_ftp_overview_endpoint(client: TestClient, auth_headers):
    """Testa o endpoint GET /api/v1/ftp-servers/overview."""
    res = client.get("/api/v1/ftp-servers/overview", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    assert "source" in data
    assert "bound_olts" in data
    assert isinstance(data["bound_olts"], list)


def test_olt_xray_endpoint(client: TestClient, auth_headers, sample_olt_xray):
    """Testa o endpoint POST /api/v1/olts/{olt_id}/xray."""
    mock_onus = [
        ONUSummary(serial="FHTT12345678", port="0/1/1", onu_id=1, status="ACTIVE", name="Cliente 1"),
        ONUSummary(serial="FHTT87654321", port="0/1/1", onu_id=2, status="ACTIVE", name="Cliente 2"),
        ONUSummary(serial="FHTT99887766", port="0/1/2", onu_id=1, status="ACTIVE", name="Cliente 3"),
    ]
    mock_vlans = [
        VLANItem(vlan_id=100, name="INTERNET", tagged_ports=["xg 0/0/1"]),
        VLANItem(vlan_id=200, name="IPTV", tagged_ports=["xg 0/0/1"]),
    ]

    with patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory:
        mock_driver = MagicMock()
        mock_driver.get_running_config.return_value = "! Software Version: V200R019\n! uptime is 20 weeks, 3 days\ninterface gpon 0/1/1\n"
        mock_driver.list_all_authorized_onus.return_value = mock_onus
        mock_driver.list_vlans.return_value = mock_vlans
        mock_factory.return_value = mock_driver

        res = client.post(f"/api/v1/olts/{sample_olt_xray.id}/xray", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["olt_id"] == sample_olt_xray.id
        assert data["total_onus_detected"] == 3
        assert len(data["ports"]) >= 8
        assert data["firmware_version"] == "V200R019"
        assert "dias" in data["uptime_human"]

        # Verifica porta com ONUs (UP) e porta vazia (DOWN)
        p1 = next((p for p in data["ports"] if p["port_id"] == "gpon 0/1/1"), None)
        assert p1 is not None
        assert p1["oper_status"] == "up"
        assert p1["onu_count"] == 2

        p_empty = next((p for p in data["ports"] if p["port_id"] == "gpon 0/1/3"), None)
        assert p_empty is not None
        assert p_empty["oper_status"] == "down"
        assert p_empty["onu_count"] == 0


def test_vlan_metrics_and_history(client: TestClient, auth_headers, sample_olt_xray):
    """Testa os endpoints GET /vlans/metrics e GET /vlans/{vlan_id}/history."""
    mock_vlans = [
        VLANItem(vlan_id=100, name="INTERNET_RESIDENCIAL", description="Tráfego PPPoE"),
        VLANItem(vlan_id=200, name="VOIP", description="Telefonia SIP"),
    ]

    with patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory:
        mock_driver = MagicMock()
        mock_driver.list_vlans.return_value = mock_vlans
        mock_factory.return_value = mock_driver

        # 1. Métricas de VLANs
        res = client.get(f"/api/v1/olts/{sample_olt_xray.id}/vlans/metrics", headers=auth_headers)
        assert res.status_code == 200
        metrics = res.json()
        assert len(metrics) >= 2
        v100 = next(m for m in metrics if m["vlan_id"] == 100)
        assert v100["name"] == "INTERNET_RESIDENCIAL"
        assert "total_provisioned_onus" in v100
        assert "total_active_onus" in v100

        # 2. Histórico de Seriais da VLAN
        res_hist = client.get(f"/api/v1/olts/{sample_olt_xray.id}/vlans/100/history", headers=auth_headers)
        assert res_hist.status_code == 200
        assert isinstance(res_hist.json(), list)
