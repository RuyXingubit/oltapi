from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.drivers.factory import DriverFactory
from app.drivers.fiberhome.fiberhome_tl1 import FiberhomeTL1Driver
from app.models.bootstrap import (
    BootstrapMode,
    BootstrapRequest,
    DefaultONUMode,
)
from app.models.olt import OLTCreateRequest, OLTInDB, OLTProtocol, OLTVendor
from app.models.provision import ProvisionRequest


def test_driver_factory_resolves_fiberhome_models():
    # AN5516-01
    olt_an5516 = OLTInDB(
        name="OLT-POP-AN5516",
        vendor=OLTVendor.FIBERHOME,
        model="AN5516-01",
        host="10.0.0.10",
        port=3337,
        protocol=OLTProtocol.TELNET,
        username="admin",
        password="pwd",
    )
    driver_an5516 = DriverFactory.get_driver(olt_an5516)
    assert isinstance(driver_an5516, FiberhomeTL1Driver)

    # AN6000
    olt_an6000 = OLTInDB(
        name="OLT-CORE-AN6000",
        vendor=OLTVendor.FIBERHOME,
        model="AN6000-7",
        host="10.0.0.11",
        port=3337,
        protocol=OLTProtocol.TELNET,
        username="admin",
        password="pwd",
    )
    driver_an6000 = DriverFactory.get_driver(olt_an6000)
    assert isinstance(driver_an6000, FiberhomeTL1Driver)


def test_fiberhome_port_normalization():
    driver = FiberhomeTL1Driver()
    assert driver.parse_port_components("1/2") == (1, 2)
    assert driver.parse_port_components("0/2/3") == (2, 3)
    assert driver.parse_port_components("4") == (1, 4)

    with pytest.raises(ValueError):
        driver.parse_port_components("invalid/port/format/extra")


def test_fiberhome_unregistered_onus_parser():
    driver = FiberhomeTL1Driver()
    raw_unreg = """
  IP 0
  M  1 COMPLD
  SLOTNO=1  PORTNO=1  ONUID=1  MAC=FHTT12345678  AUTHTYPE=MAC  DEVTYPE=AN5506-01-A
  SLOTNO=1  PORTNO=3  ONUID=1  MAC=FHTT87654321  AUTHTYPE=MAC  DEVTYPE=AN5506-02-B
  SLOTNO=2  PORTNO=4  ONUID=1  MAC=INCL99887766  AUTHTYPE=MAC  DEVTYPE=110B
  ;
    """
    unauth = driver.parse_unregistered_onus(raw_unreg)
    assert len(unauth) == 3
    assert unauth[0].port == "1/1"
    assert unauth[0].serial == "FHTT12345678"
    assert unauth[0].model == "AN5506-01-A"

    assert unauth[1].port == "1/3"
    assert unauth[1].serial == "FHTT87654321"
    assert unauth[1].model == "AN5506-02-B"

    assert unauth[2].port == "2/4"
    assert unauth[2].serial == "INCL99887766"
    assert unauth[2].model == "110B"


def test_fiberhome_port_onus_parser():
    driver = FiberhomeTL1Driver()
    raw_port_onus = """
  IP 0
  M  1 COMPLD
  SLOTNO=1  PORTNO=2  ONUID=1  NAME=Cliente_01  MAC=FHTT12345678  STATUS=up  RX=-19.50
  SLOTNO=1  PORTNO=2  ONUID=2  NAME=Cliente_02  MAC=FHTT87654321  STATUS=down  RX=--
  ;
    """
    onus = driver.parse_port_onus(raw_port_onus, "1/2")
    assert len(onus) == 2
    assert onus[0].port == "1/2"
    assert onus[0].onu_id == 1
    assert onus[0].serial == "FHTT12345678"
    assert onus[0].status == "online"

    assert onus[1].onu_id == 2
    assert onus[1].status == "offline"


def test_fiberhome_optical_info_parser():
    driver = FiberhomeTL1Driver()
    raw_optical = """
  IP 0
  M  1 COMPLD
  RX=-19.45  TX=2.15  VOLTAGE=3.30  BIAS=15.00
  ;
    """
    rx, tx = driver.parse_optical_info(raw_optical)
    assert rx == -19.45
    assert tx == 2.15


def test_fiberhome_bootstrap_generation():
    driver = FiberhomeTL1Driver()
    req = BootstrapRequest(
        mode=BootstrapMode.SINGLE_VLAN,
        vlan=100,
        uplink_port="1",
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    assert 'ADD-DBAPROF:::1::NAME="DBA-DEFAULT",TYPE=4,MAXBW=1024000;' in commands
    assert 'ADD-LINEPROF:::1::NAME="LINE-DEFAULT",DBANAME="DBA-DEFAULT";' in commands
    assert "ADD-VLAN:::1::VLANID=100,TYPE=SMART;" in commands
    assert "ADD-UPLINKPORTVLAN:::1::PORT=1,VLANID=100;" in commands


def test_fiberhome_bootstrap_vlan_per_pon():
    driver = FiberhomeTL1Driver()
    req = BootstrapRequest(
        mode=BootstrapMode.VLAN_PER_PON,
        vlan_per_pon={"1": 101, "2": 102},
        uplink_port="1",
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    assert 'ADD-LINEPROF:::1::NAME="LINE-PON1",DBANAME="DBA-DEFAULT";' in commands
    assert "ADD-VLAN:::1::VLANID=101,TYPE=SMART;" in commands
    assert "ADD-UPLINKPORTVLAN:::1::PORT=1,VLANID=101;" in commands


def test_fiberhome_provision_commands():
    driver = FiberhomeTL1Driver()
    olt = OLTInDB(
        name="OLT-TEST-FIBERHOME",
        vendor=OLTVendor.FIBERHOME,
        model="AN5516-01",
        host="10.0.0.10",
        port=3337,
        protocol=OLTProtocol.TELNET,
        username="admin",
        password="pwd",
    )
    req = ProvisionRequest(
        port="1/2",
        serial="FHTT12345678",
        vlan=500,
        description="Cliente_Fiberhome_1",
    )

    with patch.object(driver, "_execute_tl1_commands") as mock_exec:
        mock_exec.return_value = "M 1 COMPLD;"
        res = driver.provision_onu(olt, req)

        assert res.success is True
        assert res.port == "1/2"
        assert res.serial == "FHTT12345678"

        mock_exec.assert_called_once()
        cmds_called = mock_exec.call_args[0][1]
        assert any('ADD-ONU::OLTID=1,PONID=2:1::NAME="Cliente_Fiberhome_1",AUTHTYPE=MAC,MAC=FHTT12345678' in c for c in cmds_called)
        assert any("CFG-LANPORTVLAN::OLTID=1,PONID=2,ONUID=1:1::PORT=1,MODE=TAG,VLAN=500;" in c for c in cmds_called)


def test_api_fiberhome_bootstrap_preview(client: TestClient, auth_headers, setup_test_env):
    repo = setup_test_env["repo"]
    req = OLTCreateRequest(
        name="OLT-TESTE-AN5516",
        vendor=OLTVendor.FIBERHOME,
        model="AN5516-01",
        host="10.0.0.100",
        port=3337,
        protocol=OLTProtocol.TELNET,
        username="admin",
        password="pwd",
    )
    fh_olt = repo.create(req)

    payload = {
        "mode": "single_vlan",
        "vlan": 500,
        "uplink_port": "1",
    }
    res = client.post(f"/api/v1/olts/{fh_olt.id}/bootstrap/preview", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert "ADD-DBAPROF:::1" in data["script_text"]
    assert "ADD-VLAN:::1::VLANID=500" in data["script_text"]
