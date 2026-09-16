"""
Testes unitários para Telemetria de Chassi Orientada a Objetos, Coletor SNMP e Retenção Particionada.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.core.uuid import is_valid_uuid7
from app.drivers.fiberhome.fiberhome_tl1 import FiberhomeTL1Driver
from app.drivers.vsol.vsol_v1600 import VSOLV1600Driver
from app.models.olt import OLTInDB, OLTProtocol, OLTVendor
from app.models.onu import ONUSummary
from app.services.snmp_collector import SNMPCollector, _build_snmp_get, _decode_snmp_response, _encode_oid
from app.services.telemetry_retention_service import TelemetryRetentionService


@pytest.fixture
def fake_olt():
    return OLTInDB(
        id="0191e4a0-0000-7000-8000-000000000001",
        name="OLT-TEST-TELEMETRY",
        vendor=OLTVendor.FIBERHOME,
        model="AN5516-01",
        host="192.168.1.100",
        port=23,
        protocol=OLTProtocol.TELNET,
        username="admin",
        password="secretpassword",
        snmp_community="public",
        snmp_port=161,
        snmp_version="v2c",
    )


# -----------------------------------------------------------------------------
# 1. Testes de Orientação a Objetos nos Drivers (Polimorfismo & Portas Físicas)
# -----------------------------------------------------------------------------

def test_fiberhome_get_chassis_interfaces(fake_olt):
    driver = FiberhomeTL1Driver()
    mock_onus = [
        ONUSummary(port="1/1", onu_id=1, serial="FHTT11111111", status="online"),
        ONUSummary(port="1/1", onu_id=2, serial="FHTT22222222", status="online"),
        ONUSummary(port="1/2", onu_id=1, serial="FHTT33333333", status="offline"),
    ]
    with patch.object(driver, "list_all_authorized_onus", return_value=mock_onus):
        ports = driver.get_chassis_interfaces(fake_olt)
        assert len(ports) >= 18  # 16 PON + 2 Uplink
        pon1 = next(p for p in ports if p.port_id == "gpon 0/1/1")
        assert pon1.oper_status == "up"
        assert pon1.onu_count == 2
        assert "2 ONUs" in pon1.details

        pon2 = next(p for p in ports if p.port_id == "gpon 0/1/2")
        assert pon2.oper_status == "up"
        assert pon2.onu_count == 1

        pon3 = next(p for p in ports if p.port_id == "gpon 0/1/3")
        assert pon3.oper_status == "up"  # Laser ativo mesmo com 0 ONUs
        assert pon3.onu_count == 0

        # Uplink
        up1 = next(p for p in ports if p.port_id == "xg 0/0/1")
        assert up1.oper_status == "up"
        assert up1.port_type == "xg"


def test_fiberhome_get_chassis_interfaces_multislot(fake_olt):
    driver = FiberhomeTL1Driver()
    mock_onus = [
        ONUSummary(port="1/1", onu_id=1, serial="FHTT11111111", status="online"),
        ONUSummary(port="1/16", onu_id=1, serial="FHTT11111116", status="online"),
        ONUSummary(port="11/1", onu_id=1, serial="FHTT11010001", status="online"),
        ONUSummary(port="11/8", onu_id=1, serial="FHTT11080001", status="online"),
    ]
    with patch.object(driver, "list_all_authorized_onus", return_value=mock_onus):
        ports = driver.get_chassis_interfaces(fake_olt)
        # 16 PON (Slot 1) + 8 PON (Slot 11) + 2 Uplink = 26 portas
        assert len(ports) == 26
        slot1_pon1 = next(p for p in ports if p.port_id == "gpon 0/1/1")
        assert slot1_pon1.onu_count == 1
        slot1_pon16 = next(p for p in ports if p.port_id == "gpon 0/1/16")
        assert slot1_pon16.onu_count == 1
        slot11_pon1 = next(p for p in ports if p.port_id == "gpon 0/11/1")
        assert slot11_pon1.onu_count == 1
        slot11_pon8 = next(p for p in ports if p.port_id == "gpon 0/11/8")
        assert slot11_pon8.onu_count == 1
        slot11_pon2 = next(p for p in ports if p.port_id == "gpon 0/11/2")
        assert slot11_pon2.onu_count == 0  # Sem ONU, mas porta física renderizada


def test_vsol_get_chassis_interfaces(fake_olt):
    driver = VSOLV1600Driver(model_name="V1600G2")
    fake_olt.vendor = OLTVendor.VSOL
    fake_olt.model = "V1600G2"
    mock_onus = [
        ONUSummary(port="0/1", onu_id=1, serial="VSOL11111111", status="online"),
    ]
    with patch.object(driver, "list_all_authorized_onus", return_value=mock_onus), \
         patch.object(driver, "get_running_config", return_value=""):
        ports = driver.get_chassis_interfaces(fake_olt)
        assert len(ports) == 6  # 2 PON + 4 Uplink
        pon1 = next(p for p in ports if p.port_id == "gpon 0/1")
        assert pon1.oper_status == "up"
        assert pon1.onu_count == 1
        pon2 = next(p for p in ports if p.port_id == "gpon 0/2")
        assert pon2.oper_status == "up"
        assert pon2.onu_count == 0


# -----------------------------------------------------------------------------
# 2. Testes do Coletor SNMP (Encoding, Decoding e Fallback)
# -----------------------------------------------------------------------------

def test_snmp_oid_and_packet_encoding():
    encoded_oid = _encode_oid("1.3.6.1.2.1.1.3.0")
    assert len(encoded_oid) > 0
    assert encoded_oid[0] == 0x06  # ASN.1 OID tag

    packet = _build_snmp_get("public", "1.3.6.1.2.1.1.3.0")
    assert packet[0] == 0x30  # ASN.1 Sequence
    assert b"public" in packet


def test_snmp_response_decoding():
    # Simula resposta ASN.1 TimeTicks (tag 0x43, length 4, valor 12345678)
    mock_resp = b"\x30\x20\x02\x01\x01\x04\x06public\xa2\x13\x02\x04\x00\x00\x03\xe9\x02\x01\x00\x02\x01\x00\x30\x07\x30\x05\x06\x01\x00\x43\x04\x00\xbc\x61\x4e"
    val = _decode_snmp_response(mock_resp)
    assert val == 12345678


def test_snmp_collector_fallback_on_unreachable():
    # Testa timeout em host inexistente ou inacessível sem quebrar
    uptime = SNMPCollector.get_sys_uptime("192.0.2.1", community="invalid", timeout=0.1)
    assert uptime is None


# -----------------------------------------------------------------------------
# 3. Testes do Serviço de Retenção e Particionamento
# -----------------------------------------------------------------------------

def test_telemetry_retention_service(setup_test_env, fake_olt):
    session_factory = setup_test_env["session_factory"]
    repo = setup_test_env["repo"]
    created_olt = repo.create(fake_olt)

    with session_factory() as db:
        # Grava snapshot
        record = TelemetryRetentionService.record_snapshot(
            db=db,
            olt_id=created_olt.id,
            online_onus=42,
            offline_onus=3,
            active_ports=16,
            uptime_seconds=36000,
        )
        assert is_valid_uuid7(record.id)
        assert record.olt_id == created_olt.id
        assert record.online_onus == 42
        assert record.uptime_seconds == 36000

        # Testa criação de partições preventivas
        partitions = TelemetryRetentionService.ensure_monthly_partitions(db, months_ahead=2)
        assert isinstance(partitions, list)

        # Testa descarte de partições expiradas (janela de 90 dias)
        purged = TelemetryRetentionService.purge_expired_partitions(db, retention_days=90)
        assert isinstance(purged, list)


# -----------------------------------------------------------------------------
# 4. Testes de Extração de Comunidade e Detecção de Cipher por Fabricante
# -----------------------------------------------------------------------------

def test_extract_snmp_community_fiberhome_and_vsol():
    # Fiberhome
    fh_driver = FiberhomeTL1Driver()
    comm, is_cipher = fh_driver.extract_snmp_community("snmp-server community fh_fibra_ro ro\n")
    assert comm == "fh_fibra_ro"
    assert is_cipher is False

    comm, _ = fh_driver.extract_snmp_community('SET-SNMP-COMMUNITY:::1::COMMUNITY="fh_tl1_com",PERMISSION=RO;')
    assert comm == "fh_tl1_com"

    # Fiberhome WOS (running-config / backup real)
    comm, _ = fh_driver.extract_snmp_community("set snmp community readonly oltProserv\n")
    assert comm == "oltProserv"

    comm, _ = fh_driver.extract_snmp_community("set snmp community readwrite adsl\n")
    assert comm == "adsl"

    # VSOL
    vsol_driver = VSOLV1600Driver()
    comm, _ = vsol_driver.extract_snmp_community("snmp-server community vsol_noc_ro ro\n")
    assert comm == "vsol_noc_ro"


# -----------------------------------------------------------------------------
# 5. Testes de Provisionamento CLI e Gravação na Flash (save/write)
# -----------------------------------------------------------------------------

def test_configure_snmp_cli_fiberhome_and_vsol(fake_olt):
    # Fiberhome Telnet CLI
    fh = FiberhomeTL1Driver()
    mock_telnet = MagicMock()
    with patch.object(fh, "_open_telnet_session", return_value=mock_telnet), \
         patch.object(fh, "_exec_telnet_cmd", return_value="OK") as mock_exec:
        success = fh.configure_snmp(fake_olt, "fh_ro_test")
        assert success is True
        executed = [call[0][1] for call in mock_exec.call_args_list]
        assert "set snmp community readonly fh_ro_test" in executed
        assert "save" in executed

    # Fiberhome TL1 Puro (porta 3337)
    fake_olt_tl1 = fake_olt.model_copy(update={"port": 3337})
    with patch.object(fh, "_execute_tl1_commands", return_value="COMPLD") as mock_tl1, \
         patch.object(fh, "save_running_config", return_value=True):
        success = fh.configure_snmp(fake_olt_tl1, "fh_tl1_test")
        assert success is True
        calls = mock_tl1.call_args[0][1]
        assert any("fh_tl1_test" in c for c in calls)

    # VSOL
    vsol = VSOLV1600Driver()
    with patch.object(vsol, "_execute_cli_commands", return_value="OK") as mock_cli:
        success = vsol.configure_snmp(fake_olt, "vsol_ro_test")
        assert success is True
        calls = mock_cli.call_args[0][1]
        assert any("vsol_ro_test" in c for c in calls)
        assert "write" in calls


# -----------------------------------------------------------------------------
# 6. Testes da Telemetria com Auto-Descoberta Reversa
# -----------------------------------------------------------------------------

def test_telemetry_reverse_discovery_success(setup_test_env, fake_olt):
    from app.services.olt_telemetry_service import OLTTelemetryService
    repo = setup_test_env["repo"]
    storage = setup_test_env["storage"]
    onu_repo = setup_test_env["onu_repo"]

    # Cria OLT com comunidade inválida inicial "unconfigured"
    fake_olt.snmp_community = "invalid_initial_comm"
    fake_olt.name = "OLT-REVERSE-DISC-TEST"
    created = repo.create(fake_olt)

    telemetry_svc = OLTTelemetryService(olt_repo=repo, onu_repo=onu_repo, storage=storage)

    # Simula running-config contendo comunidade em texto claro da OLT
    mock_config = "! Configuração de Backup da OLT\nsnmp-server community auto_discovered_ro ro\n"

    with patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory, \
         patch("app.services.snmp_collector.SNMPCollector.test_snmp_connectivity") as mock_test_snmp, \
         patch("app.services.snmp_collector.SNMPCollector.get_sys_uptime", return_value=864000):

        mock_driver = MagicMock()
        mock_driver.get_running_config.return_value = mock_config
        mock_driver.list_vlans.return_value = []
        mock_driver.get_chassis_interfaces.return_value = []
        mock_driver.list_all_authorized_onus.return_value = []
        mock_driver.extract_snmp_community.return_value = ("auto_discovered_ro", False)
        mock_factory.return_value = mock_driver

        # Resposta: com comunidade antiga falha (False), com comunidade descoberta passa (True)
        def side_effect_test(host, community, port, timeout=0.8):
            return community == "auto_discovered_ro"

        mock_test_snmp.side_effect = side_effect_test

        result = telemetry_svc.inspect_chassis(created.id)

        # Valida que auto-descobriu e adotou no cadastro
        assert result.snmp_active is True
        assert result.snmp_status == "active"
        assert result.snmp_community == "auto_discovered_ro"
        assert "auto-descoberta" in result.snmp_message

        # Verifica persistência no banco
        reloaded = repo.get_by_id(created.id)
        assert reloaded.snmp_community == "auto_discovered_ro"


def test_telemetry_cipher_detection(setup_test_env, fake_olt):
    from app.services.olt_telemetry_service import OLTTelemetryService
    repo = setup_test_env["repo"]
    storage = setup_test_env["storage"]
    onu_repo = setup_test_env["onu_repo"]

    fake_olt.name = "OLT-CIPHER-TEST"
    fake_olt.vendor = OLTVendor.HUAWEI
    fake_olt.snmp_community = "public"
    created = repo.create(fake_olt)

    telemetry_svc = OLTTelemetryService(olt_repo=repo, onu_repo=onu_repo, storage=storage)

    with patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory, \
         patch("app.services.snmp_collector.SNMPCollector.test_snmp_connectivity", return_value=False):

        mock_driver = MagicMock()
        mock_driver.get_running_config.return_value = "snmp-server community read cipher %#%#hash...\n"
        mock_driver.list_vlans.return_value = []
        mock_driver.get_chassis_interfaces.return_value = []
        mock_driver.list_all_authorized_onus.return_value = []
        mock_driver.extract_snmp_community.return_value = (None, True)
        mock_factory.return_value = mock_driver

        result = telemetry_svc.inspect_chassis(created.id)

        assert result.snmp_active is False
        assert result.snmp_status == "cipher_detected"
        assert "criptografada" in result.snmp_message


def test_telemetry_auto_discovery_from_backup_storage(setup_test_env, fake_olt):
    from app.services.olt_telemetry_service import OLTTelemetryService
    from app.models.backup import BackupMetadata
    repo = setup_test_env["repo"]
    storage = setup_test_env["storage"]
    onu_repo = setup_test_env["onu_repo"]

    fake_olt.name = "OLT-STORAGE-BKP-TEST"
    fake_olt.snmp_community = "wrong_comm"
    created = repo.create(fake_olt)

    # Cria backup real no storage com comunidade
    bkp_meta = storage.save_backup(
        olt_id=created.id,
        content="! Backup salvo em disco\nset snmp community readonly discovered_storage_ro\n",
    )

    telemetry_svc = OLTTelemetryService(olt_repo=repo, onu_repo=onu_repo, storage=storage)

    with patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory, \
         patch("app.services.snmp_collector.SNMPCollector.test_snmp_connectivity") as mock_test_snmp, \
         patch("app.services.snmp_collector.SNMPCollector.get_sys_uptime", return_value=55555):

        mock_driver = MagicMock()
        # Simula falha ao coletar running-config ao vivo da OLT
        mock_driver.get_running_config.side_effect = ConnectionError("Timeout CLI")
        mock_driver.list_vlans.return_value = []
        mock_driver.get_chassis_interfaces.return_value = []
        mock_driver.list_all_authorized_onus.return_value = []
        # O driver real extrairia do config de backup recuperado pelo storage
        mock_driver.extract_snmp_community.side_effect = lambda cfg: ("discovered_storage_ro", False) if "discovered_storage_ro" in cfg else (None, False)
        mock_factory.return_value = mock_driver

        def side_effect_test(host, community, port, timeout=0.8):
            return community == "discovered_storage_ro"

        mock_test_snmp.side_effect = side_effect_test

        result = telemetry_svc.inspect_chassis(created.id)

        assert result.snmp_active is True
        assert result.snmp_status == "active"
        assert result.snmp_community == "discovered_storage_ro"
        assert "auto-descoberta" in result.snmp_message

        # Confirma que persistiu no cadastro
        reloaded = repo.get_by_id(created.id)
        assert reloaded.snmp_community == "discovered_storage_ro"


# -----------------------------------------------------------------------------
# 7. Testes dos Endpoints REST de Teste e Provisionamento SNMP
# -----------------------------------------------------------------------------

def test_endpoints_snmp_test_and_configure(client, auth_headers, setup_test_env, fake_olt):
    repo = setup_test_env["repo"]
    fake_olt.name = "OLT-ENDPOINT-SNMP-TEST"
    created = repo.create(fake_olt)

    # 7.1 Teste SNMP com sucesso
    with patch("app.services.snmp_collector.SNMPCollector.get_sys_uptime", return_value=123456):
        resp = client.post(
            f"/api/v1/olts/{created.id}/snmp/test",
            json={"community": "test_comm_123", "port": 161, "save_if_successful": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reachable"] is True
        assert data["uptime_seconds"] == 123456
        assert data["saved_to_db"] is True

        reloaded = repo.get_by_id(created.id)
        assert reloaded.snmp_community == "test_comm_123"

    # 7.2 Provisionamento SNMP via CLI (SUPER_ADMIN)
    with patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory, \
         patch("app.services.snmp_collector.SNMPCollector.get_sys_uptime", return_value=99999):
        mock_driver = MagicMock()
        mock_driver.configure_snmp.return_value = True
        mock_factory.return_value = mock_driver

        resp = client.post(
            f"/api/v1/olts/{created.id}/snmp/configure",
            json={"community": "noc_ro_2026", "port": 161},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured_in_cli"] is True
        assert data["saved_to_flash"] is True
        assert data["tested_ok"] is True
        assert data["community"] == "noc_ro_2026"

        reloaded = repo.get_by_id(created.id)
        assert reloaded.snmp_community == "noc_ro_2026"


def test_firmware_version_extraction_ignores_comments_and_dashes(setup_test_env, fake_olt):
    from app.services.olt_telemetry_service import OLTTelemetryService
    repo = setup_test_env["repo"]
    storage = setup_test_env["storage"]
    onu_repo = setup_test_env["onu_repo"]
    fake_olt.name = "OLT-FIRMWARE-TEST"
    created = repo.create(fake_olt)

    telemetry_svc = OLTTelemetryService(olt_repo=repo, storage=storage, onu_repo=onu_repo)

    # Config com comentários tracejados que anteriormente quebravam a extração
    cfg_fiberhome = """
    set version_cfg enable
    !ngn config version -------------------------------------------------
    check ngn_cfg version GEPON_NGN_V4.0 
    !ngn config version end -------------------------------------------------
    set mld version v2
    set snmp trapreceiver add ::ffff:143.208.136.35 version v2c community adsl signaltrace_switch disable
    """

    with patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory:
        mock_driver = MagicMock()
        mock_driver.get_running_config.return_value = cfg_fiberhome
        mock_driver.list_vlans.return_value = []
        mock_driver.get_chassis_interfaces.return_value = []
        mock_driver.list_all_authorized_onus.return_value = []
        mock_driver.extract_snmp_community.return_value = (None, False)
        mock_factory.return_value = mock_driver

        res = telemetry_svc.inspect_chassis(created.id)
        assert res.firmware_version == "GEPON_NGN_V4.0"
        assert not res.firmware_version.startswith("-")
