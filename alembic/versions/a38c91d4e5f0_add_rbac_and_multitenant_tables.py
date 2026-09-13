"""add_rbac_and_multitenant_tables

Revision ID: a38c91d4e5f0
Revises: f26d8bd34ea0
Create Date: 2026-09-12 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a38c91d4e5f0'
down_revision: Union[str, Sequence[str], None] = 'f26d8bd34ea0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabela de Tenants (Inquilinos / Organizações)
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('type', sa.String(length=32), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tenants_name'), 'tenants', ['name'], unique=True)

    # 2. Tabela de Usuários (Web UI & RBAC)
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('email', sa.String(length=128), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'], unique=False)

    # 3. Permissões de Usuário por OLT (Restrição geográfica/POP)
    op.create_table(
        'user_olt_permissions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('olt_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['olt_id'], ['olts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'olt_id', name='uq_user_olt')
    )
    op.create_index(op.f('ix_user_olt_permissions_user_id'), 'user_olt_permissions', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_olt_permissions_olt_id'), 'user_olt_permissions', ['olt_id'], unique=False)

    # 4. Alocação de VLANs por Tenant e por OLT (Isolamento L2 Rede Neutra)
    op.create_table(
        'tenant_vlan_allocations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('olt_id', sa.String(length=36), nullable=False),
        sa.Column('vlan_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['olt_id'], ['olts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'olt_id', 'vlan_id', name='uq_tenant_olt_vlan')
    )
    op.create_index(op.f('ix_tenant_vlan_allocations_tenant_id'), 'tenant_vlan_allocations', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_tenant_vlan_allocations_olt_id'), 'tenant_vlan_allocations', ['olt_id'], unique=False)

    # 5. Chaves de API Dinâmicas com Hash SHA-256 e Escopos
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('key_prefix', sa.String(length=16), nullable=False),
        sa.Column('key_hash', sa.String(length=128), nullable=False),
        sa.Column('scopes', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_keys_key_prefix'), 'api_keys', ['key_prefix'], unique=False)
    op.create_index(op.f('ix_api_keys_key_hash'), 'api_keys', ['key_hash'], unique=True)
    op.create_index(op.f('ix_api_keys_tenant_id'), 'api_keys', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_api_keys_user_id'), 'api_keys', ['user_id'], unique=False)

    # 6. Adiciona tenant_id em onus_inventory usando batch mode para compatibilidade cross-dialect
    with op.batch_alter_table('onus_inventory') as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_onus_inventory_tenant_id', 'tenants', ['tenant_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index(op.f('ix_onus_inventory_tenant_id'), ['tenant_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('onus_inventory') as batch_op:
        batch_op.drop_index(op.f('ix_onus_inventory_tenant_id'))
        batch_op.drop_constraint('fk_onus_inventory_tenant_id', type_='foreignkey')
        batch_op.drop_column('tenant_id')

    op.drop_index(op.f('ix_api_keys_user_id'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_tenant_id'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_key_hash'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_key_prefix'), table_name='api_keys')
    op.drop_table('api_keys')

    op.drop_index(op.f('ix_tenant_vlan_allocations_olt_id'), table_name='tenant_vlan_allocations')
    op.drop_index(op.f('ix_tenant_vlan_allocations_tenant_id'), table_name='tenant_vlan_allocations')
    op.drop_table('tenant_vlan_allocations')

    op.drop_index(op.f('ix_user_olt_permissions_olt_id'), table_name='user_olt_permissions')
    op.drop_index(op.f('ix_user_olt_permissions_user_id'), table_name='user_olt_permissions')
    op.drop_table('user_olt_permissions')

    op.drop_index(op.f('ix_users_tenant_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    op.drop_index(op.f('ix_tenants_name'), table_name='tenants')
    op.drop_table('tenants')
