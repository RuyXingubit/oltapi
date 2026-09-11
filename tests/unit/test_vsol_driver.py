from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.drivers.factory import DriverFactory
from app.drivers.vsol.vsol_v1600 import VSOLV1600Driver
from app.models.bootstrap import (
    BootstrapMode,
    BootstrapRequest,
    DefaultONUMode,
)
from app.models.olt import OLTCreateRequest, OLTInDB, OLTProtocol, OLTVendor
from app.models.provision import ProvisionRequest


def test_driver_factory_resolves_vsol_models():
    # V1600GT
    olt_v1600gt = OLTInDB(
        name="OLT-BANCADA-V1600GT",
        vendor=OLTVendor.VSOL,
        model="V1600GT",
        host="192.168.8.100",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    driver_gt = DriverFactory.get_driver(olt_v1600gt)
    assert isinstance(driver_gt, VSOLV1600Driver)
    assert driver_gt.model_name == "V1600GT"

    # V1600G1
    olt_v1600g1 = OLTInDB(
        name="OLT-POP-V1600G1",
        vendor=OLTVendor.VSOL,
        model="V1600G1-B",
        host="192.168.8.101",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    driver_g1 = DriverFactory.get_driver(olt_v1600g1)
    assert isinstance(driver_g1, VSOLV1600Driver)


def test_vsol_port_normalization():
    driver = VSOLV1600Driver()
    assert driver.parse_port_components("0/1") == (0, 1)
    assert driver.parse_port_components("2") == (0, 2)
    assert driver.parse_port_components("0/2") == (0, 2)

    with pytest.raises(ValueError):
        driver.parse_port_components("invalid/port/format/extra")


def test_vsol_autofind_parser():
    driver = VSOLV1600Driver()
    raw_autofind = """
  -----------------------------------------------------------------------------
  Port       ONT-SN            Vendor     Model           Time
  -----------------------------------------------------------------------------
  gpon 0/1   VSOL12345678      VSOL       V2801SG         2026-09-11 10:15:30
  gpon 0/1   HWTC88776655      HWTC       EG8145V5        2026-09-11 10:18:22
  gpon 0/2   INCL99887766      INCL       110B            2026-09-11 10:20:05
  -----------------------------------------------------------------------------
    """
    unauth = driver.parse_unauthorized_onus(raw_autofind)
    assert len(unauth) == 3
    assert unauth[0].port == "0/1"
    assert unauth[0].serial == "VSOL12345678"
    assert unauth[0].model == "V2801SG"

    assert unauth[1].port == "0/1"
    assert unauth[1].serial == "HWTC88776655"
    assert unauth[1].model == "EG8145V5"

    assert unauth[2].port == "0/2"
    assert unauth[2].serial == "INCL99887766"
    assert unauth[2].model == "110B"


def test_vsol_port_onus_parser():
    driver = VSOLV1600Driver()
    raw_port_onus = """
  -----------------------------------------------------------------------------
  Port    ONT-ID  Serial-Number     Status    Distance(m)  RxPower(dBm)  Description
  -----------------------------------------------------------------------------
  0/1     1       VSOL12345678      online    450          -19.50        Cliente_01
  0/1     2       VSOL87654321      offline   --           --            Cliente_02
  -----------------------------------------------------------------------------
    """
    onus = driver.parse_port_onus(raw_port_onus, "0/1")
    assert len(onus) == 2
    assert onus[0].port == "0/1"
    assert onus[0].onu_id == 1
    assert onus[0].serial == "VSOL12345678"
    assert onus[0].status == "online"

    assert onus[1].onu_id == 2
    assert onus[1].status == "offline"


def test_vsol_optical_info_parser():
    driver = VSOLV1600Driver()
    raw_optical = """
  ONT optical info:
  Rx optical power(dBm)                 : -19.45
  Tx optical power(dBm)                 : 2.15
  OLT Rx optical power(dBm)             : -20.10
    """
    rx, tx = driver.parse_optical_info(raw_optical)
    assert rx == -19.45
    assert tx == 2.15


def test_vsol_bootstrap_generation():
    driver = VSOLV1600Driver()
    req = BootstrapRequest(
        mode=BootstrapMode.SINGLE_VLAN,
        vlan=100,
        uplink_port="1",
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    assert "profile dba 1 dba-name DBA-DEFAULT type 4 max 1024000" in commands
    assert "profile line 1 line-name LINE-DEFAULT" in commands
    assert "gem mapping 1 1 vlan 100" in commands
    assert "vlan 100" in commands
    assert "interface ge 0/1" in commands
    assert "switchport trunk allowed vlan add 100" in commands
    assert "interface gpon 0/1" in commands
    assert "ont-autofind enable" in commands
    assert "write" in commands


def test_vsol_bootstrap_vlan_per_pon():
    driver = VSOLV1600Driver()
    req = BootstrapRequest(
        mode=BootstrapMode.VLAN_PER_PON,
        vlan_per_pon={"1": 101, "2": 102},
        uplink_port="1",
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    assert "vlan 101" in commands
    assert "vlan 102" in commands
    assert "switchport trunk allowed vlan add 101" in commands
    assert "write" in commands


def test_vsol_provision_commands():
    driver = VSOLV1600Driver()
    olt = OLTInDB(
        name="OLT-TEST-VSOL",
        vendor=OLTVendor.VSOL,
        model="V1600GT",
        host="192.168.8.100",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    req = ProvisionRequest(
        port="0/2",
        serial="VSOL12345678",
        vlan=600,
        description="Cliente_Bancada_1",
    )

    with patch.object(driver, "_execute_cli_commands") as mock_exec:
        mock_exec.return_value = "Command successful."
        res = driver.provision_onu(olt, req)

        assert res.success is True
        assert res.port == "0/2"
        assert res.serial == "VSOL12345678"

        mock_exec.assert_called_once()
        cmds_called = mock_exec.call_args[0][1]
        assert "interface gpon 0/2" in cmds_called
        assert any('ont add 1 sn-auth VSOL12345678 vlan 600 desc "Cliente_Bancada_1"' in c for c in cmds_called)
        assert "write" in cmds_called


def test_api_vsol_bootstrap_preview(client: TestClient, auth_headers, setup_test_env):
    repo = setup_test_env["repo"]
    req = OLTCreateRequest(
        name="OLT-TESTE-V1600GT",
        vendor=OLTVendor.VSOL,
        model="V1600GT",
        host="192.168.8.200",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    vsol_olt = repo.create(req)

    payload = {
        "mode": "single_vlan",
        "vlan": 600,
        "uplink_port": "1",
    }
    res = client.post(f"/api/v1/olts/{vsol_olt.id}/bootstrap/preview", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert "profile dba 1 dba-name DBA-DEFAULT" in data["script_text"]
    assert "vlan 600" in data["script_text"]
    assert "write" in data["script_text"]
