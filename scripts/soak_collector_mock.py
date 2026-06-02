from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import psutil  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "collector"))

from collector.config import get_settings  # noqa: E402
from collector.models import MachineConfig, SampleRecord, TagConfig  # noqa: E402
from collector.mysql_writer import MysqlWriter  # noqa: E402
from collector.normalization import normalize_value  # noqa: E402
from collector.opcua_client import MockOpcReader  # noqa: E402
from collector.sqlite_buffer import SqliteBuffer  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=int, default=10)
    parser.add_argument("--accelerated", action="store_true")
    parser.add_argument("--machine-count", type=int, default=10)
    parser.add_argument("--tags-per-machine", type=int, default=500)
    parser.add_argument("--memory-threshold-bytes", type=int, default=50_000_000)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--buffer-only", action="store_true", help="Write to SQLite buffer only. Expect buffer rows to grow.")
    mode.add_argument("--with-mysql", action="store_true", help="Flush buffer rows into MySQL and expect drain to zero.")
    return parser


def build_machines(machine_count: int, tags_per_machine: int, accelerated: bool) -> tuple[list[MachineConfig], dict[int, list[TagConfig]]]:
    machines = [
        MachineConfig(
            machine_id=index + 1,
            machine_code=f"MOCK{index + 1:02d}",
            display_name=f"Mock {index + 1}",
            opc_endpoint=f"opc.tcp://127.0.0.{index + 1}:4840",
            security_policy=None,
            security_mode=None,
            opc_username=None,
            opc_password=None,
            enabled=True,
        )
        for index in range(machine_count)
    ]
    tags_by_machine = {
        machine.machine_id: [
            TagConfig(
                tag_id=machine.machine_id * 100000 + tag_index,
                machine_id=machine.machine_id,
                tag_key=f"tag_{tag_index}",
                display_name=f"Tag {tag_index}",
                opc_node_id=f"ns=2;s={machine.machine_code}.Tag{tag_index}",
                scan_interval_seconds=60 if not accelerated else 1,
                enabled=True,
            )
            for tag_index in range(tags_per_machine)
        ]
        for machine in machines
    }
    return machines, tags_by_machine


def flush_buffer(buffer: SqliteBuffer, writer: MysqlWriter | None, batch_size: int) -> tuple[int, int]:
    if writer is None:
        return 0, buffer.row_count()
    flushes = 0
    while True:
        batch = buffer.fetch_batch(batch_size)
        if not batch:
            break
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
        writer.write_batch(rows)
        buffer.delete_batch([int(row["buffer_id"]) for row in batch])
        flushes += 1
    return flushes, buffer.row_count()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    mode = "with_mysql" if args.with_mysql else "buffer_only"
    settings = get_settings()
    settings.use_mock_opc = True
    settings.mock_opc_machine_count = args.machine_count
    settings.mock_opc_tag_count = args.tags_per_machine
    settings.mock_opc_failed_tag_rate = 0.01
    reader = MockOpcReader(settings)
    temp_dir = tempfile.TemporaryDirectory()
    buffer = SqliteBuffer(str(Path(temp_dir.name) / "soak.sqlite3"))
    writer = MysqlWriter(settings) if args.with_mysql else None
    tracemalloc.start()
    process = psutil.Process()
    start_rss = process.memory_info().rss
    start = perf_counter()
    samples_collected = 0
    errors = 0
    peak_rss = start_rss
    mysql_flushes = 0

    machines, tags_by_machine = build_machines(args.machine_count, args.tags_per_machine, args.accelerated)
    end_time = perf_counter() + args.duration_seconds

    async def run_loop() -> None:
        nonlocal peak_rss, samples_collected, errors, mysql_flushes
        while perf_counter() < end_time:
            for machine in machines:
                tag_batch = tags_by_machine[machine.machine_id]
                results = await reader.read_nodes(machine, [tag.opc_node_id for tag in tag_batch[:200]])
                now = datetime.now(UTC)
                samples: list[SampleRecord] = []
                for tag, result in zip(tag_batch[:200], results, strict=True):
                    if result.ok:
                        value_num, value_str, value_bool = normalize_value(result.value)
                        samples.append(
                            SampleRecord(
                                sample_ts_utc=now,
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
                        samples_collected += 1
                    else:
                        errors += 1
                buffer.insert_samples(samples)
                flushes, _ = flush_buffer(buffer, writer, settings.collector_mysql_batch_size)
                mysql_flushes += flushes
                peak_rss = max(peak_rss, process.memory_info().rss)

    try:
        asyncio.run(run_loop())
        remaining_rows = buffer.row_count()
        current, peak_alloc = tracemalloc.get_traced_memory()
        end_rss = process.memory_info().rss
        result = {
            "mode": mode,
            "starting_memory_bytes": start_rss,
            "peak_memory_bytes": max(peak_rss, end_rss),
            "ending_memory_bytes": end_rss,
            "tracemalloc_current_bytes": current,
            "tracemalloc_peak_bytes": peak_alloc,
            "samples_collected": samples_collected,
            "sqlite_buffer_rows": remaining_rows,
            "mysql_flushes": mysql_flushes,
            "errors": errors,
            "elapsed_seconds": perf_counter() - start,
            "interpretation": (
                "Buffer-only mode is expected to leave rows in SQLite because no MySQL flush is attempted."
                if not args.with_mysql
                else "With-MySQL mode is expected to drain SQLite to zero if DB writes succeed."
            ),
        }
        print(result)
        if end_rss - start_rss > args.memory_threshold_bytes:
            raise SystemExit("Memory growth exceeded threshold")
        if args.with_mysql and remaining_rows != 0:
            raise SystemExit("With-MySQL mode expected sqlite_buffer_rows=0 after flush")
    finally:
        if writer is not None:
            writer.close()
        buffer.close()
        temp_dir.cleanup()


if __name__ == "__main__":
    main()
