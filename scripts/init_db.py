from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
import mysql.connector
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.config import get_settings  # noqa: E402


def run_migrations() -> None:
    settings = get_settings()
    alembic_cfg = Config(str(ROOT / "api" / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(ROOT / "api" / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.sqlalchemy_url_for_alembic)
    command.upgrade(alembic_cfg, "head")


def create_database_if_needed() -> None:
    settings = get_settings()
    config = dict(settings.mysql_connection_kwargs)
    config.pop("database", None)
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS `{settings.db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    cursor.close()
    connection.close()


def seed_defaults(seed_mock_data: bool) -> None:
    settings = get_settings()
    engine = create_engine(
        settings.sqlalchemy_url,
        connect_args=settings.sqlalchemy_connect_args,
        pool_pre_ping=True,
        future=True,
    )
    profiles = [
        ("Off", None),
        ("5 seconds", 5),
        ("15 seconds", 15),
        ("60 seconds", 60),
        ("5 minutes", 300),
    ]
    with engine.begin() as connection:
        for profile_name, interval_seconds in profiles:
            connection.execute(
                text(
                    """
                    INSERT INTO scan_profile (profile_name, interval_seconds, enabled)
                    VALUES (:profile_name, :interval_seconds, 1)
                    ON DUPLICATE KEY UPDATE interval_seconds = VALUES(interval_seconds), enabled = VALUES(enabled)
                    """
                ),
                {"profile_name": profile_name, "interval_seconds": interval_seconds},
            )
        connection.execute(
            text(
                """
                INSERT INTO collector_config_state (id, active_config_version, pending_reload, updated_by)
                VALUES (1, 1, 0, 'init_db')
                ON DUPLICATE KEY UPDATE updated_by = VALUES(updated_by)
                """
            )
        )
    if seed_mock_data:
        from seed_mock_data import main as seed_mock_main

        seed_mock_main()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--seed-mock-data", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--create-database", action="store_true")
    args = parser.parse_args()

    from check_db import main as check_db_main

    if args.create_database:
        create_database_if_needed()
    check_db_main()
    if args.check_only:
        return
    if args.migrate:
        run_migrations()
    if args.seed or args.seed_mock_data:
        seed_defaults(seed_mock_data=args.seed_mock_data)
    print("Database initialization complete")


if __name__ == "__main__":
    main()
