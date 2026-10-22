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


def test_driver_regex_and_config_hardening_coverage(tmp_path):
    """Cobre os fluxos de limpeza de CLI, sessão SSH/Telnet, bootstrap e sanitização de logs."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from app.drivers.fiberhome.fiberhome_tl1 import FiberhomeTL1Driver
    from app.drivers.huawei.huawei_vrp import HuaweiVRPDriver
    from app.drivers.parks.parks_fiberlink import ParksFiberlinkDriver
    from app.models.bootstrap import BootstrapRequest
    from app.storage.onu_repository import ONUInventoryRepository

    # 1. Huawei clean_cli_output & bootstrap & wizard inband defaults
    cleaned = HuaweiVRPDriver.clean_cli_output("  Command: \r\n  display board 0\r\nMA5608T#")
    assert "MA5608T#" in cleaned
    assert "Command:" not in cleaned

    hw = HuaweiVRPDriver()
    boot_cmds = hw.generate_bootstrap_commands(BootstrapRequest(hostname="HW-TEST"))
    assert any(settings.OLT_HUAWEI_DEFAULT_INBAND_GW in c for c in boot_cmds)

    olt_hw = OLTInDB(
        id="hw-1",
        name="HW-1",
        vendor=OLTVendor.HUAWEI,
        model="ma5608t",
        host="10.0.0.1",
        port=23,
        protocol=OLTProtocol.TELNET,
        username="root",
        password="admin123",
    )
    wiz_req = SimpleNamespace(
        inband_config=SimpleNamespace(vlan_id=100, uplink_port="0/2/0", ip_cidr="", gateway="10.0.0.254"),
        vlans=[],
        uplink_ports=["0/2/0"],
    )
    with patch.object(hw, "_execute_cli_commands", return_value="OK"):
        wiz_cmds = hw.execute_wizard_commissioning(olt_hw, wiz_req)
        assert any("interface Vlanif100" in c for c in wiz_cmds)

    # 2. Huawei _execute_telnet_commands & _execute_ssh_commands prompt parsing
    with patch("app.drivers.huawei.huawei_vrp.TelnetClient") as mock_tn_cls, \
         patch.object(hw, "_run_interactive_telnet_cmd", return_value="output_ok"):
        tn_inst = MagicMock()
        tn_inst.read_until.side_effect = [b"User name:", b"User password:", b"Welcome MA5608T(config)#"]
        mock_tn_cls.return_value = tn_inst
        out = hw._execute_telnet_commands(olt_hw, ["display version"])
        assert "output_ok" in out

    with patch("app.drivers.huawei.huawei_vrp.paramiko.SSHClient") as mock_ssh_cls, \
         patch("app.drivers.huawei.huawei_vrp.time.sleep"):
        ssh_inst = MagicMock()
        chan = MagicMock()
        calls = {"n": 0}

        def recv_ready_side_effect():
            calls["n"] += 1
            return calls["n"] in (1, 2, 3, 4)

        chan.recv_ready.side_effect = recv_ready_side_effect
        chan.recv.return_value = b"MA5608T(config)#"
        ssh_inst.invoke_shell.return_value = chan
        mock_ssh_cls.return_value = ssh_inst
        ssh_out = hw._execute_ssh_commands(olt_hw, ["display version"], max_wait=1.0)
        assert "MA5608T(config)#" in ssh_out

    # 3. Parks generate_bootstrap_commands defaults
    pk = ParksFiberlinkDriver()
    pk_cmds = pk.generate_bootstrap_commands(
        SimpleNamespace(hostname="PK-TEST", inband_vlan=None, ip_network=None, gateway=None)
    )
    assert any(settings.OLT_DEFAULT_INBAND_GW in c for c in pk_cmds)

    # 4. Fiberhome _resolve_onu_location & save_running_config error paths
    fh = FiberhomeTL1Driver()
    fake_tn = MagicMock()
    with patch.object(fh, "_exec_telnet_cmd", return_value="1  2  5  FHTT12345678"):
        loc = fh._resolve_onu_location(fake_tn, "FHTT12345678")
        assert loc == (1, 2, 5)

    olt_fh_tn = OLTInDB(
        id="fh-1",
        name="FH-1",
        vendor=OLTVendor.FIBERHOME,
        model="an5516",
        host="10.0.0.2",
        port=23,
        protocol=OLTProtocol.TELNET,
        username="GEPON",
        password="GEPON",
    )
    with patch.object(fh, "_open_telnet_session", side_effect=RuntimeError("telnet down")):
        assert fh.save_running_config(olt_fh_tn) is False

    olt_fh_tl1 = olt_fh_tn.model_copy(update={"port": 3337})
    with patch.object(fh, "_execute_tl1_commands", side_effect=RuntimeError("tl1 down")):
        assert fh.save_running_config(olt_fh_tl1) is False

    # 5. ONURepository corrupt load & save error handling
    inv_file = tmp_path / "onus.json"
    hist_file = tmp_path / "history.json"
    inv_file.write_text("{corrupt json", encoding="utf-8")
    hist_file.write_text("{corrupt json", encoding="utf-8")
    repo = ONUInventoryRepository(inventory_file=inv_file, history_file=hist_file)
    with patch("builtins.open", side_effect=OSError("disk full\r\nerror")):
        repo._save_inventory()
        repo._save_history()

    # 6. Huawei profile resolution helpers
    assert hw._resolve_router_profiles({"OLTAPI_ROUTER_LINE": 5}, {"OLTAPI_ROUTER_SRV": 6}) == (5, 6, [])
    assert hw._resolve_router_profiles({"SMARTOLT_FLEXIBLE_GPON": 7}, {"EG8145X6-10": 8}) == (7, 8, [])
    lp_id, sp_id, r_cmds = hw._resolve_router_profiles({"OTHER": 1}, {"OTHER": 2})
    assert lp_id == 2 and sp_id == 3 and len(r_cmds) > 0
    assert hw._resolve_bridge_profiles({"OLTAPI_BRIDGE_LINE_V100": 9}, {"OLTAPI_BRIDGE_SRV_V100": 10}, 100) == (9, 10, [])
    b_lp, b_sp, b_cmds = hw._resolve_bridge_profiles({"OTHER": 1}, {"OTHER": 2}, 100)
    assert b_lp == 6 and b_sp == 3 and len(b_cmds) > 0


