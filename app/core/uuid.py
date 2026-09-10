"""
Gerador de UUID versão 7 em conformidade com a RFC 9562.
Garante ordenação temporal nativa (Time-Ordered) com resolução em milissegundos
e entropia criptográfica nos bits restantes.
"""

import os
import time
import uuid


def generate_uuid7() -> str:
    """
    Gera um UUIDv7 em formato canônico (string com hífens).
    Estrutura:
    - 48 bits: Unix timestamp em milissegundos
    - 4 bits: versão (0b0111 = 7)
    - 12 bits: entropia / sequência
    - 2 bits: variante RFC 4122/9562 (0b10)
    - 62 bits: entropia aleatória
    """
    # 48 bits do timestamp unix em milissegundos
    ms = int(time.time() * 1000)
    time_high = (ms >> 16) & 0xFFFFFFFF  # 32 bits superiores
    time_mid = ms & 0xFFFF  # 16 bits inferiores

    # 10 bytes de entropia criptograficamente segura
    rand_bytes = bytearray(os.urandom(10))

    # Versão 7 nos 4 bits superiores de time_hi_and_version
    # rand_bytes[0] e rand_bytes[1] compõem os 16 bits de ver/seq
    rand_bytes[0] = (rand_bytes[0] & 0x0F) | 0x70  # Versão 7

    # Variante RFC (10xx xxxx) nos 2 bits superiores de clock_seq_hi_and_reserved
    rand_bytes[2] = (rand_bytes[2] & 0x3F) | 0x80  # Variante RFC 4122/9562

    # Monta os 16 bytes
    uuid_bytes = (
        time_high.to_bytes(4, byteorder="big")
        + time_mid.to_bytes(2, byteorder="big")
        + bytes(rand_bytes)
    )

    return str(uuid.UUID(bytes=uuid_bytes))


def is_valid_uuid7(val: str) -> bool:
    """Valida se uma string é um UUID versão 7 válido."""
    try:
        parsed = uuid.UUID(val)
        return parsed.version == 7 and parsed.variant == uuid.RFC_4122
    except (ValueError, AttributeError, TypeError):
        return False
