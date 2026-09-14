import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import bcrypt
import jwt
from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from app.core.config import settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Padrões regex para prevenção de injeção de comandos CLI
PORT_REGEX = re.compile(r"^[0-9]+(/[0-9]+)*$")
SERIAL_REGEX = re.compile(r"^[A-Za-z0-9]{4,24}$")
SAFE_STRING_REGEX = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def get_password_hash(password: str) -> str:
    """Gera hash seguro de senha utilizando bcrypt com salt dinâmico."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Valida se a senha em texto puro confere com o hash bcrypt."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Gera um JWT assinado para sessões Web."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decodifica e valida o JWT assinado. Retorna None se inválido ou expirado."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None


def hash_api_key(api_key: str) -> str:
    """Calcula o hash SHA-256 de uma chave de API para persistência segura no banco."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key(prefix_hint: str = "live") -> Tuple[str, str, str]:
    """
    Gera uma chave de API criptograficamente segura.
    Retorna: (chave_completa_pura, prefixo_visivel, hash_sha256)
    Ex: ('olt_live_3f9a_abcdef...', 'olt_live_3f9a', 'e3b0c442...')
    """
    prefix = f"olt_{prefix_hint}_{secrets.token_hex(2)}"
    secret = secrets.token_urlsafe(32)
    full_key = f"{prefix}_{secret}"
    key_hash = hash_api_key(full_key)
    return full_key, prefix, key_hash


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Valida o cabeçalho X-API-Key contra a chave mestra configurada usando timing-attack safe compare."""
    if not api_key or not hmac.compare_digest(api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API ausente ou inválida (cabeçalho X-API-Key).",
        )
    return api_key


def sanitize_port(port: str) -> str:
    """Valida formato de porta PON (ex: '1/1', '0/1/1')."""
    if not port or not PORT_REGEX.match(port.strip()):
        raise ValueError(
            f"Formato de porta inválido: '{port}'. Esperado formato numérico como '1/1' ou '0/1/1'."
        )
    return port.strip()


def sanitize_serial(serial: str) -> str:
    """Valida formato de serial de ONU (apenas alfanumérico seguro)."""
    if not serial or not SERIAL_REGEX.match(serial.strip()):
        raise ValueError(
            f"Serial inválido: '{serial}'. Deve conter apenas caracteres alfanuméricos de 4 a 24 posições."
        )
    return serial.strip()


def sanitize_safe_string(val: str, field_name: str = "campo") -> str:
    """Valida strings livres (descrição, perfil) impedindo injeção de metacaracteres CLI."""
    if not val:
        return ""
    val_clean = val.strip()
    if not SAFE_STRING_REGEX.match(val_clean):
        raise ValueError(
            f"Valor inválido para {field_name}: '{val}'. Permitido apenas letras, números, hífens e underscores (máx 64 caracteres)."
        )
    return val_clean


def sanitize_description(val: str) -> str:
    """Valida descrição de cliente/ONU."""
    return sanitize_safe_string(val, "descrição")


def sanitize_vlan(vlan: int) -> int:
    """Valida intervalo válido de VLAN IEEE 802.1Q."""
    if not isinstance(vlan, int) or vlan < 1 or vlan > 4094:
        raise ValueError(f"VLAN inválida: {vlan}. Deve estar entre 1 e 4094.")
    return vlan


# ==============================================================================
# Criptografia Simétrica Reversível em Repouso (AES-256 Fernet)
# ==============================================================================
import base64
from cryptography.fernet import Fernet, InvalidToken

_fernet_instance: Optional[Fernet] = None


def get_fernet() -> Fernet:
    """Retorna uma instância singleton de Fernet para cifragem simétrica de senhas de OLTs/FTPs em repouso."""
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    key = getattr(settings, "DB_ENCRYPTION_KEY", None)
    if key and key.strip():
        raw_key = key.strip().encode("utf-8")
        if len(raw_key) == 44:
            try:
                base64.urlsafe_b64decode(raw_key)
                _fernet_instance = Fernet(raw_key)
                return _fernet_instance
            except Exception:
                pass
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key).digest())
        _fernet_instance = Fernet(derived)
        return _fernet_instance

    seed = f"{settings.JWT_SECRET}:{settings.API_KEY}".encode("utf-8")
    derived = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
    _fernet_instance = Fernet(derived)
    return _fernet_instance


def encrypt_password(plain_text: str) -> str:
    """Criptografa credenciais em repouso com Fernet AES-256. Retorna string segura."""
    if not plain_text:
        return ""
    if plain_text.startswith("gAAAAA"):
        return plain_text
    fernet = get_fernet()
    return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_password(cipher_or_plain: str) -> str:
    """Decifra credenciais salvas em repouso. Retorna texto puro caso já esteja descriptografado (retrocompatível)."""
    if not cipher_or_plain:
        return ""
    if not cipher_or_plain.startswith("gAAAAA"):
        return cipher_or_plain
    try:
        fernet = get_fernet()
        return fernet.decrypt(cipher_or_plain.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        # Fallback gracioso: tentar decifrar com a chave derivada (JWT_SECRET:API_KEY)
        # caso a base tenha sido cifrada antes da definição de uma DB_ENCRYPTION_KEY dedicada
        try:
            seed = f"{settings.JWT_SECRET}:{settings.API_KEY}".encode("utf-8")
            derived = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
            fallback_fernet = Fernet(derived)
            return fallback_fernet.decrypt(cipher_or_plain.encode("utf-8")).decode("utf-8")
        except Exception:
            logger.warning("Falha ao decifrar credencial em repouso com Fernet. Retornando valor bruto.")
            return cipher_or_plain
