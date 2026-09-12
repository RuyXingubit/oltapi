"""add_ftp_servers_tables

Revision ID: f26d8bd34ea0
Revises: cf1f56210add
Create Date: 2026-09-12 19:38:07.866938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f26d8bd34ea0'
down_revision: Union[str, Sequence[str], None] = 'cf1f56210add'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ftp_servers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('host', sa.String(length=128), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, server_default='21'),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('password', sa.String(length=256), nullable=False),
        sa.Column('base_path', sa.String(length=128), nullable=False, server_default='/'),
        sa.Column('is_global_default', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ftp_servers_name'), 'ftp_servers', ['name'], unique=True)

    op.create_table(
        'olt_ftp_destinations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('olt_id', sa.String(length=36), nullable=False),
        sa.Column('ftp_server_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['ftp_server_id'], ['ftp_servers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['olt_id'], ['olts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_olt_ftp_destinations_olt_id'), 'olt_ftp_destinations', ['olt_id'], unique=False)
    op.create_index(op.f('ix_olt_ftp_destinations_ftp_server_id'), 'olt_ftp_destinations', ['ftp_server_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_olt_ftp_destinations_ftp_server_id'), table_name='olt_ftp_destinations')
    op.drop_index(op.f('ix_olt_ftp_destinations_olt_id'), table_name='olt_ftp_destinations')
    op.drop_table('olt_ftp_destinations')
    op.drop_index(op.f('ix_ftp_servers_name'), table_name='ftp_servers')
    op.drop_table('ftp_servers')

