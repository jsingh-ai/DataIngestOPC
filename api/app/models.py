from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Double, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

SQLITE_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow
    )


class Machine(TimestampMixin, Base):
    __tablename__ = "machine"

    machine_id: Mapped[int] = mapped_column(SQLITE_BIGINT_PK, primary_key=True, autoincrement=True)
    machine_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=4840, nullable=False)
    opc_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    security_policy: Mapped[str | None] = mapped_column(String(64))
    security_mode: Mapped[str | None] = mapped_column(String(64))
    opc_username: Mapped[str | None] = mapped_column(String(128))
    opc_password_encrypted: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    notes: Mapped[str | None] = mapped_column(String(512))

    tags: Mapped[list[TagDefinition]] = relationship(back_populates="machine")


class ScanProfile(Base):
    __tablename__ = "scan_profile"

    scan_profile_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    interval_seconds: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TagDefinition(TimestampMixin, Base):
    __tablename__ = "tag_definition"
    __table_args__ = (
        UniqueConstraint("machine_id", "tag_key", name="uq_tag_machine_key"),
        UniqueConstraint("machine_id", "opc_node_id", name="uq_tag_machine_node"),
        Index("ix_tag_machine_enabled", "machine_id", "enabled"),
        Index("ix_tag_machine_archived", "machine_id", "archived"),
        Index("ix_tag_folder_path", "folder_path"),
        Index("ix_tag_scan_profile_id", "scan_profile_id"),
    )

    tag_id: Mapped[int] = mapped_column(SQLITE_BIGINT_PK, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.machine_id"), nullable=False)
    tag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    opc_node_id: Mapped[str] = mapped_column(String(512), nullable=False)
    browse_path: Mapped[str | None] = mapped_column(String(1024))
    folder_path: Mapped[str | None] = mapped_column(String(512))
    data_type: Mapped[str | None] = mapped_column(String(64))
    engineering_unit: Mapped[str | None] = mapped_column(String(64))
    scan_profile_id: Mapped[int | None] = mapped_column(ForeignKey("scan_profile.scan_profile_id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    machine: Mapped[Machine] = relationship(back_populates="tags")


class TagBrowserCache(Base):
    __tablename__ = "tag_browser_cache"
    __table_args__ = (
        UniqueConstraint("machine_id", "opc_node_id", name="uq_cache_machine_node"),
        Index("ix_cache_machine_variable", "machine_id", "is_variable"),
        Index("ix_cache_browse_path", "browse_path"),
    )

    cache_id: Mapped[int] = mapped_column(SQLITE_BIGINT_PK, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.machine_id"), nullable=False)
    opc_node_id: Mapped[str] = mapped_column(String(512), nullable=False)
    browse_path: Mapped[str | None] = mapped_column(String(1024))
    display_name: Mapped[str | None] = mapped_column(String(255))
    browse_name: Mapped[str | None] = mapped_column(String(255))
    node_class: Mapped[str | None] = mapped_column(String(64))
    data_type: Mapped[str | None] = mapped_column(String(64))
    is_variable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    already_added: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime())


class TagSampleMinute(Base):
    __tablename__ = "tag_sample_minute"
    __table_args__ = (
        Index("ix_sample_machine_ts", "machine_id", "sample_ts_utc"),
        Index("ix_sample_ts", "sample_ts_utc"),
    )

    sample_ts_utc: Mapped[datetime] = mapped_column(DateTime(), primary_key=True)
    machine_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tag_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    value_num: Mapped[float | None] = mapped_column(Double)
    value_str: Mapped[str | None] = mapped_column(String(255))
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    quality_code: Mapped[str | None] = mapped_column(String(64))
    source_ts_utc: Mapped[datetime | None] = mapped_column(DateTime())
    ingest_ts_utc: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class TagCurrentValue(Base):
    __tablename__ = "tag_current_value"
    __table_args__ = (Index("ix_current_sample_ts", "sample_ts_utc"),)

    machine_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tag_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sample_ts_utc: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    value_num: Mapped[float | None] = mapped_column(Double)
    value_str: Mapped[str | None] = mapped_column(String(255))
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    quality_code: Mapped[str | None] = mapped_column(String(64))
    source_ts_utc: Mapped[datetime | None] = mapped_column(DateTime())
    ingest_ts_utc: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class MachineCollectionStatus(Base):
    __tablename__ = "machine_collection_status"

    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.machine_id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    last_heartbeat_ts_utc: Mapped[datetime | None] = mapped_column(DateTime())
    last_successful_sample_ts_utc: Mapped[datetime | None] = mapped_column(DateTime())
    last_failed_sample_ts_utc: Mapped[datetime | None] = mapped_column(DateTime())
    expected_tag_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_tag_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_tag_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    opc_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mysql_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    collection_duration_ms: Mapped[int | None] = mapped_column(Integer)
    local_buffer_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_message: Mapped[str | None] = mapped_column(String(1024))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow
    )


class TagCollectionStatus(Base):
    __tablename__ = "tag_collection_status"
    __table_args__ = (Index("ix_tag_status_machine_status", "machine_id", "status"),)

    tag_id: Mapped[int] = mapped_column(ForeignKey("tag_definition.tag_id"), primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.machine_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    last_sample_ts_utc: Mapped[datetime | None] = mapped_column(DateTime())
    last_good_ts_utc: Mapped[datetime | None] = mapped_column(DateTime())
    last_bad_ts_utc: Mapped[datetime | None] = mapped_column(DateTime())
    last_quality_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(String(1024))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow
    )


class CollectorCommand(Base):
    __tablename__ = "collector_command"
    __table_args__ = (Index("ix_command_status_requested", "status", "requested_at"),)

    command_id: Mapped[int] = mapped_column(SQLITE_BIGINT_PK, primary_key=True, autoincrement=True)
    command_type: Mapped[str] = mapped_column(String(64), nullable=False)
    command_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(128))
    requested_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime())
    result_message: Mapped[str | None] = mapped_column(String(1024))


class CollectorConfigState(Base):
    __tablename__ = "collector_config_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    active_config_version: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    pending_reload: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow
    )


class ConfigAuditLog(Base):
    __tablename__ = "config_audit_log"

    audit_id: Mapped[int] = mapped_column(SQLITE_BIGINT_PK, primary_key=True, autoincrement=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    changed_by: Mapped[str | None] = mapped_column(String(128))
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    new_value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(String(512))
