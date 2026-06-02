from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import mysql.connector
from mysql.connector import Error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.config import get_settings  # noqa: E402


def redact_message(message: str, secrets: list[str]) -> str:
    redacted = message
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted


def classify_mysql_error(exc: Error) -> tuple[str, str]:
    message = str(exc).lower()
    errno = getattr(exc, "errno", None)
    if errno == 2005 or "unknown mysql server host" in message or "name or service not known" in message:
        return "dns_failure", "DNS lookup failed. Verify DB_HOST and network name resolution."
    if errno == 1045 or "access denied" in message:
        return "auth_failure", "Authentication failed. Verify DB_USER, DB_PASSWORD, and allowed source IP rules."
    if errno == 1049 or "unknown database" in message:
        return "database_missing", "Database does not exist. Create DB_NAME first or run init_db.py with --create-database."
    if errno == 2026 or "ssl" in message or "tls" in message or "certificate" in message:
        return "ssl_ca_failure", "SSL handshake failed. Verify DB_SSL_DISABLED, DB_SSL_CA, and the server certificate chain."
    if errno in {2002, 2003, 2004} or "can't connect" in message or "timed out" in message or "refused" in message or "socket" in message:
        return "network_timeout_or_refused", "Network connection failed. Verify firewall rules, MySQL listener, port, and timeout settings."
    return "unknown_failure", "Connection failed with an uncategorized MySQL error."


def main() -> None:
    settings = get_settings()
    config = settings.mysql_connection_kwargs
    try:
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor()
        cursor.execute("SELECT CURRENT_USER(), VERSION()")
        row = cast(tuple[Any, Any] | None, cursor.fetchone())
        if row is None:
            raise RuntimeError("No response from MySQL")
        current_user = row[0].decode("utf-8") if isinstance(row[0], bytes) else str(row[0])
        version = row[1].decode("utf-8") if isinstance(row[1], bytes) else str(row[1])
        ssl_status = "disabled"
        try:
            cursor.execute("SHOW STATUS LIKE 'Ssl_cipher'")
            ssl_row = cast(tuple[Any, Any] | None, cursor.fetchone())
            if ssl_row and ssl_row[1]:
                value = ssl_row[1].decode("utf-8") if isinstance(ssl_row[1], bytes) else str(ssl_row[1])
                ssl_status = f"enabled ({value})"
        except Error:
            ssl_status = "unknown"
        print(f"Connected to MySQL host={config.get('host')} port={config.get('port')} db={config.get('database')}")
        print(f"user={current_user} version={version} ssl={ssl_status}")
        cursor.close()
        connection.close()
    except Error as exc:
        category, guidance = classify_mysql_error(exc)
        driver_error = redact_message(
            str(exc),
            [str(config.get("password", "")), settings.db_password, settings.database_url],
        )
        print(
            f"MySQL connection failed category={category} host={config.get('host')} port={config.get('port')} db={config.get('database')}",
            file=sys.stderr,
        )
        print(f"guidance={guidance}", file=sys.stderr)
        print(f"driver_error={driver_error}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
