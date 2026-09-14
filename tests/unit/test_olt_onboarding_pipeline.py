"""
Testes unitários para o Onboarding Contínuo de OLTs Zero-Touch (OLTOnboardingService).
"""

from unittest.mock import MagicMock, patch
import pytest

from app.models.olt import (
    OLTOnboardRequest,
    OLTProtocol,
    OLTVendor,
)
from app.models.vlan import SyncOLTResponse
from app.services.olt_onboarding_service import (
    OLTOnboardingService,
    slugify_community,
)


def test_slugify_community():
    assert slugify_community("Provedor Alpha Fibra") == "provedor_alpha_fibra"
    assert slugify_community("GigaNet-100%_Telecom") == "giganet_100_telecom"
    assert slugify_community("") == "provedor"
    assert slugify_community(None) == "provedor"


def test_fingerprint_vendor_and_model():
    service = OLTOnboardingService(
        olt_repo=MagicMock(),
        backup_service=MagicMock(),
        sync_service=MagicMock(),
        telemetry_service=MagicMock(),
    )

    # Fiberhome
    v, m = service.fingerprint_vendor_and_model("Admin% Login successful\nAN5516-01 OLT")
    assert v == OLTVendor.FIBERHOME
    assert m == "an5516"

    # Huawei
    v, m = service.fingerprint_vendor_and_model("<HUAWEI-MA5800> VRP (R) Software")
    assert v == OLTVendor.HUAWEI
    assert m == "ma5800"

    # ZTE
    v, m = service.fingerprint_vendor_and_model("ZXA10 C320 OLT ZXROS version 2.1")
    assert v == OLTVendor.ZTE
    assert m == "c320"

    # Intelbras
    v, m = service.fingerprint_vendor_and_model("Intelbras OLT 8820 Max")
    assert v == OLTVendor.INTELBRAS
    assert m == "8820"

    # VSOL
    v, m = service.fingerprint_vendor_and_model("VSOL V1600G1 GPON OLT")
    assert v == OLTVendor.VSOL
    assert m == "v1600"


def test_probe_connectivity_ssh_success():
    service = OLTOnboardingService(
        olt_repo=MagicMock(),
        backup_service=MagicMock(),
        sync_service=MagicMock(),
        telemetry_service=MagicMock(),
    )

    with patch("paramiko.SSHClient") as mock_ssh_cls:
        mock_ssh = MagicMock()
        mock_channel = MagicMock()
        mock_channel.recv_ready.return_value = True
        mock_channel.recv.return_value = b"Admin% Fiberhome AN5516"
        mock_ssh.invoke_shell.return_value = mock_channel
        mock_ssh_cls.return_value = mock_ssh

        proto, port, banner = service.probe_connectivity("10.0.0.1", "admin", "secret")
        assert proto == OLTProtocol.SSH
        assert port == 22
        assert "Fiberhome" in banner


def test_probe_connectivity_fallback_to_telnet():
    service = OLTOnboardingService(
        olt_repo=MagicMock(),
        backup_service=MagicMock(),
        sync_service=MagicMock(),
        telemetry_service=MagicMock(),
    )

    with patch("paramiko.SSHClient.connect", side_effect=ConnectionError("Port 22 closed")), \
         patch("app.services.olt_onboarding_service.TelnetClient") as mock_tn_cls:

        mock_tn = MagicMock()
        mock_tn.read_until.return_value = b"Login: Admin%"
        mock_tn_cls.return_value = mock_tn

        proto, port, banner = service.probe_connectivity("10.0.0.1", "admin", "secret")
        assert proto == OLTProtocol.TELNET
        assert port == 23


def test_probe_connectivity_both_fail():
    service = OLTOnboardingService(
        olt_repo=MagicMock(),
        backup_service=MagicMock(),
        sync_service=MagicMock(),
        telemetry_service=MagicMock(),
    )

    with patch("paramiko.SSHClient.connect", side_effect=ConnectionRefusedError("SSH Refused")), \
         patch("app.services.olt_onboarding_service.TelnetClient") as mock_tn_cls:

        mock_tn = MagicMock()
        mock_tn.connect.side_effect = TimeoutError("Telnet Timeout")
        mock_tn_cls.return_value = mock_tn

        with pytest.raises(ConnectionError, match="Não foi possível autenticar"):
            service.probe_connectivity("10.0.0.1", "admin", "secret")


def test_execute_onboarding_pipeline_full(setup_test_env):
    repo = setup_test_env["repo"]
    storage = setup_test_env["storage"]
    onu_repo = setup_test_env["onu_repo"]

    backup_service = MagicMock()
    mock_backup = MagicMock()
    mock_backup.backup_id = "0191e4a0-test-backup-0001"
    backup_service.create_backup.return_value = mock_backup

    sync_service = MagicMock()
    sync_service.sync_olt.return_value = SyncOLTResponse(
        olt_id="0191e4a0-temp",
        olt_name="OLT-ONBOARD-TEST",
        baseline_backup_id="0191e4a0-test-backup-0001",
        total_onus_discovered=42,
        new_onus_registered=42,
        existing_onus_updated=0,
        vlans_discovered=[100, 200],
        duration_ms=145.2,
        message="OK",
    )

    telemetry_service = MagicMock()
    mock_xray = MagicMock()
    mock_xray.firmware_version = "GEPON_NGN_V4.0"
    mock_xray.uptime_human = "10 dias, 2 horas"
    mock_xray.ports = [MagicMock(oper_status="up"), MagicMock(oper_status="down")]
    telemetry_service.inspect_chassis.return_value = mock_xray

    service = OLTOnboardingService(
        olt_repo=repo,
        backup_service=backup_service,
        sync_service=sync_service,
        telemetry_service=telemetry_service,
    )

    with patch.object(service, "probe_connectivity", return_value=(OLTProtocol.TELNET, 23, "Admin% Fiberhome AN5516")), \
         patch("app.drivers.factory.DriverFactory.get_driver") as mock_driver_factory, \
         patch("app.services.snmp_collector.SNMPCollector.get_sys_uptime", return_value=12345):

        mock_driver = MagicMock()
        mock_driver.get_running_config.return_value = "! running config\n"
        mock_driver.extract_snmp_community.return_value = (None, False)
        mock_driver.configure_snmp.return_value = True
        mock_driver_factory.return_value = mock_driver

        req = OLTOnboardRequest(
            name="OLT-ONBOARD-TEST",
            host="192.168.10.1",
            username="admin",
            password="secretpassword",
        )

        res = service.execute_onboarding(req, tenant_name="Alpha Telecom")

        assert res.name == "OLT-ONBOARD-TEST"
        assert res.vendor == OLTVendor.FIBERHOME
        assert res.protocol == OLTProtocol.TELNET
        assert res.port == 23
        assert res.baseline_backup_id == "0191e4a0-test-backup-0001"
        assert res.snmp_community == "olt_alpha_telecom"
        assert res.snmp_active is True
        assert res.total_onus_detected == 42
        assert res.firmware_version == "GEPON_NGN_V4.0"
        assert len(res.steps) == 5
        assert all(s.status in ["success", "warning"] for s in res.steps)

        # Confirma que OLT foi salva no repositório com os dados corretos
        saved = repo.get_by_id(res.olt_id)
        assert saved is not None
        assert saved.name == "OLT-ONBOARD-TEST"
        assert saved.snmp_community == "olt_alpha_telecom"


def test_endpoint_onboard_api(client, auth_headers, setup_test_env):
    repo = setup_test_env["repo"]

    with patch("app.services.olt_onboarding_service.OLTOnboardingService.probe_connectivity", return_value=(OLTProtocol.SSH, 22, "<HUAWEI-MA5800>")), \
         patch("app.services.backup_service.BackupService.create_backup") as mock_bkp, \
         patch("app.services.olt_sync_service.OLTSyncService.sync_olt") as mock_sync, \
         patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory, \
         patch("app.services.snmp_collector.SNMPCollector.get_sys_uptime", return_value=99999):

        mock_bkp.return_value = MagicMock(backup_id="bkp-uuid-999")
        mock_sync.return_value = SyncOLTResponse(
            olt_id="fake-id",
            olt_name="OLT-HUAWEI-ONBOARD",
            baseline_backup_id="bkp-uuid-999",
            total_onus_discovered=10,
            new_onus_registered=10,
            existing_onus_updated=0,
            vlans_discovered=[100],
            duration_ms=88.0,
            message="OK",
        )

        mock_driver = MagicMock()
        mock_driver.get_running_config.return_value = "! Huawei config"
        mock_driver.extract_snmp_community.return_value = ("existing_ro_comm", False)
        mock_driver.get_chassis_interfaces.return_value = []
        mock_factory.return_value = mock_driver

        payload = {
            "name": "OLT-HUAWEI-ONBOARD",
            "host": "10.50.0.1",
            "username": "huawei_admin",
            "password": "huawei_pass",
        }

        resp = client.post("/api/v1/olts/onboard", json=payload, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "OLT-HUAWEI-ONBOARD"
        assert data["vendor"] == "huawei"
        assert data["protocol"] == "ssh"
        assert data["port"] == 22
        assert data["snmp_community"] == "existing_ro_comm"
        assert data["snmp_active"] is True
        assert data["total_onus_detected"] == 10
        assert "_links" in data


@pytest.mark.asyncio
async def test_execute_onboarding_stream(setup_test_env):
    import json
    repo = setup_test_env["repo"]
    onu_repo = setup_test_env["onu_repo"]

    backup_service = MagicMock()
    mock_backup = MagicMock()
    mock_backup.backup_id = "0191e4a0-stream-backup"
    backup_service.create_backup.return_value = mock_backup

    sync_service = MagicMock()
    sync_service.sync_olt.return_value = SyncOLTResponse(
        olt_id="fake-stream-olt",
        olt_name="OLT-STREAM-TEST",
        baseline_backup_id="0191e4a0-stream-backup",
        total_onus_discovered=15,
        new_onus_registered=15,
        existing_onus_updated=0,
        vlans_discovered=[100],
        duration_ms=45.0,
        message="OK",
    )
    sync_service.onu_repo = onu_repo

    telemetry_service = MagicMock()

    service = OLTOnboardingService(
        olt_repo=repo,
        backup_service=backup_service,
        sync_service=sync_service,
        telemetry_service=telemetry_service,
    )

    with patch.object(service, "probe_connectivity", return_value=(OLTProtocol.TELNET, 23, "Admin% Fiberhome AN5516")), \
         patch("app.drivers.factory.DriverFactory.get_driver") as mock_driver_factory, \
         patch("app.services.snmp_collector.SNMPCollector.get_sys_uptime", return_value=54321):

        mock_driver = MagicMock()
        mock_driver.get_snmp_community_live.return_value = ("oltAlpha", False)
        mock_driver_factory.return_value = mock_driver

        req = OLTOnboardRequest(
            name="OLT-STREAM-TEST",
            host="192.168.10.99",
            username="admin",
            password="pass",
        )

        events = []
        async for chunk in service.execute_onboarding_stream(req, tenant_name="Alpha Telecom"):
            assert chunk.startswith("data: ")
            json_data = json.loads(chunk[6:].strip())
            events.append(json_data)

        # Verifica eventos emitidos
        event_types = [e["type"] for e in events]
        assert "step_update" in event_types
        assert "completed" in event_types

        # Verifica que o evento final tem os dados da OLT
        completed = next(e for e in events if e["type"] == "completed")
        assert completed["response"]["name"] == "OLT-STREAM-TEST"
        assert completed["response"]["snmp_community"] == "oltAlpha"
        assert completed["response"]["snmp_active"] is True
        assert completed["response"]["total_onus_detected"] == 15


def test_endpoint_onboard_stream_api(client, auth_headers, setup_test_env):
    import json
    with patch("app.services.olt_onboarding_service.OLTOnboardingService.probe_connectivity", return_value=(OLTProtocol.SSH, 22, "<HUAWEI-MA5800>")), \
         patch("app.services.backup_service.BackupService.create_backup") as mock_bkp, \
         patch("app.services.olt_sync_service.OLTSyncService.sync_olt") as mock_sync, \
         patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory, \
         patch("app.services.snmp_collector.SNMPCollector.get_sys_uptime", return_value=88888):

        mock_bkp.return_value = MagicMock(backup_id="bkp-stream-uuid")
        mock_sync.return_value = SyncOLTResponse(
            olt_id="stream-olt-id",
            olt_name="OLT-STREAM-API",
            baseline_backup_id="bkp-stream-uuid",
            total_onus_discovered=8,
            new_onus_registered=8,
            existing_onus_updated=0,
            vlans_discovered=[200],
            duration_ms=40.0,
            message="OK",
        )

        mock_driver = MagicMock()
        mock_driver.get_snmp_community_live.return_value = (None, False)
        mock_driver.extract_snmp_community.return_value = ("stream_comm", False)
        mock_driver.get_chassis_interfaces.return_value = []
        mock_factory.return_value = mock_driver

        payload = {
            "name": "OLT-STREAM-API",
            "host": "10.60.0.1",
            "username": "stream_user",
            "password": "stream_pass",
        }

        resp = client.post("/api/v1/olts/onboard/stream", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        # Parse SSE events from response text
        lines = resp.text.split("\n")
        data_lines = [l.replace("data: ", "").strip() for l in lines if l.startswith("data: ")]
        parsed_events = [json.loads(d) for d in data_lines if d]

        assert any(e.get("type") == "step_update" for e in parsed_events)
        completed_ev = next(e for e in parsed_events if e.get("type") == "completed")
        assert completed_ev["response"]["name"] == "OLT-STREAM-API"
        assert completed_ev["response"]["total_onus_detected"] == 8

