import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.uuid import generate_uuid7
from app.db.models import AutoProvisionTaskModel, OLTPonPolicyModel
from app.db.session import SessionLocal
from app.models.pon_policy import (
    AutoProvisionTaskCreate,
    AutoProvisionTaskItem,
    PonPolicyCreateOrUpdate,
    PonPolicyItem,
)

logger = logging.getLogger(__name__)


class SQLPonPolicyRepository:
    """Repositório relacional para políticas default por porta PON e Tasks de Cutover."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def _to_policy_model(self, m: OLTPonPolicyModel) -> PonPolicyItem:
        vendor_params = {}
        if m.vendor_parameters:
            try:
                vendor_params = json.loads(m.vendor_parameters)
            except Exception:
                vendor_params = {}
        return PonPolicyItem(
            id=m.id,
            olt_id=m.olt_id,
            port=m.port,
            default_vlan=m.default_vlan,
            default_mode=m.default_mode,
            default_line_profile=m.default_line_profile,
            default_srv_profile=m.default_srv_profile,
            vendor_parameters=vendor_params,
            auto_authorize_enabled=m.auto_authorize_enabled,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def _to_task_model(self, m: AutoProvisionTaskModel) -> AutoProvisionTaskItem:
        vendor_params = {}
        if m.vendor_parameters:
            try:
                vendor_params = json.loads(m.vendor_parameters)
            except Exception:
                vendor_params = {}

        now = datetime.now(timezone.utc)
        remaining = 0
        if m.status == "RUNNING":
            rem = (m.expires_at - now).total_seconds()
            remaining = max(0, int(rem))

        return AutoProvisionTaskItem(
            id=m.id,
            olt_id=m.olt_id,
            pon_port=m.pon_port,
            target_vlan=m.target_vlan,
            default_mode=m.default_mode,
            default_line_profile=m.default_line_profile,
            default_srv_profile=m.default_srv_profile,
            vendor_parameters=vendor_params,
            status=m.status,
            starts_at=m.starts_at,
            expires_at=m.expires_at,
            remaining_seconds=remaining,
            provisioned_count=m.provisioned_count,
            created_by=m.created_by,
            created_at=m.created_at,
        )

    # --- Métodos de Políticas por PON ---

    def list_policies_by_olt(self, olt_id: str) -> List[PonPolicyItem]:
        with self.session_factory() as db:
            items = (
                db.query(OLTPonPolicyModel)
                .filter(OLTPonPolicyModel.olt_id == olt_id)
                .order_by(OLTPonPolicyModel.port.asc())
                .all()
            )
            return [self._to_policy_model(m) for m in items]

    def get_policy(self, olt_id: str, port: str) -> Optional[PonPolicyItem]:
        clean_port = port.strip()
        with self.session_factory() as db:
            m = (
                db.query(OLTPonPolicyModel)
                .filter(
                    OLTPonPolicyModel.olt_id == olt_id,
                    OLTPonPolicyModel.port == clean_port,
                )
                .first()
            )
            return self._to_policy_model(m) if m else None

    def upsert_policy(self, olt_id: str, port: str, data: PonPolicyCreateOrUpdate) -> PonPolicyItem:
        clean_port = port.strip()
        vendor_json = json.dumps(data.vendor_parameters or {})
        with self.session_factory() as db:
            m = (
                db.query(OLTPonPolicyModel)
                .filter(
                    OLTPonPolicyModel.olt_id == olt_id,
                    OLTPonPolicyModel.port == clean_port,
                )
                .first()
            )
            if m:
                m.default_vlan = data.default_vlan
                m.default_mode = data.default_mode
                m.default_line_profile = data.default_line_profile
                m.default_srv_profile = data.default_srv_profile
                m.vendor_parameters = vendor_json
                m.auto_authorize_enabled = data.auto_authorize_enabled
                m.updated_at = datetime.now(timezone.utc)
            else:
                m = OLTPonPolicyModel(
                    id=generate_uuid7(),
                    olt_id=olt_id,
                    port=clean_port,
                    default_vlan=data.default_vlan,
                    default_mode=data.default_mode,
                    default_line_profile=data.default_line_profile,
                    default_srv_profile=data.default_srv_profile,
                    vendor_parameters=vendor_json,
                    auto_authorize_enabled=data.auto_authorize_enabled,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(m)
            db.commit()
            db.refresh(m)
            return self._to_policy_model(m)

    def delete_policy(self, olt_id: str, port: str) -> bool:
        clean_port = port.strip()
        with self.session_factory() as db:
            m = (
                db.query(OLTPonPolicyModel)
                .filter(
                    OLTPonPolicyModel.olt_id == olt_id,
                    OLTPonPolicyModel.port == clean_port,
                )
                .first()
            )
            if not m:
                return False
            db.delete(m)
            db.commit()
            return True

    # --- Métodos de Tasks Temporizadas de Cutover ---

    def create_task(self, olt_id: str, req: AutoProvisionTaskCreate, default_vlan: int) -> AutoProvisionTaskItem:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=req.duration_minutes)
        vlan = req.target_vlan or default_vlan
        vendor_json = json.dumps(req.vendor_parameters or {})

        with self.session_factory() as db:
            task = AutoProvisionTaskModel(
                id=generate_uuid7(),
                olt_id=olt_id,
                pon_port=req.pon_port.strip(),
                target_vlan=vlan,
                default_mode=req.default_mode,
                default_line_profile=req.default_line_profile,
                default_srv_profile=req.default_srv_profile,
                vendor_parameters=vendor_json,
                status="RUNNING",
                starts_at=now,
                expires_at=expires_at,
                provisioned_count=0,
                created_by=req.created_by,
                created_at=now,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return self._to_task_model(task)

    def get_task(self, task_id: str) -> Optional[AutoProvisionTaskItem]:
        with self.session_factory() as db:
            m = db.query(AutoProvisionTaskModel).filter(AutoProvisionTaskModel.id == task_id).first()
            if not m:
                return None
            # Auto-completa se já expirou
            now = datetime.now(timezone.utc)
            if m.status == "RUNNING" and m.expires_at <= now:
                m.status = "COMPLETED"
                db.commit()
            return self._to_task_model(m)

    def get_active_task_for_port(self, olt_id: str, port: str) -> Optional[AutoProvisionTaskItem]:
        now = datetime.now(timezone.utc)
        clean_port = port.strip()
        with self.session_factory() as db:
            tasks = (
                db.query(AutoProvisionTaskModel)
                .filter(
                    AutoProvisionTaskModel.olt_id == olt_id,
                    AutoProvisionTaskModel.status == "RUNNING",
                )
                .all()
            )
            for t in tasks:
                if t.expires_at <= now:
                    t.status = "COMPLETED"
                    db.commit()
                    continue
                if t.pon_port == "ALL" or t.pon_port == clean_port:
                    return self._to_task_model(t)
            return None

    def list_tasks(self, olt_id: str, limit: int = 50) -> List[AutoProvisionTaskItem]:
        now = datetime.now(timezone.utc)
        with self.session_factory() as db:
            tasks = (
                db.query(AutoProvisionTaskModel)
                .filter(AutoProvisionTaskModel.olt_id == olt_id)
                .order_by(AutoProvisionTaskModel.created_at.desc())
                .limit(limit)
                .all()
            )
            updated = False
            for t in tasks:
                if t.status == "RUNNING" and t.expires_at <= now:
                    t.status = "COMPLETED"
                    updated = True
            if updated:
                db.commit()
            return [self._to_task_model(t) for t in tasks]

    def increment_task_counter(self, task_id: str) -> int:
        with self.session_factory() as db:
            t = db.query(AutoProvisionTaskModel).filter(AutoProvisionTaskModel.id == task_id).first()
            if t:
                t.provisioned_count += 1
                db.commit()
                return t.provisioned_count
            return 0

    def cancel_task(self, task_id: str) -> Optional[AutoProvisionTaskItem]:
        with self.session_factory() as db:
            t = db.query(AutoProvisionTaskModel).filter(AutoProvisionTaskModel.id == task_id).first()
            if not t:
                return None
            t.status = "CANCELLED"
            db.commit()
            db.refresh(t)
            return self._to_task_model(t)
