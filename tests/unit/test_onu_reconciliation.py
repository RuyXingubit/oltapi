from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.circuit_id import generate_circuit_id
from app.models.olt import OLTCreateRequest, OLTVendor, OLTProtocol
from app.models.provision import ProvisionResponse, ONUActionResponse


# ---------------------------------------------------------------------------
# Testes do Gerador de Circuit ID (Broadband Forum TR-101)
# ---------------------------------------------------------------------------

def test_circuit_id_generation():
    # Padrão simples
    cid = generate_circuit_id("OLT-CENTRAL-01", "1/1", 5, 100)
    assert cid == "OLT-CENTRAL-01 eth 1/1:5:100"

    # Porta com prefixo gpon
    cid2 = generate_circuit_id("OLT-POP-SUL", "gpon 0/2", 12, 200)
    assert cid2 == "OLT-POP-SUL eth 0/2:12:200"

    # Porta com slot/subslot/port
    cid3 = generate_circuit_id("OLT-HUAWEI-MA5800", "0/1/3", 1, 300)
    assert cid3 == "OLT-HUAWEI-MA5800 eth 0/1/3:1:300"

    # Normalização de espaços
    cid4 = generate_circuit_id("  olt-zte-c300  ", "1/1/1", 8, 400)
    assert cid4 == "OLT-ZTE-C300 eth 1/1/1:8:400"

    # Nome de OLT com espaços internos (ex: 'OLT VTX')
    cid5 = generate_circuit_id("OLT VTX", "1/1", 3, 100)
    assert cid5 == "OLT-VTX eth 1/1:3:100"

    # Nome de OLT com múltiplos espaços internos
    cid6 = generate_circuit_id("  OLT   CIDADE   NOVA  ", "0/2/1", 7, 200)
    assert cid6 == "OLT-CIDADE-NOVA eth 0/2/1:7:200"


# ---------------------------------------------------------------------------
# Testes de Cadastro no Inventário e Coordenadas Geográficas
# ---------------------------------------------------------------------------

def test_register_onu_inventory_endpoint(client: TestClient, auth_headers, sample_olt_8820):
    payload = {
        "serial": "INCL99887766",
        "contract_id": "CTR-100200",
        "subscriber_name": "Provedor Turbo Fibra Ltda",
        "contract_status": "ACTIVE",
        "current_olt_id": str(sample_olt_8820.id),
        "current_port": "1/1",
        "current_onu_id": 4,
        "vlan": 150,
        "profile": "1G_DOWN_500M_UP",
        "latitude": -23.550520,
        "longitude": -46.633308,
        "notes": "Cliente corporativo migrado com sucesso",
    }

    response = client.post("/api/v1/onus", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()

    assert data["serial"] == "INCL99887766"
    assert data["contract_id"] == "CTR-100200"
    assert data["contract_status"] == "ACTIVE"
    assert data["circuit_id"] == f"{sample_olt_8820.name} eth 1/1:4:150"
    assert data["latitude"] == -23.550520
    assert data["longitude"] == -46.633308
    assert "_links" in data
    assert "self" in data["_links"]
    assert "history" in data["_links"]


def test_get_onu_inventory_by_serial(client: TestClient, auth_headers, sample_olt_8820):
    # Consulta a ONU registrada no teste anterior
    response = client.get("/api/v1/onus/INCL99887766", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["serial"] == "INCL99887766"
    assert data["subscriber_name"] == "Provedor Turbo Fibra Ltda"
    assert data["circuit_id"] == f"{sample_olt_8820.name} eth 1/1:4:150"


def test_list_onu_inventory_filters(client: TestClient, auth_headers, sample_olt_8820):
    # Filtrar por contract_id
    resp = client.get("/api/v1/onus?contract_id=CTR-100200", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert items[0]["contract_id"] == "CTR-100200"

    # Filtrar por OLT
    resp2 = client.get(f"/api/v1/onus?olt_id={sample_olt_8820.id}", headers=auth_headers)
    assert resp2.status_code == 200
    items2 = resp2.json()
    assert len(items2) >= 1


# ---------------------------------------------------------------------------
# Testes de Auto-Reconciliação Reativa de Campo (Field Event)
# ---------------------------------------------------------------------------

@patch("app.drivers.factory.DriverFactory.get_driver")
def test_reconcile_field_event_intra_olt(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    """
    Cenário: Fusão invertida na caixa de emenda (CEO) ou troca de CTO na mesma OLT.
    A ONU estava na porta 1/1 (onu_id 4) e acende na porta 1/3 (onu_id 8).
    O sistema deve desprovisionar da 1/1 e provisionar na 1/3, recalculando o Circuit ID TR-101.
    """
    mock_driver = MagicMock()
    mock_driver.provision_onu.return_value = ProvisionResponse(
        success=True,
        olt_id=str(sample_olt_8820.id),
        serial="INCL99887766",
        port="1/3",
        onu_id=8,
        vlan=150,
        message="Provisionado com sucesso",
    )
    mock_driver.deprovision_onu.return_value = ONUActionResponse(
        success=True,
        action="deprovision",
        olt_id=str(sample_olt_8820.id),
        serial="INCL99887766",
        port="1/1",
        onu_id=4,
        message="Desprovisionado da porta antiga",
    )
    mock_get_driver.return_value = mock_driver

    payload = {
        "serial": "INCL99887766",
        "detected_olt_id": str(sample_olt_8820.id),
        "detected_port": "1/3",
        "detected_onu_id": 8,
        "reason": "Fusão invertida identificada na caixa CEO-04",
        "latitude": -23.551000,
        "longitude": -46.634000,
    }

    response = client.post("/api/v1/onus/reconcile-field-event", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["action_taken"] == "reconciled_intra_olt"
    assert data["serial"] == "INCL99887766"
    assert data["old_port"] == "1/1"
    assert data["new_port"] == "1/3"
    assert data["new_onu_id"] == 8
    assert data["new_circuit_id"] == f"{sample_olt_8820.name} eth 1/3:8:150"

    # Confirma chamadas ao driver
    assert mock_driver.provision_onu.called
    assert mock_driver.deprovision_onu.called

    # Confirma que inventário foi atualizado com as novas coordenadas e porta
    get_resp = client.get("/api/v1/onus/INCL99887766", headers=auth_headers)
    assert get_resp.status_code == 200
    updated_item = get_resp.json()
    assert updated_item["current_port"] == "1/3"
    assert updated_item["current_onu_id"] == 8
    assert updated_item["latitude"] == -23.551000
    assert updated_item["longitude"] == -46.634000
    assert updated_item["circuit_id"] == f"{sample_olt_8820.name} eth 1/3:8:150"


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_reconcile_field_event_cross_olt(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820, setup_test_env):
    """
    Cenário: Migração noturna de POP ou cutover de rede.
    A ONU estava na OLT Intelbras 8820 (porta 1/3) e agora aparece fisicamente
    em uma OLT Huawei MA5800 (porta 0/2, onu_id 2).
    O sistema deve migrar a ONU entre as OLTs, atualizar o Circuit ID e limpar a antiga.
    """
    repo = setup_test_env["repo"]
    huawei_req = OLTCreateRequest(
        name="OLT-HUAWEI-POP-CENTRO",
        vendor=OLTVendor.HUAWEI,
        model="MA5800",
        host="192.168.2.50",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="huawei_password",
    )
    huawei_olt = repo.create(huawei_req)

    mock_driver = MagicMock()
    mock_driver.provision_onu.return_value = ProvisionResponse(
        success=True,
        olt_id=str(huawei_olt.id),
        serial="INCL99887766",
        port="0/2",
        onu_id=2,
        vlan=150,
        message="Provisionado na Huawei MA5800",
    )
    mock_driver.deprovision_onu.return_value = ONUActionResponse(
        success=True,
        action="deprovision",
        olt_id=str(sample_olt_8820.id),
        serial="INCL99887766",
        port="1/3",
        onu_id=8,
        message="Desprovisionado da Intelbras 8820",
    )
    mock_get_driver.return_value = mock_driver

    payload = {
        "serial": "INCL99887766",
        "detected_olt_id": str(huawei_olt.id),
        "detected_port": "0/2",
        "detected_onu_id": 2,
        "reason": "Cutover de anel óptico da madrugada - POP Centro",
    }

    response = client.post("/api/v1/onus/reconcile-field-event", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["action_taken"] == "reconciled_cross_olt"
    assert data["old_olt_id"] == str(sample_olt_8820.id)
    assert data["new_olt_id"] == str(huawei_olt.id)
    assert data["new_circuit_id"] == f"{huawei_olt.name} eth 0/2:2:150"


@patch("app.drivers.factory.DriverFactory.get_driver")
def test_reconcile_field_event_rejected_in_stock(mock_get_driver, client: TestClient, auth_headers, sample_olt_8820):
    """
    Cenário: ONU devolvida para o estoque da operadora (status IN_STOCK).
    Se ela acender em qualquer PON, o sistema DEVE REJEITAR a auto-conciliação
    para impedir herança indevida de dados/VLAN do antigo titular.
    """
    mock_driver = MagicMock()
    mock_get_driver.return_value = mock_driver

    # Registra ONU em estoque
    stock_payload = {
        "serial": "STCK11223344",
        "contract_id": None,
        "subscriber_name": None,
        "contract_status": "IN_STOCK",
        "vlan": 100,
        "profile": "DEFAULT",
        "notes": "ONU recolhida em campo após cancelamento",
    }
    create_resp = client.post("/api/v1/onus", json=stock_payload, headers=auth_headers)
    assert create_resp.status_code == 201

    # Evento de campo tenta auto-conciliar a ONU em estoque
    reconcile_payload = {
        "serial": "STCK11223344",
        "detected_olt_id": str(sample_olt_8820.id),
        "detected_port": "1/4",
        "reason": "Tentativa de ligar ONU de estoque sem novo contrato",
    }

    resp = client.post("/api/v1/onus/reconcile-field-event", json=reconcile_payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is False
    assert data["action_taken"] == "rejected_in_stock_onu"
    assert "bloqueada" in data["message"]
    # Nenhum comando de provisionamento deve ter sido disparado
    assert not mock_driver.provision_onu.called


def test_reconcile_field_event_unregistered_onu(client: TestClient, auth_headers, sample_olt_8820):
    """
    Cenário: Serial virgem que não existe no inventário.
    """
    payload = {
        "serial": "UNKN00000000",
        "detected_olt_id": str(sample_olt_8820.id),
        "detected_port": "1/1",
    }
    resp = client.post("/api/v1/onus/reconcile-field-event", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["action_taken"] == "onu_not_found"


# ---------------------------------------------------------------------------
# Testes da Timeline e Auditoria de Migração para o NOC
# ---------------------------------------------------------------------------

def test_noc_history_endpoints(client: TestClient, auth_headers):
    # Consulta histórico global do NOC
    resp_global = client.get("/api/v1/onus/history", headers=auth_headers)
    assert resp_global.status_code == 200
    events = resp_global.json()
    assert isinstance(events, list)
    assert len(events) >= 2  # Devem existir pelo menos os eventos dos testes intra e cross-olt

    # Verifica integridade dos dados registrados para os operadores do NOC
    event = events[0]
    assert "serial" in event
    assert "from_circuit_id" in event
    assert "to_circuit_id" in event
    assert "timestamp" in event
    assert "_links" in event

    # Consulta histórico específico da ONU migrada
    resp_onu = client.get("/api/v1/onus/INCL99887766/history", headers=auth_headers)
    assert resp_onu.status_code == 200
    onu_events = resp_onu.json()
    assert len(onu_events) >= 2
    for ev in onu_events:
        assert ev["serial"] == "INCL99887766"


def test_update_onu_inventory(client: TestClient, auth_headers):
    """Testa a atualização cadastral e de parâmetros (PATCH /onus/{serial})."""
    serial = "INCL99887766"
    patch_payload = {
        "subscriber_name": "Maria Silva Atualizada",
        "description": "Cliente Fibra 500M - Sala 102",
        "circuit_id": "CTO-08-PORTA-03",
        "vlan": 302,
        "profile": "PLAN_500M",
    }
    patch_resp = client.patch(f"/api/v1/onus/{serial}", json=patch_payload, headers=auth_headers)
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["serial"] == serial
    assert data["subscriber_name"] == "Maria Silva Atualizada"
    assert data["description"] == "Cliente Fibra 500M - Sala 102"
    assert data["circuit_id"] == "CTO-08-PORTA-03"
    assert data["vlan"] == 302
    assert data["profile"] == "PLAN_500M"

    # Confirma persistência via GET
    get_resp = client.get(f"/api/v1/onus/{serial}", headers=auth_headers)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["subscriber_name"] == "Maria Silva Atualizada"
    assert get_data["vlan"] == 302
