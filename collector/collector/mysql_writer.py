from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, text

from collector.config import CollectorSettings
from collector.models import TagStatusRecord


class MysqlWriter:
    def __init__(self, settings: CollectorSettings) -> None:
        self.engine = create_engine(
            settings.sqlalchemy_url,
            connect_args=settings.sqlalchemy_connect_args,
            pool_pre_ping=True,
            pool_recycle=3600,
            future=True,
        )

    def write_batch(self, rows: list[dict]) -> None:
        if not rows:
            return
        sample_sql = text(
            """
            INSERT INTO tag_sample_minute (
                sample_ts_utc, machine_id, tag_id, value_num, value_str, value_bool,
                quality_code, source_ts_utc, ingest_ts_utc
            ) VALUES (
                :sample_ts_utc, :machine_id, :tag_id, :value_num, :value_str, :value_bool,
                :quality_code, :source_ts_utc, :ingest_ts_utc
            )
            ON DUPLICATE KEY UPDATE
                value_num = VALUES(value_num),
                value_str = VALUES(value_str),
                value_bool = VALUES(value_bool),
                quality_code = VALUES(quality_code),
                source_ts_utc = VALUES(source_ts_utc),
                ingest_ts_utc = VALUES(ingest_ts_utc)
            """
        )
        current_sql = text(
            """
            INSERT INTO tag_current_value (
                machine_id, tag_id, sample_ts_utc, value_num, value_str, value_bool,
                quality_code, source_ts_utc, ingest_ts_utc
            ) VALUES (
                :machine_id, :tag_id, :sample_ts_utc, :value_num, :value_str, :value_bool,
                :quality_code, :source_ts_utc, :ingest_ts_utc
            )
            ON DUPLICATE KEY UPDATE
                sample_ts_utc = VALUES(sample_ts_utc),
                value_num = VALUES(value_num),
                value_str = VALUES(value_str),
                value_bool = VALUES(value_bool),
                quality_code = VALUES(quality_code),
                source_ts_utc = VALUES(source_ts_utc),
                ingest_ts_utc = VALUES(ingest_ts_utc)
            """
        )
        with self.engine.begin() as connection:
            connection.execute(sample_sql, rows)
            connection.execute(current_sql, rows)

    def update_machine_status(
        self,
        machine_id: int,
        *,
        status: str,
        expected_tag_count: int,
        successful_tag_count: int,
        failed_tag_count: int,
        opc_connected: bool,
        mysql_connected: bool,
        collection_duration_ms: int | None,
        local_buffer_rows: int,
        last_error_message: str | None,
    ) -> None:
        sql = text(
            """
            INSERT INTO machine_collection_status (
                machine_id, status, last_heartbeat_ts_utc, last_successful_sample_ts_utc,
                last_failed_sample_ts_utc, expected_tag_count, successful_tag_count, failed_tag_count,
                opc_connected, mysql_connected, collection_duration_ms, local_buffer_rows,
                last_error_message, updated_at
            ) VALUES (
                :machine_id, :status, :heartbeat, :success_ts, :failed_ts,
                :expected_tag_count, :successful_tag_count, :failed_tag_count, :opc_connected,
                :mysql_connected, :collection_duration_ms, :local_buffer_rows, :last_error_message, :updated_at
            )
            ON DUPLICATE KEY UPDATE
                status = VALUES(status),
                last_heartbeat_ts_utc = VALUES(last_heartbeat_ts_utc),
                last_successful_sample_ts_utc = VALUES(last_successful_sample_ts_utc),
                last_failed_sample_ts_utc = VALUES(last_failed_sample_ts_utc),
                expected_tag_count = VALUES(expected_tag_count),
                successful_tag_count = VALUES(successful_tag_count),
                failed_tag_count = VALUES(failed_tag_count),
                opc_connected = VALUES(opc_connected),
                mysql_connected = VALUES(mysql_connected),
                collection_duration_ms = VALUES(collection_duration_ms),
                local_buffer_rows = VALUES(local_buffer_rows),
                last_error_message = VALUES(last_error_message),
                updated_at = VALUES(updated_at)
            """
        )
        now = datetime.now(UTC)
        payload = {
            "machine_id": machine_id,
            "status": status,
            "heartbeat": now,
            "success_ts": now if successful_tag_count else None,
            "failed_ts": now if failed_tag_count else None,
            "expected_tag_count": expected_tag_count,
            "successful_tag_count": successful_tag_count,
            "failed_tag_count": failed_tag_count,
            "opc_connected": opc_connected,
            "mysql_connected": mysql_connected,
            "collection_duration_ms": collection_duration_ms,
            "local_buffer_rows": local_buffer_rows,
            "last_error_message": last_error_message,
            "updated_at": now,
        }
        with self.engine.begin() as connection:
            connection.execute(sql, [payload])

    def update_tag_statuses(self, rows: list[TagStatusRecord]) -> None:
        if not rows:
            return
        sql = text(
            """
            INSERT INTO tag_collection_status (
                tag_id, machine_id, status, last_sample_ts_utc, last_good_ts_utc,
                last_bad_ts_utc, last_quality_code, last_error_message, updated_at
            ) VALUES (
                :tag_id, :machine_id, :status, :last_sample_ts_utc, :last_good_ts_utc,
                :last_bad_ts_utc, :last_quality_code, :last_error_message, :updated_at
            )
            ON DUPLICATE KEY UPDATE
                status = VALUES(status),
                last_sample_ts_utc = VALUES(last_sample_ts_utc),
                last_good_ts_utc = VALUES(last_good_ts_utc),
                last_bad_ts_utc = VALUES(last_bad_ts_utc),
                last_quality_code = VALUES(last_quality_code),
                last_error_message = VALUES(last_error_message),
                updated_at = VALUES(updated_at)
            """
        )
        payload = [
            {
                "tag_id": row.tag_id,
                "machine_id": row.machine_id,
                "status": row.status,
                "last_sample_ts_utc": row.last_sample_ts_utc,
                "last_good_ts_utc": row.last_good_ts_utc,
                "last_bad_ts_utc": row.last_bad_ts_utc,
                "last_quality_code": row.last_quality_code,
                "last_error_message": row.last_error_message,
                "updated_at": datetime.now(UTC),
            }
            for row in rows
        ]
        with self.engine.begin() as connection:
            connection.execute(sql, payload)

    def complete_command(self, command_id: int, result_message: str, status: str = "completed") -> None:
        sql = text(
            """
            UPDATE collector_command
            SET status = :status,
                completed_at = UTC_TIMESTAMP(6),
                result_message = :result_message
            WHERE command_id = :command_id
            """
        )
        with self.engine.begin() as connection:
            connection.execute(sql, {"status": status, "result_message": result_message[:1024], "command_id": command_id})

    def update_mysql_connectivity(
        self,
        machine_ids: list[int],
        *,
        mysql_connected: bool,
        local_buffer_rows: int,
        last_error_message: str | None,
    ) -> None:
        if not machine_ids:
            return
        sql = text(
            """
            UPDATE machine_collection_status
            SET mysql_connected = :mysql_connected,
                local_buffer_rows = :local_buffer_rows,
                last_error_message = CASE
                    WHEN :last_error_message IS NULL THEN last_error_message
                    ELSE :last_error_message
                END,
                updated_at = UTC_TIMESTAMP(6)
            WHERE machine_id = :machine_id
            """
        )
        payload = [
            {
                "machine_id": machine_id,
                "mysql_connected": mysql_connected,
                "local_buffer_rows": local_buffer_rows,
                "last_error_message": None if mysql_connected else (last_error_message or "")[:1024],
            }
            for machine_id in machine_ids
        ]
        with self.engine.begin() as connection:
            connection.execute(sql, payload)

    def close(self) -> None:
        self.engine.dispose()
