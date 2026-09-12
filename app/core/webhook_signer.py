import hashlib
import hmac
import secrets


def generate_webhook_secret() -> str:
    """Gera uma chave secreta criptograficamente segura (32 bytes hex) para autenticação de webhook."""
    return f"whsec_{secrets.token_hex(24)}"


def sign_payload(secret: str, payload_bytes: bytes) -> str:
    """
    Calcula a assinatura digital HMAC SHA-256 de um payload em bytes.
    Retorna no formato padronizado 'sha256=<hex_digest>'.
    """
    if not secret:
        raise ValueError("Chave secreta (secret) é obrigatória para assinar o payload do webhook.")
    
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(secret: str, payload_bytes: bytes, signature_header: str) -> bool:
    """
    Valida a assinatura recebida no cabeçalho X-OLTAPI-Signature contra o corpo bruto.
    Utiliza hmac.compare_digest para proteção contra ataques de temporização (timing attacks).
    """
    if not secret or not signature_header:
        return False
    
    expected_signature = sign_payload(secret, payload_bytes)
    return hmac.compare_digest(expected_signature, signature_header)
