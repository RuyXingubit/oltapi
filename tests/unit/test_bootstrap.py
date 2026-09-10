from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.uuid import is_valid_uuid7
from app.drivers.intelbras.intelbras_8820 import Intelbras8820Driver
from app.models.bootstrap import (
    BootstrapMode,
    BootstrapRequest,
    DefaultONUMode,
)


def test_driver_bootstrap_single_vlan():
    driver = Intelbras8820Driver()
    req = BootstrapRequest(
        mode=BootstrapMode.SINGLE_VLAN,
        uplink_port="1",
        vlan=200,
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    assert "enable" in commands
    assert "config" in commands
    assert "bridge add 1 downlink vlan 200 tagged" in commands
    assert "bridge-profile add default downlink vlan 200 tagged eth 1" in commands
    assert "bridge-profile add default-router downlink vlan 200 tagged router" in commands

    # Binds Intelbras
    assert "bridge-profile bind add default device intelbras-110b" in commands
    assert "bridge-profile bind add default-router device intelbras-121w" in commands
    assert "bridge-profile bind add default-router device intelbras-ax1800v" in commands

    # Ativação do auto-service
    assert "onu set auto" in commands
    assert "auto-service enable" in commands
    assert "write" in commands


def test_driver_bootstrap_vlan_per_pon():
    driver = Intelbras8820Driver()
    req = BootstrapRequest(
        mode=BootstrapMode.VLAN_PER_PON,
        uplink_port="2",
        vlan_per_pon={"1": 101, "2": 102, "3": 103, "4": 104, "5": 105, "6": 106, "7": 107, "8": 108},
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    assert "bridge add 2 downlink vlan 101 tagged" in commands
    assert "bridge add 2 downlink vlan 108 tagged" in commands
    assert "bridge-profile add gpon1-default downlink vlan 101 tagged eth 1" in commands
    assert "bridge-profile add gpon8-default-router downlink vlan 108 tagged router" in commands
    assert "bridge-profile bind add gpon1-default device intelbras-110b gpon 1" in commands
    assert "bridge-profile bind add gpon8-default-router device intelbras-ax1800v gpon 8" in commands


def test_driver_bootstrap_sanitization_rejection():
    driver = Intelbras8820Driver()

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
    assert "bridge add 1 downlink vlan 100 tagged" in data["script_text"]


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
