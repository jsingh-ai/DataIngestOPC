from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from collector.models import CommandRecord


def fetch_pending_commands(engine: Engine) -> list[CommandRecord]:
    sql = text(
        """
        SELECT command_id, command_type
        FROM collector_command
        WHERE status = 'pending'
        ORDER BY requested_at ASC
        LIMIT 20
        """
    )
    with engine.begin() as connection:
        rows = connection.execute(sql).mappings().all()
        return [CommandRecord(command_id=row["command_id"], command_type=row["command_type"]) for row in rows]


def mark_command_started(engine: Engine, command_id: int) -> None:
    sql = text(
        """
        UPDATE collector_command
        SET status = 'running',
            started_at = UTC_TIMESTAMP(6)
        WHERE command_id = :command_id
        """
    )
    with engine.begin() as connection:
        connection.execute(sql, {"command_id": command_id})
