from dataclasses import dataclass, field
from typing import Dict, Optional, Set
from fastapi import HTTPException, status


@dataclass
class SecurityContext:
    """
    Contexto de segurança imutável injetado em cada requisição autenticada.
    Contém a identidade do chamador, seu papel, escopos e restrições de OLT e VLAN.
    """
    caller_type: str  # "MASTER_KEY", "DYNAMIC_API_KEY", "USER_JWT"
    role: str  # "SUPER_ADMIN", "NOC", "FIELD_TECH", "TENANT_ADMIN", "TENANT_TECH"
    scopes: Set[str] = field(default_factory=lambda: {"*"})
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
    tenant_type: Optional[str] = None  # "PROVIDER_OWNER" ou "NEUTRAL_OPERATOR"
    allowed_olt_ids: Optional[Set[str]] = None  # None = irrestrito (todas as OLTs)
    allowed_vlans: Optional[Dict[str, Set[int]]] = None  # None = irrestrito (todas as VLANs)

    @property
    def is_super_admin(self) -> bool:
        return self.role == "SUPER_ADMIN" or "*" in self.scopes

    def enforce_scope(self, required_scope: str) -> None:
        """Valida se o chamador possui o escopo necessário para a operação."""
        if "*" in self.scopes or required_scope in self.scopes:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permissão negada: esta ação requer o escopo '{required_scope}'.",
        )

    def enforce_olt(self, olt_id: str) -> None:
        """Valida se o chamador tem permissão para visualizar ou operar na OLT especificada."""
        if self.allowed_olt_ids is None or olt_id in self.allowed_olt_ids:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Acesso não autorizado à OLT '{olt_id}'. Sua conta não tem permissão para este equipamento.",
        )

    def enforce_vlan(self, olt_id: str, vlan: int) -> None:
        """Valida se a VLAN solicitada pertence ao contrato do operador nesta OLT."""
        if self.allowed_vlans is None:
            return  # Administrador ou NOC do provedor possuem acesso a qualquer VLAN

        permitted_for_olt = self.allowed_vlans.get(olt_id, set())
        if vlan in permitted_for_olt:
            return

        formatted_allowed = sorted(list(permitted_for_olt)) if permitted_for_olt else "nenhuma"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"VLAN {vlan} não autorizada para seu inquilino nesta OLT. "
                f"VLANs contratadas/permitidas nesta OLT: {formatted_allowed}."
            ),
        )
