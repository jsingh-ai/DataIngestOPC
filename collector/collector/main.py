from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import create_engine, text

from collector.commands import fetch_pending_commands, mark_command_started
from collector.config import CollectorSettings, get_settings
from collector.models import MachineConfig, SampleRecord, TagConfig, TagStatusRecord
from collector.mysql_writer import MysqlWriter
from collector.normalization import normalize_value
from collector.opcua_client import MachineBackoffError, get_reader
from collector.security import decrypt_secret
from collector.sqlite_buffer import SqliteBuffer

logger = logging.getLogger("opc_platform.collector")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


class CollectorApp:
    def __init__(self, settings: CollectorSettings) -> None:
        self.settings = settings
        self.engine = create_engine(
            settings.sqlalchemy_url,
            connect_args=settings.sqlalchemy_connect_args,
            pool_pre_ping=True,
            pool_recycle=3600,
            future=True,
        )
        self.writer = MysqlWriter(settings)
        self.buffer = SqliteBuffer(settings.collector_sqlite_path)
        self.reader = get_reader(settings)
        self.stop_event = asyncio.Event()
        self.config_version = 0
        self.machines: dict[int, MachineConfig] = {}
        self.tag_groups: dict[tuple[int, int], list[TagConfig]] = {}
        self.next_run_at: dict[tuple[int, int], float] = {}
        self.pending_restart_command_id: int | None = None
        self.last_command_poll = 0.0
        self.last_config_poll = 0.0
        self.total_samples_collected = 0
        self.total_flush_batches = 0
        self.total_flush_failures = 0

    def _next_due_epoch(self, now: datetime, interval_seconds: int) -> float:
        seconds = int(now.timestamp())
        return float(seconds - (seconds % interval_seconds) + interval_seconds)

    async def load_config(self) -> None:
        logger.info("collector_load_config db_url=%s", self.settings.redacted_sqlalchemy_url)
        with self.engine.begin() as connection:
            state = connection.execute(
                text("SELECT active_config_version, pending_reload FROM collector_config_state WHERE id = 1")
            ).mappings().one()
            machine_rows = connection.execute(
                text(
                    """
                    SELECT machine_id, machine_code, display_name, opc_endpoint, security_policy,
                           security_mode, opc_username, opc_password_encrypted, enabled
                    FROM machine
                    WHERE enabled = 1 AND status NOT IN ('archived', 'disabled')
                    """
                )
            ).mappings().all()
            tag_rows = connection.execute(
                text(
                    """
                    SELECT t.tag_id, t.machine_id, t.tag_key, t.display_name, t.opc_node_id,
                           sp.interval_seconds, t.enabled
                    FROM tag_definition t
                    JOIN scan_profile sp ON sp.scan_profile_id = t.scan_profile_id
                    WHERE t.enabled = 1 AND t.archived = 0 AND sp.interval_seconds IS NOT NULL
                    """
                )
            ).mappings().all()
            self.config_version = int(state["active_config_version"])
            machines = {
                row["machine_id"]: MachineConfig(
                    machine_id=row["machine_id"],
                    machine_code=row["machine_code"],
                    display_name=row["display_name"],
                    opc_endpoint=row["opc_endpoint"],
                    security_policy=row["security_policy"],
                    security_mode=row["security_mode"],
                    opc_username=row["opc_username"],
                    opc_password=decrypt_secret(row["opc_password_encrypted"]),
                    enabled=bool(row["enabled"]),
                )
                for row in machine_rows
            }
            groups: dict[tuple[int, int], list[TagConfig]] = defaultdict(list)
            for row in tag_rows:
                if row["machine_id"] not in machines:
                    continue
                interval = int(row["interval_seconds"])
                groups[(row["machine_id"], interval)].append(
                    TagConfig(
                        tag_id=row["tag_id"],
                        machine_id=row["machine_id"],
                        tag_key=row["tag_key"],
                        display_name=row["display_name"],
                        opc_node_id=row["opc_node_id"],
                        scan_interval_seconds=interval,
                        enabled=bool(row["enabled"]),
                    )
                )
            connection.execute(
                text(
                    "UPDATE collector_config_state SET pending_reload = 0, updated_at = UTC_TIMESTAMP(6) WHERE id = 1"
                )
            )

        old_machine_ids = set(self.machines)
        new_machine_ids = set(machines)
        self.machines = machines
        self.tag_groups = dict(groups)
        now = datetime.now(UTC)
        self.next_run_at = {
            key: self._next_due_epoch(now, key[1])
            for key in self.tag_groups
        }
        await self.reader.sync_machines(new_machine_ids)
        for removed_machine_id in old_machine_ids - new_machine_ids:
            await self.reader.disconnect_machine(removed_machine_id)
        logger.info("collector_config_loaded version=%s machines=%s groups=%s", self.config_version, len(self.machines), len(self.tag_groups))

    def _aligned_sample_ts(self, now: datetime, interval_seconds: int) -> datetime:
        if interval_seconds == 60:
            return now.replace(second=0, microsecond=0)
        if interval_seconds > 60:
            epoch = int(now.timestamp())
            aligned = epoch - (epoch % interval_seconds)
            return datetime.fromtimestamp(aligned, tz=UTC)
        return now

    def _safe_update_machine_status(self, **kwargs: object) -> None:
        try:
            self.writer.update_machine_status(**kwargs)  # type: ignore[arg-type]
        except Exception as exc:
            logger.warning("machine_status_update_failed error=%s machine_id=%s", exc, kwargs.get("machine_id"))

    def _safe_update_tag_statuses(self, rows: list[TagStatusRecord]) -> None:
        try:
            self.writer.update_tag_statuses(rows)
        except Exception as exc:
            logger.warning("tag_status_update_failed error=%s count=%s", exc, len(rows))

    def _safe_mark_mysql_connectivity(self, connected: bool, error_message: str | None = None) -> None:
        try:
            self.writer.update_mysql_connectivity(
                list(self.machines),
                mysql_connected=connected,
                local_buffer_rows=self.buffer.row_count(),
                last_error_message=error_message,
            )
        except Exception as exc:
            logger.warning("mysql_connectivity_update_failed error=%s", exc)

    async def process_machine_group(
        self, machine: MachineConfig, interval_seconds: int, tags: list[TagConfig]
    ) -> None:
        if not tags:
            return
        start = datetime.now(UTC)
        samples: list[SampleRecord] = []
        tag_status_rows: list[TagStatusRecord] = []
        success_count = 0
        failed_count = 0
        machine_error: str | None = None
        for offset in range(0, len(tags), self.settings.collector_opc_read_chunk_size):
            chunk = tags[offset : offset + self.settings.collector_opc_read_chunk_size]
            try:
                results = await self.reader.read_nodes(machine, [tag.opc_node_id for tag in chunk])
            except MachineBackoffError as exc:
                machine_error = str(exc)
                failed_count = len(tags)
                for tag in chunk:
                    tag_status_rows.append(
                        TagStatusRecord(
                            tag_id=tag.tag_id,
                            machine_id=machine.machine_id,
                            status="backoff",
                            last_sample_ts_utc=None,
                            last_good_ts_utc=None,
                            last_bad_ts_utc=start,
                            last_quality_code="Backoff",
                            last_error_message=machine_error,
                        )
                    )
                break
            except Exception as exc:
                machine_error = str(exc)
                failed_count += len(chunk)
                for tag in chunk:
                    tag_status_rows.append(
                        TagStatusRecord(
                            tag_id=tag.tag_id,
                            machine_id=machine.machine_id,
                            status="read_error",
                            last_sample_ts_utc=None,
                            last_good_ts_utc=None,
                            last_bad_ts_utc=start,
                            last_quality_code="Bad",
                            last_error_message=machine_error,
                        )
                    )
                continue

            now = datetime.now(UTC)
            sample_ts = self._aligned_sample_ts(now, interval_seconds)
            for tag, result in zip(chunk, results, strict=True):
                value_num, value_str, value_bool = normalize_value(result.value)
                if result.ok:
                    samples.append(
                        SampleRecord(
                            sample_ts_utc=sample_ts,
                            machine_id=machine.machine_id,
                            tag_id=tag.tag_id,
                            value_num=value_num,
                            value_str=value_str,
                            value_bool=value_bool,
                            quality_code=result.quality_code,
                            source_ts_utc=result.source_ts_utc,
                            ingest_ts_utc=now,
                        )
                    )
                    success_count += 1
                    tag_status_rows.append(
                        TagStatusRecord(
                            tag_id=tag.tag_id,
                            machine_id=machine.machine_id,
                            status="good",
                            last_sample_ts_utc=sample_ts,
                            last_good_ts_utc=sample_ts,
                            last_bad_ts_utc=None,
                            last_quality_code=result.quality_code,
                            last_error_message=None,
                        )
                    )
                else:
                    failed_count += 1
                    tag_status_rows.append(
                        TagStatusRecord(
                            tag_id=tag.tag_id,
                            machine_id=machine.machine_id,
                            status="bad",
                            last_sample_ts_utc=sample_ts,
                            last_good_ts_utc=None,
                            last_bad_ts_utc=sample_ts,
                            last_quality_code=result.quality_code,
                            last_error_message=result.error_message,
                        )
                    )

        if samples:
            self.buffer.insert_samples(samples)
            self.total_samples_collected += len(samples)
        self._safe_update_tag_statuses(tag_status_rows)
        self._safe_update_machine_status(
            machine_id=machine.machine_id,
            status="running" if machine_error is None else "error",
            expected_tag_count=len(tags),
            successful_tag_count=success_count,
            failed_tag_count=failed_count,
            opc_connected=machine_error is None,
            mysql_connected=True,
            collection_duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
            local_buffer_rows=self.buffer.row_count(),
            last_error_message=machine_error,
        )

    async def process_due_groups_once(self) -> None:
        now_epoch = time.time()
        due_keys = [
            key for key, next_due in self.next_run_at.items()
            if now_epoch >= next_due
        ]
        for machine_id, interval_seconds in due_keys:
            machine = self.machines.get(machine_id)
            tags = self.tag_groups.get((machine_id, interval_seconds), [])
            if machine is None or not machine.enabled or not tags:
                continue
            await self.process_machine_group(machine, interval_seconds, tags)
            self.next_run_at[(machine_id, interval_seconds)] = self._next_due_epoch(datetime.now(UTC), interval_seconds)

    def flush_buffer_once(self) -> int:
        batch = self.buffer.fetch_batch(self.settings.collector_mysql_batch_size)
        if not batch:
            return 0
        rows = [
            {
                "sample_ts_utc": row["sample_ts_utc"],
                "machine_id": row["machine_id"],
                "tag_id": row["tag_id"],
                "value_num": row["value_num"],
                "value_str": row["value_str"],
                "value_bool": None if row["value_bool"] is None else bool(row["value_bool"]),
                "quality_code": row["quality_code"],
                "source_ts_utc": row["source_ts_utc"],
                "ingest_ts_utc": row["created_at"],
            }
            for row in batch
        ]
        buffer_ids = [int(row["buffer_id"]) for row in batch]
        try:
            self.writer.write_batch(rows)
            self.buffer.delete_batch(buffer_ids)
            self.total_flush_batches += 1
            self._safe_mark_mysql_connectivity(True)
            return len(buffer_ids)
        except Exception as exc:
            self.total_flush_failures += 1
            self.buffer.mark_flush_failure(buffer_ids, str(exc))
            self._safe_mark_mysql_connectivity(False, str(exc))
            logger.warning("buffer_flush_failed error=%s rows=%s", exc, len(buffer_ids))
            return 0

    async def handle_commands_once(self) -> None:
        try:
            commands = fetch_pending_commands(self.engine)
        except Exception as exc:
            logger.warning("fetch_pending_commands_failed error=%s", exc)
            return
        for command in commands:
            mark_command_started(self.engine, command.command_id)
            if command.command_type == "reload_config":
                try:
                    await self.load_config()
                    self.writer.complete_command(command.command_id, "Configuration reloaded")
                except Exception as exc:
                    self.writer.complete_command(command.command_id, f"Reload failed: {exc}", status="failed")
            elif command.command_type == "restart_collector":
                self.pending_restart_command_id = command.command_id
                self.stop_event.set()
                break
            else:
                self.writer.complete_command(command.command_id, "Unsupported command", status="failed")

    async def poll_config_state_once(self) -> None:
        try:
            with self.engine.begin() as connection:
                state = connection.execute(
                    text("SELECT active_config_version, pending_reload FROM collector_config_state WHERE id = 1")
                ).mappings().one()
        except Exception as exc:
            logger.warning("poll_config_state_failed error=%s", exc)
            return
        if state["pending_reload"] or int(state["active_config_version"]) != self.config_version:
            await self.load_config()

    async def flush_on_shutdown(self) -> None:
        for _ in range(5):
            if self.stop_event.is_set() and self.buffer.row_count() == 0:
                break
            flushed = self.flush_buffer_once()
            if flushed == 0:
                break
            await asyncio.sleep(0)

    async def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                await self.load_config()
                break
            except Exception as exc:
                logger.warning("initial_config_load_failed error=%s", exc)
                await asyncio.sleep(5)
        while not self.stop_event.is_set():
            now_monotonic = time.monotonic()
            if now_monotonic - self.last_command_poll >= self.settings.collector_command_poll_seconds:
                await self.handle_commands_once()
                self.last_command_poll = now_monotonic
            if self.stop_event.is_set():
                break
            if now_monotonic - self.last_config_poll >= self.settings.collector_config_poll_seconds:
                await self.poll_config_state_once()
                self.last_config_poll = now_monotonic
            await self.process_due_groups_once()
            self.flush_buffer_once()
            await asyncio.sleep(self.settings.collector_scan_tick_seconds)

        await self.flush_on_shutdown()
        if self.pending_restart_command_id is not None:
            try:
                self.writer.complete_command(
                    self.pending_restart_command_id,
                    "Collector exiting for restart",
                )
            except Exception as exc:
                logger.warning("restart_command_completion_failed error=%s", exc)
        await self.reader.shutdown()
        self.writer.close()
        self.buffer.close()
        self.engine.dispose()


async def _main() -> None:
    configure_logging()
    app = CollectorApp(get_settings())
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, app.stop_event.set)
        except NotImplementedError:
            if sys.platform == "win32":
                try:
                    signal.signal(sig, lambda *_: app.stop_event.set())
                except (ValueError, RuntimeError, AttributeError):
                    logger.debug("signal_handler_unsupported platform=%s signal=%s", sys.platform, sig)
            else:
                raise
    await app.run()


if __name__ == "__main__":
    asyncio.run(_main())
