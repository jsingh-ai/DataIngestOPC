from __future__ import annotations

import argparse
import getpass
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.security import hash_password  # noqa: E402


def prompt(name: str, default: str = "", secret: bool = False) -> str:
    label = f"{name} [{default}]: " if default else f"{name}: "
    if secret:
        value = getpass.getpass(label)
    else:
        value = input(label)
    return value or default


def escape_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
    return f"\"{escaped}\""


def build_values(mode: str, interactive: bool, args: argparse.Namespace) -> dict[str, str]:
    local_defaults = {
        "APP_ENV": "local",
        "USE_MOCK_OPC": "true",
        "DB_HOST": "localhost" if mode == "azure" else "127.0.0.1",
        "DB_PORT": "3306",
        "DB_NAME": "opc_platform",
        "DB_USER": "opc_user",
        "DB_PASSWORD": "opcpassword" if mode == "local" else "",
        "DB_SSL_CA": "",
        "DB_SSL_DISABLED": "false" if mode == "azure" else "true",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "admin123!" if mode == "local" else "",
        "COLLECTOR_SQLITE_PATH": "./data/opc_buffer.sqlite",
        "COLLECTOR_OPC_CONNECT_TIMEOUT_SECONDS": "10",
        "COLLECTOR_OPC_READ_TIMEOUT_SECONDS": "10",
        "COLLECTOR_OPC_BROWSE_TIMEOUT_SECONDS": "30",
    }
    values = dict(local_defaults)
    if interactive:
        for key in ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_SSL_CA", "DB_SSL_DISABLED", "ADMIN_USERNAME", "COLLECTOR_SQLITE_PATH", "COLLECTOR_OPC_CONNECT_TIMEOUT_SECONDS", "COLLECTOR_OPC_READ_TIMEOUT_SECONDS", "COLLECTOR_OPC_BROWSE_TIMEOUT_SECONDS"]:
            values[key] = prompt(key, values[key])
        values["DB_PASSWORD"] = prompt("DB_PASSWORD", secret=True)
        values["ADMIN_PASSWORD"] = prompt("ADMIN_PASSWORD", secret=True)
        values["USE_MOCK_OPC"] = prompt("USE_MOCK_OPC", values["USE_MOCK_OPC"])
    for key, arg_name in {
        "DB_HOST": "db_host",
        "DB_PORT": "db_port",
        "DB_NAME": "db_name",
        "DB_USER": "db_user",
        "DB_PASSWORD": "db_password",
        "DB_SSL_CA": "db_ssl_ca",
        "DB_SSL_DISABLED": "db_ssl_disabled",
        "ADMIN_USERNAME": "admin_username",
        "ADMIN_PASSWORD": "admin_password",
        "USE_MOCK_OPC": "use_mock_opc",
        "COLLECTOR_SQLITE_PATH": "collector_sqlite_path",
        "COLLECTOR_OPC_CONNECT_TIMEOUT_SECONDS": "opc_connect_timeout",
        "COLLECTOR_OPC_READ_TIMEOUT_SECONDS": "opc_read_timeout",
        "COLLECTOR_OPC_BROWSE_TIMEOUT_SECONDS": "opc_browse_timeout",
    }.items():
        value = getattr(args, arg_name)
        if value is not None:
            values[key] = str(value)
    values["JWT_SECRET_KEY"] = secrets.token_urlsafe(48)
    values["PASSWORD_ENCRYPTION_KEY"] = secrets.token_urlsafe(48)
    if values["ADMIN_PASSWORD"]:
        values["ADMIN_PASSWORD_HASH"] = hash_password(values["ADMIN_PASSWORD"])
    else:
        values["ADMIN_PASSWORD_HASH"] = ""
    values.setdefault("API_AUTH_DISABLED", "false")
    values.setdefault("COLLECTOR_NAME", "opc-collector-01")
    values.setdefault("COLLECTOR_SCAN_TICK_SECONDS", "1")
    values.setdefault("COLLECTOR_CONFIG_POLL_SECONDS", "15")
    values.setdefault("COLLECTOR_COMMAND_POLL_SECONDS", "10")
    values.setdefault("COLLECTOR_MYSQL_BATCH_SIZE", "5000")
    values.setdefault("COLLECTOR_OPC_READ_CHUNK_SIZE", "200")
    values.setdefault("COLLECTOR_MACHINE_BACKOFF_INITIAL_SECONDS", "5")
    values.setdefault("COLLECTOR_MACHINE_BACKOFF_MAX_SECONDS", "300")
    values.setdefault("OPC_BROWSE_MAX_DEPTH", "6")
    values.setdefault("OPC_BROWSE_MAX_NODES", "5000")
    values.setdefault("API_HOST", "0.0.0.0")
    values.setdefault("API_PORT", "8000")
    values.setdefault("FRONTEND_API_BASE_URL", "http://localhost:8000")
    values.setdefault("DATABASE_URL", "")
    values.setdefault("OPC_CLIENT_CERTIFICATE_PATH", "")
    values.setdefault("OPC_CLIENT_PRIVATE_KEY_PATH", "")
    values.setdefault("OPC_CLIENT_PRIVATE_KEY_PASSWORD", "")
    values.setdefault("OPC_SERVER_CERTIFICATE_PATH", "")
    values.setdefault("MOCK_OPC_MACHINE_COUNT", "10")
    values.setdefault("MOCK_OPC_TAG_COUNT", "500")
    values.setdefault("MOCK_OPC_OFFLINE_MACHINE_CODES", "")
    values.setdefault("MOCK_OPC_FAILED_TAG_RATE", "0.01")
    values.setdefault("MOCK_OPC_SLOW_MS", "0")
    return values


def render_env(values: dict[str, str]) -> str:
    lines = []
    for key in [
        "APP_ENV",
        "USE_MOCK_OPC",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_SSL_CA",
        "DB_SSL_DISABLED",
        "DATABASE_URL",
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD_HASH",
        "ADMIN_PASSWORD",
        "API_AUTH_DISABLED",
        "JWT_SECRET_KEY",
        "PASSWORD_ENCRYPTION_KEY",
        "COLLECTOR_NAME",
        "COLLECTOR_SQLITE_PATH",
        "COLLECTOR_SCAN_TICK_SECONDS",
        "COLLECTOR_CONFIG_POLL_SECONDS",
        "COLLECTOR_COMMAND_POLL_SECONDS",
        "COLLECTOR_MYSQL_BATCH_SIZE",
        "COLLECTOR_OPC_READ_CHUNK_SIZE",
        "COLLECTOR_OPC_CONNECT_TIMEOUT_SECONDS",
        "COLLECTOR_OPC_READ_TIMEOUT_SECONDS",
        "COLLECTOR_OPC_BROWSE_TIMEOUT_SECONDS",
        "COLLECTOR_MACHINE_BACKOFF_INITIAL_SECONDS",
        "COLLECTOR_MACHINE_BACKOFF_MAX_SECONDS",
        "OPC_BROWSE_MAX_DEPTH",
        "OPC_BROWSE_MAX_NODES",
        "OPC_CLIENT_CERTIFICATE_PATH",
        "OPC_CLIENT_PRIVATE_KEY_PATH",
        "OPC_CLIENT_PRIVATE_KEY_PASSWORD",
        "OPC_SERVER_CERTIFICATE_PATH",
        "MOCK_OPC_MACHINE_COUNT",
        "MOCK_OPC_TAG_COUNT",
        "MOCK_OPC_OFFLINE_MACHINE_CODES",
        "MOCK_OPC_FAILED_TAG_RATE",
        "MOCK_OPC_SLOW_MS",
        "API_HOST",
        "API_PORT",
        "FRONTEND_API_BASE_URL",
    ]:
        lines.append(f"{key}={escape_env_value(values.get(key, ''))}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["local", "azure"], default="local")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--output", default=str(ROOT / ".env"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--db-host")
    parser.add_argument("--db-port")
    parser.add_argument("--db-name")
    parser.add_argument("--db-user")
    parser.add_argument("--db-password")
    parser.add_argument("--db-ssl-ca")
    parser.add_argument("--db-ssl-disabled")
    parser.add_argument("--admin-username")
    parser.add_argument("--admin-password")
    parser.add_argument("--use-mock-opc")
    parser.add_argument("--collector-sqlite-path")
    parser.add_argument("--opc-connect-timeout")
    parser.add_argument("--opc-read-timeout")
    parser.add_argument("--opc-browse-timeout")
    args = parser.parse_args()

    output = Path(args.output)
    if output.exists() and not args.overwrite:
        raise SystemExit(f"{output} already exists. Use --overwrite to replace it.")

    values = build_values(args.mode, args.interactive, args)
    output.write_text(render_env(values), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
