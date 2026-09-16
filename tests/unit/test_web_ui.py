import pytest
from fastapi.testclient import TestClient


def test_root_endpoint_operational_json(client: TestClient):
    """Garante que a rota raiz (/) retorna JSON operacional padrão e não serve HTML estático."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "application/json"
    data = resp.json()
    assert data["message"] == "OLTAPI Backend Operational"
    assert data["status"] == "online"
    assert "version" in data
    assert "service" in data


def test_root_endpoint_head_method(client: TestClient):
    """Garante suporte ao método HEAD na rota raiz."""
    resp = client.head("/")
    assert resp.status_code == 200


def test_security_headers_present(client: TestClient):
    """Garante a injeção rigorosa dos cabeçalhos de segurança OWASP em todas as respostas HTTP."""
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "geolocation=()" in resp.headers.get("Permissions-Policy", "")


def test_static_files_not_found(client: TestClient):
    """Garante que rotas de arquivos estáticos legados não estão mais ativas no backend."""
    resp_css = client.get("/static/css/style.css")
    assert resp_css.status_code == 404
    resp_js = client.get("/static/js/app.js")
    assert resp_js.status_code == 404


