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
        mock_exec.return_value = "interface gpon 0/2\nexit"
        res = driver.provision_onu(olt, req)

        assert res.success is True
        assert res.port == "0/2"
        assert res.serial == "VSOL12345678"

        # O driver consulta o running config e depois aplica os comandos
        assert mock_exec.call_count == 2
        cmds_called = mock_exec.call_args_list[1][0][1]
        assert "interface gpon 0/2" in cmds_called
        assert any("onu add 1 profile default sn VSOL12345678" in c for c in cmds_called)
        assert any("onu 1 profile line name line_1" in c for c in cmds_called)
        assert any("onu 1 profile srv name srv_1" in c for c in cmds_called)
        assert any('onu 1 desc "Cliente_Bancada_1"' in c for c in cmds_called)
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


def test_vsol_parse_management_architecture_scenarios():
    driver = VSOLV1600Driver()

    # Cenário 1: Bancada Pura (AUX_ONLY)
    cfg_aux_only = """
    interface aux
    ip address 192.168.8.200 255.255.255.0
    exit
    vlan 1
    exit
    """
    res1 = driver.parse_management_architecture(cfg_aux_only, "192.168.8.200")
    assert res1["access_scenario"] == "aux_only"
    assert res1["aux_ip"] == "192.168.8.200"
    assert len(res1["existing_svis"]) == 0
    assert "não possui gerência In-Band" in res1["prompt_message"]

    # Cenário 2: Conectado na AUX, mas In-Band já configurada (AUX_WITH_INBAND)
    cfg_aux_with_inband = """
    interface aux
    ip address 192.168.8.200 255.255.255.0
    exit
    vlan 1 - 2
    vlan 2
    description VLAN2_GERENCIA
    exit
    interface vlan 2
    ip address 172.16.251.60/24
    exit
    ip route 0.0.0.0/0 172.16.251.1
    """
    res2 = driver.parse_management_architecture(cfg_aux_with_inband, "192.168.8.200")
    assert res2["access_scenario"] == "aux_with_inband"
    assert res2["aux_ip"] == "192.168.8.200"
    assert len(res2["existing_svis"]) == 1
    assert res2["existing_svis"][0].vlan_id == 2
    assert res2["gateway"] == "172.16.251.1"
    assert "já possui gerência In-Band ativa" in res2["prompt_message"]

    # Cenário 3: Acesso Direto In-Band em Produção (INBAND_ACTIVE)
    res3 = driver.parse_management_architecture(cfg_aux_with_inband, "172.16.251.60")
    assert res3["access_scenario"] == "inband_active"
    assert "Acesso direto via In-Band" in res3["prompt_message"]


def test_vsol_compact_onu_state_parser():
    driver = VSOLV1600Driver()
    raw_state = """
    OnuIndex    Admin State    OMCC State    Phase State    Serial Number
    ---------------------------------------------------------------
    2:1enableenableworkingHWTC073545b7
    2:2enableenablesyncMibITBS5f44ca50
    total: 2 working: 1
    """
    onus = driver.parse_port_onus(raw_state)
    assert len(onus) == 2
    assert onus[0].port == "0/2"
    assert onus[0].onu_id == 1
    assert onus[0].serial == "HWTC073545b7"
    assert onus[0].status == "online"

    assert onus[1].port == "0/2"
    assert onus[1].onu_id == 2
    assert onus[1].serial == "ITBS5f44ca50"
    assert onus[1].status == "online"


def test_vsol_generate_wizard_commissioning_commands():
    from app.models.olt import (
        BandwidthPolicyType,
        BandwidthQoSPolicy,
        InBandManagementConfig,
        OLTWizardOnboardRequest,
        VLANServiceItem,
        VLANServicePurpose,
    )
    driver = VSOLV1600Driver()
    req = OLTWizardOnboardRequest(
        name="OLT_BANCADA_VSOL",
        host="192.168.8.200",
        username="admin",
        password="pwd",
        inband_config=InBandManagementConfig(
            vlan_id=2,
            uplink_port="ge 0/1",
            ip_cidr="172.16.251.60/24",
            gateway="172.16.251.1",
            tagged=True,
            name="MGMT_VLAN2",
        ),
        services=[
            VLANServiceItem(
                vlan_id=100,
                name="INTERNET_FTTH",
                purpose=VLANServicePurpose.PPPOE_ROUTER,
                uplink_port="ge 0/1",
                tagged=True,
                test_port="ge 0/4",
            ),
            VLANServiceItem(
                vlan_id=500,
                name="LAN_TO_LAN_P2P",
                purpose=VLANServicePurpose.LAN_TO_LAN,
                uplink_port="ge 0/1",
                tagged=True,
            ),
        ],
        qos_policy=BandwidthQoSPolicy(
            policy_type=BandwidthPolicyType.TRANSPARENT_1G,
            upstream_kbps=1024000,
        ),
    )

    cmds = driver.generate_wizard_commissioning_commands(req)
    cmd_str = "\n".join(cmds)

    # In-Band SVI
    assert "interface vlan 2" in cmd_str
    assert "ip address 172.16.251.60/24" in cmd_str
    assert "ip route 0.0.0.0/0 172.16.251.1" in cmd_str
    assert "switchport hybrid vlan 2 tagged" in cmd_str

    # Test Port Untagged
    assert "interface gigabitEthernet 0/4" in cmd_str
    assert "switchport hybrid pvid vlan 100" in cmd_str
    assert "switchport hybrid vlan 100 untagged" in cmd_str

    # Line Profiles com commit
    assert "profile line id 100 name line_vlan100" in cmd_str
    assert "profile line id 500 name line_vlan500" in cmd_str
    assert "commit" in cmd_str

    # Service Profiles com commit
    assert "profile srv id 10 name srv_hgu" in cmd_str
    assert "portvlan veip 1 mode transparent" in cmd_str
    assert "profile srv id 20 name srv_bridge" in cmd_str
    assert "portvlan eth 1 mode transparent" in cmd_str

    # P2P enable para LAN-to-LAN
    assert "p2p enable" in cmd_str

    # Persistência final
    assert "write" in cmd_str

