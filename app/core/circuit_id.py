import re
from app.core.security import sanitize_port, sanitize_safe_string, sanitize_vlan


def generate_circuit_id(olt_name: str, port: str, onu_id: int, vlan: int) -> str:
    """
    Gera o identificador físico de circuito (Circuit ID) em conformidade com
    a especificação Broadband Forum TR-101 (Access Node System Architecture)
    e RFC 3046 (DHCP Relay Agent Information Option 82 / Circuit ID Sub-option).

    Sintaxe padronizada de telecom:
    "{clean_olt_name} eth {clean_port}:{onu_id}:{vlan}"
    Exemplo: "OLT-CENTRAL-01 eth 1/1:3:100" ou "HUAWEI-MA5800 eth 0/1/2:1:200"
    """
    clean_olt = sanitize_safe_string(olt_name.strip(), "nome da olt").replace(" ", "-").upper()
    
    # Remove prefixos comuns de tecnologia da porta caso fornecidos (ex: 'gpon ', 'epon ', 'gpon-olt_')
    normalized_port = re.sub(r"^(gpon|epon|xgpon)[\s\-_]*", "", port.strip(), flags=re.IGNORECASE)
    clean_port = sanitize_port(normalized_port)
    clean_vlan = sanitize_vlan(vlan)
    
    if not isinstance(onu_id, int) or onu_id < 1 or onu_id > 256:
        raise ValueError(f"ONU ID inválido ({onu_id}). Deve ser um número inteiro entre 1 e 256.")

    return f"{clean_olt} eth {clean_port}:{onu_id}:{clean_vlan}"
