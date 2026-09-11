from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.drivers.factory import DriverFactory
from app.drivers.huawei.huawei_vrp import HuaweiVRPDriver
from app.models.bootstrap import (
    BootstrapMode,
    BootstrapRequest,
    DefaultONUMode,
)
from app.models.olt import OLTCreateRequest, OLTInDB, OLTProtocol, OLTVendor
from app.models.provision import ProvisionRequest


def test_driver_factory_resolves_huawei_models():
    # MA5800
    olt_ma5800 = OLTInDB(
        name="OLT-CORE-MA5800",
        vendor=OLTVendor.HUAWEI,
        model="MA5800-X7",
        host="10.0.0.1",
        port=22,
        protocol=OLTProtocol.SSH,
        username="root",
        password="pwd",
    )
    driver_5800 = DriverFactory.get_driver(olt_ma5800)
    assert isinstance(driver_5800, HuaweiVRPDriver)

    # MA5608T
    olt_ma5608t = OLTInDB(
        name="OLT-POP-MA5608T",
        vendor=OLTVendor.HUAWEI,
        model="SmartAX MA5608T",
        host="10.0.0.2",
        port=22,
        protocol=OLTProtocol.SSH,
        username="root",
        password="pwd",
    )
    driver_5608 = DriverFactory.get_driver(olt_ma5608t)
    assert isinstance(driver_5608, HuaweiVRPDriver)


def test_huawei_port_normalization():
    driver = HuaweiVRPDriver()
    assert driver.parse_port_components("0/1/0") == (0, 1, 0)
    assert driver.parse_port_components("1/2") == (0, 1, 2)
    assert driver.parse_port_components("3") == (0, 1, 3)

    with pytest.raises(ValueError):
        driver.parse_port_components("invalid/port/format/extra")


def test_huawei_autofind_parser():
    driver = HuaweiVRPDriver()
    raw_autofind = """
  ----------------------------------------------------------------------------
  Number F/S/P  Autofind SN       Password         Vendor-ID Equip-ID Logic-SN
  ----------------------------------------------------------------------------
  1      0/1/0  48575443ABC12345  0x000000000000   HWTC      EG8145V5 -
  2      0/1/3  48575443DEF67890  0x000000000000   HWTC      HG8245H  -
  3      0/2/1  ITBS99887766      0x000000000000   ITBS      110B     -
  ----------------------------------------------------------------------------
    """
    unauth = driver.parse_unauthorized_onus(raw_autofind)
    assert len(unauth) == 3
    assert unauth[0].port == "0/1/0"
    assert unauth[0].serial == "48575443ABC12345"
    assert unauth[0].model == "EG8145V5"

    assert unauth[1].port == "0/1/3"
    assert unauth[1].serial == "48575443DEF67890"
    assert unauth[1].model == "HG8245H"

    assert unauth[2].port == "0/2/1"
    assert unauth[2].serial == "ITBS99887766"
    assert unauth[2].model == "110B"


def test_huawei_port_onus_parser():
    driver = HuaweiVRPDriver()
    raw_port_onus = """
  -----------------------------------------------------------------------------
  F/S/P   ONT-ID  SN                  Control-flag  Run-state  Config-state
  -----------------------------------------------------------------------------
  0/1/0   1       4857544312345678    active        online     normal
  0/1/0   2       4857544387654321    active        offline    initial
  -----------------------------------------------------------------------------
    """
    onus = driver.parse_port_onus(raw_port_onus, "0/1/0")
    assert len(onus) == 2
    assert onus[0].port == "0/1/0"
    assert onus[0].onu_id == 1
    assert onus[0].serial == "4857544312345678"
    assert onus[0].status == "online"

    assert onus[1].onu_id == 2
    assert onus[1].status == "offline"


def test_huawei_optical_info_parser():
    driver = HuaweiVRPDriver()
    raw_optical = """
  -----------------------------------------------------------------------------
  ONT optical information:
  -----------------------------------------------------------------------------
  ONT Rx optical power(dBm)                 : -19.45
  ONT Tx optical power(dBm)                 : 2.15
  OLT Rx optical power(dBm)                 : -20.10
  CATV Rx optical power(dBm)                : -
  -----------------------------------------------------------------------------
    """
    rx, tx = driver.parse_optical_info(raw_optical)
    assert rx == -19.45
    assert tx == 2.15


def test_huawei_bootstrap_generation():
    driver = HuaweiVRPDriver()
    req = BootstrapRequest(
        mode=BootstrapMode.SINGLE_VLAN,
        vlan=100,
        uplink_port="0/19/0",
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    # Verifica comandos essenciais VRP
    assert 'dba-profile add profile-id 10 profile-name "DBA-DEFAULT" type4 max 1024000' in commands
    assert 'ont-lineprofile gpon profile-id 10 profile-name "LINE-DEFAULT"' in commands
    assert "gem mapping 1 1 vlan 100" in commands
    assert 'ont-srvprofile gpon profile-id 10 profile-name "SRV-DEFAULT"' in commands
    assert "vlan 100 smart" in commands
    assert "port vlan 100 0/0 0/19/0" in commands
    assert "interface gpon 0/1" in commands
    assert "port 0 ont-auto-find enable" in commands
    assert "save" in commands


def test_huawei_bootstrap_vlan_per_pon():
    driver = HuaweiVRPDriver()
    req = BootstrapRequest(
        mode=BootstrapMode.VLAN_PER_PON,
        vlan_per_pon={"1": 101, "2": 102},
        uplink_port="0/19/0",
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)
    assert 'ont-lineprofile gpon profile-id 10 profile-name "LINE-PON1"' in commands
    assert "gem mapping 1 1 vlan 101" in commands
    assert "vlan 101 smart" in commands
    assert "port vlan 101 0/0 0/19/0" in commands


def test_huawei_provision_commands():
    driver = HuaweiVRPDriver()
    olt = OLTInDB(
        name="OLT-TEST-HUAWEI",
        vendor=OLTVendor.HUAWEI,
        model="MA5800-X7",
        host="10.0.0.1",
        port=22,
        protocol=OLTProtocol.SSH,
        username="root",
        password="pwd",
    )
    req = ProvisionRequest(
        port="0/1/2",
        serial="48575443ABC12345",
        vlan=500,
        description="Cliente_VIP_1",
    )

    with patch.object(driver, "_execute_cli_commands") as mock_exec:
        mock_exec.return_value = "Command executed successfully."
        res = driver.provision_onu(olt, req)

        assert res.success is True
        assert res.port == "0/1/2"
        assert res.serial == "48575443ABC12345"

        mock_exec.assert_called_once()
        cmds_called = mock_exec.call_args[0][1]
        assert "interface gpon 0/1" in cmds_called
        assert any('ont add 2 sn-auth 48575443ABC12345' in c for c in cmds_called)
        assert any('service-port vlan 500 gpon 0/1/2 ont 1' in c for c in cmds_called)
        assert "save" in cmds_called


def test_api_huawei_bootstrap_preview(client: TestClient, auth_headers, setup_test_env):
    repo = setup_test_env["repo"]
    req = OLTCreateRequest(
        name="OLT-TESTE-MA5800",
        vendor=OLTVendor.HUAWEI,
        model="MA5800-X7",
        host="10.0.0.50",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    hw_olt = repo.create(req)

    payload = {
        "mode": "single_vlan",
        "vlan": 400,
        "uplink_port": "0/19/0",
    }
    res = client.post(f"/api/v1/olts/{hw_olt.id}/bootstrap/preview", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert "vlan 400 smart" in data["script_text"]
    assert "dba-profile add profile-id 10" in data["script_text"]
