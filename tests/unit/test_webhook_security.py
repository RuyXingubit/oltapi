import pytest
from app.core.webhook_signer import generate_webhook_secret, sign_payload, verify_signature


def test_generate_webhook_secret():
    sec1 = generate_webhook_secret()
    sec2 = generate_webhook_secret()
    assert sec1.startswith("whsec_")
    assert sec2.startswith("whsec_")
    assert sec1 != sec2
    assert len(sec1) >= 40


def test_sign_payload_format():
    secret = "whsec_test_secret_12345"
    payload = b'{"event":"onu.reconciled","serial":"INCL12345678"}'
    sig = sign_payload(secret, payload)
    assert sig.startswith("sha256=")
    # sha256 hex digest tem 64 caracteres
    assert len(sig) == 7 + 64


def test_verify_signature_valid():
    secret = "whsec_test_secret_12345"
    payload = b'{"event":"onu.reconciled","serial":"INCL12345678"}'
    sig = sign_payload(secret, payload)
    assert verify_signature(secret, payload, sig) is True


def test_verify_signature_tampered_payload():
    secret = "whsec_test_secret_12345"
    payload = b'{"event":"onu.reconciled","serial":"INCL12345678"}'
    sig = sign_payload(secret, payload)

    # Payload adulterado por atacante (MITM)
    tampered_payload = b'{"event":"onu.reconciled","serial":"INCL99999999"}'
    assert verify_signature(secret, tampered_payload, sig) is False


def test_verify_signature_wrong_secret():
    secret1 = "whsec_correct_secret"
    secret2 = "whsec_wrong_secret"
    payload = b'{"event":"onu.reconciled","serial":"INCL12345678"}'
    sig = sign_payload(secret1, payload)

    assert verify_signature(secret2, payload, sig) is False


def test_verify_signature_empty_or_none():
    assert verify_signature("", b"payload", "sha256=123") is False
    assert verify_signature("secret", b"payload", "") is False
