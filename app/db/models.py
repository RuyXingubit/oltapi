from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class OLTModel(Base):
    __tablename__ = "olts"

    id = Column(String(36), primary_key=True)
    name = Column(String(64), unique=True, index=True, nullable=False)
    vendor = Column(String(32), nullable=False)
    model = Column(String(32), nullable=False)
    host = Column(String(128), nullable=False)
    port = Column(Integer, nullable=False, default=22)
    protocol = Column(String(16), nullable=False, default="ssh")
    username = Column(String(64), nullable=False)
    password = Column(String(256), nullable=False)
    snmp_community = Column(String(64), nullable=True, default="public")
    snmp_port = Column(Integer, nullable=True, default=161)
    snmp_version = Column(String(16), nullable=True, default="v2c")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ChassisTelemetryHistoryModel(Base):
    __tablename__ = "chassis_telemetry_history"
    __table_args__ = (
        {"postgresql_partition_by": "RANGE (recorded_at)"},
    )

    id = Column(String(36), primary_key=True)
    olt_id = Column(
        String(36), ForeignKey("olts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    online_onus = Column(Integer, nullable=False, default=0)
    offline_onus = Column(Integer, nullable=False, default=0)
    active_ports = Column(Integer, nullable=False, default=0)
    uptime_seconds = Column(Integer, nullable=True)
    recorded_at = Column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ONUInventoryModel(Base):
    __tablename__ = "onus_inventory"

    id = Column(String(36), primary_key=True)
    serial = Column(String(32), unique=True, index=True, nullable=False)
    contract_id = Column(String(64), index=True, nullable=True)
    subscriber_name = Column(String(128), nullable=True)
    contract_status = Column(String(32), index=True, nullable=False, default="ACTIVE")
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    current_olt_id = Column(
        String(36), ForeignKey("olts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    current_port = Column(String(32), nullable=True)
    current_onu_id = Column(Integer, nullable=True)
    circuit_id = Column(String(128), index=True, nullable=True)
    vlan = Column(Integer, nullable=True)
    profile = Column(String(64), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    last_rx_power_dbm = Column(Float, nullable=True)
    last_tx_power_dbm = Column(Float, nullable=True)
    last_olt_rx_power_dbm = Column(Float, nullable=True)
    last_down_cause = Column(String(32), nullable=True, index=True)
    last_down_time = Column(String(64), nullable=True)
    last_telemetry_at = Column(DateTime(timezone=True), nullable=True)
    zone_id = Column(
        String(36), ForeignKey("network_zones.id", ondelete="SET NULL"), nullable=True, index=True
    )
    odb_id = Column(
        String(36), ForeignKey("optical_distribution_boxes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    odb_splitter_port = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ONUMigrationHistoryModel(Base):
    __tablename__ = "onus_history"

    id = Column(String(36), primary_key=True)
    serial = Column(String(32), index=True, nullable=False)
    contract_id = Column(String(64), nullable=True)
    subscriber_name = Column(String(128), nullable=True)
    reason = Column(String(128), nullable=False)
    from_olt_id = Column(String(36), nullable=True)
    from_olt_name = Column(String(64), nullable=True)
    from_port = Column(String(32), nullable=True)
    from_onu_id = Column(Integer, nullable=True)
    from_circuit_id = Column(String(128), nullable=True)
    to_olt_id = Column(String(36), nullable=True)
    to_olt_name = Column(String(64), nullable=True)
    to_port = Column(String(32), nullable=True)
    to_onu_id = Column(Integer, nullable=True)
    to_circuit_id = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="success")
    details = Column(Text, nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ONUVLANHistoryModel(Base):
    """Histórico de vinculação e rastreabilidade de seriais de ONUs por VLAN."""
    __tablename__ = "onu_vlan_history"

    id = Column(String(36), primary_key=True)
    serial = Column(String(32), index=True, nullable=False)
    vlan_id = Column(Integer, index=True, nullable=False)
    olt_id = Column(String(36), ForeignKey("olts.id", ondelete="CASCADE"), index=True, nullable=False)
    port = Column(String(32), nullable=True)
    contract_id = Column(String(64), nullable=True)
    subscriber_name = Column(String(128), nullable=True)
    reason = Column(String(64), nullable=False, default="PROVISIONING")
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    ended_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )


class WebhookSubscriptionModel(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(String(36), primary_key=True)
    url = Column(String(256), nullable=False)
    secret = Column(String(128), nullable=False)
    events = Column(Text, nullable=False)  # Armazenado como JSON string ou lista delimitada
    is_active = Column(Boolean, nullable=False, default=True)
    description = Column(String(256), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    deliveries = relationship(
        "WebhookDeliveryModel",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )


class WebhookDeliveryModel(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(String(36), primary_key=True)
    subscription_id = Column(
        String(36),
        ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event = Column(String(64), nullable=False)
    url = Column(String(256), nullable=False)
    status_code = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False)
    duration_ms = Column(Float, nullable=False)
    error_message = Column(Text, nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    subscription = relationship("WebhookSubscriptionModel", back_populates="deliveries")


class BackupMetadataModel(Base):
    __tablename__ = "backups_metadata"

    backup_id = Column(String(36), primary_key=True)
    olt_id = Column(
        String(36),
        ForeignKey("olts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    olt_name = Column(String(64), nullable=False)
    filename = Column(String(128), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    notes = Column(Text, nullable=True)


class FTPServerModel(Base):
    __tablename__ = "ftp_servers"

    id = Column(String(36), primary_key=True)
    name = Column(String(64), unique=True, index=True, nullable=False)
    host = Column(String(128), nullable=False)
    port = Column(Integer, nullable=False, default=21)
    username = Column(String(64), nullable=False)
    password = Column(String(256), nullable=False)
    base_path = Column(String(128), nullable=False, default="/")
    is_global_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    destinations = relationship(
        "OLTFTPDestinationModel",
        back_populates="ftp_server",
        cascade="all, delete-orphan",
    )


class OLTFTPDestinationModel(Base):
    __tablename__ = "olt_ftp_destinations"

    id = Column(String(36), primary_key=True)
    olt_id = Column(
        String(36),
        ForeignKey("olts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    ftp_server_id = Column(
        String(36),
        ForeignKey("ftp_servers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    ftp_server = relationship("FTPServerModel", back_populates="destinations")


class TenantModel(Base):
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True)
    name = Column(String(64), unique=True, index=True, nullable=False)
    type = Column(String(32), nullable=False)  # PROVIDER_OWNER, NEUTRAL_OPERATOR
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    users = relationship("UserModel", back_populates="tenant", cascade="all, delete-orphan")
    vlan_allocations = relationship(
        "TenantVLANAllocationModel", back_populates="tenant", cascade="all, delete-orphan"
    )
    api_keys = relationship("APIKeyModel", back_populates="tenant", cascade="all, delete-orphan")


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name = Column(String(128), nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False)  # SUPER_ADMIN, NOC, FIELD_TECH, TENANT_ADMIN, TENANT_TECH
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tenant = relationship("TenantModel", back_populates="users")
    olt_permissions = relationship(
        "UserOLTPermissionModel", back_populates="user", cascade="all, delete-orphan"
    )
    api_keys = relationship("APIKeyModel", back_populates="user", cascade="all, delete-orphan")


class UserOLTPermissionModel(Base):
    __tablename__ = "user_olt_permissions"
    __table_args__ = (UniqueConstraint("user_id", "olt_id", name="uq_user_olt"),)

    id = Column(String(36), primary_key=True)
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    olt_id = Column(
        String(36),
        ForeignKey("olts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("UserModel", back_populates="olt_permissions")
    olt = relationship("OLTModel")


class TenantVLANAllocationModel(Base):
    __tablename__ = "tenant_vlan_allocations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "olt_id", "vlan_id", name="uq_tenant_olt_vlan"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    olt_id = Column(
        String(36),
        ForeignKey("olts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    vlan_id = Column(Integer, nullable=False)
    description = Column(String(128), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    tenant = relationship("TenantModel", back_populates="vlan_allocations")
    olt = relationship("OLTModel")


class APIKeyModel(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name = Column(String(64), nullable=False)
    key_prefix = Column(String(16), nullable=False, index=True)
    key_hash = Column(String(128), unique=True, nullable=False, index=True)
    scopes = Column(Text, nullable=False)  # JSON array de escopos autorizados
    is_active = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    tenant = relationship("TenantModel", back_populates="api_keys")
    user = relationship("UserModel", back_populates="api_keys")


class OLTPonPolicyModel(Base):
    __tablename__ = "olt_pon_policies"
    __table_args__ = (
        UniqueConstraint("olt_id", "port", name="uq_olt_pon_policy_port"),
    )

    id = Column(String(36), primary_key=True)
    olt_id = Column(
        String(36),
        ForeignKey("olts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    port = Column(String(32), nullable=False, index=True)
    default_vlan = Column(Integer, nullable=False)
    default_mode = Column(String(32), nullable=False, default="transparent")
    default_line_profile = Column(String(64), nullable=True)
    default_srv_profile = Column(String(64), nullable=True)
    vendor_parameters = Column(Text, nullable=True)
    auto_authorize_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    olt = relationship("OLTModel")


class AutoProvisionTaskModel(Base):
    __tablename__ = "auto_provision_tasks"

    id = Column(String(36), primary_key=True)
    olt_id = Column(
        String(36),
        ForeignKey("olts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    pon_port = Column(String(32), nullable=False, default="ALL")
    target_vlan = Column(Integer, nullable=False)
    default_mode = Column(String(32), nullable=False, default="transparent")
    default_line_profile = Column(String(64), nullable=True)
    default_srv_profile = Column(String(64), nullable=True)
    vendor_parameters = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="RUNNING", index=True)
    starts_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    provisioned_count = Column(Integer, nullable=False, default=0)
    created_by = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    olt = relationship("OLTModel")


class ONUOpticalTelemetryHistoryModel(Base):
    """Série temporal de potência óptica (Rx/Tx/OLT Rx) e estado operacional da ONU (Fase 2)."""
    __tablename__ = "onu_optical_telemetry_history"

    id = Column(String(36), primary_key=True)
    serial = Column(String(32), index=True, nullable=False)
    olt_id = Column(
        String(36),
        ForeignKey("olts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    port = Column(String(32), nullable=True)
    onu_id = Column(Integer, nullable=True)
    rx_power_dbm = Column(Float, nullable=True)
    tx_power_dbm = Column(Float, nullable=True)
    olt_rx_power_dbm = Column(Float, nullable=True)
    status = Column(String(32), nullable=False, default="online")
    last_down_cause = Column(String(32), nullable=True)
    recorded_at = Column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ProvisioningPresetModel(Base):
    """Templates universais de provisionamento reutilizáveis (Fase 3)."""
    __tablename__ = "provisioning_presets"

    id = Column(String(36), primary_key=True)
    name = Column(String(64), unique=True, index=True, nullable=False)
    description = Column(String(256), nullable=True)
    vlan = Column(Integer, nullable=False)
    mode = Column(String(32), nullable=False, default="transparent")
    line_profile = Column(String(64), nullable=True, default="DEFAULT")
    srv_profile = Column(String(64), nullable=True, default="DEFAULT")
    tenant_id = Column(
        String(36), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class NetworkZoneModel(Base):
    """Zonas de atendimento FTTH (Bairro / Setor / Cidade) para topologia passiva (Fase 4)."""
    __tablename__ = "network_zones"

    id = Column(String(36), primary_key=True)
    name = Column(String(64), unique=True, index=True, nullable=False)
    sector = Column(String(64), nullable=True)
    city = Column(String(64), nullable=True)
    description = Column(String(256), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class OpticalDistributionBoxModel(Base):
    """Caixas de Terminação Óptica (CTO / ODB) e Splitters de campo (Fase 4)."""
    __tablename__ = "optical_distribution_boxes"

    id = Column(String(36), primary_key=True)
    code = Column(String(32), unique=True, index=True, nullable=False)
    name = Column(String(64), nullable=False)
    zone_id = Column(
        String(36), ForeignKey("network_zones.id", ondelete="SET NULL"), nullable=True, index=True
    )
    olt_id = Column(
        String(36), ForeignKey("olts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    pon_port = Column(String(32), nullable=True)
    splitter_capacity = Column(Integer, nullable=False, default=16)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String(256), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ACSServerConfigModel(Base):
    """Configuração de servidores ACS TR-069 / CWMP (ex: GenieACS NBI) para gerência L3/L7 (Fase 5)."""
    __tablename__ = "acs_server_configs"

    id = Column(String(36), primary_key=True)
    name = Column(String(64), unique=True, index=True, nullable=False)
    nbi_url = Column(String(256), nullable=False)
    username = Column(String(64), nullable=True)
    password_encrypted = Column(String(256), nullable=True)
    cwmp_inform_url = Column(String(256), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

