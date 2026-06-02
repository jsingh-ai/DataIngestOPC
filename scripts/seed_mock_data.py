import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.config import get_settings  # noqa: E402
from app.security import encrypt_secret  # noqa: E402


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.sqlalchemy_url, connect_args=settings.sqlalchemy_connect_args, future=True)
    with engine.begin() as connection:
        for machine_index in range(1, 11):
            machine_code = f"MOCK{machine_index:02d}"
            connection.execute(
                text(
                    """
                    INSERT INTO machine (
                        machine_code, display_name, ip_address, port, opc_endpoint,
                        opc_username, opc_password_encrypted, enabled, status, created_at, updated_at
                    ) VALUES (
                        :machine_code, :display_name, :ip_address, 4840, :opc_endpoint,
                        'mock', :password, 1, 'active', UTC_TIMESTAMP(6), UTC_TIMESTAMP(6)
                    )
                    ON DUPLICATE KEY UPDATE
                        display_name = VALUES(display_name),
                        enabled = VALUES(enabled),
                        opc_username = VALUES(opc_username),
                        opc_password_encrypted = VALUES(opc_password_encrypted),
                        status = VALUES(status),
                        updated_at = UTC_TIMESTAMP(6)
                    """
                ),
                {
                    "machine_code": machine_code,
                    "display_name": f"Mock Machine {machine_index}",
                    "ip_address": f"10.0.1.{machine_index}",
                    "opc_endpoint": f"opc.tcp://10.0.1.{machine_index}:4840",
                    "password": encrypt_secret("mock-password"),
                },
            )


if __name__ == "__main__":
    main()
