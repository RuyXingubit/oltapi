import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.core.uuid import generate_uuid7
from app.drivers.fiberhome.fiberhome_tl1 import (
    FiberhomeTL1Driver,
    parse_all_authorized_onus,
    parse_profiles,
    parse_vlans,
)
from app.models.olt import OLTCreateRequest, OLTInDB, OLTProtocol, OLTVendor
from app.models.onu import ONUSummary
from app.models.vlan import ProfileItem, VLANCreateRequest, VLANItem
from app.services.backup_service import BackupService
from app.services.olt_sync_service import OLTSyncService
from app.storage.sql.olt_repository import SQLOLTRepository
from app.storage.sql.onu_repository import SQLONUInventoryRepository


# --- DADOS TL1 MOCKADOS DE EXEMPLO FIBERHOME ---

SAMPLE_LST_ONU_OUTPUT = """
RESPONSE:
   1-1-1-1    FHTT12345678  ACTIVE    CLIENTE_JOAO_FIBRA
   1-1-1-2    FHTT87654321  INACTIVE  CLIENTE_MARIA_SILVA
   1-1-2-10   FHTT11223344  ACTIVE    EMPRESA_XYZ
;
"""

SAMPLE_LST_VLAN_OUTPUT = """
RESPONSE:
   VLAN 100: INTERNET_PPPOE
   VLAN 200: VOIP_SIP
   VLAN 300: IPTV_MULTICAST
;
"""

SAMPLE_LST_PROFILES_OUTPUT = """
RESPONSE:
   LINEPROF: 100M_PLAN
   LINEPROF: 500M_GIGA
   DBAPROF: DBA_UPSTREAM_DEFAULT
;
"""


# --- TESTES DE PARSERS TL1 ---

def test_parse_all_authorized_onus():
    onus = parse_all_authorized_onus(SAMPLE_LST_ONU_OUTPUT)
    assert len(onus) == 3

    assert onus[0].serial == "FHTT12345678"
    assert onus[0].port == "1/1"
    assert onus[0].onu_id == 1
    assert onus[0].status == "ACTIVE"
    assert onus[0].name == "CLIENTE_JOAO_FIBRA"

    assert onus[1].serial == "FHTT87654321"
    assert onus[1].port == "1/1"
    assert onus[1].onu_id == 2
    assert onus[1].status == "INACTIVE"
    assert onus[1].name == "CLIENTE_MARIA_SILVA"

    assert onus[2].serial == "FHTT11223344"
    assert onus[2].port == "1/2"
    assert onus[2].onu_id == 10
    assert onus[2].status == "ACTIVE"
    assert onus[2].name == "EMPRESA_XYZ"


def test_parse_vlans():
    vlans = parse_vlans(SAMPLE_LST_VLAN_OUTPUT)
    assert len(vlans) == 3
    assert vlans[0].vlan_id == 100
    assert vlans[0].name == "INTERNET_PPPOE"
    assert vlans[1].vlan_id == 200
    assert vlans[1].name == "VOIP_SIP"
    assert vlans[2].vlan_id == 300
    assert vlans[2].name == "IPTV_MULTICAST"


def test_parse_profiles():
    profiles = parse_profiles(SAMPLE_LST_PROFILES_OUTPUT)
    assert len(profiles) == 3
    assert profiles[0].profile_type == "line"
    assert profiles[0].name == "100M_PLAN"
    assert profiles[1].profile_type == "line"
    assert profiles[1].name == "500M_GIGA"
    assert profiles[2].profile_type == "dba"
    assert profiles[2].name == "DBA_UPSTREAM_DEFAULT"


# --- FIXTURE OLT FIBERHOME ---

@pytest.fixture
def sample_olt_fiberhome(setup_test_env) -> OLTInDB:
    repo: SQLOLTRepository = setup_test_env["repo"]
    for existing in repo.list_all():
        if existing.name == "OLT-FIBERHOME-CENTRAL":
            return existing
    req = OLTCreateRequest(
        name="OLT-FIBERHOME-CENTRAL",
        vendor=OLTVendor.FIBERHOME,
        model="AN5516-01",
        host="192.168.10.100",
        port=3337,
        protocol=OLTProtocol.TELNET,
        username="admin",
        password="secret_password",
    )
    return repo.create(req)


# --- TESTE DO SERVIÇO DE SINCRONIZAÇÃO (BROWNFIELD ONBOARDING) ---

def test_sync_olt_service_success(setup_test_env, sample_olt_fiberhome):
    olt_repo: SQLOLTRepository = setup_test_env["repo"]
    onu_repo: SQLONUInventoryRepository = setup_test_env["onu_repo"]
    backup_storage = setup_test_env["storage"]

    backup_service = BackupService(olt_repo=olt_repo, storage=backup_storage)
    sync_service = OLTSyncService(
        olt_repo=olt_repo,
        onu_repo=onu_repo,
        backup_service=backup_service,
    )

    mock_onus = [
        ONUSummary(serial="FHTT99001122", port="1/1/1", onu_id=1, status="ACTIVE", name="CLIENTE_TESTE_1"),
        ONUSummary(serial="FHTT99003344", port="1/1/1", onu_id=2, status="ACTIVE", name="CLIENTE_TESTE_2"),
    ]
    mock_vlans = [
        VLANItem(vlan_id=100, name="VLAN_INTERNET"),
        VLANItem(vlan_id=200, name="VLAN_VOIP"),
    ]

    with patch("app.drivers.fiberhome.fiberhome_tl1.FiberhomeTL1Driver.get_running_config", return_value="CONFIG_FIBERHOME_V0"), \
         patch("app.drivers.fiberhome.fiberhome_tl1.FiberhomeTL1Driver.list_all_authorized_onus", return_value=mock_onus), \
         patch("app.drivers.fiberhome.fiberhome_tl1.FiberhomeTL1Driver.list_vlans", return_value=mock_vlans):

        # 1. Executa sincronização inicial
        res = sync_service.sync_olt(sample_olt_fiberhome.id)

        assert res.olt_id == sample_olt_fiberhome.id
        assert res.total_onus_discovered == 2
        assert res.new_onus_registered == 2
        assert res.existing_onus_updated == 0
        assert res.vlans_discovered == [100, 200]
        assert res.baseline_backup_id is not None

        # 2. Verifica se o backup de baseline v0 foi gravado no storage
        backups = backup_storage.list_by_olt(sample_olt_fiberhome.id)
        assert len(backups) >= 1
        assert any(b.backup_id == res.baseline_backup_id for b in backups)

        # 3. Verifica se as ONUs foram cadastradas no inventário relacional com Circuit ID TR-101
        onu1 = onu_repo.get_by_serial("FHTT99001122")
        assert onu1 is not None
        assert onu1.contract_status == "ACTIVE"
        assert onu1.current_olt_id == sample_olt_fiberhome.id
        assert onu1.current_port == "1/1/1"
        assert onu1.current_onu_id == 1
        assert onu1.circuit_id == f"{sample_olt_fiberhome.name} eth 1/1/1:1:100"

        # 4. Executa segunda sincronização (deve atualizar ao invés de duplicar)
        res2 = sync_service.sync_olt(sample_olt_fiberhome.id)
        assert res2.total_onus_discovered == 2
        assert res2.new_onus_registered == 0
        assert res2.existing_onus_updated == 2


# --- TESTES DE ENDPOINTS HTTP VIA FASTAPI TESTCLIENT ---

def test_api_sync_olt_endpoint(client: TestClient, auth_headers, sample_olt_fiberhome):
    mock_onus = [
        ONUSummary(serial="FHTT55667788", port="1/1/3", onu_id=5, status="ACTIVE", name="ASSINANTE_FIBRA"),
    ]
    mock_vlans = [VLANItem(vlan_id=150, name="VLAN_PROVEDOR")]

    with patch("app.drivers.fiberhome.fiberhome_tl1.FiberhomeTL1Driver.backup_config", return_value="RUNNING_CFG_TL1"), \
         patch("app.drivers.fiberhome.fiberhome_tl1.FiberhomeTL1Driver.list_all_authorized_onus", return_value=mock_onus), \
         patch("app.drivers.fiberhome.fiberhome_tl1.FiberhomeTL1Driver.list_vlans", return_value=mock_vlans):

        response = client.post(f"/api/v1/olts/{sample_olt_fiberhome.id}/sync", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["olt_id"] == sample_olt_fiberhome.id
        assert data["total_onus_discovered"] == 1
        assert 150 in data["vlans_discovered"]
        assert data["baseline_backup_id"] is not None


def test_api_list_vlans_endpoint(client: TestClient, auth_headers, sample_olt_fiberhome):
    mock_vlans = [
        VLANItem(vlan_id=100, name="INTERNET", description="VLAN de Internet PPPoE"),
        VLANItem(vlan_id=200, name="VOIP", description="VLAN de Telefonia IP"),
    ]

    with patch("app.drivers.fiberhome.fiberhome_tl1.FiberhomeTL1Driver.list_vlans", return_value=mock_vlans):

        response = client.get(f"/api/v1/olts/{sample_olt_fiberhome.id}/vlans", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["vlan_id"] == 100
        assert data[0]["_links"]["self"]["href"] == f"/api/v1/olts/{sample_olt_fiberhome.id}/vlans"
        assert data[1]["vlan_id"] == 200


def test_api_create_vlan_endpoint_and_save_flash(client: TestClient, auth_headers, sample_olt_fiberhome):
    payload = {
        "vlan_id": 500,
        "name": "VLAN_DEDICADA",
        "description": "Link dedicado corporativo",
        "tagged_ports": ["1/1/1", "1/1/2"],
    }

    with patch("app.drivers.fiberhome.fiberhome_tl1.FiberhomeTL1Driver.create_vlan", return_value=True) as mock_create, \
         patch("app.drivers.fiberhome.fiberhome_tl1.FiberhomeTL1Driver.save_running_config", return_value=True) as mock_save:

        response = client.post(
            f"/api/v1/olts/{sample_olt_fiberhome.id}/vlans",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["vlan_id"] == 500
        assert "flash" in data["message"]
        # Garante que gravou na flash
        mock_create.assert_called_once()
        mock_save.assert_called_once()


def test_api_list_profiles_endpoint(client: TestClient, auth_headers, sample_olt_fiberhome):
    mock_profiles = [
        ProfileItem(name="PLAN_1G", profile_type="line", details="Plano 1Gbps"),
        ProfileItem(name="DBA_DEFAULT", profile_type="dba", details="DBA profile"),
    ]

    with patch("app.drivers.fiberhome.fiberhome_tl1.FiberhomeTL1Driver.list_profiles", return_value=mock_profiles):

        response = client.get(f"/api/v1/olts/{sample_olt_fiberhome.id}/profiles", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "PLAN_1G"
        assert data[0]["profile_type"] == "line"
        assert data[1]["name"] == "DBA_DEFAULT"


def test_api_sync_and_vlans_olt_not_found(client: TestClient, auth_headers):
    fake_id = generate_uuid7()
    resp_sync = client.post(f"/api/v1/olts/{fake_id}/sync", headers=auth_headers)
    assert resp_sync.status_code == 404

    resp_vlans = client.get(f"/api/v1/olts/{fake_id}/vlans", headers=auth_headers)
    assert resp_vlans.status_code == 404

    resp_create_vlan = client.post(
        f"/api/v1/olts/{fake_id}/vlans",
        json={"vlan_id": 999, "name": "FAIL"},
        headers=auth_headers,
    )
    assert resp_create_vlan.status_code == 404
