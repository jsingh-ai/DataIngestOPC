from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.config import get_settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify first-machine database ingestion after the collector is running.")
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--machine-code")
    identity.add_argument("--machine-id", type=int)
    parser.add_argument("--minutes", type=int, default=15, help="Sample lookback window in minutes")
    return parser.parse_args()


def read_buffer_rows(sqlite_path: str) -> int | None:
    path = Path(sqlite_path)
    if not path.exists():
        return None
    connection = sqlite3.connect(path)
    try:
        row = connection.execute("SELECT COUNT(*) FROM buffer_samples").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    engine = create_engine(settings.sqlalchemy_url, connect_args=settings.sqlalchemy_connect_args, future=True)
    failures: list[str] = []

    with engine.begin() as connection:
        machine_clause = "machine_code = :machine_code" if args.machine_code else "machine_id = :machine_id"
        machine = connection.execute(
            text(
                f"""
                SELECT machine_id, machine_code, display_name, enabled, status
                FROM machine
                WHERE {machine_clause}
                """
            ),
            {"machine_code": args.machine_code, "machine_id": args.machine_id},
        ).mappings().first()
        if machine is None:
            raise SystemExit("FAIL: machine not found")

        enabled_tag_count = int(
            connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM tag_definition
                    WHERE machine_id = :machine_id
                      AND enabled = 1
                      AND archived = 0
                    """
                ),
                {"machine_id": machine["machine_id"]},
            ).scalar_one()
        )
        status_row = connection.execute(
            text(
                """
                SELECT status, opc_connected, mysql_connected, last_heartbeat_ts_utc,
                       expected_tag_count, successful_tag_count, failed_tag_count,
                       local_buffer_rows, last_error_message
                FROM machine_collection_status
                WHERE machine_id = :machine_id
                """
            ),
            {"machine_id": machine["machine_id"]},
        ).mappings().first()
        current_value_count = int(
            connection.execute(
                text("SELECT COUNT(*) FROM tag_current_value WHERE machine_id = :machine_id"),
                {"machine_id": machine["machine_id"]},
            ).scalar_one()
        )
        recent_sample_count = int(
            connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM tag_sample_minute
                    WHERE machine_id = :machine_id
                      AND sample_ts_utc >= UTC_TIMESTAMP() - INTERVAL :minutes MINUTE
                    """
                ),
                {"machine_id": machine["machine_id"], "minutes": args.minutes},
            ).scalar_one()
        )

    engine.dispose()
    sqlite_rows = read_buffer_rows(settings.collector_sqlite_path)

    if not bool(machine["enabled"]):
        failures.append("Machine is disabled. Enable it in the dashboard before rollout validation.")
    if enabled_tag_count == 0:
        failures.append("No enabled tags found. Add 5-10 safe read-only tags and reload collector config.")
    if status_row is None:
        failures.append("No machine_collection_status row found. Confirm the collector is running and config was reloaded.")
    else:
        if not bool(status_row["opc_connected"]):
            failures.append("Collector status shows opc_connected=false. Check endpoint, security, or machine availability.")
        if not bool(status_row["mysql_connected"]):
            failures.append("Collector status shows mysql_connected=false. Check MySQL connectivity and buffer growth.")
        if status_row["last_error_message"]:
            failures.append(f"Collector reported last_error_message={status_row['last_error_message']}")
    if current_value_count == 0:
        failures.append("No tag_current_value rows found. Collector may not be reading enabled tags yet.")
    if recent_sample_count == 0:
        failures.append(f"No recent samples found in the last {args.minutes} minutes.")
    if sqlite_rows is not None and sqlite_rows > 0:
        failures.append(f"SQLite buffer contains {sqlite_rows} rows. Investigate flush lag or MySQL connectivity.")

    print(f"machine_code={machine['machine_code']} machine_id={machine['machine_id']} display_name={machine['display_name']}")
    print(f"machine_enabled={bool(machine['enabled'])} machine_status={machine['status']}")
    print(f"enabled_tag_count={enabled_tag_count}")
    if status_row is None:
        print("collector_status=missing")
    else:
        print(
            "collector_status="
            f"{status_row['status']} opc_connected={bool(status_row['opc_connected'])} "
            f"mysql_connected={bool(status_row['mysql_connected'])} "
            f"last_heartbeat_ts_utc={status_row['last_heartbeat_ts_utc']} "
            f"expected_tag_count={status_row['expected_tag_count']} "
            f"successful_tag_count={status_row['successful_tag_count']} "
            f"failed_tag_count={status_row['failed_tag_count']} "
            f"local_buffer_rows={status_row['local_buffer_rows']}"
        )
    print(f"tag_current_value_count={current_value_count}")
    print(f"recent_sample_count_last_{args.minutes}_minutes={recent_sample_count}")
    print(f"sqlite_buffer_rows={sqlite_rows if sqlite_rows is not None else 'unavailable'}")

    if failures:
        print("FAIL")
        for item in failures:
            print(f"- {item}")
        raise SystemExit(1)

    print("PASS")


if __name__ == "__main__":
    main()
