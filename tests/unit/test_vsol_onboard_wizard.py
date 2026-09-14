"""
Testes unitários e de integração de API para o Wizard de Onboarding da OLT V-SOL V1600GT.
Testa os endpoints /api/v1/olts/inspect e /api/v1/olts/onboard-wizard.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.drivers.vsol.vsol_v1600 import VSOLV1600Driver
from app.models.olt import (
    BandwidthPolicyType,
    BandwidthQoSPolicy,
    InBandManagementConfig,
    ManagementAccessScenario,
    OLTInspectRequest,
    OLTProtocol,
    OLTVendor,
    OLTWizardOnboardRequest,
    VLANServiceItem,
    VLANServicePurpose,
)
from app.models.vlan import SyncOLTResponse


MOCK_VSOL_CFG_AUX_ONLY = """
!
version 1.0.1R
hostname OLT_FACTORY
interface aux
 ip address 192.168.8.200 255.255.255.0
!
vlan 1
!
"""

MOCK_VSOL_CFG_AUX_WITH_INBAND = """
!
version 1.0.1R
hostname OLT_BANCADA_VSOL
interface aux
 ip address 192.168.8.200 255.255.255.0
!
vlan 1-2,100,500
!
interface vlan 2
 ip address 172.16.251.60/24
!
ip route 0.0.0.0/0 172.16.251.1
!
interface gigabitEthernet 0/1
 switchport mode hybrid
 switchport hybrid vlan 2,100,500 tagged
!
"""

MOCK_VSOL_CFG_INBAND_ACTIVE = """
!
version 1.0.1R
hostname OLT_PRODUCAO
interface aux
 ip address 192.168.8.200 255.255.255.0
!
vlan 1-2,100
!
interface vlan 2
 ip address 10.200.1.10/24
!
ip route 0.0.0.0/0 10.200.1.1
!
"""


def test_endpoint_inspect_aux_only(client, auth_headers):
    """Testa inspeção quando a OLT é acessada pela porta AUX e ainda não possui SVI in-band."""
    with patch("app.services.olt_onboarding_service.OLTOnboardingService.probe_connectivity", return_value=(OLTProtocol.SSH, 22, "VSOL V1600GT GPON OLT")), \
         patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory:

        mock_driver = MagicMock(spec=VSOLV1600Driver)
        mock_driver.get_running_config.return_value = MOCK_VSOL_CFG_AUX_ONLY
        mock_driver.parse_management_architecture.side_effect = VSOLV1600Driver.parse_management_architecture
        mock_factory.return_value = mock_driver

        payload = {
            "host": "192.168.8.200",
            "username": "admin",
            "password": "pwd",
        }

        resp = client.post("/api/v1/olts/inspect", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_scenario"] == ManagementAccessScenario.AUX_ONLY.value
        assert data["vendor"] == "vsol"
        assert data["aux_ip"] == "192.168.8.200"
        assert len(data["existing_svis"]) == 0
        assert "porta auxiliar" in data["prompt_message"].lower()


def test_endpoint_inspect_aux_with_inband(client, auth_headers):
    """Testa inspeção quando a OLT é acessada pela porta AUX, mas já possui gerência in-band configurada."""
    with patch("app.services.olt_onboarding_service.OLTOnboardingService.probe_connectivity", return_value=(OLTProtocol.SSH, 22, "VSOL V1600GT GPON OLT")), \
         patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory:

        mock_driver = MagicMock(spec=VSOLV1600Driver)
        mock_driver.get_running_config.return_value = MOCK_VSOL_CFG_AUX_WITH_INBAND
        mock_driver.parse_management_architecture.side_effect = VSOLV1600Driver.parse_management_architecture
        mock_factory.return_value = mock_driver

        payload = {
            "host": "192.168.8.200",
            "username": "admin",
            "password": "pwd",
        }

        resp = client.post("/api/v1/olts/inspect", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_scenario"] == ManagementAccessScenario.AUX_WITH_INBAND.value
        assert len(data["existing_svis"]) == 1
        assert data["existing_svis"][0]["vlan_id"] == 2
        assert data["existing_svis"][0]["ip_cidr"] == "172.16.251.60/24"
        assert data["gateway"] == "172.16.251.1"
        assert "in-band ativa" in data["prompt_message"].lower()


def test_endpoint_inspect_inband_active(client, auth_headers):
    """Testa inspeção quando a OLT é acessada diretamente pelo IP de gerência in-band."""
    with patch("app.services.olt_onboarding_service.OLTOnboardingService.probe_connectivity", return_value=(OLTProtocol.SSH, 22, "VSOL V1600GT GPON OLT")), \
         patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory:

        mock_driver = MagicMock(spec=VSOLV1600Driver)
        mock_driver.get_running_config.return_value = MOCK_VSOL_CFG_INBAND_ACTIVE
        mock_driver.parse_management_architecture.side_effect = VSOLV1600Driver.parse_management_architecture
        mock_factory.return_value = mock_driver

        payload = {
            "host": "10.200.1.10",
            "username": "admin",
            "password": "pwd",
        }

        resp = client.post("/api/v1/olts/inspect", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_scenario"] == ManagementAccessScenario.INBAND_ACTIVE.value
        assert len(data["existing_svis"]) == 1
        assert "rede do provedor" in data["prompt_message"].lower()



def test_endpoint_onboard_wizard_success(client, auth_headers, setup_test_env):
    """Testa o fluxo completo do Wizard de Onboarding com execução de comissionamento via API."""
    repo = setup_test_env["repo"]

    with patch("app.services.olt_onboarding_service.OLTOnboardingService.probe_connectivity", return_value=(OLTProtocol.SSH, 22, "VSOL V1600GT GPON OLT")), \
         patch("app.services.backup_service.BackupService.create_backup") as mock_bkp, \
         patch("app.services.olt_sync_service.OLTSyncService.sync_olt") as mock_sync, \
         patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory, \
         patch("app.services.snmp_collector.SNMPCollector.get_sys_uptime", return_value=864000):

        mock_bkp.return_value = MagicMock(backup_id="bkp-uuid-vsol-001")
        mock_sync.return_value = SyncOLTResponse(
            olt_id="fake-id",
            olt_name="OLT_BANCADA_VSOL",
            baseline_backup_id="bkp-uuid-vsol-001",
            total_onus_discovered=2,
            new_onus_registered=2,
            existing_onus_updated=0,
            vlans_discovered=[2, 100, 500],
            duration_ms=120.0,
            message="OK",
        )

        mock_driver = MagicMock()
        mock_driver.get_running_config.return_value = MOCK_VSOL_CFG_AUX_ONLY
        mock_driver.execute_wizard_commissioning.return_value = True
        mock_driver.extract_snmp_community.return_value = (None, False)
        mock_driver.configure_snmp.return_value = True
        mock_driver.get_chassis_interfaces.return_value = []
        mock_factory.return_value = mock_driver

        payload = {
            "name": "OLT_BANCADA_VSOL",
            "host": "192.168.8.200",
            "username": "admin",
            "password": "pwd",
            "inband_config": {
                "vlan_id": 2,
                "uplink_port": "ge 0/1",
                "ip_cidr": "172.16.251.60/24",
                "gateway": "172.16.251.1",
                "tagged": True,
                "name": "VLAN2_GERENCIA",
            },
            "services": [
                {
                    "vlan_id": 100,
                    "name": "INTERNET_FTTH",
                    "purpose": "pppoe_router",
                    "uplink_port": "ge 0/1",
                    "tagged": True,
                    "test_port": "ge 0/4",
                },
                {
                    "vlan_id": 500,
                    "name": "LAN_TO_LAN_P2P",
                    "purpose": "lan_to_lan",
                    "uplink_port": "ge 0/1",
                    "tagged": True,
                },
            ],
            "qos_policy": {
                "policy_type": "transparent_1g",
                "upstream_kbps": 1024000,
            },
        }

        resp = client.post("/api/v1/olts/onboard-wizard", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "OLT_BANCADA_VSOL"
        assert data["vendor"] == "vsol"
        assert data["protocol"] == "ssh"
        assert data["baseline_backup_id"] == "bkp-uuid-vsol-001"
        assert data["total_onus_detected"] == 2
        assert "_links" in data

        # Verifica se o driver executou o comissionamento do wizard
        mock_driver.execute_wizard_commissioning.assert_called_once()
        step_keys = [s["step_key"] for s in data["steps"]]
        assert "wizard_commissioning" in step_keys
        assert all(s["status"] in ["success", "warning"] for s in data["steps"])

        # Confirma persistência no repositório
        saved = repo.get_by_id(data["olt_id"])
        assert saved is not None
        assert saved.name == "OLT_BANCADA_VSOL"
        assert saved.vendor == OLTVendor.VSOL
