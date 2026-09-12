import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.uuid import generate_uuid7
from app.db.models import OLTModel
from app.db.session import SessionLocal
from app.models.olt import OLTCreateRequest, OLTInDB, OLTProtocol, OLTVendor

logger = logging.getLogger(__name__)


class SQLOLTRepository:
    """Repositório de OLTs persistido em banco de dados relacional via SQLAlchemy."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def _to_model(self, m: OLTModel) -> OLTInDB:
        return OLTInDB(
            id=m.id,
            name=m.name,
            vendor=OLTVendor(m.vendor),
            model=m.model,
            host=m.host,
            port=m.port,
            protocol=OLTProtocol(m.protocol),
            username=m.username,
            password=m.password,
            created_at=m.created_at,
        )

    def list_all(self) -> List[OLTInDB]:
        with self.session_factory() as db:
            models = db.query(OLTModel).order_by(OLTModel.name.asc()).all()
            return [self._to_model(m) for m in models]

    def get_by_id(self, olt_id: str) -> Optional[OLTInDB]:
        with self.session_factory() as db:
            m = db.query(OLTModel).filter(OLTModel.id == olt_id).first()
            return self._to_model(m) if m else None

    def create(self, req: OLTCreateRequest) -> OLTInDB:
        with self.session_factory() as db:
            olt_id = generate_uuid7()
            m = OLTModel(
                id=olt_id,
                name=req.name,
                vendor=req.vendor.value if hasattr(req.vendor, "value") else str(req.vendor),
                model=req.model,
                host=req.host,
                port=req.port,
                protocol=req.protocol.value if hasattr(req.protocol, "value") else str(req.protocol),
                username=req.username,
                password=req.password,
            )
            db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_model(m)

    def delete(self, olt_id: str) -> bool:
        with self.session_factory() as db:
            m = db.query(OLTModel).filter(OLTModel.id == olt_id).first()
            if m:
                db.delete(m)
                db.commit()
                return True
            return False
