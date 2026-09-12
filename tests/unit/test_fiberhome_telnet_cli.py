from unittest.mock import MagicMock, patch
import pytest

from app.drivers.fiberhome.fiberhome_tl1 import (
    FiberhomeTL1Driver,
    parse_telnet_port_onus,
    parse_telnet_profiles,
    parse_telnet_unauth_onus,
    parse_telnet_vlans,
)
from app.models.olt import OLTInDB, OLTProtocol, OLTVendor


def test_is_telnet_cli():
    driver = FiberhomeTL1Driver()
    olt_telnet = OLTInDB(
        name="OLT-TELNET",
        vendor=OLTVendor.FIBERHOME,
        model="AN5516-01",
        host="192.0.2.1",
        port=23,
        protocol=OLTProtocol.TELNET,
        username="tecnico",
        password="pwd",
    )
    assert driver.is_telnet_cli(olt_telnet) is True

    olt_tl1 = OLTInDB(
        name="OLT-TL1",
        vendor=OLTVendor.FIBERHOME,
        model="AN5516-01",
        host="192.0.2.1",
        port=3337,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    assert driver.is_telnet_cli(olt_tl1) is False


def test_parse_telnet_vlans():
    sample_output = """
vlan count:11.
3   ,           10   ~ 13  ,    301  ~ 302 ,    1000,           
2333 ~ 2334,    3000,           
Admin\\vlan# 
    """
    vlans = parse_telnet_vlans(sample_output)
    vids = [v.vlan_id for v in vlans]
    assert vids == [3, 10, 11, 12, 13, 301, 302, 1000, 2333, 2334, 3000]
    assert len(vlans) == 11
    assert vlans[0].name == "VLAN_3"


def test_parse_telnet_port_onus():
    sample_output = """
-----  ONU Auth Table, SLOT = 1, PON = 1, ITEM = 4 -----
Slot Pon Onu OnuType        ST Lic OST PhyId        PhyPwd     LogicId                  LogicPwd     
---- --- --- -------------- -- --- --- ------------ ---------- ------------------------ ------------
1    1   1   110B           A  1   dn  ITBS8b69e88f                                                  
1    1   2   110B           A  1   up  ITBS0d4d2243                                                  
1    1   3   HG6145E        A  1   up  FHTTfe132d48                                                  
1    1   4   120AC          A  1   dn  ITBS325547aa                                                  
Command execute success. 
Admin\\onu# 
    """
    onus = parse_telnet_port_onus(sample_output, "1/1")
    assert len(onus) == 4
    assert onus[0].port == "1/1"
    assert onus[0].onu_id == 1
    assert onus[0].serial == "ITBS8b69e88f"
    assert onus[0].status == "offline"
    assert onus[0].name == "110B"

    assert onus[1].onu_id == 2
    assert onus[1].serial == "ITBS0d4d2243"
    assert onus[1].status == "online"

    assert onus[2].serial == "FHTTfe132d48"
    assert onus[2].status == "online"
    assert onus[2].name == "HG6145E"


def test_parse_telnet_unauth_onus_empty_and_populated():
    # Saída vazia
    empty_output = """
----- ONU Unauth Table, ITEM = 0 -----
No  OnuType        PhyId        PhyPwd     LogicId                  LogicPwd     Time                SoftVersion      HardVersion      Vendor EquipId              
--- -------------- ------------ ---------- ------------------------ ------------ --------
Command execute success. 
Admin\\onu# 
    """
    assert parse_telnet_unauth_onus(empty_output) == []

    # Saída com ONU encontrada via show unauthlist
    populated_output = """
----- ONU Unauth Table, ITEM = 1 -----
No  OnuType        PhyId        PhyPwd     LogicId                  LogicPwd     Time                SoftVersion      HardVersion      Vendor EquipId              
--- -------------- ------------ ---------- ------------------------ ------------ --------
1   HG6145E        FHTT12345678                                                  2026-09-12 19:00:00 V1.0             V1.0             FHTT   HG6145E
Admin\\onu# 
    """
    unauth = parse_telnet_unauth_onus(populated_output)
    assert len(unauth) == 1
    assert unauth[0].serial == "FHTT12345678"
    assert unauth[0].model == "HG6145E"

    # Saída com ONU encontrada via show discovery
    discovery_output = """
1    1   HG6145E   FHTT99887766
Command execute success.
    """
    disc_unauth = parse_telnet_unauth_onus(discovery_output)
    assert len(disc_unauth) == 1
    assert disc_unauth[0].port == "1/1"
    assert disc_unauth[0].serial == "FHTT99887766"


def test_parse_telnet_profiles():
    sample_output = """
Service model profile index 1 :name vlan20 type unicast cvlan transparent translate disable qinq disable null 
Service model profile index 2 :name ROUTER type unicast cvlan transparent translate disable qinq disable null 
Admin\\profile# 
    """
    profiles = parse_telnet_profiles(sample_output)
    assert len(profiles) == 2
    assert profiles[0].name == "vlan20"
    assert profiles[0].profile_type == "unicast"
    assert profiles[1].name == "ROUTER"
    assert profiles[1].profile_type == "unicast"


def test_telnet_driver_mocked_flow():
    driver = FiberhomeTL1Driver()
    olt = OLTInDB(
        name="OLT-MOCK",
        vendor=OLTVendor.FIBERHOME,
        model="AN5516-01",
        host="192.0.2.10",
        port=23,
        protocol=OLTProtocol.TELNET,
        username="tecnico",
        password="pwd",
    )

    mock_client = MagicMock()
    # Simula respostas para login e comandos
    mock_client.read_until.return_value = b"Admin#"

    with patch.object(driver, "_open_telnet_session", return_value=mock_client), \
         patch.object(driver, "_exec_telnet_cmd") as mock_exec:
        
        # Teste list_vlans
        mock_exec.return_value = "vlan count:2.\n10, 20\nAdmin\\vlan#"
        vlans = driver.list_vlans(olt)
        assert len(vlans) == 2
        assert vlans[0].vlan_id == 10
        assert vlans[1].vlan_id == 20

        # Teste get_port_onus
        mock_exec.return_value = "1 1 1 110B A 1 up ITBS11223344\nAdmin\\onu#"
        port_onus = driver.get_port_onus(olt, "1/1")
        assert len(port_onus) == 1
        assert port_onus[0].serial == "ITBS11223344"
        assert port_onus[0].status == "online"

        # Teste list_unauthorized_onus
        mock_exec.return_value = "Command execute success.\nAdmin\\onu#"
        unauth = driver.list_unauthorized_onus(olt)
        assert unauth == []

        # Teste list_profiles
        mock_exec.return_value = "Service model profile index 1 :name PLAN_100M type unicast\nAdmin\\profile#"
        profs = driver.list_profiles(olt)
        assert len(profs) == 1
        assert profs[0].name == "PLAN_100M"
