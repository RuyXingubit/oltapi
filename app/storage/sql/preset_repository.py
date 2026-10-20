from datetime import datetime, timezone
from typing import List, Optional

from app.core.uuid import generate_uuid7
from app.db.models import ProvisioningPresetModel
from app.db.session import SessionLocal
from app.models.presets import ProvisioningPresetCreate, ProvisioningPresetItem


class SQLPresetRepository:
    """Repositório relacional para Presets Universais de Provisionamento (Fase 3)."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def _to_item(self, m: ProvisioningPresetModel) -> ProvisioningPresetItem:
        return ProvisioningPresetItem(
            id=m.id,
            name=m.name,
            description=m.description,
            vlan=m.vlan,
            mode=m.mode or "transparent",
            line_profile=m.line_profile or "DEFAULT",
            srv_profile=m.srv_profile or "DEFAULT",
            tenant_id=m.tenant_id,
            is_default=bool(m.is_default),
            created_at=m.created_at,
        )

    def list_presets(self, tenant_id: Optional[str] = None) -> List[ProvisioningPresetItem]:
        with self.session_factory() as db:
            q = db.query(ProvisioningPresetModel)
            if tenant_id:
                q = q.filter(
                    (ProvisioningPresetModel.tenant_id == tenant_id)
                    | (ProvisioningPresetModel.tenant_id.is_(None))
                )
            rows = q.order_by(
                ProvisioningPresetModel.is_default.desc(),
                ProvisioningPresetModel.name.asc(),
            ).all()
            return [self._to_item(r) for r in rows]

    def get_preset(self, preset_id: str) -> Optional[ProvisioningPresetItem]:
        with self.session_factory() as db:
            m = db.query(ProvisioningPresetModel).filter(ProvisioningPresetModel.id == preset_id).first()
            return self._to_item(m) if m else None

    def create_preset(self, req: ProvisioningPresetCreate) -> ProvisioningPresetItem:
        clean_name = req.name.strip()
        with self.session_factory() as db:
            existing = (
                db.query(ProvisioningPresetModel)
                .filter(ProvisioningPresetModel.name == clean_name)
                .first()
            )
            if existing:
                raise ValueError(f"Já existe um Preset com o nome '{clean_name}'.")

            if req.is_default:
                db.query(ProvisioningPresetModel).update({ProvisioningPresetModel.is_default: False})

            m = ProvisioningPresetModel(
                id=generate_uuid7(),
                name=clean_name,
                description=req.description.strip() if req.description else None,
                vlan=req.vlan,
                mode=req.mode.strip() if req.mode else "transparent",
                line_profile=req.line_profile.strip() if req.line_profile else "DEFAULT",
                srv_profile=req.srv_profile.strip() if req.srv_profile else "DEFAULT",
                tenant_id=req.tenant_id,
                is_default=req.is_default,
                created_at=datetime.now(timezone.utc),
            )
            db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_item(m)

    def delete_preset(self, preset_id: str) -> bool:
        with self.session_factory() as db:
            m = db.query(ProvisioningPresetModel).filter(ProvisioningPresetModel.id == preset_id).first()
            if not m:
                return False
            db.delete(m)
            db.commit()
            return True
