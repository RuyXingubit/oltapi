from unittest.mock import MagicMock, patch
import pytest

from app.drivers.fiberhome.fiberhome_tl1 import (
    FiberhomeTL1Driver,
    build_telnet_deprovision_commands,
    build_telnet_provision_commands,
    build_telnet_reboot_commands,
    build_telnet_resume_commands,
    build_telnet_suspend_commands,
    parse_telnet_optical_info,
    parse_telnet_port_onus,
    parse_telnet_profiles,
    parse_telnet_service_vlan,
    parse_telnet_unauth_onus,
    parse_telnet_vlans,
)
from app.models.olt import OLTInDB, OLTProtocol, OLTVendor
from app.models.provision import ProvisionRequest


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


def test_build_telnet_provision_commands_bridge():
    cmds = build_telnet_provision_commands(
        slot=1,
        pon=1,
        onu_id=60,
        mac="FHTT12345678",
        onu_tipo="HG6145E",
        vlan=100,
        mode="bridge",
    )
    assert "cd onu" in cmds
    assert any("set whitelist  phy_addr address FHTT12345678" in c or "set whitelist phy_addr address FHTT12345678" in c for c in cmds)
    assert any("set epon slot 1 pon 1 onu 60 port 1 service 1 vlan_mode tag 0 33024 100" in c for c in cmds)
    assert any("apply onu 1 1 60 vlan" in c for c in cmds)


def test_build_telnet_provision_commands_router():
    cmds = build_telnet_provision_commands(
        slot=1,
        pon=2,
        onu_id=15,
        mac="FHTT88776655",
        onu_tipo="HG6145E",
        vlan=300,
        mode="router",
        pppoe_user="cliente_teste",
        pppoe_pass="senha_secreta",
    )
    assert "cd lan" in cmds
    assert any("cliente_teste senha_secreta" in c for c in cmds)
    assert any("apply wancfg slot 1 2 15" in c for c in cmds)


def test_build_telnet_provision_commands_third_party_veip():
    cmds = build_telnet_provision_commands(
        slot=1,
        pon=16,
        onu_id=20,
        mac="HWTCbbaa2ab6",
        onu_tipo="HG260",
        vlan=11,
        mode="veip",
    )
    assert "cd onu" in cmds
    assert any("mac_num_limit 30" in c for c in cmds)
    assert "cd lan" in cmds
    assert any("speed 1000m duplex full" in c for c in cmds)
    assert any("onuveip 1 33024 11" in c for c in cmds)
    assert any("apply onu 1 16 20 vlan" in c for c in cmds)



def test_build_telnet_lifecycle_commands():
    deprovision_cmds = build_telnet_deprovision_commands(1, 1, 5)
    assert any("no whitelist slot 1 pon 1 onu 5" in c for c in deprovision_cmds)

    suspend_cmds = build_telnet_suspend_commands(1, 1, 5)
    assert any("set onu_enable_status slot 1 pon 1 onu 5 status disable" in c for c in suspend_cmds)

    resume_cmds = build_telnet_resume_commands(1, 1, 5)
    assert any("set onu_enable_status slot 1 pon 1 onu 5 status enable" in c for c in resume_cmds)

    reboot_cmds = build_telnet_reboot_commands(1, 1, 5)
    assert any("reboot onu slot 1 pon 1 onu 5 ;" in c for c in reboot_cmds)


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

        # Teste provision_onu (modo router)
        req = ProvisionRequest(
            port="1/1",
            serial="FHTT99881122",
            vlan=100,
            mode="router",
            pppoe_user="user1",
            pppoe_password="pass1",
            onu_id=5,
        )
        mock_exec.return_value = "Command execute success.\nAdmin#"
        res = driver.provision_onu(olt, req)
        assert res.success is True
        assert res.onu_id == 5
        assert res.serial == "FHTT99881122"

        # Teste deprovision_onu
        dep_res = driver.deprovision_onu(olt, serial_or_id="FHTT99881122", port="1/1", onu_id=5)
        assert dep_res.success is True
        assert dep_res.action == "deprovision"

        # Teste reboot_onu
        reb_res = driver.reboot_onu(olt, serial_or_id="FHTT99881122", port="1/1", onu_id=5)
        assert reb_res.success is True
        assert reb_res.action == "reboot"


def test_parse_telnet_optical_info():
    sample_optical = """
 onu (1/1/6).
-----  ONU OPTICAL INFO 1.1.6-----
SEND POWER   :  1.61\t(Dbm)
RECV POWER   : -24.69\t(Dbm)
Admin\\onu# 
    """
    rx, tx, olt_rx = parse_telnet_optical_info(sample_optical)
    assert rx == -24.69
    assert tx == 1.61
    assert olt_rx is None


def test_parse_telnet_optical_info_with_olt_recv():
    sample_module = """
SEND POWER   :  2.42 (Dbm)
RECV POWER   : -22.52 (Dbm)
OLT RECV POWER : -21.12 (Dbm)
Admin\\onu# 
    """
    rx, tx, olt_rx = parse_telnet_optical_info(sample_module)
    assert rx == -22.52
    assert tx == 2.42
    assert olt_rx == -21.12


def test_parse_telnet_optical_info_error():
    sample_error = """
show onu opticalpower-info phy-id FHTT00000000
[Error -506]: Onu is not authcated. 
Command executes failed.
Admin\\onu# 
    """
    rx, tx, olt_rx = parse_telnet_optical_info(sample_error)
    assert rx is None
    assert tx is None
    assert olt_rx is None


def test_parse_telnet_service_vlan():
    sample_srv = """
FE service info : 

NO.  SL/LI/ONU PORT ID TYPE  MODE CVID COS  TPID  TVID COS  TPID  SVID COS  TPID PVID COS DATATYPE PRIQUE GEMPORT
1    1 /1 /6   1    1  unica tag  301  0    33024 null null null  null null null  null null default default default

VEIP service info : 

------------------------------------------------------------------
Slot 1 pon 1 onu 6 port 1 service 1 onuveip info:
Service no(Gemport)     : 1
Cvlan                   : 301
    """
    vlan = parse_telnet_service_vlan(sample_srv)
    assert vlan == 301


def test_fiberhome_get_onu_details_telnet_cli():
    driver = FiberhomeTL1Driver()
    olt = OLTInDB(
        name="OLT-TEST",
        vendor=OLTVendor.FIBERHOME,
        model="AN5516-01",
        host="192.0.2.1",
        port=23,
        protocol=OLTProtocol.TELNET,
        username="tecnico",
        password="pwd",
    )

    with patch.object(driver, "_open_telnet_session") as mock_open, \
         patch.object(driver, "_exec_telnet_cmd") as mock_exec:
        mock_client = MagicMock()
        mock_open.return_value = mock_client

        def side_effect(client, cmd):
            if "show onu opticalpower-info" in cmd:
                return " onu (1/1/6).\n-----  ONU OPTICAL INFO 1.1.6-----\nSEND POWER   :  1.97\t(Dbm)\nRECV POWER   : -24.69\t(Dbm)\n"
            elif "show onu-info" in cmd:
                return "1    1    6    AN5516\nAdmin\\onu#"
            elif "show optic_module" in cmd:
                return "SEND POWER   :  1.97\t(Dbm)\nRECV POWER   : -24.69\t(Dbm)\nOLT RECV POWER : -21.12\t(Dbm)\nAdmin\\onu#"
            elif "show authorization" in cmd:
                return "1    1    6    AN5516    A    1    up    FHTTc0829bac\nAdmin\\onu#"
            elif "show onu service-info" in cmd:
                return "Cvlan                   : 301\nAdmin\\onu#"
            return ""

        mock_exec.side_effect = side_effect

        details = driver.get_onu_details(olt, "FHTTc0829bac")
        assert details.serial == "FHTTc0829bac"
        assert details.port == "1/1"
        assert details.onu_id == 6
        assert details.status == "online"
        assert details.rx_power_dbm == -24.69
        assert details.tx_power_dbm == 1.97
        assert details.olt_rx_power_dbm == -21.12
        assert details.vlan == 301

