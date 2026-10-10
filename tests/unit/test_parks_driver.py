from unittest.mock import MagicMock, patch
import pytest

from app.drivers.factory import DriverFactory
from app.drivers.parks.parks_fiberlink import ParksFiberlinkDriver
from app.models.bootstrap import BootstrapRequest
from app.models.olt import OLTInDB, OLTProtocol, OLTVendor
from app.models.provision import ProvisionRequest


def test_driver_factory_resolves_parks_models():
    # Fiberlink 10008S Series 2
    olt_parks_10008s = OLTInDB(
        name="OLT-BANCADA-PARKS",
        vendor=OLTVendor.PARKS,
        model="Fiberlink 10008S Series 2",
        host="192.168.1.1",
        port=23,
        protocol=OLTProtocol.TELNET,
        username="admin",
        password="secret_password",
    )
    driver = DriverFactory.get_driver(olt_parks_10008s)
    assert isinstance(driver, ParksFiberlinkDriver)
    assert driver.model_name == "Fiberlink 10008S Series 2"

    # Fiberlink 2108
    olt_2108 = OLTInDB(
        name="OLT-POP-2108",
        vendor=OLTVendor.PARKS,
        model="Fiberlink 2108",
        host="192.168.1.2",
        port=23,
        protocol=OLTProtocol.TELNET,
        username="admin",
        password="secret_password",
    )
    driver_2108 = DriverFactory.get_driver(olt_2108)
    assert isinstance(driver_2108, ParksFiberlinkDriver)


def test_parks_port_normalization():
    driver = ParksFiberlinkDriver()
    assert driver.normalize_port("1/1") == "gpon1/1"
    assert driver.normalize_port("gpon1/1") == "gpon1/1"
    assert driver.normalize_port("2/4") == "gpon2/4"
    assert driver.normalize_port("0/2") == "gpon1/2"
    assert driver.normalize_port("3") == "gpon1/3"


def test_parks_vendor_detection_by_serial():
    driver = ParksFiberlinkDriver()
    assert driver.detect_vendor_by_serial("HWTC17D37AB2") == OLTVendor.HUAWEI
    assert driver.detect_vendor_by_serial("FHTTFE25D822") == OLTVendor.FIBERHOME
    assert driver.detect_vendor_by_serial("ITBS5FED363D") == OLTVendor.INTELBRAS
    assert driver.detect_vendor_by_serial("IBTS5FED363D") == OLTVendor.INTELBRAS
    assert driver.detect_vendor_by_serial("PRKS00BF5D6C") == OLTVendor.PARKS
    assert driver.detect_vendor_by_serial("VSOL12345678") == OLTVendor.VSOL
    assert driver.detect_vendor_by_serial("TDTC1433254E") == OLTVendor.ZTE
    assert driver.detect_vendor_by_serial("XYZ123456789") == OLTVendor.PARKS


def test_parks_autofind_parser():
    driver = ParksFiberlinkDriver()
    raw_autofind = """
Interface       | Serial       | Model                         
--------------- + ------------ +------------------------------
gpon1/1         | HWTC17D37AB2 | EG8041X6
gpon1/2         | ITBS5B2E50F4 | 110GB
OLTabacaxi# 
"""
    mock_olt = MagicMock(spec=OLTInDB)
    with patch.object(driver, "_execute_cli_commands", return_value=raw_autofind):
        unauth = driver.list_unauthorized_onus(mock_olt)
        assert len(unauth) == 2
        assert unauth[0].serial == "HWTC17D37AB2"
        assert unauth[0].port == "gpon1/1"
        assert unauth[0].model == "EG8041X6"

        assert unauth[1].serial == "ITBS5B2E50F4"
        assert unauth[1].port == "gpon1/2"
        assert unauth[1].model == "110GB"


def test_parks_optical_details_parser():
    driver = ParksFiberlinkDriver()
    raw_optical = """
show gpon onu prks00bf5d6c status
\t1-prks00bf5d6c:
\t\tStatus      : ACTIVE
\t\tPower Level : -18.42 dBm
\t\tRSSI        : -19.10 dBm
OLTabacaxi# 
show gpon onu prks00bf5d6c rssi
\t1-prks00bf5d6c:
\t\tRSSI Level   : -19.10 dBm
OLTabacaxi# 
"""
    mock_olt = MagicMock(spec=OLTInDB)
    with patch.object(driver, "_execute_cli_commands", return_value=raw_optical):
        details = driver.get_onu_details(mock_olt, "PRKS00BF5D6C")
        assert details.serial == "PRKS00BF5D6C"
        assert details.status == "online"
        assert details.rx_power_dbm == -18.42
        assert details.olt_rx_power_dbm == -19.10


def test_parks_provision_commands_router_mode():
    driver = ParksFiberlinkDriver()
    mock_olt = MagicMock(spec=OLTInDB)
    mock_olt.id = "0191e4a0-0000-7000-8000-000000000001"
    mock_olt.name = "OLT-PARKS-TEST"

    req = ProvisionRequest(
        port="1/1",
        serial="HWTC17D37AB2",
        vlan=621,
        profile="router_vlan621",
        mode="router",
        description="Cliente_Teste_Fibra",
    )

    with patch.object(driver, "_execute_cli_commands", return_value="Success") as mock_cli:
        res = driver.provision_onu(mock_olt, req)
        assert res.success is True
        assert res.serial == "HWTC17D37AB2"
        assert res.port == "gpon1/1"

        cmds = mock_cli.call_args[0][1]
        assert "interface gpon1/1" in cmds
        assert "onu add serial-number hwtc17d37ab2" in cmds
        assert "onu hwtc17d37ab2 flow-profile router_vlan621" in cmds
        assert "onu hwtc17d37ab2 alias Cliente_Teste_Fibra" in cmds
        assert "onu hwtc17d37ab2 ethernet-profile auto-on uni-port 1-4" in cmds
        assert "onu hwtc17d37ab2 iphost 1 ip dhcp" in cmds
        assert "copy running-config startup-config" in cmds


def test_parks_provision_commands_bridge_mode():
    driver = ParksFiberlinkDriver()
    mock_olt = MagicMock(spec=OLTInDB)
    mock_olt.id = "0191e4a0-0000-7000-8000-000000000001"
    mock_olt.name = "OLT-PARKS-TEST"

    req = ProvisionRequest(
        port="gpon1/2",
        serial="ITBS5B2E50F4",
        vlan=202,
        profile="flow_bridge_v202",
        mode="bridge",
        description="Empresa_Bridge",
    )

    with patch.object(driver, "_execute_cli_commands", return_value="Success") as mock_cli:
        res = driver.provision_onu(mock_olt, req)
        assert res.success is True
        assert res.serial == "ITBS5B2E50F4"
        assert res.port == "gpon1/2"

        cmds = mock_cli.call_args[0][1]
        assert "interface gpon1/2" in cmds
        assert "onu add serial-number itbs5b2e50f4" in cmds
        assert "onu itbs5b2e50f4 flow-profile flow_bridge_v202" in cmds
        assert "onu itbs5b2e50f4 ethernet-profile auto-on uni-port 1" in cmds


def test_parks_lifecycle_actions():
    driver = ParksFiberlinkDriver()
    mock_olt = MagicMock(spec=OLTInDB)
    mock_olt.id = "0191e4a0-0000-7000-8000-000000000001"

    # 1. Deprovision
    with patch.object(driver, "_execute_cli_commands", return_value="Success") as mock_cli:
        res_dep = driver.deprovision_onu(mock_olt, "HWTC17D37AB2", port="gpon1/1")
        assert res_dep.success is True
        assert res_dep.action == "deprovision"
        assert res_dep.olt_id == mock_olt.id
        cmds = mock_cli.call_args[0][1]
        assert "no onu hwtc17d37ab2" in cmds

    # 2. Suspend (Blacklist)
    with patch.object(driver, "_execute_cli_commands", return_value="Success") as mock_cli:
        res_susp = driver.suspend_onu(mock_olt, "HWTC17D37AB2")
        assert res_susp.success is True
        assert res_susp.action == "suspend"
        cmds = mock_cli.call_args[0][1]
        assert "gpon blacklist serial-number hwtc17d37ab2" in cmds

    # 3. Resume (Un-blacklist)
    with patch.object(driver, "_execute_cli_commands", return_value="Success") as mock_cli:
        res_res = driver.resume_onu(mock_olt, "HWTC17D37AB2")
        assert res_res.success is True
        assert res_res.action == "resume"
        cmds = mock_cli.call_args[0][1]
        assert "no gpon blacklist serial-number hwtc17d37ab2" in cmds

    # 4. Reboot
    with patch.object(driver, "_execute_cli_commands", return_value="Success") as mock_cli:
        res_reb = driver.reboot_onu(mock_olt, "HWTC17D37AB2", port="gpon1/1")
        assert res_reb.success is True
        assert res_reb.action == "reboot"
        cmds = mock_cli.call_args[0][1]
        assert "onu reset hwtc17d37ab2" in cmds


def test_parks_uptime_parser():
    driver = ParksFiberlinkDriver()
    mock_olt = MagicMock(spec=OLTInDB)
    raw_uptime = """
uptime   : 0 days, 5:14:44
idle time: 0 days, 4:03:35
OLTabacaxi# 
"""
    with patch.object(driver, "_execute_cli_commands", return_value=raw_uptime):
        uptime_sec = driver.get_chassis_uptime(mock_olt)
        assert uptime_sec == 0 * 86400 + 5 * 3600 + 14 * 60 + 44


def test_parks_vlans_parser():
    driver = ParksFiberlinkDriver()
    mock_olt = MagicMock(spec=OLTInDB)
    raw_vlan = "Existing VLANs:  vlan1-vlan2, vlan100, vlan621\nOLTabacaxi# "

    with patch.object(driver, "_execute_cli_commands", return_value=raw_vlan):
        vlans = driver.list_vlans(mock_olt)
        vlan_ids = [v.vlan_id for v in vlans]
        assert 1 in vlan_ids
        assert 2 in vlan_ids
        assert 100 in vlan_ids
        assert 621 in vlan_ids


def test_parks_profiles_parser():
    driver = ParksFiberlinkDriver()
    mock_olt = MagicMock(spec=OLTInDB)
    raw_profiles = """
bridge_vlan621
Index | Type     | VLAN | COS | Encryption | Downstream | Bandwidth Name           | Shared | PBMP Ports
1     | PBMP     | 621  | -   | DISABLED   | 0          | 500Mbps                  | No     | 1 
router_vlan621
Index | Type     | VLAN | COS | Encryption | Downstream | Bandwidth Name           | Shared | PBMP Ports
1     | VEIP     | 621  | -   | DISABLED   | 0          | 500Mbps                  | No     | 
OLTabacaxi# 
Name                             | Type         | Fixed    | Assured  | Maximum 
1000Mbps                         | INTERNET     | 0        | 0        | 1024000 
500Mbps                          | INTERNET     | 0        | 0        | 512000  
"""
    with patch.object(driver, "_execute_cli_commands", return_value=raw_profiles):
        profiles = driver.list_profiles(mock_olt)
        names = [p.name for p in profiles]
        assert "bridge_vlan621" in names
        assert "router_vlan621" in names
        assert "500Mbps" in names
        assert "1000Mbps" in names
