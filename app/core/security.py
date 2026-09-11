import hmac
import re
from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from app.core.config import settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Padrões regex para prevenção de injeção de comandos CLI
PORT_REGEX = re.compile(r"^[0-9]+(/[0-9]+)*$")
SERIAL_REGEX = re.compile(r"^[A-Za-z0-9]{4,24}$")
SAFE_STRING_REGEX = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Valida o cabeçalho X-API-Key contra a chave configurada usando timing-attack safe compare."""
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
