import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.config import get_settings  # noqa: E402


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.sqlalchemy_url, connect_args=settings.sqlalchemy_connect_args, future=True)
    inserts = [
        ("Off", None),
        ("5 seconds", 5),
        ("15 seconds", 15),
        ("60 seconds", 60),
        ("5 minutes", 300),
    ]
    with engine.begin() as connection:
        for name, interval in inserts:
            connection.execute(
                text(
                    """
                    INSERT INTO scan_profile (profile_name, interval_seconds, enabled)
                    VALUES (:profile_name, :interval_seconds, 1)
                    ON DUPLICATE KEY UPDATE interval_seconds = VALUES(interval_seconds), enabled = VALUES(enabled)
                    """
                ),
                {"profile_name": name, "interval_seconds": interval},
            )
        connection.execute(
            text(
                """
                INSERT INTO collector_config_state (id, active_config_version, pending_reload, updated_by)
                VALUES (1, 1, 0, 'seed_defaults')
                ON DUPLICATE KEY UPDATE updated_by = VALUES(updated_by)
                """
            )
        )


if __name__ == "__main__":
    main()
