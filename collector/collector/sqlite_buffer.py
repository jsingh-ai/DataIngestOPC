from __future__ import annotations

import sqlite3
from pathlib import Path

from collector.models import SampleRecord


class SqliteBuffer:
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS buffer_samples (
                buffer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_ts_utc TEXT NOT NULL,
                machine_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                value_num REAL NULL,
                value_str TEXT NULL,
                value_bool INTEGER NULL,
                quality_code TEXT NULL,
                source_ts_utc TEXT NULL,
                created_at TEXT NOT NULL,
                flush_attempt_count INTEGER NOT NULL DEFAULT 0,
                last_flush_error TEXT NULL
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_buffer_samples_buffer_id ON buffer_samples(buffer_id)"
        )
        self.connection.commit()

    def insert_samples(self, samples: list[SampleRecord]) -> None:
        if not samples:
            return
        with self.connection:
            self.connection.executemany(
                """
                INSERT INTO buffer_samples (
                    sample_ts_utc, machine_id, tag_id, value_num, value_str, value_bool,
                    quality_code, source_ts_utc, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        sample.sample_ts_utc.isoformat(),
                        sample.machine_id,
                        sample.tag_id,
                        sample.value_num,
                        sample.value_str,
                        1 if sample.value_bool is True else 0 if sample.value_bool is False else None,
                        sample.quality_code,
                        sample.source_ts_utc.isoformat() if sample.source_ts_utc else None,
                        sample.ingest_ts_utc.isoformat(),
                    )
                    for sample in samples
                ],
            )

    def fetch_batch(self, limit: int) -> list[sqlite3.Row]:
        cursor = self.connection.execute(
            "SELECT * FROM buffer_samples ORDER BY buffer_id ASC LIMIT ?", (limit,)
        )
        return list(cursor.fetchall())

    def delete_batch(self, buffer_ids: list[int]) -> None:
        if not buffer_ids:
            return
        with self.connection:
            self.connection.executemany(
                "DELETE FROM buffer_samples WHERE buffer_id = ?",
                [(buffer_id,) for buffer_id in buffer_ids],
            )

    def mark_flush_failure(self, buffer_ids: list[int], error: str) -> None:
        if not buffer_ids:
            return
        with self.connection:
            self.connection.executemany(
                """
                UPDATE buffer_samples
                SET flush_attempt_count = flush_attempt_count + 1,
                    last_flush_error = ?
                WHERE buffer_id = ?
                """,
                [(error[:512], buffer_id) for buffer_id in buffer_ids],
            )

    def row_count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM buffer_samples").fetchone()[0])

    def close(self) -> None:
        self.connection.close()
