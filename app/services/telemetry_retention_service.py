"""
Serviço de Retenção de Telemetria e Descarte Físico com Particionamento PostgreSQL.
Garante que partições com mais de 90 dias (3 meses) sejam desconectadas e
removidas via DROP TABLE, devolvendo fisicamente os blocos de disco ao SO.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.uuid import generate_uuid7
from app.db.models import ChassisTelemetryHistoryModel

logger = logging.getLogger(__name__)


class TelemetryRetentionService:
    """Gerencia a ingestão compacta de telemetria e o ciclo de vida das partições PostgreSQL."""

    @staticmethod
    def record_snapshot(
        db: Session,
        olt_id: str,
        online_onus: int,
        offline_onus: int,
        active_ports: int,
        uptime_seconds: Optional[int] = None,
        recorded_at: Optional[datetime] = None,
    ) -> ChassisTelemetryHistoryModel:
        """Grava um registro de telemetria na partição correspondente usando UUIDv7."""
        ts = recorded_at or datetime.now(timezone.utc)
        record = ChassisTelemetryHistoryModel(
            id=generate_uuid7(),
            olt_id=olt_id,
            online_onus=online_onus,
            offline_onus=offline_onus,
            active_ports=active_ports,
            uptime_seconds=uptime_seconds,
            recorded_at=ts,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def ensure_monthly_partitions(db: Session, months_ahead: int = 2) -> List[str]:
        """
        Cria preventivamente as partições dos meses correntes e futuros no PostgreSQL.
        """
        bind = db.get_bind()
        if bind.dialect.name != "postgresql":
            return []

        created = []
        now = datetime.now(timezone.utc)
        for i in range(-1, months_ahead + 1):
            # Calcula mês relativo
            year = now.year + ((now.month + i - 1) // 12)
            month = ((now.month + i - 1) % 12) + 1

            next_year = year + (1 if month == 12 else 0)
            next_month = 1 if month == 12 else month + 1

            part_name = f"chassis_telemetry_history_{year:04d}_{month:02d}"
            start_date = f"{year:04d}-{month:02d}-01 00:00:00+00"
            end_date = f"{next_year:04d}-{next_month:02d}-01 00:00:00+00"

            sql = f"""
                CREATE TABLE IF NOT EXISTS {part_name} PARTITION OF chassis_telemetry_history
                FOR VALUES FROM ('{start_date}') TO ('{end_date}');
            """
            try:
                db.execute(text(sql))
                db.commit()
                created.append(part_name)
            except Exception as e:
                db.rollback()
                logger.warning(f"Aviso ao verificar partição {part_name}: {e}")

        return created

    @staticmethod
    def purge_expired_partitions(db: Session, retention_days: int = 90) -> List[str]:
        """
        Identifica e descarta partições mais antigas que a janela de retenção (90 dias).
        Executa DETACH PARTITION e DROP TABLE, acionando o descarte físico no filesystem do SO.
        """
        bind = db.get_bind()
        is_postgres = bind.dialect.name == "postgresql"

        dropped_partitions = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        if is_postgres:
            # Lista todas as partições filhas de chassis_telemetry_history
            query = text("""
                SELECT c.relname
                FROM pg_inherits i
                JOIN pg_class c ON c.oid = i.inhrelid
                JOIN pg_class p ON p.oid = i.inhparent
                WHERE p.relname = 'chassis_telemetry_history';
            """)
            try:
                result = db.execute(query).fetchall()
                for row in result:
                    table_name = row[0]
                    # Espera padrão chassis_telemetry_history_YYYY_MM
                    match = re.search(r"chassis_telemetry_history_(\d{4})_(\d{2})", table_name)
                    if match:
                        pyear = int(match.group(1))
                        pmonth = int(match.group(2))
                        # Final do mês da partição
                        next_year = pyear + (1 if pmonth == 12 else 0)
                        next_month = 1 if pmonth == 12 else pmonth + 1
                        partition_end = datetime(next_year, next_month, 1, tzinfo=timezone.utc)

                        if partition_end < cutoff_date:
                            logger.info(f"Descartando partição expirada ({table_name}) para liberar disco no SO...")
                            db.execute(text(f"ALTER TABLE chassis_telemetry_history DETACH PARTITION {table_name};"))
                            db.execute(text(f"DROP TABLE {table_name};"))
                            db.commit()
                            dropped_partitions.append(table_name)
            except Exception as e:
                db.rollback()
                logger.error(f"Erro ao expurgar partições antigas no PostgreSQL: {e}")
        else:
            # Fallback SQLite para testes unitários
            try:
                del_sql = text("DELETE FROM chassis_telemetry_history WHERE recorded_at < :cutoff;")
                db.execute(del_sql, {"cutoff": cutoff_date})
                db.commit()
            except Exception as e:
                db.rollback()
                logger.debug(f"Aviso no fallback de retenção SQLite: {e}")

        return dropped_partitions
