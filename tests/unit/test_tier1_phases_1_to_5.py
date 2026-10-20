from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.models.onu import ONUDetails, ONUMacEntry, UnauthorizedONU
from app.models.optical_telemetry import OpticalTelemetrySample
from app.models.provision import ONUActionResponse, ProvisionResponse
from app.services.autofind_scanner import AutofindScannerService


# ==============================================================================
# FASE 1: Causa da Última Queda (Dying Gasp vs LoS) & Tabela MAC por ONU
# ==============================================================================
def test_phase1_mac_table_and_down_cause_endpoints(client: TestClient, auth_headers, sample_olt_8820):
    mock_driver = MagicMock()
    mock_driver.get_onu_details.return_value = ONUDetails(
        olt_id=sample_olt_8820.id,
        port="0/1",
        onu_id=4,
        serial="VSOL11223344",
        status="offline",
        rx_power_dbm=-21.4,
        tx_power_dbm=2.1,
        olt_rx_power_dbm=-22.8,
        last_down_cause="dying_gasp",
        last_down_time="2026-10-19 15:10:00",
        mac_table=[
            ONUMacEntry(mac_address="AA:BB:CC:11:22:33", vlan=100, port="eth1"),
        ],
    )
    mock_driver.get_onu_mac_table.return_value = [
        ONUMacEntry(mac_address="AA:BB:CC:11:22:33", vlan=100, port="eth1"),
        ONUMacEntry(mac_address="DE:AD:BE:EF:00:01", vlan=100, port="veip1"),
    ]

    with patch("app.api.v1.endpoints_diagnostics.DriverFactory.get_driver", return_value=mock_driver):
        det_resp = client.get(
            f"/api/v1/olts/{sample_olt_8820.id}/onus/VSOL11223344",
            headers=auth_headers,
        )
        assert det_resp.status_code == 200
        det_json = det_resp.json()
        assert det_json["last_down_cause"] == "dying_gasp"
        assert det_json["last_down_time"] == "2026-10-19 15:10:00"
        assert "macs" in det_json["_links"]
        assert "optical_history" in det_json["_links"]

        mac_resp = client.get(
            f"/api/v1/olts/{sample_olt_8820.id}/onus/VSOL11223344/macs?port=0/1&onu_id=4",
            headers=auth_headers,
        )
        assert mac_resp.status_code == 200
        macs = mac_resp.json()
        assert len(macs) == 2
        assert macs[0]["mac_address"] == "AA:BB:CC:11:22:33"


# ==============================================================================
# FASE 2: Série Temporal de Potência Óptica (dBm) & Radar de Degradação
# ==============================================================================
def test_phase2_optical_telemetry_history_and_degradation_radar(
    client: TestClient, auth_headers, sample_olt_8820, setup_test_env
):
    onu_repo = setup_test_env["onu_repo"]
    serial = "FHTT77889900"

    # Cadastra ONU no inventário
    reg_resp = client.post(
        "/api/v1/onus",
        json={
            "serial": serial,
            "subscriber_name": "Assinante Fibra Degradada",
            "contract_id": "CTR-2026-99",
            "olt_id": sample_olt_8820.id,
            "port": "0/2",
            "onu_id": 7,
            "vlan": 200,
        },
        headers=auth_headers,
    )
    assert reg_resp.status_code == 201

    base_ts = datetime.now(timezone.utc) - timedelta(hours=5)
    # Grava 3 leituras saudáveis (-19.0 dBm) e 1 leitura com queda brusca (-26.2 dBm -> deriva de -7.2 dB)
    for idx, rx in enumerate([-19.0, -19.1, -18.9, -26.2]):
        onu_repo.record_optical_sample(
            OpticalTelemetrySample(
                serial=serial,
                olt_id=sample_olt_8820.id,
                port="0/2",
                onu_id=7,
                rx_power_dbm=rx,
                tx_power_dbm=2.2,
                olt_rx_power_dbm=rx - 1.5,
                status="online",
                last_down_cause="dying_gasp",
                recorded_at=base_ts + timedelta(hours=idx),
            )
        )

    # 1. Consulta série temporal óptica da ONU
    hist_resp = client.get(f"/api/v1/onus/{serial}/optical-history", headers=auth_headers)
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["serial"] == serial
    assert hist_data["current_rx_power_dbm"] == -26.2
    assert hist_data["baseline_rx_power_dbm"] is not None
    assert hist_data["drift_db"] <= -2.5
    assert hist_data["is_degraded"] is True
    assert len(hist_data["samples"]) >= 4

    # 2. Consulta Radar Global de Degradação Óptica
    deg_resp = client.get(
        f"/api/v1/onus/degraded?olt_id={sample_olt_8820.id}",
        headers=auth_headers,
    )
    assert deg_resp.status_code == 200
    deg_items = deg_resp.json()
    target_deg = next((d for d in deg_items if d["serial"] == serial), None)
    assert target_deg is not None
    assert target_deg["severity"] == "critical"
    assert len(target_deg["reasons"]) >= 1


# ==============================================================================
# FASE 3: Presets Universais, Pré-Provisionamento por Serial & Batch Actions
# ==============================================================================
@pytest.mark.asyncio
async def test_phase3_presets_pre_provisioning_and_batch_actions(
    client: TestClient, auth_headers, sample_olt_8820, setup_test_env
):
    # 1. Criar Preset Universal
    preset_resp = client.post(
        "/api/v1/presets",
        json={
            "name": "Plano Gamer 1Gbps",
            "description": "Preset Bridge VLAN 500",
            "vlan": 500,
            "mode": "transparent",
            "line_profile": "LINE_1G",
            "srv_profile": "SRV_BRIDGE",
            "is_default": True,
        },
        headers=auth_headers,
    )
    assert preset_resp.status_code == 201
    preset = preset_resp.json()
    preset_id = preset["id"]
    assert preset["vlan"] == 500

    # Listar Presets
    list_resp = client.get("/api/v1/presets", headers=auth_headers)
    assert list_resp.status_code == 200
    assert any(p["id"] == preset_id for p in list_resp.json())

    # 2. Pré-Provisionar uma ONU antes da instalação física usando o Preset
    pre_serial = "PRKS55667788"
    pre_resp = client.post(
        "/api/v1/onus/pre-provision",
        json={
            "serial": pre_serial,
            "subscriber_name": "Cliente Zero Touch",
            "contract_id": "CTR-ZT-001",
            "preset_id": preset_id,
            "olt_id": sample_olt_8820.id,
        },
        headers=auth_headers,
    )
    assert pre_resp.status_code == 201
    pre_item = pre_resp.json()
    assert pre_item["contract_status"] == "PRE_PROVISIONED"
    assert pre_item["vlan"] == 500
    assert pre_item["profile"] == "LINE_1G"

    # 3. Simular acendimento físico no AutofindScanner -> deve ativar automaticamente para ACTIVE!
    mock_driver = MagicMock()
    mock_driver.list_unauthorized_onus.side_effect = lambda olt_obj: (
        [UnauthorizedONU(port="0/4", serial=pre_serial, model="FD511G")]
        if olt_obj.id == sample_olt_8820.id
        else []
    )
    mock_driver.provision_onu.return_value = ProvisionResponse(
        success=True,
        port="0/4",
        onu_id=9,
        serial=pre_serial,
        message="Auto-provisioned from PRE_PROVISIONED",
    )

    scanner: AutofindScannerService = setup_test_env["scanner_service"]
    with patch("app.services.autofind_scanner.DriverFactory.get_driver", return_value=mock_driver):
        scan_res = await scanner.run_scan_cycle()
        assert pre_serial in [
            s for olt_sum in scan_res.olt_results for s in olt_sum.reconciled_serials
        ]

    # Confirma no inventário que o status virou ACTIVE e gerou Circuit ID TR-101
    inv_check = client.get(f"/api/v1/onus/{pre_serial}", headers=auth_headers)
    assert inv_check.status_code == 200
    inv_json = inv_check.json()
    assert inv_json["contract_status"] == "ACTIVE"
    assert inv_json["current_port"] == "0/4"
    assert inv_json["current_onu_id"] == 9
    assert inv_json["circuit_id"] is not None

    # 4. Operações em Lote (Batch Actions: suspend & resume)
    mock_driver.suspend_onu.return_value = ONUActionResponse(
        success=True,
        olt_id=sample_olt_8820.id,
        port="0/4",
        onu_id=9,
        serial=pre_serial,
        action="suspend",
        status="suspended",
        message="Suspended in batch",
    )
    with patch("app.api.v1.endpoints_provision.DriverFactory.get_driver", return_value=mock_driver):
        batch_resp = client.post(
            f"/api/v1/olts/{sample_olt_8820.id}/onus/batch-action",
            json={
                "action": "suspend",
                "targets": [{"serial": pre_serial, "port": "0/4", "onu_id": 9}],
            },
            headers=auth_headers,
        )
        assert batch_resp.status_code == 200
        b_data = batch_resp.json()
        assert b_data["total"] == 1
        assert b_data["succeeded"] == 1

    inv_after_suspend = client.get(f"/api/v1/onus/{pre_serial}", headers=auth_headers).json()
    assert inv_after_suspend["contract_status"] == "SUSPENDED"


# ==============================================================================
# FASE 4: Topologia Passiva FTTH (Zonas, CTOs/ODBs, Splitters & Mapa de Saúde)
# ==============================================================================
def test_phase4_passive_topology_and_health_map_correlation(
    client: TestClient, auth_headers, sample_olt_8820, setup_test_env
):
    onu_repo = setup_test_env["onu_repo"]

    # 1. Criar Zona FTTH
    zone_resp = client.post(
        "/api/v1/topology/zones",
        json={
            "name": "Zona Centro Histórico",
            "sector": "Setor Norte",
            "city": "Florianópolis",
            "description": "Rede FTTH subterrânea",
        },
        headers=auth_headers,
    )
    assert zone_resp.status_code == 201
    zone_id = zone_resp.json()["id"]

    # 2. Criar 2 CTOs: uma para teste de Queda de Energia (Dying Gasp) e outra para Rompimento (LoS)
    odb1_resp = client.post(
        "/api/v1/topology/odbs",
        json={
            "code": "CTO-CEN-01",
            "name": "CTO Praça XV",
            "zone_id": zone_id,
            "olt_id": sample_olt_8820.id,
            "pon_port": "0/1",
            "splitter_capacity": 8,
            "latitude": -27.5954,
            "longitude": -48.5480,
        },
        headers=auth_headers,
    )
    assert odb1_resp.status_code == 201
    odb1_id = odb1_resp.json()["id"]

    odb2_resp = client.post(
        "/api/v1/topology/odbs",
        json={
            "code": "CTO-CEN-02",
            "name": "CTO Hercílio Luz",
            "zone_id": zone_id,
            "olt_id": sample_olt_8820.id,
            "pon_port": "0/2",
            "splitter_capacity": 8,
        },
        headers=auth_headers,
    )
    assert odb2_resp.status_code == 201
    odb2_id = odb2_resp.json()["id"]

    # 3. Cadastrar 2 ONUs na CTO-CEN-01 (ambas em dying_gasp) e testar anti-colisão de porta do splitter
    for idx, s in enumerate(["VSOL00001001", "VSOL00001002"], start=1):
        client.post(
            "/api/v1/onus",
            json={"serial": s, "subscriber_name": f"Cliente CTO1 {idx}", "olt_id": sample_olt_8820.id, "port": "0/1", "vlan": 100},
            headers=auth_headers,
        )
        topo_patch = client.patch(
            f"/api/v1/onus/{s}/topology",
            json={"odb_id": odb1_id, "odb_splitter_port": idx},
            headers=auth_headers,
        )
        assert topo_patch.status_code == 200
        onu_repo.record_optical_sample(
            OpticalTelemetrySample(
                serial=s,
                olt_id=sample_olt_8820.id,
                port="0/1",
                onu_id=idx,
                rx_power_dbm=-20.1,
                status="offline",
                last_down_cause="dying_gasp",
            )
        )

    # Tentar alocar VSOL00001002 na porta 1 (já ocupada por VSOL00001001) -> deve retornar 400 Bad Request
    collision_resp = client.patch(
        "/api/v1/onus/VSOL00001002/topology",
        json={"odb_id": odb1_id, "odb_splitter_port": 1},
        headers=auth_headers,
    )
    assert collision_resp.status_code == 400

    # 4. Cadastrar 2 ONUs na CTO-CEN-02 (ambas em LoS -> rompimento óptico)
    for idx, s in enumerate(["VSOL00002001", "VSOL00002002"], start=1):
        client.post(
            "/api/v1/onus",
            json={"serial": s, "subscriber_name": f"Cliente CTO2 {idx}", "olt_id": sample_olt_8820.id, "port": "0/2", "vlan": 100},
            headers=auth_headers,
        )
        client.patch(
            f"/api/v1/onus/{s}/topology",
            json={"odb_id": odb2_id, "odb_splitter_port": idx},
            headers=auth_headers,
        )
        onu_repo.record_optical_sample(
            OpticalTelemetrySample(
                serial=s,
                olt_id=sample_olt_8820.id,
                port="0/2",
                onu_id=idx,
                rx_power_dbm=-35.0,
                status="los",
                last_down_cause="los",
            )
        )

    # 5. Consultar Mapa de Saúde da Topologia Passiva
    map_resp = client.get(f"/api/v1/topology/health-map?zone_id={zone_id}", headers=auth_headers)
    assert map_resp.status_code == 200
    map_data = map_resp.json()
    assert map_data["power_outage_odbs"] >= 1
    assert map_data["fiber_cut_odbs"] >= 1

    node_cto1 = next(n for n in map_data["nodes"] if n["code"] == "CTO-CEN-01")
    node_cto2 = next(n for n in map_data["nodes"] if n["code"] == "CTO-CEN-02")
    assert node_cto1["health_status"] == "power_outage"
    assert node_cto2["health_status"] == "fiber_cut"


# ==============================================================================
# FASE 5: Integração TR-069 / CWMP & ACS (Wi-Fi, WAN PPPoE & Firmware OTA)
# ==============================================================================
def test_phase5_acs_tr069_server_and_remote_actions(client: TestClient, auth_headers):
    # 1. Cadastrar servidor ACS com senha cifrada em repouso
    srv_resp = client.post(
        "/api/v1/acs/servers",
        json={
            "name": "GenieACS Matriz",
            "nbi_url": "http://10.250.0.10:7557",
            "username": "acs_admin",
            "password": "super_secret_acs_password",
            "cwmp_inform_url": "http://10.250.0.10:7547",
            "is_active": True,
        },
        headers=auth_headers,
    )
    assert srv_resp.status_code == 201
    srv_data = srv_resp.json()
    assert srv_data["name"] == "GenieACS Matriz"
    assert "password" not in srv_data

    # 2. Simular respostas da NBI do GenieACS para consulta TR-069 e envio de tasks Wi-Fi e WAN
    fake_genie_device = [
        {
            "_id": "00259E-EG8145V5-FHTT77889900",
            "_lastInform": "2026-10-19T16:30:00Z",
            "InternetGatewayDevice": {
                "DeviceInfo": {
                    "SoftwareVersion": {"_value": "V5R020C10S202"},
                    "HardwareVersion": {"_value": "1152.A"},
                },
                "WANDevice": {
                    "1": {
                        "WANConnectionDevice": {
                            "1": {
                                "WANPPPConnection": {
                                    "1": {
                                        "ExternalIPAddress": {"_value": "100.64.12.88"},
                                        "Username": {"_value": "cliente.fibra@isp"},
                                    }
                                }
                            }
                        }
                    }
                },
                "LANDevice": {
                    "1": {
                        "WLANConfiguration": {
                            "1": {"SSID": {"_value": "FIBRA_2G_CASA"}},
                            "5": {"SSID": {"_value": "FIBRA_5G_CASA"}},
                        }
                    }
                },
            },
        }
    ]

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = fake_genie_device

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200

    with patch("app.services.acs_service.httpx.Client") as mock_client_cls:
        mock_http = MagicMock()
        mock_http.get.return_value = mock_get_resp
        mock_http.post.return_value = mock_post_resp
        mock_client_cls.return_value.__enter__.return_value = mock_http

        # Consulta sumário TR-069 da ONU
        tr_resp = client.get("/api/v1/onus/FHTT77889900/tr069", headers=auth_headers)
        assert tr_resp.status_code == 200
        tr_data = tr_resp.json()
        assert tr_data["registered_in_acs"] is True
        assert tr_data["wan_ip"] == "100.64.12.88"
        assert tr_data["pppoe_username"] == "cliente.fibra@isp"
        assert tr_data["ssid_24g"] == "FIBRA_2G_CASA"
        assert tr_data["ssid_5g"] == "FIBRA_5G_CASA"

        # Alteração remota de Wi-Fi 2.4G/5G via TR-069
        wifi_resp = client.post(
            "/api/v1/onus/FHTT77889900/tr069/wifi",
            json={
                "ssid_24g": "NOVA_REDE_2G",
                "password_24g": "senhaSegura123",
                "ssid_5g": "NOVA_REDE_5G",
                "password_5g": "senhaSegura123",
            },
            headers=auth_headers,
        )
        assert wifi_resp.status_code == 200
        assert wifi_resp.json()["task_queued"] is True

        # Alteração remota de WAN PPPoE via TR-069
        wan_resp = client.post(
            "/api/v1/onus/FHTT77889900/tr069/wan",
            json={
                "mode": "pppoe",
                "pppoe_username": "novo.login@isp",
                "pppoe_password": "novaSenhaPppoe",
                "vlan_id": 200,
            },
            headers=auth_headers,
        )
        assert wan_resp.status_code == 200
        assert wan_resp.json()["task_queued"] is True
