from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.drivers.fiberhome.fiberhome_tl1 import FiberhomeTL1Driver
from app.drivers.vsol.vsol_v1600 import VSOLV1600Driver
from app.models.onu import ONUDetails, ONUSummary
from app.models.provision import ONUActionResponse


# ---------------------------------------------------------------------------
# Testes de Endpoints REST & HATEOAS
# ---------------------------------------------------------------------------

@patch("app.drivers.factory.DriverFactory.get_driver")
def test_deprovision_onu_endpoint(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.deprovision_onu.return_value = ONUActionResponse(
        success=True,
        action="deprovision",
        olt_id=str(sample_olt_8820.id),
        serial="INCL12345678",
        port="1/1",
        onu_id=1,
        message="ONU desprovisionada com sucesso.",
    )
    mock_get_driver.return_value = mock_driver

    response = client.delete(
        f"/api/v1/olts/{sample_olt_8820.id}/onus/INCL12345678?port=1/1&onu_id=1",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["action"] == "deprovision"
    assert data["serial"] == "INCL12345678"

    # HATEOAS Links
    links = data["_links"]
    assert "unauthorized_onus" in links
    assert links["unauthorized_onus"]["href"] == f"/api/v1/olts/{sample_olt_8820.id}/unauthorized"
    assert "port_onus" in links
    assert "olt" in links


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_reboot_onu_endpoint(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.reboot_onu.return_value = ONUActionResponse(
        success=True,
        action="reboot",
        olt_id=str(sample_olt_8820.id),
        serial="INCL12345678",
        port="1/1",
        onu_id=1,
        message="ONU reiniciada com sucesso.",
    )
    mock_get_driver.return_value = mock_driver

    response = client.post(
        f"/api/v1/olts/{sample_olt_8820.id}/onus/INCL12345678/reboot?port=1/1&onu_id=1",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "reboot"
    links = data["_links"]
    assert "details" in links
    assert links["details"]["href"] == f"/api/v1/olts/{sample_olt_8820.id}/onus/INCL12345678"
    assert "olt" in links


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_suspend_onu_endpoint(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.suspend_onu.return_value = ONUActionResponse(
        success=True,
        action="suspend",
        olt_id=str(sample_olt_8820.id),
        serial="INCL12345678",
        port="1/1",
        onu_id=1,
        message="ONU suspensa administrativamente.",
    )
    mock_get_driver.return_value = mock_driver

    response = client.post(
        f"/api/v1/olts/{sample_olt_8820.id}/onus/INCL12345678/suspend?port=1/1&onu_id=1",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "suspend"
    links = data["_links"]
    assert "resume" in links
    assert "details" in links
    assert "deprovision" in links
    assert "resume" in links["resume"]["href"]


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_resume_onu_endpoint(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.resume_onu.return_value = ONUActionResponse(
        success=True,
        action="resume",
        olt_id=str(sample_olt_8820.id),
        serial="INCL12345678",
        port="1/1",
        onu_id=1,
        message="ONU reativada com sucesso.",
    )
    mock_get_driver.return_value = mock_driver

    response = client.post(
        f"/api/v1/olts/{sample_olt_8820.id}/onus/INCL12345678/resume?port=1/1&onu_id=1",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "resume"
    links = data["_links"]
    assert "details" in links
    assert "suspend" in links
    assert "reboot" in links


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_onu_details_contains_hateoas_shortcuts(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.get_onu_details.return_value = ONUDetails(
        port="1/1",
        onu_id=1,
        serial="INCL12345678",
        status="online",
        rx_power_dbm=-19.5,
        tx_power_dbm=2.3,
    )
    mock_get_driver.return_value = mock_driver

    response = client.get(
        f"/api/v1/olts/{sample_olt_8820.id}/onus/INCL12345678",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "_links" in data
    links = data["_links"]
    assert "reboot" in links
    assert "suspend" in links
    assert "resume" in links
    assert "deprovision" in links
    assert "port_onus" in links


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_port_onus_contains_hateoas_shortcuts(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.get_port_onus.return_value = [
        ONUSummary(port="1/1", onu_id=1, serial="INCL12345678", status="online"),
    ]
    mock_get_driver.return_value = mock_driver

    response = client.get(
        f"/api/v1/olts/{sample_olt_8820.id}/ports/1/1/onus",
        headers=auth_headers,
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert "_links" in items[0]
    assert "details" in items[0]["_links"]
    assert "reboot" in items[0]["_links"]
    assert "suspend" in items[0]["_links"]


# ---------------------------------------------------------------------------
# Testes Unitários de Drivers (Geração de Comandos por Fabricante)
# ---------------------------------------------------------------------------

def test_fiberhome_tl1_driver_actions(sample_olt_8820):
    driver = FiberhomeTL1Driver()
    with patch.object(driver, "_execute_tl1_commands", return_value="COMPLD") as mock_exec:
        driver.deprovision_onu(sample_olt_8820, "FHTT12345678", port="1/3", onu_id=7)
        mock_exec.assert_called_with(sample_olt_8820, ["DEL-ONU::OLTID=1,PONID=3,ONUID=7:1::;"])

        driver.reboot_onu(sample_olt_8820, "FHTT12345678", port="1/3", onu_id=7)
        mock_exec.assert_called_with(sample_olt_8820, ["RESET-ONU::OLTID=1,PONID=3,ONUID=7:1::;"])

        driver.suspend_onu(sample_olt_8820, "FHTT12345678", port="1/3", onu_id=7)
        mock_exec.assert_called_with(sample_olt_8820, ["SET-ONU::OLTID=1,PONID=3,ONUID=7:1::ADMINSTATUS=DOWN;"])

        driver.resume_onu(sample_olt_8820, "FHTT12345678", port="1/3", onu_id=7)
        mock_exec.assert_called_with(sample_olt_8820, ["SET-ONU::OLTID=1,PONID=3,ONUID=7:1::ADMINSTATUS=UP;"])


def test_vsol_v1600_driver_actions(sample_olt_8820):
    driver = VSOLV1600Driver()
    with patch.object(driver, "_execute_cli_commands", return_value="OK") as mock_exec:
        driver.deprovision_onu(sample_olt_8820, "VSOL12345678", port="0/4", onu_id=3)
        mock_exec.assert_called_with(
            sample_olt_8820,
            ["configure terminal", "interface gpon 0/4", "no onu 3", "exit", "exit", "write"],
        )

        driver.reboot_onu(sample_olt_8820, "VSOL12345678", port="0/4", onu_id=3)
        mock_exec.assert_called_with(
            sample_olt_8820,
            ["configure terminal", "interface gpon 0/4", "onu 3 reboot", "exit", "exit"],
        )

        driver.suspend_onu(sample_olt_8820, "VSOL12345678", port="0/4", onu_id=3)
        mock_exec.assert_called_with(
            sample_olt_8820,
            ["configure terminal", "interface gpon 0/4", "onu 3 disable", "exit", "exit", "write"],
        )

        driver.resume_onu(sample_olt_8820, "VSOL12345678", port="0/4", onu_id=3)
        mock_exec.assert_called_with(
            sample_olt_8820,
            ["configure terminal", "interface gpon 0/4", "onu 3 enable", "exit", "exit", "write"],
        )
