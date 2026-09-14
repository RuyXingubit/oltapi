"""add_snmp_and_partitioned_telemetry

Revision ID: c72e91d5f0b1
Revises: b51f89c10f3a
Create Date: 2026-09-13 17:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c72e91d5f0b1'
down_revision: Union[str, Sequence[str], None] = 'b51f89c10f3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Campos de telemetria SNMP no modelo de OLT
    op.add_column('olts', sa.Column('snmp_community', sa.String(length=64), nullable=True, server_default='public'))
    op.add_column('olts', sa.Column('snmp_port', sa.Integer(), nullable=True, server_default='161'))
    op.add_column('olts', sa.Column('snmp_version', sa.String(length=16), nullable=True, server_default='v2c'))

    # 2. Tabela de histórico de telemetria com particionamento por mês
    if is_postgres:
        op.execute("""
            CREATE TABLE chassis_telemetry_history (
                id VARCHAR(36) NOT NULL,
                olt_id VARCHAR(36) NOT NULL REFERENCES olts(id) ON DELETE CASCADE,
                online_onus INTEGER NOT NULL DEFAULT 0,
                offline_onus INTEGER NOT NULL DEFAULT 0,
                active_ports INTEGER NOT NULL DEFAULT 0,
                uptime_seconds BIGINT,
                recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
                PRIMARY KEY (id, recorded_at)
            ) PARTITION BY RANGE (recorded_at);
        """)
        op.execute("""
            CREATE TABLE IF NOT EXISTS chassis_telemetry_history_2026_07 PARTITION OF chassis_telemetry_history
                FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');
            CREATE TABLE IF NOT EXISTS chassis_telemetry_history_2026_08 PARTITION OF chassis_telemetry_history
                FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');
            CREATE TABLE IF NOT EXISTS chassis_telemetry_history_2026_09 PARTITION OF chassis_telemetry_history
                FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');
            CREATE TABLE IF NOT EXISTS chassis_telemetry_history_2026_10 PARTITION OF chassis_telemetry_history
                FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');
            CREATE TABLE IF NOT EXISTS chassis_telemetry_history_2026_11 PARTITION OF chassis_telemetry_history
                FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');
        """)
        op.create_index('ix_chassis_telemetry_olt_id', 'chassis_telemetry_history', ['olt_id'])
    else:
        op.create_table(
            'chassis_telemetry_history',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('olt_id', sa.String(length=36), sa.ForeignKey('olts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('online_onus', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('offline_onus', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('active_ports', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('uptime_seconds', sa.BigInteger(), nullable=True),
            sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id', 'recorded_at')
        )
        op.create_index('ix_chassis_telemetry_olt_id', 'chassis_telemetry_history', ['olt_id'])


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP TABLE IF EXISTS chassis_telemetry_history CASCADE;")
    else:
        op.drop_table('chassis_telemetry_history')

    op.drop_column('olts', 'snmp_version')
    op.drop_column('olts', 'snmp_port')
    op.drop_column('olts', 'snmp_community')
