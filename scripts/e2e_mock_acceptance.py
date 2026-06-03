from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "collector"))

from app.config import get_settings as get_api_settings  # type: ignore[import-not-found]  # noqa: E402
from collector.config import CollectorSettings  # type: ignore[import-not-found]  # noqa: E402
from collector.main import CollectorApp  # type: ignore[import-not-found]  # noqa: E402


def run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def seed_mock_tags(tag_count: int) -> None:
    settings = get_api_settings()
    engine = create_engine(settings.sqlalchemy_url, connect_args=settings.sqlalchemy_connect_args, future=True)
    with engine.begin() as connection:
        scan_profile_id = connection.execute(
            text("SELECT scan_profile_id FROM scan_profile WHERE profile_name = '5 seconds'")
        ).scalar_one()
        machine_rows = connection.execute(
            text("SELECT machine_id, machine_code FROM machine WHERE machine_code LIKE 'MOCK%' ORDER BY machine_id ASC LIMIT 2")
        ).mappings().all()
        machine_ids = [int(row["machine_id"]) for row in machine_rows]
        if machine_ids:
            id_list = ", ".join(str(machine_id) for machine_id in machine_ids)
            connection.execute(
                text(f"DELETE FROM machine_collection_status WHERE machine_id IN ({id_list})")
            )
            connection.execute(
                text(f"DELETE FROM tag_current_value WHERE machine_id IN ({id_list})")
            )
            connection.execute(
                text(f"DELETE FROM tag_collection_status WHERE machine_id IN ({id_list})")
            )
            connection.execute(
                text(f"DELETE FROM tag_sample_minute WHERE machine_id IN ({id_list})")
            )
        for row in machine_rows:
            for tag_index in range(tag_count):
                connection.execute(
                    text(
                        """
                        INSERT INTO tag_definition (
                            machine_id, tag_key, display_name, opc_node_id, browse_path, folder_path, data_type,
                            engineering_unit, scan_profile_id, enabled, archived, created_at, updated_at
                        ) VALUES (
                            :machine_id, :tag_key, :display_name, :opc_node_id, :browse_path, :folder_path, :data_type,
                            NULL, :scan_profile_id, 1, 0, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6)
                        )
                        ON DUPLICATE KEY UPDATE
                            display_name = VALUES(display_name),
                            browse_path = VALUES(browse_path),
                            folder_path = VALUES(folder_path),
                            scan_profile_id = VALUES(scan_profile_id),
                            enabled = VALUES(enabled),
                            archived = VALUES(archived),
                            updated_at = UTC_TIMESTAMP(6)
                        """
                    ),
                    {
                        "machine_id": row["machine_id"],
                        "tag_key": f"mock_tag_{tag_index}",
                        "display_name": f"Mock Tag {tag_index}",
                        "opc_node_id": f"ns=2;s={row['machine_code']}.Tag{tag_index}",
                        "browse_path": f"Root/Objects/{row['machine_code']}/Tag{tag_index}",
                        "folder_path": row["machine_code"],
                        "data_type": "Double" if tag_index % 2 == 0 else "Boolean",
                        "scan_profile_id": scan_profile_id,
                    },
                )
    engine.dispose()


async def run_collector_once(sqlite_path: str) -> dict[str, int]:
    os.environ["USE_MOCK_OPC"] = "true"
    os.environ["COLLECTOR_SQLITE_PATH"] = sqlite_path
    settings = CollectorSettings()
    app = CollectorApp(settings)
    try:
        await app.load_config()
        for key in list(app.next_run_at):
            app.next_run_at[key] = 0.0
        await app.process_due_groups_once()
        flushed = 0
        while True:
            count = app.flush_buffer_once()
            if count == 0:
                break
            flushed += count
        engine = create_engine(settings.sqlalchemy_url, connect_args=settings.sqlalchemy_connect_args, future=True)
        with engine.begin() as connection:
            current_values = int(connection.execute(text("SELECT COUNT(*) FROM tag_current_value")).scalar_one())
            machine_status = int(connection.execute(text("SELECT COUNT(*) FROM machine_collection_status")).scalar_one())
        engine.dispose()
        return {
            "current_values": current_values,
            "machine_status": machine_status,
            "sqlite_buffer_rows": app.buffer.row_count(),
            "flushed_rows": flushed,
        }
    finally:
        await app.reader.shutdown()
        app.writer.close()
        app.buffer.close()
        app.engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local mock end-to-end acceptance check.")
    parser.add_argument("--tag-count", type=int, default=8)
    parser.add_argument(
        "--bootstrap-local",
        action="store_true",
        help="Create a local Docker MySQL environment before running the acceptance check.",
    )
    args = parser.parse_args()

    if args.bootstrap_local:
        run(["docker", "compose", "up", "-d", "mysql"])
        run([PYTHON, "scripts/create_env.py", "--mode", "local", "--overwrite"])

    run([PYTHON, "scripts/check_db.py"])
    run([PYTHON, "scripts/init_db.py", "--migrate", "--seed"])
    run([PYTHON, "scripts/seed_mock_data.py"])
    seed_mock_tags(args.tag_count)

    with tempfile.TemporaryDirectory() as temp_dir:
        sqlite_path = str(Path(temp_dir) / "acceptance.sqlite3")
        result = asyncio.run(run_collector_once(sqlite_path))

    if result["current_values"] <= 0:
        raise SystemExit("Acceptance failed: tag_current_value table is empty")
    if result["machine_status"] <= 0:
        raise SystemExit("Acceptance failed: machine_collection_status table is empty")
    if result["sqlite_buffer_rows"] != 0:
        raise SystemExit("Acceptance failed: SQLite buffer did not drain to zero")

    print(result)


if __name__ == "__main__":
    main()
