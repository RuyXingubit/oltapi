"""add_onu_vlan_history

Revision ID: b51f89c10f3a
Revises: a38c91d4e5f0
Create Date: 2026-09-13 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b51f89c10f3a'
down_revision: Union[str, Sequence[str], None] = 'a38c91d4e5f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'onu_vlan_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('serial', sa.String(length=32), nullable=False),
        sa.Column('vlan_id', sa.Integer(), nullable=False),
        sa.Column('olt_id', sa.String(length=36), nullable=False),
        sa.Column('port', sa.String(length=32), nullable=True),
        sa.Column('contract_id', sa.String(length=64), nullable=True),
        sa.Column('subscriber_name', sa.String(length=128), nullable=True),
        sa.Column('reason', sa.String(length=64), nullable=False, server_default='PROVISIONING'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['olt_id'], ['olts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_onu_vlan_history_serial'), 'onu_vlan_history', ['serial'], unique=False)
    op.create_index(op.f('ix_onu_vlan_history_vlan_id'), 'onu_vlan_history', ['vlan_id'], unique=False)
    op.create_index(op.f('ix_onu_vlan_history_olt_id'), 'onu_vlan_history', ['olt_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_onu_vlan_history_olt_id'), table_name='onu_vlan_history')
    op.drop_index(op.f('ix_onu_vlan_history_vlan_id'), table_name='onu_vlan_history')
    op.drop_index(op.f('ix_onu_vlan_history_serial'), table_name='onu_vlan_history')
    op.drop_table('onu_vlan_history')
