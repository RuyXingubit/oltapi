import pytest
from fastapi.testclient import TestClient


def test_serve_ui_root_endpoint(client: TestClient):
    """Garante que a rota raiz (/) serve o HTML principal da aplicação com todas as views de workflow."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "OLTAPI • Gestão de ONUs" in resp.text
    assert "id=\"view-setup\"" in resp.text
    assert "id=\"view-login\"" in resp.text
    assert "id=\"subview-bancada\"" in resp.text
    assert "id=\"subview-inventario\"" in resp.text
    assert "id=\"subview-olts\"" in resp.text
    assert "id=\"subview-xray\"" in resp.text
    assert "id=\"subview-vlans\"" in resp.text
    assert "id=\"subview-config\"" in resp.text
    assert "id=\"modal-vlan-history\"" in resp.text
    assert "id=\"modal-new-olt\"" in resp.text
    assert "id=\"onboarding-stepper-section\"" in resp.text
    assert "id=\"modal-new-vlan\"" in resp.text
    assert "id=\"setup-admin-password-confirm\"" in resp.text
    assert "password-toggle-btn" in resp.text
    assert "password-input-wrapper" in resp.text


def test_serve_static_css_and_js(client: TestClient):
    """Garante que os arquivos estáticos CSS e JS são entregues com os Content-Types adequados e novas features."""
    resp_css = client.get("/static/css/style.css")
    assert resp_css.status_code == 200
    assert "text/css" in resp_css.headers.get("content-type", "")
    assert "--bg-base" in resp_css.text
    assert ".ports-grid" in resp_css.text
    assert ".port-led" in resp_css.text
    assert ".led-up" in resp_css.text
    assert ".onboarding-stepper" in resp_css.text
    assert ".password-input-wrapper" in resp_css.text
    assert ".password-toggle-btn" in resp_css.text

    resp_js = client.get("/static/js/app.js")
    assert resp_js.status_code == 200
    assert "javascript" in resp_js.headers.get("content-type", "")
    assert "checkSystemSetup" in resp_js.text
    assert "openOLTXRay" in resp_js.text
    assert "loadVLANsMetrics" in resp_js.text
    assert "loadFTPOverview" in resp_js.text
    assert "openVLANHistoryModal" in resp_js.text
    assert "handleStartOnboarding" in resp_js.text
    assert "initPasswordToggles" in resp_js.text
    assert "setup-admin-password-confirm" in resp_js.text
