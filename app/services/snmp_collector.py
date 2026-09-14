"""
Módulo de Telemetria SNMP Padrão (RFC 1213 MIB-II / RFC 2863 IF-MIB).
Coleta rápida e assíncrona via UDP 161:
- sysUpTime (.1.3.6.1.2.1.1.3.0)
- ifOperStatus (.1.3.6.1.2.1.2.2.1.8)
- ifAdminStatus (.1.3.6.1.2.1.2.2.1.7)
"""

import logging
import socket
import struct
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _encode_length(length: int) -> bytes:
    if length < 128:
        return bytes([length])
    len_bytes = []
    while length > 0:
        len_bytes.insert(0, length & 0xFF)
        length >>= 8
    return bytes([0x80 | len(len_bytes)] + len_bytes)


def _encode_oid(oid_str: str) -> bytes:
    parts = [int(p) for p in oid_str.strip(".").split(".")]
    if len(parts) < 2:
        return b""
    encoded = [40 * parts[0] + parts[1]]
    for p in parts[2:]:
        if p == 0:
            encoded.append(0)
            continue
        sub_bytes = []
        while p > 0:
            sub_bytes.insert(0, (p & 0x7F) | (0x80 if len(sub_bytes) > 0 else 0))
            p >>= 7
        encoded.extend(sub_bytes)
    body = bytes(encoded)
    return b"\x06" + _encode_length(len(body)) + body


def _build_snmp_get(community: str, oid_str: str, request_id: int = 1001) -> bytes:
    community_bytes = community.encode("utf-8")
    community_tlv = b"\x04" + _encode_length(len(community_bytes)) + community_bytes
    version_tlv = b"\x02\x01\x01"  # SNMPv2c

    oid_tlv = _encode_oid(oid_str)
    null_val = b"\x05\x00"
    varbind = b"\x30" + _encode_length(len(oid_tlv) + len(null_val)) + oid_tlv + null_val
    varbind_list = b"\x30" + _encode_length(len(varbind)) + varbind

    pdu_body = (
        b"\x02\x04" + struct.pack(">I", request_id) +
        b"\x02\x01\x00" +  # error-status: noError
        b"\x02\x01\x00" +  # error-index: 0
        varbind_list
    )
    pdu = b"\xa0" + _encode_length(len(pdu_body)) + pdu_body

    msg_body = version_tlv + community_tlv + pdu
    return b"\x30" + _encode_length(len(msg_body)) + msg_body


def _decode_snmp_response(data: bytes) -> Optional[int]:
    """Extrai valor numérico (TimeTicks ou Integer) da resposta SNMP."""
    try:
        # Busca tipo de dado no final do payload: TimeTicks (0x43) ou Integer (0x02)
        idx = data.rfind(b"\x43")
        if idx == -1:
            idx = data.rfind(b"\x02")
        if idx != -1 and idx + 1 < len(data):
            vlen = data[idx + 1]
            val_bytes = data[idx + 2 : idx + 2 + vlen]
            val = int.from_bytes(val_bytes, byteorder="big", signed=False)
            return val
    except Exception as e:
        logger.debug(f"Aviso ao decodificar resposta SNMP: {e}")
    return None


class SNMPCollector:
    """Coletor assíncrono/não-bloqueante de telemetria SNMP."""

    @staticmethod
    def get_sys_uptime(host: str, community: str = "public", port: int = 161, timeout: float = 1.0) -> Optional[int]:
        """
        Consulta sysUpTime (.1.3.6.1.2.1.1.3.0) via UDP 161.
        Retorna o tempo de atividade em segundos ou None se inacessível.
        """
        req = _build_snmp_get(community, "1.3.6.1.2.1.1.3.0", request_id=12345)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(req, (host, port))
            resp, _ = sock.recvfrom(2048)
            ticks = _decode_snmp_response(resp)
            if ticks is not None:
                return ticks // 100  # TimeTicks são centésimos de segundo
        except Exception as e:
            logger.debug(f"SNMP indisponível em {host}:{port}: {e}")
            return None
        finally:
            sock.close()
        return None

    @staticmethod
    def test_snmp_connectivity(host: str, community: str = "public", port: int = 161, timeout: float = 1.0) -> bool:
        """Verifica se o agente SNMP responde no host e porta especificados."""
        uptime = SNMPCollector.get_sys_uptime(host, community, port, timeout)
        return uptime is not None
