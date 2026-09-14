import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import encrypt_password
from app.db.models import (
    BackupMetadataModel,
    Base,
    FTPServerModel,
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

def encrypt_existing_plain_passwords(db: Optional[Session] = None):
    """
    Varre as tabelas de OLTs e servidores FTP e cifra em repouso qualquer
    senha legada que ainda esteja armazenada em texto claro no PostgreSQL.
    """
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        # Cifra senhas de OLTs
        olts = db.query(OLTModel).all()
        migrated_olts = 0
        for olt in olts:
            if olt.password and not olt.password.startswith("gAAAAA"):
                olt.password = encrypt_password(olt.password)
                migrated_olts += 1

        # Cifra senhas de Servidores FTP
        ftps = db.query(FTPServerModel).all()
        migrated_ftps = 0
        for ftp in ftps:
            if ftp.password and not ftp.password.startswith("gAAAAA"):
                ftp.password = encrypt_password(ftp.password)
                migrated_ftps += 1

        if migrated_olts > 0 or migrated_ftps > 0:
            db.commit()
            logger.info(
                f"[Security Hardening] Criptografadas {migrated_olts} senhas de OLTs e {migrated_ftps} de FTPs em repouso."
            )
    except Exception as e:
        logger.warning(f"Erro ao verificar/cifrar senhas em repouso: {e}")
        db.rollback()
    finally:
        if close_session:
            db.close()


def init_db():
    """Inicialização completa: aplica migrações, migra dados legados e cifra senhas em repouso."""
    run_migrations()
    migrate_legacy_json_data()
    encrypt_existing_plain_passwords()
