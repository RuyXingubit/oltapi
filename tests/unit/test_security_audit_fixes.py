import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.rate_limit import limiter
from app.core.rbac import SecurityContext
from app.core.security import decrypt_password
from app.db.models import WebhookSubscriptionModel
from app.main import app
from app.models.olt import OLTCreateRequest, OLTInDB, OLTProtocol, OLTVendor


@pytest.fixture
def tech_olt_a_headers(client: TestClient, auth_headers, sample_olt_8820: OLTInDB, setup_test_env):
    """Cria duas OLTs (sample_olt_8820 e olt_b) e um técnico restrito apenas à sample_olt_8820."""
    limiter.reset()
    repo = setup_test_env["repo"]
    olt_b = None
    for existing in repo.list_all():
        if existing.name == "OLT-SEC-AUDIT-B":
            olt_b = existing
            break
    if not olt_b:
        olt_b = repo.create(
            OLTCreateRequest(
                name="OLT-SEC-AUDIT-B",
                vendor=OLTVendor.VSOL,
                model="V1600GT",
                host="192.168.99.200",
                port=22,
                protocol=OLTProtocol.SSH,
                username="admin",
                password="secret_b_password",
            )
        )

    # Garante que existe um tenant matriz para criar o usuário
    client.post(
        "/api/v1/setup/init",
        json={
            "provider_name": "Provedor Audit",
            "admin_name": "Admin Audit",
            "admin_email": "admin.audit@provedor.local",
            "admin_password": "senha_forte_admin_123",
        },
        headers=auth_headers,
    )

    email = "tech.audit.olta@provedor.local"
    client.post(
        "/api/v1/users",
        json={
            "name": "Técnico Restrito OLT A",
            "email": email,
            "password": "senha_tech_audit_123",
            "role": "FIELD_TECH",
            "allowed_olt_ids": [sample_olt_8820.id],
        },
        headers=auth_headers,
    )

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "senha_tech_audit_123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "olt_a": sample_olt_8820,
        "olt_b": olt_b,
    }


def test_decrypt_password_corrupted_token_does_not_raise_name_error():
    """Garante que um token Fernet inválido/corrompido não levanta NameError por falta de logger."""
    corrupted = "gAAAAABl_invalid_corrupted_fernet_token_payload_xyz123"
    result = decrypt_password(corrupted)
    assert result == corrupted


def test_api_key_privilege_escalation_blocked_for_field_tech(client: TestClient, tech_olt_a_headers):
    """
    Garante que um técnico de campo (FIELD_TECH, sem escopo 'api_keys:manage')
    não consegue criar nem listar chaves de API para escalar privilégios para '*'.
    """
    headers = tech_olt_a_headers["headers"]

    list_resp = client.get("/api/v1/api-keys", headers=headers)
    assert list_resp.status_code == 403

    create_resp = client.post(
        "/api/v1/api-keys",
        json={"name": "Escalação Ilegal", "scopes": ["*"]},
        headers=headers,
    )
    assert create_resp.status_code == 403


def test_api_key_scope_subset_enforcement(client: TestClient):
    """
    Garante que um chamador com 'api_keys:manage' mas sem '*' não pode emitir uma
    chave com escopos que ele próprio não possui.
    """
    limited_admin_ctx = SecurityContext(
        caller_type="USER_JWT",
        role="TENANT_ADMIN",
        scopes={"api_keys:manage", "olts:read", "onus:read"},
        user_id="user-limited-admin",
        user_name="Admin Limitado",
        user_email="limited@provedor.local",
        tenant_id="tenant-1",
        tenant_name="Provedor",
        tenant_type="PROVIDER_OWNER",
    )

    prev_sec_ctx = app.dependency_overrides.get(deps.get_security_context)
    prev_req_key = app.dependency_overrides.get(deps.require_api_key)
    app.dependency_overrides[deps.get_security_context] = lambda: limited_admin_ctx
    app.dependency_overrides[deps.require_api_key] = lambda: limited_admin_ctx

    try:
        # Tentar criar chave com '*' ou 'olts:admin' (que não estão nos escopos do chamador) deve dar 403
        resp_wildcard = client.post(
            "/api/v1/api-keys",
            json={"name": "Chave Wildcard", "scopes": ["*"]},
        )
        assert resp_wildcard.status_code == 403

        resp_admin = client.post(
            "/api/v1/api-keys",
            json={"name": "Chave Admin", "scopes": ["olts:admin"]},
        )
        assert resp_admin.status_code == 403
    finally:
        if prev_sec_ctx is not None:
            app.dependency_overrides[deps.get_security_context] = prev_sec_ctx
        else:
            app.dependency_overrides.pop(deps.get_security_context, None)
        if prev_req_key is not None:
            app.dependency_overrides[deps.require_api_key] = prev_req_key
        else:
            app.dependency_overrides.pop(deps.require_api_key, None)


def test_rbac_and_olt_isolation_on_config_backups_vlans_and_policies(client: TestClient, tech_olt_a_headers):
    """
    Garante que o técnico restrito à OLT-A (FIELD_TECH):
    1. Recebe 403 ao tentar acessar running-config, VLANs, perfis ou políticas da OLT-B.
    2. Recebe 403 ao tentar disparar/listar/expurgar backups (não tem 'backups:read' nem 'backups:create').
    3. Recebe 403 ao tentar criar VLAN, aplicar bootstrap, gerenciar FTP ou controlar o Scanner ('olts:admin').
    """
    headers = tech_olt_a_headers["headers"]
    olt_a = tech_olt_a_headers["olt_a"]
    olt_b = tech_olt_a_headers["olt_b"]

    # 1. Isolamento de OLT (tentando acessar OLT-B não permitida)
    assert client.get(f"/api/v1/olts/{olt_b.id}/config", headers=headers).status_code == 403
    assert client.post(f"/api/v1/olts/{olt_b.id}/test-connection", headers=headers).status_code == 403
    assert client.get(f"/api/v1/olts/{olt_b.id}/vlans", headers=headers).status_code == 403
    assert client.get(f"/api/v1/olts/{olt_b.id}/vlans/metrics", headers=headers).status_code == 403
    assert client.get(f"/api/v1/olts/{olt_b.id}/profiles", headers=headers).status_code == 403
    assert client.get(f"/api/v1/olts/{olt_b.id}/provisioning-schema", headers=headers).status_code == 403
    assert client.get(f"/api/v1/olts/{olt_b.id}/pon-policies", headers=headers).status_code == 403

    # 2. Restrição de escopo de Backups (FIELD_TECH não possui backups:read nem backups:create)
    assert client.get(f"/api/v1/olts/{olt_a.id}/backups", headers=headers).status_code == 403
    assert client.post(f"/api/v1/olts/{olt_a.id}/backups", headers=headers).status_code == 403
    assert client.post(f"/api/v1/olts/{olt_a.id}/backups/purge", headers=headers).status_code == 403
    assert client.post("/api/v1/backups/run-all", headers=headers).status_code == 403
    assert client.get("/api/v1/backups/audit-all", headers=headers).status_code == 403
    assert client.post("/api/v1/backups/purge-all", headers=headers).status_code == 403

    # 3. Restrição de escopo Administrativo (olts:admin)
    assert client.post(
        f"/api/v1/olts/{olt_a.id}/vlans",
        json={"vlan_id": 999, "name": "VLAN_TEST"},
        headers=headers,
    ).status_code == 403
    assert client.post(
        f"/api/v1/olts/{olt_a.id}/bootstrap/apply",
        json={"mode": "single_vlan", "uplink_port": "1", "vlan": 100},
        headers=headers,
    ).status_code == 403
    assert client.post(f"/api/v1/olts/{olt_a.id}/sync", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/ftp-servers",
        json={"name": "FTP-HACK", "host": "10.0.0.1", "username": "u", "password": "p"},
        headers=headers,
    ).status_code == 403
    assert client.post("/api/v1/scanner/start", headers=headers).status_code == 403
    assert client.post("/api/v1/scanner/stop", headers=headers).status_code == 403
    assert client.post("/api/v1/scanner/run-now", headers=headers).status_code == 403


def test_webhook_ssrf_protection(client: TestClient, auth_headers):
    """
    Garante que o cadastro de Webhooks bloqueia URLs internas de loopback,
    metadata de nuvem (169.254.169.254) e esquemas não-HTTP(S).
    """
    forbidden_urls = [
        "http://127.0.0.1:8000/health",
        "http://localhost:5432/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]:8000/",
        "file:///etc/passwd",
        "ftp://192.168.1.1/file",
    ]
    for bad_url in forbidden_urls:
        resp = client.post(
            "/api/v1/webhooks",
            json={"url": bad_url, "description": "Tentativa SSRF"},
            headers=auth_headers,
        )
        assert resp.status_code in (400, 422), f"URL insegura não foi bloqueada: {bad_url}"


def test_webhook_secret_encrypted_at_rest(client: TestClient, auth_headers, setup_test_env):
    """
    Garante que o segredo HMAC de um webhook é persistido cifrado com Fernet (gAAAAA...)
    no banco de dados, enquanto a camada de repositório decifra transparentemente.
    """
    raw_secret = "whsec_super_secret_at_rest_test_999"
    resp = client.post(
        "/api/v1/webhooks",
        json={
            "url": "https://erp.seguro.com.br/webhook",
            "secret": raw_secret,
            "description": "Teste Criptografia em Repouso",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    sub_id = resp.json()["id"]

    # Verifica diretamente na tabela SQL se o valor salvo está cifrado com Fernet
    db = setup_test_env["session_factory"]()
    try:
        row = db.query(WebhookSubscriptionModel).filter(WebhookSubscriptionModel.id == sub_id).first()
        assert row is not None
        assert row.secret != raw_secret
        assert row.secret.startswith("gAAAAA")
    finally:
        db.close()
