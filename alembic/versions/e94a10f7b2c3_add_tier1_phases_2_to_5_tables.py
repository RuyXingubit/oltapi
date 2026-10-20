"""add_tier1_phases_2_to_5_tables

Revision ID: e94a10f7b2c3
Revises: d83f92e6a1b2
Create Date: 2026-10-19 16:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e94a10f7b2c3'
down_revision: Union[str, Sequence[str], None] = 'd83f92e6a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Fase 2: Série Temporal de Potência Óptica (dBm)
    op.create_table(
        'onu_optical_telemetry_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('serial', sa.String(length=32), nullable=False),
        sa.Column('olt_id', sa.String(length=36), nullable=False),
        sa.Column('port', sa.String(length=32), nullable=True),
        sa.Column('onu_id', sa.Integer(), nullable=True),
        sa.Column('rx_power_dbm', sa.Float(), nullable=True),
        sa.Column('tx_power_dbm', sa.Float(), nullable=True),
        sa.Column('olt_rx_power_dbm', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='online'),
        sa.Column('last_down_cause', sa.String(length=32), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['olt_id'], ['olts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_onu_optical_telemetry_history_serial'), 'onu_optical_telemetry_history', ['serial'], unique=False)
    op.create_index(op.f('ix_onu_optical_telemetry_history_olt_id'), 'onu_optical_telemetry_history', ['olt_id'], unique=False)
    op.create_index(op.f('ix_onu_optical_telemetry_history_recorded_at'), 'onu_optical_telemetry_history', ['recorded_at'], unique=False)

    # 2. Fase 3: Presets Universais de Provisionamento
    op.create_table(
        'provisioning_presets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=256), nullable=True),
        sa.Column('vlan', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(length=32), nullable=False, server_default='transparent'),
        sa.Column('line_profile', sa.String(length=64), nullable=True, server_default='DEFAULT'),
        sa.Column('srv_profile', sa.String(length=64), nullable=True, server_default='DEFAULT'),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_provisioning_presets_name'), 'provisioning_presets', ['name'], unique=True)
    op.create_index(op.f('ix_provisioning_presets_tenant_id'), 'provisioning_presets', ['tenant_id'], unique=False)

    # 3. Fase 4: Topologia Passiva FTTH (Zonas e CTOs / ODBs)
    op.create_table(
        'network_zones',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('sector', sa.String(length=64), nullable=True),
        sa.Column('city', sa.String(length=64), nullable=True),
        sa.Column('description', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_network_zones_name'), 'network_zones', ['name'], unique=True)

    op.create_table(
        'optical_distribution_boxes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('zone_id', sa.String(length=36), nullable=True),
        sa.Column('olt_id', sa.String(length=36), nullable=True),
        sa.Column('pon_port', sa.String(length=32), nullable=True),
        sa.Column('splitter_capacity', sa.Integer(), nullable=False, server_default='16'),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('address', sa.String(length=256), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['zone_id'], ['network_zones.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['olt_id'], ['olts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_optical_distribution_boxes_code'), 'optical_distribution_boxes', ['code'], unique=True)
    op.create_index(op.f('ix_optical_distribution_boxes_zone_id'), 'optical_distribution_boxes', ['zone_id'], unique=False)
    op.create_index(op.f('ix_optical_distribution_boxes_olt_id'), 'optical_distribution_boxes', ['olt_id'], unique=False)

    # 4. Fase 5: Servidores ACS TR-069 / CWMP
    op.create_table(
        'acs_server_configs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('nbi_url', sa.String(length=256), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=True),
        sa.Column('password_encrypted', sa.String(length=256), nullable=True),
        sa.Column('cwmp_inform_url', sa.String(length=256), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_acs_server_configs_name'), 'acs_server_configs', ['name'], unique=True)

    # 5. Novas colunas em onus_inventory (Telemetria + Topologia Passiva)
    op.add_column('onus_inventory', sa.Column('last_rx_power_dbm', sa.Float(), nullable=True))
    op.add_column('onus_inventory', sa.Column('last_tx_power_dbm', sa.Float(), nullable=True))
    op.add_column('onus_inventory', sa.Column('last_olt_rx_power_dbm', sa.Float(), nullable=True))
    op.add_column('onus_inventory', sa.Column('last_down_cause', sa.String(length=32), nullable=True))
    op.add_column('onus_inventory', sa.Column('last_down_time', sa.String(length=64), nullable=True))
    op.add_column('onus_inventory', sa.Column('last_telemetry_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('onus_inventory', sa.Column('zone_id', sa.String(length=36), nullable=True))
    op.add_column('onus_inventory', sa.Column('odb_id', sa.String(length=36), nullable=True))
    op.add_column('onus_inventory', sa.Column('odb_splitter_port', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_onus_inventory_last_down_cause'), 'onus_inventory', ['last_down_cause'], unique=False)
    op.create_index(op.f('ix_onus_inventory_zone_id'), 'onus_inventory', ['zone_id'], unique=False)
    op.create_index(op.f('ix_onus_inventory_odb_id'), 'onus_inventory', ['odb_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_onus_inventory_odb_id'), table_name='onus_inventory')
    op.drop_index(op.f('ix_onus_inventory_zone_id'), table_name='onus_inventory')
    op.drop_index(op.f('ix_onus_inventory_last_down_cause'), table_name='onus_inventory')
    op.drop_column('onus_inventory', 'odb_splitter_port')
    op.drop_column('onus_inventory', 'odb_id')
    op.drop_column('onus_inventory', 'zone_id')
    op.drop_column('onus_inventory', 'last_telemetry_at')
    op.drop_column('onus_inventory', 'last_down_time')
    op.drop_column('onus_inventory', 'last_down_cause')
    op.drop_column('onus_inventory', 'last_olt_rx_power_dbm')
    op.drop_column('onus_inventory', 'last_tx_power_dbm')
    op.drop_column('onus_inventory', 'last_rx_power_dbm')

    op.drop_index(op.f('ix_acs_server_configs_name'), table_name='acs_server_configs')
    op.drop_table('acs_server_configs')

    op.drop_index(op.f('ix_optical_distribution_boxes_olt_id'), table_name='optical_distribution_boxes')
    op.drop_index(op.f('ix_optical_distribution_boxes_zone_id'), table_name='optical_distribution_boxes')
    op.drop_index(op.f('ix_optical_distribution_boxes_code'), table_name='optical_distribution_boxes')
    op.drop_table('optical_distribution_boxes')

    op.drop_index(op.f('ix_network_zones_name'), table_name='network_zones')
    op.drop_table('network_zones')

    op.drop_index(op.f('ix_provisioning_presets_tenant_id'), table_name='provisioning_presets')
    op.drop_index(op.f('ix_provisioning_presets_name'), table_name='provisioning_presets')
    op.drop_table('provisioning_presets')

    op.drop_index(op.f('ix_onu_optical_telemetry_history_recorded_at'), table_name='onu_optical_telemetry_history')
    op.drop_index(op.f('ix_onu_optical_telemetry_history_olt_id'), table_name='onu_optical_telemetry_history')
    op.drop_index(op.f('ix_onu_optical_telemetry_history_serial'), table_name='onu_optical_telemetry_history')
    op.drop_table('onu_optical_telemetry_history')
