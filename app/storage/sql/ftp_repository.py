import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.security import decrypt_password, encrypt_password
from app.core.uuid import generate_uuid7
from app.db.models import FTPServerModel, OLTFTPDestinationModel, OLTModel
from app.db.session import SessionLocal
from app.models.ftp import (
    FTPServerCreate,
    FTPServerResponse,
    FTPServerUpdate,
    OLTFTPDestinationResponse,
)

logger = logging.getLogger(__name__)


class SQLFTPRepository:
    """Repositório de servidores FTP e vínculos com OLTs via SQLAlchemy."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def _to_response(self, m: FTPServerModel) -> FTPServerResponse:
        return FTPServerResponse(
            id=m.id,
            name=m.name,
            host=m.host,
            port=m.port,
            username=m.username,
            base_path=m.base_path,
            is_global_default=m.is_global_default,
            is_active=m.is_active,
            created_at=m.created_at,
        )

    def list_all(self, active_only: bool = False) -> List[FTPServerResponse]:
        with self.session_factory() as db:
            q = db.query(FTPServerModel)
            if active_only:
                q = q.filter(FTPServerModel.is_active.is_(True))
            models = q.order_by(FTPServerModel.name.asc()).all()
            return [self._to_response(m) for m in models]

    def get_by_id(self, ftp_id: str) -> Optional[FTPServerResponse]:
        with self.session_factory() as db:
            m = db.query(FTPServerModel).filter(FTPServerModel.id == ftp_id).first()
            return self._to_response(m) if m else None

    def get_raw_by_id(self, ftp_id: str) -> Optional[FTPServerModel]:
        """Retorna o modelo com a senha decifrada para conexões internas."""
        with self.session_factory() as db:
            m = db.query(FTPServerModel).filter(FTPServerModel.id == ftp_id).first()
            if m:
                db.expunge(m)
                m.password = decrypt_password(m.password)
            return m

    def get_by_name(self, name: str) -> Optional[FTPServerResponse]:
        with self.session_factory() as db:
            m = db.query(FTPServerModel).filter(FTPServerModel.name == name).first()
            return self._to_response(m) if m else None

    def create(self, req: FTPServerCreate) -> FTPServerResponse:
        with self.session_factory() as db:
            server_id = generate_uuid7()
            m = FTPServerModel(
                id=server_id,
                name=req.name,
                host=req.host,
                port=req.port,
                username=req.username,
                password=encrypt_password(req.password),
                base_path=req.base_path,
                is_global_default=req.is_global_default,
                is_active=req.is_active,
            )
            db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_response(m)

    def update(self, ftp_id: str, req: FTPServerUpdate) -> Optional[FTPServerResponse]:
        with self.session_factory() as db:
            m = db.query(FTPServerModel).filter(FTPServerModel.id == ftp_id).first()
            if not m:
                return None
            if req.name is not None:
                m.name = req.name
            if req.host is not None:
                m.host = req.host
            if req.port is not None:
                m.port = req.port
            if req.username is not None:
                m.username = req.username
            if req.password is not None:
                m.password = encrypt_password(req.password)
            if req.base_path is not None:
                m.base_path = req.base_path
            if req.is_global_default is not None:
                m.is_global_default = req.is_global_default
            if req.is_active is not None:
                m.is_active = req.is_active
            db.commit()
            db.refresh(m)
            return self._to_response(m)

    def delete(self, ftp_id: str) -> bool:
        with self.session_factory() as db:
            m = db.query(FTPServerModel).filter(FTPServerModel.id == ftp_id).first()
            if m:
                db.delete(m)
                db.commit()
                return True
            return False

    def bind_olt(self, olt_id: str, ftp_server_ids: List[str]) -> None:
        with self.session_factory() as db:
            # Remove vínculos existentes e adiciona novos
            db.query(OLTFTPDestinationModel).filter(OLTFTPDestinationModel.olt_id == olt_id).delete()
            for fid in ftp_server_ids:
                # Checa se o FTP existe
                ftp = db.query(FTPServerModel).filter(FTPServerModel.id == fid).first()
                if ftp:
                    binding = OLTFTPDestinationModel(
                        id=generate_uuid7(),
                        olt_id=olt_id,
                        ftp_server_id=fid,
                    )
                    db.add(binding)
            db.commit()

    def get_destinations_for_olt(self, olt_id: str) -> OLTFTPDestinationResponse:
        with self.session_factory() as db:
            # 1. Específicos
            bindings = (
                db.query(OLTFTPDestinationModel)
                .filter(OLTFTPDestinationModel.olt_id == olt_id)
                .all()
            )
            specific_ids = [b.ftp_server_id for b in bindings]
            specific_models = (
                db.query(FTPServerModel)
                .filter(FTPServerModel.id.in_(specific_ids), FTPServerModel.is_active.is_(True))
                .all()
                if specific_ids
                else []
            )

            # 2. Globais
            global_models = (
                db.query(FTPServerModel)
                .filter(FTPServerModel.is_global_default.is_(True), FTPServerModel.is_active.is_(True))
                .all()
            )

            specific_responses = [self._to_response(m) for m in specific_models]
            global_responses = [self._to_response(m) for m in global_models]

            # 3. União efetiva sem duplicidades por ID
            seen_ids = set()
            effective = []
            for resp in specific_responses + global_responses:
                if resp.id not in seen_ids:
                    seen_ids.add(resp.id)
                    effective.append(resp)

            return OLTFTPDestinationResponse(
                olt_id=olt_id,
                specific_destinations=specific_responses,
                global_destinations=global_responses,
                effective_destinations=effective,
            )
