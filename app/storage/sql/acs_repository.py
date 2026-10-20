from datetime import datetime, timezone
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from app.core.security import decrypt_password, encrypt_password
from app.core.uuid import generate_uuid7
from app.db.models import ACSServerConfigModel
from app.db.session import SessionLocal
from app.models.acs import ACSServerConfigCreate, ACSServerConfigItem


class SQLACSRepository:
    """Repositório relacional para servidores ACS TR-069 / CWMP com senha cifrada em repouso (Fase 5)."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def _to_item(self, m: ACSServerConfigModel) -> ACSServerConfigItem:
        return ACSServerConfigItem(
            id=m.id,
            name=m.name,
            nbi_url=m.nbi_url,
            username=m.username,
            cwmp_inform_url=m.cwmp_inform_url,
            is_active=bool(m.is_active),
            created_at=m.created_at,
        )

    @staticmethod
    def _validate_url(url: str, field_name: str = "nbi_url") -> str:
        clean = url.strip().rstrip("/")
        parsed = urlparse(clean)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"URL inválida em '{field_name}': use http:// ou https:// com host válido.")
        return clean

    def list_servers(self) -> List[ACSServerConfigItem]:
        with self.session_factory() as db:
            rows = (
                db.query(ACSServerConfigModel)
                .order_by(ACSServerConfigModel.is_active.desc(), ACSServerConfigModel.name.asc())
                .all()
            )
            return [self._to_item(r) for r in rows]

    def get_server(self, server_id: str) -> Optional[ACSServerConfigItem]:
        with self.session_factory() as db:
            m = db.query(ACSServerConfigModel).filter(ACSServerConfigModel.id == server_id).first()
            return self._to_item(m) if m else None

    def get_server_with_credentials(self, server_id: Optional[str] = None) -> Optional[Tuple[ACSServerConfigItem, Optional[str]]]:
        """Retorna o servidor ACS (específico ou o ativo principal) junto com a senha decifrada em memória."""
        with self.session_factory() as db:
            if server_id:
                m = db.query(ACSServerConfigModel).filter(ACSServerConfigModel.id == server_id).first()
            else:
                m = (
                    db.query(ACSServerConfigModel)
                    .filter(ACSServerConfigModel.is_active.is_(True))
                    .order_by(ACSServerConfigModel.created_at.desc())
                    .first()
                )
            if not m:
                return None
            plain_pwd = decrypt_password(m.password_encrypted) if m.password_encrypted else None
            return self._to_item(m), plain_pwd

    def create_server(self, req: ACSServerConfigCreate) -> ACSServerConfigItem:
        clean_name = req.name.strip()
        clean_nbi = self._validate_url(req.nbi_url, "nbi_url")
        clean_cwmp = self._validate_url(req.cwmp_inform_url, "cwmp_inform_url") if req.cwmp_inform_url else None

        with self.session_factory() as db:
            existing = (
                db.query(ACSServerConfigModel)
                .filter(ACSServerConfigModel.name == clean_name)
                .first()
            )
            if existing:
                raise ValueError(f"Já existe um servidor ACS com o nome '{clean_name}'.")

            enc_pwd = encrypt_password(req.password) if req.password else None
            m = ACSServerConfigModel(
                id=generate_uuid7(),
                name=clean_name,
                nbi_url=clean_nbi,
                username=req.username.strip() if req.username else None,
                password_encrypted=enc_pwd,
                cwmp_inform_url=clean_cwmp,
                is_active=req.is_active,
                created_at=datetime.now(timezone.utc),
            )
            db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_item(m)

    def delete_server(self, server_id: str) -> bool:
        with self.session_factory() as db:
            m = db.query(ACSServerConfigModel).filter(ACSServerConfigModel.id == server_id).first()
            if not m:
                return False
            db.delete(m)
            db.commit()
            return True
