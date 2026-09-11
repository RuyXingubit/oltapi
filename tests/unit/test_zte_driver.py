from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.drivers.factory import DriverFactory
from app.drivers.zte.zte_zxros import ZTEZXROSDriver
from app.models.bootstrap import (
    BootstrapMode,
    BootstrapRequest,
    DefaultONUMode,
)
from app.models.olt import OLTCreateRequest, OLTInDB, OLTProtocol, OLTVendor
from app.models.provision import ProvisionRequest


def test_driver_factory_resolves_zte_models():
    # C320
    olt_c320 = OLTInDB(
        name="OLT-POP-C320",
        vendor=OLTVendor.ZTE,
        model="ZXA10 C320",
        host="10.20.0.1",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    driver_c320 = DriverFactory.get_driver(olt_c320)
    assert isinstance(driver_c320, ZTEZXROSDriver)
    assert driver_c320.model_name == "ZXA10 C320"

    # C300
    olt_c300 = OLTInDB(
        name="OLT-CORE-C300",
        vendor=OLTVendor.ZTE,
        model="C300",
        host="10.20.0.2",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    driver_c300 = DriverFactory.get_driver(olt_c300)
    assert isinstance(driver_c300, ZTEZXROSDriver)

    # C600 Titan
    olt_c600 = OLTInDB(
        name="OLT-TITAN-C600",
        vendor=OLTVendor.ZTE,
        model="Titan C600",
        host="10.20.0.3",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    driver_c600 = DriverFactory.get_driver(olt_c600)
    assert isinstance(driver_c600, ZTEZXROSDriver)


def test_zte_port_normalization():
    driver = ZTEZXROSDriver()
    assert driver.parse_port_components("1/1/1") == (1, 1, 1)
    assert driver.parse_port_components("1/2") == (1, 1, 2)
    assert driver.parse_port_components("0/2/3") == (1, 2, 3)

    with pytest.raises(ValueError):
        driver.parse_port_components("invalid/port/format/extra")


def test_zte_autofind_parser():
    driver = ZTEZXROSDriver()
    raw_autofind = """
  OnuIndex               Sn                  State
  ---------------------------------------------------------------------
  gpon-onu_1/1/1:1       ZTEGC1234567        uncfg
  gpon-onu_1/1/2:1       ZTEGC8765432        uncfg
  gpon-onu_1/2/1:1       HWTC11223344        uncfg
  ---------------------------------------------------------------------
    """
    unauth = driver.parse_unauthorized_onus(raw_autofind)
    assert len(unauth) == 3
    assert unauth[0].port == "1/1/1"
    assert unauth[0].serial == "ZTEGC1234567"

    assert unauth[1].port == "1/1/2"
    assert unauth[1].serial == "ZTEGC8765432"

    assert unauth[2].port == "1/2/1"
    assert unauth[2].serial == "HWTC11223344"


def test_zte_port_onus_parser():
    driver = ZTEZXROSDriver()
    raw_port_onus = """
  OnuIndex               AdminState  OperState    RxPower(dBm)  SN
  ---------------------------------------------------------------------
  gpon-onu_1/1/1:1       enable      online       -19.50        ZTEGC1234567
  gpon-onu_1/1/1:2       enable      offline      --            ZTEGC8765432
  ---------------------------------------------------------------------
    """
    onus = driver.parse_port_onus(raw_port_onus, "1/1/1")
    assert len(onus) == 2
    assert onus[0].port == "1/1/1"
    assert onus[0].onu_id == 1
    assert onus[0].serial == "ZTEGC1234567"
    assert onus[0].status == "online"

    assert onus[1].onu_id == 2
    assert onus[1].status == "offline"


def test_zte_optical_info_parser():
    driver = ZTEZXROSDriver()
    raw_optical = """
  optical-info:
  Rx optical power: -19.45 dBm
  Tx optical power: 2.15 dBm
  OLT Rx optical power: -20.10 dBm
    """
    rx, tx = driver.parse_optical_info(raw_optical)
    assert rx == -19.45
    assert tx == 2.15


def test_zte_bootstrap_generation():
    driver = ZTEZXROSDriver()
    req = BootstrapRequest(
        mode=BootstrapMode.SINGLE_VLAN,
        vlan=100,
        uplink_port="1",
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    assert "profile tcont 1G type 4 maximum 1024000" in commands
    assert "profile traffic 1G sir 1024000 pir 1024000" in commands
    assert "vlan 100" in commands
    assert "interface gei_1/1/1" in commands
    assert "switchport trunk vlan 100" in commands
    assert "write" in commands


def test_zte_bootstrap_vlan_per_pon():
    driver = ZTEZXROSDriver()
    req = BootstrapRequest(
        mode=BootstrapMode.VLAN_PER_PON,
        vlan_per_pon={"1": 101, "2": 102},
        uplink_port="1",
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    assert "vlan 101" in commands
    assert "vlan 102" in commands
    assert "switchport trunk vlan 101" in commands
    assert "write" in commands


def test_zte_provision_commands():
    driver = ZTEZXROSDriver()
    olt = OLTInDB(
        name="OLT-TEST-ZTE",
        vendor=OLTVendor.ZTE,
        model="ZXA10 C320",
        host="10.20.0.1",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    req = ProvisionRequest(
        port="1/1/2",
        serial="ZTEGC1234567",
        vlan=700,
        description="Cliente_ZTE_1",
    )

    with patch.object(driver, "_execute_cli_commands") as mock_exec:
        mock_exec.return_value = "Command successful."
        res = driver.provision_onu(olt, req)

        assert res.success is True
        assert res.port == "1/1/2"
        assert res.serial == "ZTEGC1234567"

        mock_exec.assert_called_once()
        cmds_called = mock_exec.call_args[0][1]
        assert "interface gpon-olt_1/1/2" in cmds_called
        assert any("onu 1 type auto sn ZTEGC1234567" in c for c in cmds_called)
        assert any("service-port 1 vport 1 user-vlan 700 vlan 700" in c for c in cmds_called)
        assert "write" in cmds_called


def test_api_zte_bootstrap_preview(client: TestClient, auth_headers, setup_test_env):
    repo = setup_test_env["repo"]
    req = OLTCreateRequest(
        name="OLT-TESTE-C320",
        vendor=OLTVendor.ZTE,
        model="C320",
        host="10.20.0.50",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    zte_olt = repo.create(req)

    payload = {
        "mode": "single_vlan",
        "vlan": 700,
        "uplink_port": "1",
    }
    res = client.post(f"/api/v1/olts/{zte_olt.id}/bootstrap/preview", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert "profile tcont 1G" in data["script_text"]
    assert "vlan 700" in data["script_text"]
    assert "write" in data["script_text"]
