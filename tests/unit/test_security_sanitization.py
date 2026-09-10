import pytest
from fastapi import HTTPException
from app.core.config import settings
from app.core.security import (
    sanitize_description,
    sanitize_port,
    sanitize_safe_string,
    sanitize_serial,
    sanitize_vlan,
    verify_api_key,
)


def test_sanitize_port_valid():
    assert sanitize_port("1/1") == "1/1"
    assert sanitize_port("0/1/1") == "0/1/1"
    assert sanitize_port(" 1/16 ") == "1/16"


def test_sanitize_port_injection_attempts():
    injection_payloads = [
        "1/1; reboot",
        "1/1 | cat /etc/passwd",
        "1/1`reboot`",
        "1/1 && rm -rf /",
        "1/1\nreboot",
        "invalid_port",
        "",
    ]
    for payload in injection_payloads:
        with pytest.raises(ValueError):
            sanitize_port(payload)


def test_sanitize_serial_valid():
    assert sanitize_serial("INCL12345678") == "INCL12345678"
    assert sanitize_serial("HWTC99887766") == "HWTC99887766"
    assert sanitize_serial(" 4857544312345678 ") == "4857544312345678"


def test_sanitize_serial_injection_attempts():
    injection_payloads = [
        "INCL; reboot",
        "INCL 1234",
        "INCL&&ls",
        "INCL|sh",
        "INCL' OR '1'='1",
        "",
        "ab",  # Muito curto
    ]
    for payload in injection_payloads:
        with pytest.raises(ValueError):
            sanitize_serial(payload)


def test_sanitize_vlan_valid():
    assert sanitize_vlan(1) == 1
    assert sanitize_vlan(100) == 100
    assert sanitize_vlan(4094) == 4094


def test_sanitize_vlan_invalid_range():
    invalid_vlans = [0, -1, 4095, 5000, "100"]
    for v in invalid_vlans:
        with pytest.raises(ValueError):
            sanitize_vlan(v)


def test_sanitize_safe_string_valid():
    assert sanitize_safe_string("Cliente_Joao") == "Cliente_Joao"
    assert sanitize_safe_string("PLAN-100M") == "PLAN-100M"
    assert sanitize_safe_string("") == ""


def test_sanitize_safe_string_injection_attempts():
    bad_strings = [
        "Cliente\"; reboot;",
        "Cliente && id",
        "teste|cat",
        "linha\nnova",
        "espaço no meio com aspas '",
    ]
    for s in bad_strings:
        with pytest.raises(ValueError):
            sanitize_safe_string(s)


def test_verify_api_key_valid():
    assert verify_api_key(settings.API_KEY) == settings.API_KEY


def test_verify_api_key_invalid():
    with pytest.raises(HTTPException) as exc:
        verify_api_key("wrong_key")
    assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc:
        verify_api_key(None)
    assert exc.value.status_code == 401
