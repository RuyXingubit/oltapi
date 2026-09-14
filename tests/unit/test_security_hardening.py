import pytest
from fastapi.testclient import TestClient

from app.core.concurrency import olt_concurrency_manager
from app.core.config import settings
from app.core.rbac import SecurityContext
from app.core.security import decrypt_password, encrypt_password
from app.main import app
from app.models.olt import OLTInDB, OLTProtocol, OLTVendor
from app.storage.olt_repository import OLTRepository


@pytest.fixture
def test_client():
    return TestClient(app)


def test_fernet_encryption_and_decryption():
    """Valida que a criptografia simétrica Fernet (AES-256) cifra, decifra e é retrocompatível."""
    original = "SuperSecretP@ssw0rd!"
    cipher = encrypt_password(original)
    
    # Deve ser cifrado e começar com o prefixo Fernet
    assert cipher != original
    assert cipher.startswith("gAAAAA")
    
    # Decifragem deve restaurar exatamente o texto original
    plain = decrypt_password(cipher)
    assert plain == original
    
    # Idempotência: re-cifrar uma string já cifrada não deve alterar
    assert encrypt_password(cipher) == cipher
    
    # Retrocompatibilidade: strings legadas em texto plano são retornadas intactas
    assert decrypt_password("senha_antiga_plana") == "senha_antiga_plana"
    assert decrypt_password("") == ""
    assert encrypt_password("") == ""


def test_owasp_security_headers(test_client):
    """Valida que o middleware injeta os cabeçalhos de segurança OWASP defensivos."""
    response = test_client.get("/health")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "SAMEORIGIN"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert headers.get("x-xss-protection") == "1; mode=block"


def test_reveal_credentials_unauthorized(test_client):
    """Valida que requisições anônimas ou sem token recebem 401 em /reveal-credentials."""
    response = test_client.post("/api/v1/olts/dummy-id/reveal-credentials")
    assert response.status_code == 401


def test_reveal_credentials_forbidden_for_non_admin(test_client):
    """Valida que usuários com papéis não-administrativos (ex: FIELD_TECH) recebem 403."""
    from app.api import deps

    dummy_tech_ctx = SecurityContext(
        caller_type="USER_JWT",
        role="FIELD_TECH",
        scopes={"olts:read"},
        user_id="tech-uuid-1",
        user_name="Técnico de Campo",
        user_email="tech@provedor.com.br",
        tenant_id="tenant-1",
        tenant_name="Inquilino",
        tenant_type="ISP_PARTNER",
    )
    prev_sec_ctx = app.dependency_overrides.get(deps.get_security_context)
    prev_req_key = app.dependency_overrides.get(deps.require_api_key)

    app.dependency_overrides[deps.require_api_key] = lambda: dummy_tech_ctx
    app.dependency_overrides[deps.get_security_context] = lambda: dummy_tech_ctx

    try:
        response = test_client.post(
            "/api/v1/olts/dummy-id/reveal-credentials",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "Permissão negada" in detail or "apenas Administradores" in detail
    finally:
        if prev_sec_ctx is not None:
            app.dependency_overrides[deps.get_security_context] = prev_sec_ctx
        else:
            app.dependency_overrides.pop(deps.get_security_context, None)
        if prev_req_key is not None:
            app.dependency_overrides[deps.require_api_key] = prev_req_key
        else:
            app.dependency_overrides.pop(deps.require_api_key, None)


def test_reveal_credentials_admin_success(test_client):
    """Valida que o SUPER_ADMIN consegue recuperar as credenciais descriptografadas da OLT."""
    from app.api import deps

    mock_olt = OLTInDB(
        id="olt-test-reveal-1",
        name="OLT-TEST-REVEAL",
        vendor=OLTVendor.FIBERHOME,
        model="an5516",
        host="192.168.10.1",
        port=23,
        protocol=OLTProtocol.TELNET,
        username="admin_olt",
        password="plain_or_decrypted_pass_123",
    )

    class DummyRepo:
        def get_by_id(self, olt_id):
            return mock_olt if olt_id == mock_olt.id else None

    admin_ctx = SecurityContext(
        caller_type="USER_JWT",
        role="SUPER_ADMIN",
        scopes={"*"},
        user_id="admin-uuid-1",
        user_name="Super Admin",
        user_email="admin@provedor.com.br",
        tenant_id="tenant-root",
        tenant_name="Matriz",
        tenant_type="PROVIDER_OWNER",
    )

    prev_sec_ctx = app.dependency_overrides.get(deps.get_security_context)
    prev_req_key = app.dependency_overrides.get(deps.require_api_key)
    prev_olt_repo = app.dependency_overrides.get(deps.get_olt_repo)

    app.dependency_overrides[deps.require_api_key] = lambda: admin_ctx
    app.dependency_overrides[deps.get_security_context] = lambda: admin_ctx
    app.dependency_overrides[deps.get_olt_repo] = lambda: DummyRepo()

    try:
        response = test_client.post(
            f"/api/v1/olts/{mock_olt.id}/reveal-credentials",
            headers={"Authorization": "Bearer admin-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["olt_id"] == mock_olt.id
        assert data["olt_name"] == "OLT-TEST-REVEAL"
        assert data["username"] == "admin_olt"
        assert data["password"] == "plain_or_decrypted_pass_123"
        assert "audit_warning" in data
    finally:
        if prev_sec_ctx is not None:
            app.dependency_overrides[deps.get_security_context] = prev_sec_ctx
        else:
            app.dependency_overrides.pop(deps.get_security_context, None)
        if prev_req_key is not None:
            app.dependency_overrides[deps.require_api_key] = prev_req_key
        else:
            app.dependency_overrides.pop(deps.require_api_key, None)
        if prev_olt_repo is not None:
            app.dependency_overrides[deps.get_olt_repo] = prev_olt_repo
        else:
            app.dependency_overrides.pop(deps.get_olt_repo, None)


def test_olt_concurrency_manager():
    """Valida que o gerenciador de concorrência entrega locks consistentes por OLT."""
    lock1 = olt_concurrency_manager.get_lock("olt-alpha")
    lock2 = olt_concurrency_manager.get_lock("olt-alpha")
    lock3 = olt_concurrency_manager.get_lock("olt-beta")

    assert lock1 is lock2
    assert lock1 is not lock3
