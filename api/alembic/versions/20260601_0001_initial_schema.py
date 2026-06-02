"""initial schema"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260601_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "machine",
        sa.Column("machine_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("machine_code", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="4840"),
        sa.Column("opc_endpoint", sa.String(255), nullable=False),
        sa.Column("security_policy", sa.String(64), nullable=True),
        sa.Column("security_mode", sa.String(64), nullable=True),
        sa.Column("opc_username", sa.String(128), nullable=True),
        sa.Column("opc_password_encrypted", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("notes", sa.String(512), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("UTC_TIMESTAMP(6)")),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("UTC_TIMESTAMP(6)")),
        sa.UniqueConstraint("machine_code", name="uq_machine_code"),
    )
    op.create_table(
        "scan_profile",
        sa.Column("scan_profile_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("profile_name", sa.String(64), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("profile_name", name="uq_scan_profile_name"),
    )
    op.create_table(
        "tag_definition",
        sa.Column("tag_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machine.machine_id"), nullable=False),
        sa.Column("tag_key", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("opc_node_id", sa.String(512), nullable=False),
        sa.Column("browse_path", sa.String(1024), nullable=True),
        sa.Column("folder_path", sa.String(512), nullable=True),
        sa.Column("data_type", sa.String(64), nullable=True),
        sa.Column("engineering_unit", sa.String(64), nullable=True),
        sa.Column("scan_profile_id", sa.Integer(), sa.ForeignKey("scan_profile.scan_profile_id"), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("UTC_TIMESTAMP(6)")),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("UTC_TIMESTAMP(6)")),
        sa.UniqueConstraint("machine_id", "tag_key", name="uq_tag_machine_key"),
        sa.UniqueConstraint("machine_id", "opc_node_id", name="uq_tag_machine_node"),
    )
    op.create_index("ix_tag_machine_enabled", "tag_definition", ["machine_id", "enabled"])
    op.create_index("ix_tag_machine_archived", "tag_definition", ["machine_id", "archived"])
    op.create_index("ix_tag_folder_path", "tag_definition", ["folder_path"])
    op.create_index("ix_tag_scan_profile_id", "tag_definition", ["scan_profile_id"])
    op.create_table(
        "tag_browser_cache",
        sa.Column("cache_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machine.machine_id"), nullable=False),
        sa.Column("opc_node_id", sa.String(512), nullable=False),
        sa.Column("browse_path", sa.String(1024), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("browse_name", sa.String(255), nullable=True),
        sa.Column("node_class", sa.String(64), nullable=True),
        sa.Column("data_type", sa.String(64), nullable=True),
        sa.Column("is_variable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("already_added", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_seen_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.UniqueConstraint("machine_id", "opc_node_id", name="uq_cache_machine_node"),
    )
    op.create_index("ix_cache_machine_variable", "tag_browser_cache", ["machine_id", "is_variable"])
    op.create_index("ix_cache_browse_path", "tag_browser_cache", ["browse_path"], mysql_length=255)
    op.create_table(
        "tag_sample_minute",
        sa.Column("sample_ts_utc", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("machine_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column("value_num", sa.Float(), nullable=True),
        sa.Column("value_str", sa.String(255), nullable=True),
        sa.Column("value_bool", sa.Boolean(), nullable=True),
        sa.Column("quality_code", sa.String(64), nullable=True),
        sa.Column("source_ts_utc", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("ingest_ts_utc", mysql.DATETIME(fsp=6), nullable=False),
        sa.PrimaryKeyConstraint("tag_id", "sample_ts_utc"),
    )
    op.create_index("ix_sample_machine_ts", "tag_sample_minute", ["machine_id", "sample_ts_utc"])
    op.create_index("ix_sample_ts", "tag_sample_minute", ["sample_ts_utc"])
    op.create_table(
        "tag_current_value",
        sa.Column("machine_id", sa.BigInteger(), primary_key=True),
        sa.Column("tag_id", sa.BigInteger(), primary_key=True),
        sa.Column("sample_ts_utc", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("value_num", sa.Float(), nullable=True),
        sa.Column("value_str", sa.String(255), nullable=True),
        sa.Column("value_bool", sa.Boolean(), nullable=True),
        sa.Column("quality_code", sa.String(64), nullable=True),
        sa.Column("source_ts_utc", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("ingest_ts_utc", mysql.DATETIME(fsp=6), nullable=False),
    )
    op.create_index("ix_current_sample_ts", "tag_current_value", ["sample_ts_utc"])
    op.create_table(
        "machine_collection_status",
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machine.machine_id"), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("last_heartbeat_ts_utc", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("last_successful_sample_ts_utc", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("last_failed_sample_ts_utc", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("expected_tag_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_tag_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_tag_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opc_connected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("mysql_connected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("collection_duration_ms", sa.Integer(), nullable=True),
        sa.Column("local_buffer_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_message", sa.String(1024), nullable=True),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("UTC_TIMESTAMP(6)")),
    )
    op.create_table(
        "tag_collection_status",
        sa.Column("tag_id", sa.BigInteger(), sa.ForeignKey("tag_definition.tag_id"), primary_key=True),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machine.machine_id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("last_sample_ts_utc", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("last_good_ts_utc", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("last_bad_ts_utc", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("last_quality_code", sa.String(64), nullable=True),
        sa.Column("last_error_message", sa.String(1024), nullable=True),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("UTC_TIMESTAMP(6)")),
    )
    op.create_index("ix_tag_status_machine_status", "tag_collection_status", ["machine_id", "status"])
    op.create_table(
        "collector_command",
        sa.Column("command_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("command_type", sa.String(64), nullable=False),
        sa.Column("command_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(128), nullable=True),
        sa.Column("requested_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("UTC_TIMESTAMP(6)")),
        sa.Column("started_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("completed_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("result_message", sa.String(1024), nullable=True),
    )
    op.create_index("ix_command_status_requested", "collector_command", ["status", "requested_at"])
    op.create_table(
        "collector_config_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("active_config_version", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("pending_reload", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("UTC_TIMESTAMP(6)")),
    )
    op.create_table(
        "config_audit_log",
        sa.Column("audit_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("changed_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.text("UTC_TIMESTAMP(6)")),
        sa.Column("changed_by", sa.String(128), nullable=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("old_value_json", sa.JSON(), nullable=True),
        sa.Column("new_value_json", sa.JSON(), nullable=True),
        sa.Column("notes", sa.String(512), nullable=True),
    )
    op.bulk_insert(
        sa.table(
            "scan_profile",
            sa.column("profile_name", sa.String()),
            sa.column("interval_seconds", sa.Integer()),
            sa.column("enabled", sa.Boolean()),
        ),
        [
            {"profile_name": "Off", "interval_seconds": None, "enabled": True},
            {"profile_name": "5 seconds", "interval_seconds": 5, "enabled": True},
            {"profile_name": "15 seconds", "interval_seconds": 15, "enabled": True},
            {"profile_name": "60 seconds", "interval_seconds": 60, "enabled": True},
            {"profile_name": "5 minutes", "interval_seconds": 300, "enabled": True},
        ],
    )
    op.bulk_insert(
        sa.table(
            "collector_config_state",
            sa.column("id", sa.Integer()),
            sa.column("active_config_version", sa.BigInteger()),
            sa.column("pending_reload", sa.Boolean()),
            sa.column("updated_by", sa.String()),
        ),
        [{"id": 1, "active_config_version": 1, "pending_reload": False, "updated_by": "migration"}],
    )


def downgrade() -> None:
    op.drop_table("config_audit_log")
    op.drop_table("collector_config_state")
    op.drop_index("ix_command_status_requested", table_name="collector_command")
    op.drop_table("collector_command")
    op.drop_index("ix_tag_status_machine_status", table_name="tag_collection_status")
    op.drop_table("tag_collection_status")
    op.drop_table("machine_collection_status")
    op.drop_index("ix_current_sample_ts", table_name="tag_current_value")
    op.drop_table("tag_current_value")
    op.drop_index("ix_sample_ts", table_name="tag_sample_minute")
    op.drop_index("ix_sample_machine_ts", table_name="tag_sample_minute")
    op.drop_table("tag_sample_minute")
    op.drop_index("ix_cache_browse_path", table_name="tag_browser_cache")
    op.drop_index("ix_cache_machine_variable", table_name="tag_browser_cache")
    op.drop_table("tag_browser_cache")
    op.drop_index("ix_tag_scan_profile_id", table_name="tag_definition")
    op.drop_index("ix_tag_folder_path", table_name="tag_definition")
    op.drop_index("ix_tag_machine_archived", table_name="tag_definition")
    op.drop_index("ix_tag_machine_enabled", table_name="tag_definition")
    op.drop_table("tag_definition")
    op.drop_table("scan_profile")
    op.drop_table("machine")
