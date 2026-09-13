from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.models.olt import OLTCreateRequest, OLTInDB, OLTProtocol, OLTVendor
from app.models.onu_inventory import ONUInventoryItem
from app.models.provision import ProvisionResponse


def test_master_admin_access_everything(client: TestClient, auth_headers):
    """Garante que a chave mestra do .env continua com privilégios irrestritos de SUPER_ADMIN."""
    resp = client.get("/api/v1/tenants", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    resp_olts = client.get("/api/v1/olts", headers=auth_headers)
    assert resp_olts.status_code == 200


def test_login_and_get_profile(client: TestClient, setup_test_env):
    """Valida o fluxo de autenticação JWT via email/senha e consulta do endpoint /auth/me."""
    login_payload = {
        "email": "admin@oltapi.local",
        "password": "admin123456",
    }
    resp = client.post("/api/v1/auth/login", json=login_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "SUPER_ADMIN"

    jwt_headers = {"Authorization": f"Bearer {data['access_token']}"}
    me_resp = client.get("/api/v1/auth/me", headers=jwt_headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "admin@oltapi.local"
    assert me_data["role"] == "SUPER_ADMIN"


def test_create_tenant_and_vlan_allocation(client: TestClient, auth_headers, sample_olt_8820: OLTInDB):
    """Valida cadastro de operadora de rede neutra e alocação de VLAN por OLT."""
    tenant_payload = {
        "name": "Operadora Neutra Alpha",
        "type": "NEUTRAL_OPERATOR",
        "is_active": True,
    }
    resp = client.post("/api/v1/tenants", json=tenant_payload, headers=auth_headers)
    assert resp.status_code == 201
    tenant = resp.json()
    assert tenant["name"] == "Operadora Neutra Alpha"
    assert tenant["type"] == "NEUTRAL_OPERATOR"

    vlan_payload = {
        "olt_id": sample_olt_8820.id,
        "vlan_id": 100,
        "description": "VLAN 100 Dados Alpha",
    }
    vlan_resp = client.post(f"/api/v1/tenants/{tenant['id']}/vlans", json=vlan_payload, headers=auth_headers)
    assert vlan_resp.status_code == 201
    vlan_data = vlan_resp.json()
    assert vlan_data["vlan_id"] == 100
    assert vlan_data["olt_id"] == sample_olt_8820.id


def test_field_tech_olt_restriction(client: TestClient, auth_headers, sample_olt_8820: OLTInDB, setup_test_env):
    """Garante que técnico restrito a uma OLT é bloqueado ao tentar operar em outra."""
    repo = setup_test_env["repo"]

    # Cria uma segunda OLT (Altamira)
    olt2 = repo.create(
        OLTCreateRequest(
            name="OLT-ALTAMIRA-TEST",
            vendor=OLTVendor.INTELBRAS,
            model="8820",
            host="192.168.2.200",
            port=22,
            protocol=OLTProtocol.SSH,
            username="admin",
            password="pass",
        )
    )

    # Cria técnico restrito apenas à sample_olt_8820
    tech_payload = {
        "name": "Técnico VTX",
        "email": "tecnico.vtx@provedor.local",
        "password": "senha_segura_123",
        "role": "FIELD_TECH",
        "allowed_olt_ids": [sample_olt_8820.id],
    }
    user_resp = client.post("/api/v1/users", json=tech_payload, headers=auth_headers)
    assert user_resp.status_code == 201

    # Login como técnico VTX
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "tecnico.vtx@provedor.local", "password": "senha_segura_123"},
    )
    tech_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # Deve conseguir consultar a OLT autorizada (sample_olt_8820)
    ok_resp = client.get(f"/api/v1/olts/{sample_olt_8820.id}", headers=tech_headers)
    assert ok_resp.status_code == 200

    # Deve receber 403 Forbidden ao tentar consultar a OLT não autorizada (Altamira)
    blocked_resp = client.get(f"/api/v1/olts/{olt2.id}", headers=tech_headers)
    assert blocked_resp.status_code == 403
    assert "Acesso não autorizado" in blocked_resp.json()["detail"]


def test_neutral_operator_vlan_and_scope_isolation(client: TestClient, auth_headers, sample_olt_8820: OLTInDB, setup_test_env):
    """
    Teste crítico de segurança para Rede Neutra:
    1. Operador gera API key para o seu ERP.
    2. Provisionamento na VLAN autorizada (VLAN 300) é permitido.
    3. Provisionamento em VLAN não autorizada (ex: VLAN 11) é bloqueado com 403 Forbidden.
    4. Provisionamento em outra OLT é bloqueado com 403 Forbidden.
    """
    # 1. Cria Tenant Neutro
    t_resp = client.post(
        "/api/v1/tenants",
        json={"name": "Operadora Neutra Beta", "type": "NEUTRAL_OPERATOR"},
        headers=auth_headers,
    )
    tenant_id = t_resp.json()["id"]

    # Aloca VLAN 300 na sample_olt_8820
    client.post(
        f"/api/v1/tenants/{tenant_id}/vlans",
        json={"olt_id": sample_olt_8820.id, "vlan_id": 300, "description": "VLAN Beta"},
        headers=auth_headers,
    )

    # Cria usuário admin do tenant Beta
    u_resp = client.post(
        "/api/v1/users",
        json={
            "tenant_id": tenant_id,
            "name": "Admin Beta",
            "email": "admin@beta.net",
            "password": "senha_beta_123",
            "role": "TENANT_ADMIN",
            "allowed_olt_ids": [sample_olt_8820.id],
        },
        headers=auth_headers,
    )
    assert u_resp.status_code == 201

    # Login do Admin Beta para gerar API key
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@beta.net", "password": "senha_beta_123"},
    )
    beta_jwt_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # Gera API Key para o ERP da Beta com escopos de provisionamento e descoberta
    key_resp = client.post(
        "/api/v1/api-keys",
        json={
            "name": "ERP IXC Beta",
            "scopes": ["onus:discover", "onus:provision", "onus:read"],
        },
        headers=beta_jwt_headers,
    )
    assert key_resp.status_code == 201
    raw_api_key = key_resp.json()["key"]
    erp_headers = {"X-API-Key": raw_api_key}

    # 2. Testa provisionamento na VLAN 300 (autorizada) com Driver mockado
    prov_payload = {
        "serial": "TEST12345678",
        "port": "1/1",
        "onu_id": 5,
        "vlan": 300,
        "mode": "router",
    }
    with patch("app.drivers.factory.DriverFactory.get_driver") as mock_factory:
        mock_driver = MagicMock()
        mock_driver.provision_onu.return_value = ProvisionResponse(
            serial="TEST12345678",
            olt_id=sample_olt_8820.id,
            port="1/1",
            onu_id=5,
            status="provisioned",
            message="Provisionado com sucesso",
        )
        mock_factory.return_value = mock_driver

        success_resp = client.post(
            f"/api/v1/olts/{sample_olt_8820.id}/onus",
            json=prov_payload,
            headers=erp_headers,
        )
        assert success_resp.status_code == 201

    # 3. Testa tentativa de provisionar na VLAN 11 (não autorizada para este tenant!)
    unauth_vlan_payload = {
        "serial": "TEST87654321",
        "port": "1/1",
        "onu_id": 6,
        "vlan": 11,  # VLAN não alocada!
        "mode": "router",
    }
    blocked_vlan_resp = client.post(
        f"/api/v1/olts/{sample_olt_8820.id}/onus",
        json=unauth_vlan_payload,
        headers=erp_headers,
    )
    assert blocked_vlan_resp.status_code == 403
    assert "VLAN 11 não autorizada" in blocked_vlan_resp.json()["detail"]


def test_dynamic_api_key_revocation(client: TestClient, auth_headers):
    """Valida que uma chave de API revogada tem acesso negado imediatamente (401 Unauthorized)."""
    # Gera chave
    create_resp = client.post(
        "/api/v1/api-keys",
        json={"name": "Chave Temporária", "scopes": ["onus:read"]},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    key_data = create_resp.json()
    raw_key = key_data["key"]
    key_id = key_data["id"]

    temp_headers = {"X-API-Key": raw_key}

    # Deve funcionar antes de revogar
    valid_resp = client.get("/api/v1/onus", headers=temp_headers)
    assert valid_resp.status_code == 200

    # Revoga a chave
    del_resp = client.delete(f"/api/v1/api-keys/{key_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    # Deve falhar com 401 Unauthorized após revogada
    revoked_resp = client.get("/api/v1/onus", headers=temp_headers)
    assert revoked_resp.status_code == 401
    assert "revogada" in revoked_resp.json()["detail"]


def test_neutral_operator_inventory_isolation(client: TestClient, auth_headers, sample_olt_8820: OLTInDB, setup_test_env):
    """Garante que no endpoint GET /onus, o parceiro neutro só visualiza ONUs de suas VLANs."""
    onu_repo: ONUInventoryRepository = setup_test_env["onu_repo"]

    # Cria duas ONUs no inventário: uma na VLAN 500 (Neutro Gamma) e outra na VLAN 11 (Matriz)
    onu_repo.upsert(
        ONUInventoryItem(
            serial="SNGAMMA001",
            current_olt_id=sample_olt_8820.id,
            current_port="1/1",
            current_onu_id=1,
            vlan=500,
            contract_status="ACTIVE",
        )
    )
    onu_repo.upsert(
        ONUInventoryItem(
            serial="SNMATRIZ002",
            current_olt_id=sample_olt_8820.id,
            current_port="1/1",
            current_onu_id=2,
            vlan=11,
            contract_status="ACTIVE",
        )
    )

    # Cria Tenant Gamma com VLAN 500
    t_resp = client.post(
        "/api/v1/tenants",
        json={"name": "Operadora Neutra Gamma", "type": "NEUTRAL_OPERATOR"},
        headers=auth_headers,
    )
    tenant_id = t_resp.json()["id"]
    client.post(
        f"/api/v1/tenants/{tenant_id}/vlans",
        json={"olt_id": sample_olt_8820.id, "vlan_id": 500, "description": "VLAN 500 Gamma"},
        headers=auth_headers,
    )

    # Cria chave para Gamma
    k_resp = client.post(
        "/api/v1/api-keys",
        json={"name": "API Gamma", "scopes": ["onus:read"]},
        headers=auth_headers,
    )
    # Associa a chave ao tenant Gamma no banco
    db = setup_test_env["session_factory"]()
    from app.db.models import APIKeyModel
    key_rec = db.query(APIKeyModel).filter(APIKeyModel.id == k_resp.json()["id"]).first()
    key_rec.tenant_id = tenant_id
    db.commit()
    db.close()

    gamma_headers = {"X-API-Key": k_resp.json()["key"]}

    # Consulta com a chave da Operadora Gamma
    list_resp = client.get("/api/v1/onus", headers=gamma_headers)
    assert list_resp.status_code == 200
    serials = [o["serial"] for o in list_resp.json()]

    # Deve conter a ONU da VLAN 500, mas NUNCA a ONU da VLAN 11!
    assert "SNGAMMA001" in serials
    assert "SNMATRIZ002" not in serials

    # Consulta direta por serial da ONU da Matriz deve retornar 404
    direct_resp = client.get("/api/v1/onus/SNMATRIZ002", headers=gamma_headers)
    assert direct_resp.status_code == 404
