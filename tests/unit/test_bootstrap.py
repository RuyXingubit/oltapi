from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.uuid import is_valid_uuid7
from app.drivers.vsol.vsol_v1600 import VSOLV1600Driver
from app.models.bootstrap import (
    BootstrapMode,
    BootstrapRequest,
    DefaultONUMode,
)


def test_driver_bootstrap_single_vlan():
    driver = VSOLV1600Driver()
    req = BootstrapRequest(
        mode=BootstrapMode.SINGLE_VLAN,
        uplink_port="1",
        vlan=200,
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    assert "enable" in commands
    assert "configure terminal" in commands
    assert "profile dba 1 dba-name DBA-DEFAULT type 4 max 1024000" in commands
    assert "profile line 1 line-name LINE-DEFAULT" in commands
    assert "gem mapping 1 1 vlan 200" in commands
    assert "vlan 200" in commands
    assert "interface ge 0/1" in commands
    assert "switchport trunk allowed vlan add 200" in commands
    assert "ont-autofind enable" in commands
    assert "write" in commands


def test_driver_bootstrap_vlan_per_pon():
    driver = VSOLV1600Driver()
    req = BootstrapRequest(
        mode=BootstrapMode.VLAN_PER_PON,
        uplink_port="2",
        vlan_per_pon={"1": 101, "2": 102, "3": 103, "4": 104, "5": 105, "6": 106, "7": 107, "8": 108},
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    assert "vlan 101" in commands
    assert "vlan 108" in commands
    assert "interface ge 0/2" in commands
    assert "switchport trunk allowed vlan add 101" in commands
    assert "switchport trunk allowed vlan add 108" in commands
    assert "ont-autofind enable" in commands
    assert "write" in commands


def test_driver_bootstrap_sanitization_rejection():
    driver = VSOLV1600Driver()

    # Tentativa de injeção na porta de uplink
    req_bad_port = BootstrapRequest(uplink_port="1; reboot;")
    with pytest.raises(ValueError):
        driver.generate_bootstrap_commands(req_bad_port)


def test_api_bootstrap_preview(client: TestClient, auth_headers, sample_olt_8820):
    payload = {
        "mode": "single_vlan",
        "uplink_port": "1",
        "vlan": 100,
        "default_onu_mode": "router",
    }
    response = client.post(f"/api/v1/olts/{sample_olt_8820.id}/bootstrap/preview", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["olt_id"] == sample_olt_8820.id
    assert data["mode"] == "single_vlan"
    assert len(data["commands"]) > 10
    assert "switchport trunk allowed vlan add 100" in data["script_text"]


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_api_bootstrap_apply_success(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.apply_bootstrap.return_value = 25
    mock_driver.backup_config.return_value = "! post-bootstrap configuration"
    mock_get_driver.return_value = mock_driver

    payload = {
        "mode": "single_vlan",
        "uplink_port": "1",
        "vlan": 150,
        "default_onu_mode": "router",
    }
    response = client.post(f"/api/v1/olts/{sample_olt_8820.id}/bootstrap/apply", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["olt_id"] == sample_olt_8820.id
    assert is_valid_uuid7(data["backup_id"]) is True
    assert data["total_commands_executed"] == 25
    assert "sucesso" in data["message"].lower()


def test_api_bootstrap_olt_not_found(client: TestClient, auth_headers):
    random_uuid = "0191e4f2-51a8-7d84-a12b-000000000000"
    payload = {"mode": "single_vlan", "uplink_port": "1", "vlan": 100}
    response = client.post(f"/api/v1/olts/{random_uuid}/bootstrap/preview", json=payload, headers=auth_headers)
    assert response.status_code == 404
