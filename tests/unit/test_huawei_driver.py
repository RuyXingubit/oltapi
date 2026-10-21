from unittest.mock import patch
import pytest

from app.drivers.huawei.huawei_vrp import HuaweiVRPDriver
from app.models.olt import OLTInDB, OLTProtocol, OLTVendor
from app.models.provision import ProvisionRequest
from app.models.vlan import VLANCreateRequest


@pytest.fixture
def huawei_driver() -> HuaweiVRPDriver:
    return HuaweiVRPDriver(model_name="MA5800-X2")


@pytest.fixture
def sample_huawei_olt() -> OLTInDB:
    return OLTInDB(
        id="0192ac00-0000-7000-8000-000000000010",
        name="OLT-HUAWEI-BANCADA",
        vendor=OLTVendor.HUAWEI,
        model="MA5800-X2",
        host="10.200.250.10",
        port=23,
        protocol=OLTProtocol.TELNET,
        username="smartoltuser",
        password="SmartOltAbacaxi12#",
    )


def test_serial_conversion_bidirectional():
    cases = [
        ("ITBS0A97CF4C", "495442530A97CF4C"),
        ("HWTC181B37B2", "48575443181B37B2"),
        ("FHTTFE27EDFF", "46485454FE27EDFF"),
        ("PRKS00CF38B8", "50524B5300CF38B8"),
        ("MKPGB4E9DD13", "4D4B5047B4E9DD13"),
    ]
    for ascii_sn, hex_sn in cases:
        assert HuaweiVRPDriver.to_huawei_hex_sn(ascii_sn) == hex_sn
        assert HuaweiVRPDriver.to_huawei_hex_sn(hex_sn) == hex_sn
        assert HuaweiVRPDriver.from_huawei_hex_sn(hex_sn) == ascii_sn
        assert HuaweiVRPDriver.from_huawei_hex_sn(ascii_sn) == ascii_sn


def test_parse_chassis_interfaces_real_ma5800_bench(huawei_driver):
    board_0_out = """
  SlotID  BoardName  Status          SubType0 SubType1    Online/Offline
  0       H901PISA   Normal
  1       H901GPHF   Normal
  3       H901MPSG   Standby_normal  CPCG
  4       H901MPSG   Active_normal   CPCG
    """
    board_0_1_out = """
    Port   Port   min-distance   max-distance   Optical-module
           type       (km)           (km)           status
    0     GPON        0              20             Online
    1     GPON        0              20             Online
    2     GPON        0              20             Online
    3     GPON        0              20             Online
    4     GPON        15             30             Online
  In port 0/ 1/0 , the total of ONTs are:   8, online:   0
  In port 0/ 1/1 , the total of ONTs are:  62, online:   0
  In port 0/ 1/2 , the total of ONTs are:  18, online:   0
  In port 0/ 1/3 , the total of ONTs are:   7, online:   0
  In port 0/ 1/4 , the total of ONTs are:   3, online:   0
    """
    board_0_4_out = """
  Port  Port Optic   Native  MDI    Speed      Duplex    Flow-  Active   Link
        Type Status  VLAN           (Mbps)               Ctrl   State
     0  10GE absence      1  -      10000      full      off    active   offline
     3  GE   normal       1  -      auto_1000  auto_full off    active   online
    """
    running_cfg = """
[gpon]
  <gpon-0/1>
 interface gpon 0/1
 port 0 ont-auto-find enable
 shutdown 3
 shutdown 4
#
    """
    interfaces = huawei_driver.parse_chassis_interfaces_from_outputs(
        board_0_out,
        {1: board_0_1_out, 4: board_0_4_out},
        running_cfg,
    )
    assert len(interfaces) == 7
    p0 = next(i for i in interfaces if i.port_id == "0/1/0")
    p1 = next(i for i in interfaces if i.port_id == "0/1/1")
    p3 = next(i for i in interfaces if i.port_id == "0/1/3")
    u3 = next(i for i in interfaces if i.port_id == "0/4/3")

    assert p0.onu_count == 8 and p0.admin_state == "enabled" and p0.oper_status == "up"
    assert p1.onu_count == 62
    assert p3.onu_count == 7 and p3.admin_state == "disabled" and p3.oper_status == "down"
    assert u3.port_type == "ge" and u3.oper_status == "up"


def test_parse_vlans_and_port_bindings_smartolt(huawei_driver, sample_huawei_olt):
    vlan_out = """
  -----------------------------------------------------------------------
  VLAN   Type      Attribute  STND-Port NUM   SERV-Port NUM  VLAN-Con NUM
  -----------------------------------------------------------------------
     1   smart     common                 8               0             -
     6   smart     common                 2               0             -
    20   smart     common                 1               2             -
   621   smart     common                 1              98             -
   711   smart     common                 0               0             -
  -----------------------------------------------------------------------
    """
    vlan_cfg = """
[vlan-config]
  <vlan-config>
 vlan 6 smart
 vlan 20 smart
 vlan 621 smart
 vlan 711 smart
 port vlan 6 0/4 0
 port vlan 6 0/4 3
 port vlan 20 0/4 3
 port vlan 621 0/4 3
#
    """
    vlans = huawei_driver.parse_vlans_from_outputs(vlan_out, vlan_cfg)
    v_map = {v.vlan_id: v for v in vlans}
    assert 6 in v_map and v_map[6].tagged_ports == ["0/4/0", "0/4/3"]
    assert 621 in v_map and v_map[621].tagged_ports == ["0/4/3"]
    assert 711 in v_map and v_map[711].tagged_ports == []

    # Testa passar e remover VLAN nas interfaces (update_vlan_ports) e excluir VLAN (delete_vlan)
    with patch.object(huawei_driver, "_execute_cli_commands", return_value="OK") as mock_cli:
        huawei_driver.update_vlan_ports(
            sample_huawei_olt,
            vlan_id=711,
            add_ports=["0/4/3", "0/3/0"],
            remove_ports=["0/4/0"],
        )
        sent = mock_cli.call_args[0][1]
        assert "port vlan 711 0/4 3" in sent
        assert "port vlan 711 0/3 0" in sent
        assert "undo port vlan 711 0/4 0" in sent

    with patch.object(huawei_driver, "_execute_cli_commands", side_effect=[vlan_cfg, "OK"]) as mock_del:
        huawei_driver.delete_vlan(sample_huawei_olt, vlan_id=621)
        del_cmds = mock_del.call_args_list[1][0][1]
        assert "undo port vlan 621 0/4 3" in del_cmds
        assert "undo vlan 621" in del_cmds


def test_parse_smartolt_profiles(huawei_driver):
    raw = """
display ont-lineprofile gpon all
  ------------------------------------------------------------------------------
  Profile-ID  Profile-name                                Binding times
  ------------------------------------------------------------------------------
  1           SMARTOLT_FLEXIBLE_GPON                      17
  6           Generic_1_V621                              72
  15          SmartOLT_G                                  7
display ont-srvprofile gpon all
  -----------------------------------------------------------------------------
  Profile-ID  Profile-name                                Binding times
  -----------------------------------------------------------------------------
  1           Generic_1_V621                              72
  10          EG8145X6-10                                 23
display current-configuration section global-config
 traffic table ip index 8 name "SMARTOLT-1G-UP" cir 1048064 cbs 2620160 pir 1048064 pbs 2620160
 traffic table ip index 9 name "SMARTOLT-1G-DOWN" cir 1048064 cbs 2620160 pir 1048064 pbs 2620160
 dba-profile add profile-id 10 profile-name "SMARTOLT_DEFAULT_TCONT_1G" type4 max 1048000
    """
    profiles = huawei_driver.parse_profiles_from_outputs(raw)
    names_types = {(p.name, p.profile_type) for p in profiles}
    assert ("SMARTOLT_FLEXIBLE_GPON", "line") in names_types
    assert ("Generic_1_V621", "line") in names_types
    assert ("EG8145X6-10", "service") in names_types
    assert ("SMARTOLT_DEFAULT_TCONT_1G", "dba") in names_types
    assert ("SMARTOLT-1G-DOWN", "traffic") in names_types


def test_parse_authorized_onus_and_service_ports(huawei_driver):
    summary_out = """
  In port 0/1/1, the total of ONTs are: 3, online: 0
  ------------------------------------------------------------------------------
  ONT  Run     Last                Last                Last
  ID   State   UpTime              DownTime            DownCause
  ------------------------------------------------------------------------------
  0    offline -                   -                   dying-gasp
  1    offline -                   -                   LOFi
  56   offline -                   -                   -
  ------------------------------------------------------------------------------
  ONT        SN        Type          Distance Rx/Tx power  Description
  ID                                    (m)      (dBm)
  ------------------------------------------------------------------------------
  0   495442530A97CF4C -                -     -/-          DonaAntonia
  1   48575443181B37B2 -                -     -/-          manoeldamasceno
  56  50524B5300CF38B8 -                -     -/-          tiagofreitas
    """
    sp_out = """
   INDEX VLAN VLAN     PORT F/ S/ P VPI  VCI   FLOW  FLOW       RX   TX   STATE
        0  621 common   gpon 0/1 /1  0    1     vlan  621        9    12   down
       29  621 common   gpon 0/1 /1  1    1     vlan  621        9    12   down
      199  621 common   gpon 0/1 /1  56   1     vlan  621        9    8    down
    """
    onus = huawei_driver.parse_authorized_onus_from_outputs(summary_out, sp_out)
    assert len(onus) == 3
    assert onus[0].serial == "ITBS0A97CF4C"
    assert onus[0].vlan == 621
    assert onus[0].last_down_cause == "dying_gasp"
    assert onus[1].serial == "HWTC181B37B2"
    assert onus[1].last_down_cause == "lofi"
    assert onus[2].serial == "PRKS00CF38B8"
    assert onus[2].name == "tiagofreitas"


def test_provision_and_deprovision_onu_commands(huawei_driver, sample_huawei_olt):
    pre_query_out = """
display ont info 0 1 0 all
  0/ 1/0    1  46485454FE27EDFF  active      offline  initial  initial  no
display ont-lineprofile gpon all
  1           SMARTOLT_FLEXIBLE_GPON                      17
  6           Generic_1_V621                              72
display ont-srvprofile gpon all
  1           Generic_1_V621                              72
  10          EG8145X6-10                                 23
display traffic table ip from-index 0
     8 1048064   2620160    1048064   2620160      0 -                local-pri
     9 1048064   2620160    1048064   2620160      0 -                local-pri
    12 209664    2620800    209664    2620800      0 -                local-pri
    """
    with patch.object(huawei_driver, "_execute_cli_commands", side_effect=[pre_query_out, "ONTID :0"]) as mock_cli:
        req = ProvisionRequest(
            port="0/1/0",
            serial="ITBS99887766",
            vlan=621,
            description="Cliente_Teste_Huawei",
            mode="bridge",
        )
        resp = huawei_driver.provision_onu(sample_huawei_olt, req)
        assert resp.success is True
        assert resp.onu_id == 0  # Menor ID livre na 0/1/0 (pois 1 está em uso e 0 estava livre)
        assert resp.serial == "ITBS99887766"
        prov_cmds = mock_cli.call_args_list[1][0][1]
        assert any('ont add 0 0 sn-auth "4954425399887766" omci ont-lineprofile-id 6 ont-srvprofile-id 1' in c for c in prov_cmds)
        assert any("ont port native-vlan 0 0 eth 1 vlan 621 priority 0" in c for c in prov_cmds)
        assert any("service-port vlan 621 gpon 0/1/0 ont 0 gemport 1 multi-service user-vlan 621" in c for c in prov_cmds)

    # Desprovisionamento deve executar undo service-port ANTES de ont delete
    with patch.object(huawei_driver, "_execute_cli_commands", return_value="OK") as mock_deprov:
        deprov_resp = huawei_driver.deprovision_onu(
            sample_huawei_olt,
            serial_or_id="ITBS99887766",
            port="0/1/0",
            onu_id=0,
        )
        assert deprov_resp.success is True
        d_cmds = mock_deprov.call_args[0][1]
        idx_undo_sp = d_cmds.index("undo service-port port 0/1/0 ont 0")
        idx_ont_del = d_cmds.index("ont delete 0 0")
        assert idx_undo_sp < idx_ont_del


def test_snmp_live_and_cipher_detection(huawei_driver, sample_huawei_olt):
    cfg = 'snmp-agent community read cipher "%+%##!!!!"'
    comm, is_cipher = huawei_driver.extract_snmp_community(cfg)
    assert comm is None and is_cipher is True

    live_out = """
   Community name: Yew1[qbci0kZ
   Storage type: nonVolatile
   View name: ViewDefault
    """
    with patch.object(huawei_driver, "_execute_cli_commands", return_value=live_out):
        live_comm, live_cipher = huawei_driver.get_snmp_community_live(sample_huawei_olt)
        assert live_comm == "Yew1[qbci0kZ"
        assert live_cipher is False


def test_huawei_change_onu_vlan_and_move_port(huawei_driver, sample_huawei_olt):
    info_out = """
  F/S/P                   : 0/1/0
  ONT-ID                  : 0
  Description             : CLIENTE_MIGRADO
    """
    sp_out = """
     0 621  common   gpon 0/1 /0  0    1     vlan  621        12   9    down
    """
    pre_out = """
    display ont info 0 1 0 all
    0/ 1/0    1  46485454FE27EDFF  active      offline   initial   initial   no
    display ont-lineprofile gpon all
      6      Generic_1_V621                      72
    display ont-srvprofile gpon all
      1      Generic_1_V621                      72
    display traffic table ip from-index 0
       9     1048064        off       2620160   1048064   2620160    0        local-setting
      12      209664        off       2620800    209664   2620800    0        local-setting
    """
    with patch.object(
        huawei_driver,
        "_execute_cli_commands",
        side_effect=[info_out, sp_out, pre_out, "OK"],
    ):
        vlan_res = huawei_driver.change_onu_vlan(sample_huawei_olt, "ITBS99887766", new_vlan=202)
        assert vlan_res.success is True
        assert vlan_res.action == "change_vlan"
        assert vlan_res.port == "0/1/0"
        assert vlan_res.onu_id == 0

    with patch.object(
        huawei_driver,
        "_execute_cli_commands",
        side_effect=[info_out, sp_out, "OK", pre_out, "OK"],
    ):
        move_res = huawei_driver.move_onu_port(sample_huawei_olt, "ITBS99887766", target_port="0/1/5")
        assert move_res.success is True
        assert move_res.action == "move_port"
        assert move_res.port == "0/1/5"
        assert move_res.onu_id == 0

