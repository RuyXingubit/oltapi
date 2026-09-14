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
            snmp_community=getattr(m, "snmp_community", "public") or "public",
            snmp_port=getattr(m, "snmp_port", 161) or 161,
            snmp_version=getattr(m, "snmp_version", "v2c") or "v2c",
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
                snmp_community=getattr(req, "snmp_community", "public") or "public",
                snmp_port=getattr(req, "snmp_port", 161) or 161,
                snmp_version=getattr(req, "snmp_version", "v2c") or "v2c",
            )
            db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_model(m)

    def update(self, olt: OLTInDB) -> OLTInDB:
        with self.session_factory() as db:
            m = db.query(OLTModel).filter(OLTModel.id == olt.id).first()
            if m:
                m.name = olt.name
                m.vendor = olt.vendor.value if hasattr(olt.vendor, "value") else str(olt.vendor)
                m.model = olt.model
                m.host = olt.host
                m.port = olt.port
                m.protocol = olt.protocol.value if hasattr(olt.protocol, "value") else str(olt.protocol)
                m.username = olt.username
                m.password = olt.password
                m.snmp_community = olt.snmp_community
                m.snmp_port = olt.snmp_port
                m.snmp_version = olt.snmp_version
                db.commit()
                db.refresh(m)
                return self._to_model(m)
            return olt

    def delete(self, olt_id: str) -> bool:
        with self.session_factory() as db:
            m = db.query(OLTModel).filter(OLTModel.id == olt_id).first()
            if m:
                db.delete(m)
                db.commit()
                return True
            return False
