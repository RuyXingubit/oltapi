import pytest
from fastapi.testclient import TestClient


def test_serve_ui_root_endpoint(client: TestClient):
    """Garante que a rota raiz (/) serve o HTML principal da bancada."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "OLTAPI • Bancada de Provisionamento & Diagnóstico" in resp.text
    assert "id=\"view-setup\"" in resp.text
    assert "id=\"view-login\"" in resp.text
    assert "id=\"subview-bancada\"" in resp.text


def test_serve_static_css_and_js(client: TestClient):
    """Garante que os arquivos estáticos CSS e JS são entregues com os Content-Types adequados."""
    resp_css = client.get("/static/css/style.css")
    assert resp_css.status_code == 200
    assert "text/css" in resp_css.headers.get("content-type", "")
    assert "--bg-base" in resp_css.text

    resp_js = client.get("/static/js/app.js")
    assert resp_js.status_code == 200
    assert "javascript" in resp_js.headers.get("content-type", "")
    assert "checkSystemSetup" in resp_js.text
