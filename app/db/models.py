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
    created_at = Column(
        DateTime(timezone=True),
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

