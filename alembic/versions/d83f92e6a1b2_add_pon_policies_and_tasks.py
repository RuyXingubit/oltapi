"""add_pon_policies_and_tasks

Revision ID: d83f92e6a1b2
Revises: c72e91d5f0b1
Create Date: 2026-09-16 11:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd83f92e6a1b2'
down_revision: Union[str, Sequence[str], None] = 'c72e91d5f0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabela de Políticas por Porta PON
    op.create_table(
        'olt_pon_policies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('olt_id', sa.String(length=36), nullable=False),
        sa.Column('port', sa.String(length=32), nullable=False),
        sa.Column('default_vlan', sa.Integer(), nullable=False),
        sa.Column('default_mode', sa.String(length=32), nullable=False, server_default='transparent'),
        sa.Column('default_line_profile', sa.String(length=64), nullable=True),
        sa.Column('default_srv_profile', sa.String(length=64), nullable=True),
        sa.Column('vendor_parameters', sa.Text(), nullable=True),
        sa.Column('auto_authorize_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['olt_id'], ['olts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('olt_id', 'port', name='uq_olt_pon_policy_port'),
    )
    op.create_index(op.f('ix_olt_pon_policies_olt_id'), 'olt_pon_policies', ['olt_id'], unique=False)
    op.create_index(op.f('ix_olt_pon_policies_port'), 'olt_pon_policies', ['port'], unique=False)

    # 2. Tabela de Tasks de Auto-Provisionamento (Cutover)
    op.create_table(
        'auto_provision_tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('olt_id', sa.String(length=36), nullable=False),
        sa.Column('pon_port', sa.String(length=32), nullable=False, server_default='ALL'),
        sa.Column('target_vlan', sa.Integer(), nullable=False),
        sa.Column('default_mode', sa.String(length=32), nullable=False, server_default='transparent'),
        sa.Column('default_line_profile', sa.String(length=64), nullable=True),
        sa.Column('default_srv_profile', sa.String(length=64), nullable=True),
        sa.Column('vendor_parameters', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='RUNNING'),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('provisioned_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['olt_id'], ['olts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_auto_provision_tasks_olt_id'), 'auto_provision_tasks', ['olt_id'], unique=False)
    op.create_index(op.f('ix_auto_provision_tasks_status'), 'auto_provision_tasks', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_auto_provision_tasks_status'), table_name='auto_provision_tasks')
    op.drop_index(op.f('ix_auto_provision_tasks_olt_id'), table_name='auto_provision_tasks')
    op.drop_table('auto_provision_tasks')

    op.drop_index(op.f('ix_olt_pon_policies_port'), table_name='olt_pon_policies')
    op.drop_index(op.f('ix_olt_pon_policies_olt_id'), table_name='olt_pon_policies')
    op.drop_table('olt_pon_policies')
