from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.drivers.factory import DriverFactory
from app.drivers.intelbras.intelbras_gseries import IntelbrasGSeriesDriver
from app.models.bootstrap import (
    BootstrapMode,
    BootstrapRequest,
    DefaultONUMode,
)
from app.models.olt import OLTCreateRequest, OLTInDB, OLTProtocol, OLTVendor


def test_driver_factory_resolves_g08_and_g16():
    olt_g08 = OLTInDB(
        name="OLT-POP-G08",
        vendor=OLTVendor.INTELBRAS,
        model="OLT G08",
        host="192.168.1.10",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    driver_g08 = DriverFactory.get_driver(olt_g08)
    assert isinstance(driver_g08, IntelbrasGSeriesDriver)
    assert driver_g08.total_pons == 8
    assert driver_g08.model_name == "G08"

    olt_g16 = OLTInDB(
        name="OLT-POP-G16",
        vendor=OLTVendor.INTELBRAS,
        model="G16 GPON",
        host="192.168.1.11",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    driver_g16 = DriverFactory.get_driver(olt_g16)
    assert isinstance(driver_g16, IntelbrasGSeriesDriver)
    assert driver_g16.total_pons == 16
    assert driver_g16.model_name == "G16"


def test_g08_bootstrap_single_vlan():
    driver = IntelbrasGSeriesDriver(total_pons=8, model_name="G08")
    req = BootstrapRequest(
        mode=BootstrapMode.SINGLE_VLAN,
        vlan=100,
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    # Perfis centrais
    assert "deploy profile dba" in commands
    assert "aim 1 name DBA-DEFAULT" in commands
    assert "deploy profile vlan" in commands
    assert "aim 1 name VLAN-100" in commands
    assert "translate old-vlan 100 new-vlan 100" in commands
    assert "deploy profile line" in commands
    assert "mapping 1 port veip vlan 100 gemport 1" in commands

    # Auto config para 8 portas
    assert "ont auto-config name ROUTER-VLAN-100 line 1 interface gpon 0/1" in commands
    assert "ont auto-config name ROUTER-VLAN-100 line 1 interface gpon 0/8" in commands
    assert not any("0/9" in cmd for cmd in commands)  # G08 tem estritamente 8 portas
    assert "write" in commands


def test_g16_bootstrap_single_vlan():
    driver = IntelbrasGSeriesDriver(total_pons=16, model_name="G16")
    req = BootstrapRequest(
        mode=BootstrapMode.SINGLE_VLAN,
        vlan=200,
        default_onu_mode=DefaultONUMode.ROUTER,
    )
    commands = driver.generate_bootstrap_commands(req)

    # Verifica que atende até a porta 16
    assert "ont auto-config name ROUTER-VLAN-200 line 1 interface gpon 0/1" in commands
    assert "ont auto-config name ROUTER-VLAN-200 line 1 interface gpon 0/16" in commands
    assert "ont auto-config name TERCEIROS-16 all-ont line 1 interface gpon 0/16" in commands


def test_gseries_parsers():
    driver = IntelbrasGSeriesDriver(total_pons=8, model_name="G08")

    # 1. Parser Autofind
    raw_autofind = """
----------------------------------------------------------------------
Ont-find list:
----------------------------------------------------------------------
Port      SN              Model         Equipment ID    Password
----------------------------------------------------------------------
0/1       INCL12345678    110B          GPON            --
0/8       HWTC88776655    auto          GPON            --
----------------------------------------------------------------------
    """
    unauth = driver.parse_unauthorized_onus(raw_autofind)
    assert len(unauth) == 2
    assert unauth[0].port == "0/1"
    assert unauth[0].serial == "INCL12345678"
    assert unauth[0].model == "110B"
    assert unauth[1].port == "0/8"
    assert unauth[1].serial == "HWTC88776655"

    # 2. Parser Port ONUs
    raw_port_onus = """
----------------------------------------------------------------------
Port    OntId  SN              State     RxPower(dBm)  Desc
----------------------------------------------------------------------
0/1     1      INCL12345678    online    -19.50        Cliente_01
0/1     2      INCL87654321    offline   --            Cliente_02
----------------------------------------------------------------------
    """
    onus = driver.parse_port_onus(raw_port_onus, "0/1")
    assert len(onus) == 2
    assert onus[0].port == "0/1"
    assert onus[0].onu_id == 1
    assert onus[0].status == "online"
    assert onus[1].status == "offline"

    # 3. Parser Optical Info
    raw_optical = """
Rx optical power(dBm): -19.50
Tx optical power(dBm): 2.30
    """
    rx, tx = driver.parse_optical_info(raw_optical)
    assert rx == -19.50
    assert tx == 2.30


def test_api_g16_bootstrap_flow(client: TestClient, auth_headers, setup_test_env):
    repo = setup_test_env["repo"]
    req = OLTCreateRequest(
        name="OLT-TESTE-G16",
        vendor=OLTVendor.INTELBRAS,
        model="G16",
        host="192.168.1.150",
        port=22,
        protocol=OLTProtocol.SSH,
        username="admin",
        password="pwd",
    )
    g16_olt = repo.create(req)

    # Teste de Preview
    payload = {
        "mode": "single_vlan",
        "vlan": 300,
        "default_onu_mode": "router",
    }
    res = client.post(f"/api/v1/olts/{g16_olt.id}/bootstrap/preview", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    # Confere se a porta 16 está no script gerado para a G16
    assert "interface gpon 0/16" in data["script_text"]
