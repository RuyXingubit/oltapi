import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    BackupMetadataModel,
    Base,
    OLTModel,
    ONUInventoryModel,
    ONUMigrationHistoryModel,
    WebhookDeliveryModel,
    WebhookSubscriptionModel,
)
from app.db.session import SessionLocal, engine

logger = logging.getLogger(__name__)


def run_migrations():
    """Executa migrações do Alembic até a última versão (head) de forma automática."""
    ini_path = settings.BASE_DIR / "alembic.ini"
    try:
        if ini_path.exists():
            alembic_cfg = Config(str(ini_path))
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
            command.upgrade(alembic_cfg, "head")
            logger.info("Migrações do banco de dados (Alembic) aplicadas com sucesso.")
        else:
            Base.metadata.create_all(bind=engine)
            logger.info("Tabelas do banco de dados criadas via SQLAlchemy metadata.")
    except Exception as e:
        logger.warning(f"Aviso ao executar Alembic upgrade (tentando fallback para Base.metadata): {e}")
        Base.metadata.create_all(bind=engine)


def migrate_legacy_json_data(db: Optional[Session] = None):
    """
    Migra dados legados de arquivos JSON existentes em data/ para o banco relacional.
    A migração é estritamente idempotente (não duplica registros se já existirem).
    """
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        data_dir = settings.DATA_DIR

        # 1. Migração de OLTs
        olts_file = data_dir / "olts.json"
        if olts_file.exists():
            try:
                with open(olts_file, "r", encoding="utf-8") as f:
                    olts_data = json.load(f)
                    for item in olts_data:
                        if not db.query(OLTModel).filter(OLTModel.id == item["id"]).first():
                            created_at = datetime.fromisoformat(item["created_at"]) if "created_at" in item else datetime.now(timezone.utc)
                            olt_m = OLTModel(
                                id=item["id"],
                                name=item["name"],
                                vendor=item["vendor"],
                                model=item["model"],
                                host=item["host"],
                                port=item.get("port", 22),
                                protocol=item.get("protocol", "ssh"),
                                username=item["username"],
                                password=item["password"],
                                created_at=created_at,
                            )
                            db.add(olt_m)
                    db.commit()
            except Exception as e:
                logger.warning(f"Erro na migração de olts.json legado: {e}")
                db.rollback()

        # 2. Migração de Inventário de ONUs
        onus_file = data_dir / "onus_inventory.json"
        if onus_file.exists():
            try:
                with open(onus_file, "r", encoding="utf-8") as f:
                    onus_data = json.load(f)
                    for item in onus_data:
                        if not db.query(ONUInventoryModel).filter(ONUInventoryModel.id == item["id"]).first():
                            created_at = datetime.fromisoformat(item["created_at"]) if "created_at" in item else datetime.now(timezone.utc)
                            updated_at = datetime.fromisoformat(item["updated_at"]) if "updated_at" in item else datetime.now(timezone.utc)
                            onu_m = ONUInventoryModel(
                                id=item["id"],
                                serial=item["serial"],
                                contract_id=item.get("contract_id"),
                                subscriber_name=item.get("subscriber_name"),
                                contract_status=item.get("contract_status", "ACTIVE"),
                                current_olt_id=item.get("current_olt_id"),
                                current_port=item.get("current_port"),
                                current_onu_id=item.get("current_onu_id"),
                                circuit_id=item.get("circuit_id"),
                                vlan=item.get("vlan"),
                                profile=item.get("profile"),
                                latitude=item.get("latitude"),
                                longitude=item.get("longitude"),
                                description=item.get("description") or item.get("notes"),
                                created_at=created_at,
                                updated_at=updated_at,
                            )
                            db.add(onu_m)
                    db.commit()
            except Exception as e:
                logger.warning(f"Erro na migração de onus_inventory.json legado: {e}")
                db.rollback()

        # 3. Migração do Histórico do NOC
        history_file = data_dir / "onus_history.json"
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
                    for item in history_data:
                        if not db.query(ONUMigrationHistoryModel).filter(ONUMigrationHistoryModel.id == item["id"]).first():
                            ts = datetime.fromisoformat(item["timestamp"]) if "timestamp" in item else datetime.now(timezone.utc)
                            hist_m = ONUMigrationHistoryModel(
                                id=item["id"],
                                serial=item["serial"],
                                contract_id=item.get("contract_id"),
                                subscriber_name=item.get("subscriber_name"),
                                reason=item.get("reason", "manual"),
                                from_olt_id=item.get("from_olt_id"),
                                from_olt_name=item.get("from_olt_name"),
                                from_port=item.get("from_port"),
                                from_onu_id=item.get("from_onu_id"),
                                from_circuit_id=item.get("from_circuit_id"),
                                to_olt_id=item.get("to_olt_id"),
                                to_olt_name=item.get("to_olt_name"),
                                to_port=item.get("to_port"),
                                to_onu_id=item.get("to_onu_id"),
                                to_circuit_id=item.get("to_circuit_id"),
                                status=item.get("status", "success"),
                                details=item.get("details"),
                                timestamp=ts,
                            )
                            db.add(hist_m)
                    db.commit()
            except Exception as e:
                logger.warning(f"Erro na migração de onus_history.json legado: {e}")
                db.rollback()

        # 4. Migração de Webhooks
        webhooks_file = data_dir / "webhooks.json"
        if webhooks_file.exists():
            try:
                with open(webhooks_file, "r", encoding="utf-8") as f:
                    wh_data = json.load(f)
                    for item in wh_data:
                        if not db.query(WebhookSubscriptionModel).filter(WebhookSubscriptionModel.id == item["id"]).first():
                            events_str = json.dumps(item.get("events", [])) if isinstance(item.get("events"), list) else str(item.get("events"))
                            created_at = datetime.fromisoformat(item["created_at"]) if "created_at" in item else datetime.now(timezone.utc)
                            wh_m = WebhookSubscriptionModel(
                                id=item["id"],
                                url=item["url"],
                                secret=item["secret"],
                                events=events_str,
                                is_active=item.get("is_active", True),
                                description=item.get("description"),
                                created_at=created_at,
                            )
                            db.add(wh_m)
                    db.commit()
            except Exception as e:
                logger.warning(f"Erro na migração de webhooks.json legado: {e}")
                db.rollback()

    finally:
        if close_session:
            db.close()


def seed_default_tenant_and_admin(db: Optional[Session] = None):
    """Gera o Tenant padrão (Provedor Matriz) e usuário Super Admin se não existirem."""
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        from app.core.security import get_password_hash
        from app.core.uuid import generate_uuid7
        from app.db.models import TenantModel, UserModel, ONUInventoryModel

        # 1. Tenant Matriz
        matriz = db.query(TenantModel).filter(TenantModel.type == "PROVIDER_OWNER").first()
        if not matriz:
            matriz = TenantModel(
                id=generate_uuid7(),
                name="Provedor Matriz",
                type="PROVIDER_OWNER",
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            db.add(matriz)
            db.commit()
            db.refresh(matriz)
            logger.info(f"Tenant padrão criado: {matriz.name} ({matriz.id})")

        # 2. Usuário Administrador Padrão
        admin_user = db.query(UserModel).filter(UserModel.email == "admin@oltapi.local").first()
        if not admin_user:
            admin_user = UserModel(
                id=generate_uuid7(),
                tenant_id=matriz.id,
                name="Administrador do Sistema",
                email="admin@oltapi.local",
                password_hash=get_password_hash("admin123456"),
                role="SUPER_ADMIN",
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(admin_user)
            db.commit()
            logger.info("Usuário Admin padrão criado: admin@oltapi.local")

        # 3. Vincula ONUs sem tenant ao Provedor Matriz
        unassigned_onus = db.query(ONUInventoryModel).filter(ONUInventoryModel.tenant_id.is_(None)).all()
        if unassigned_onus:
            for onu in unassigned_onus:
                onu.tenant_id = matriz.id
            db.commit()
            logger.info(f"{len(unassigned_onus)} ONUs vinculadas ao Tenant Matriz.")

    except Exception as e:
        logger.warning(f"Erro ao criar seed inicial de RBAC/Tenant: {e}")
        db.rollback()
    finally:
        if close_session:
            db.close()


def init_db():
    """Inicialização completa: aplica migrações e migra dados legados."""
    run_migrations()
    migrate_legacy_json_data()
    seed_default_tenant_and_admin()
