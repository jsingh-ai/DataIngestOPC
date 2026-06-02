from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

import certifi
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_env_file() -> str:
    return str(Path(__file__).resolve().parents[2] / ".env")


class CollectorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_default_env_file(), extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    use_mock_opc: bool = Field(default=True, alias="USE_MOCK_OPC")

    db_host: str = Field(default="localhost", validation_alias=AliasChoices("DB_HOST", "MYSQL_HOST"))
    db_port: int = Field(default=3306, validation_alias=AliasChoices("DB_PORT", "MYSQL_PORT"))
    db_name: str = Field(default="opc_platform", validation_alias=AliasChoices("DB_NAME", "MYSQL_DATABASE"))
    db_user: str = Field(default="opc_user", validation_alias=AliasChoices("DB_USER", "MYSQL_USER"))
    db_password: str = Field(default="", validation_alias=AliasChoices("DB_PASSWORD", "MYSQL_PASSWORD"))
    db_ssl_ca: str = Field(default="", alias="DB_SSL_CA")
    db_ssl_disabled: bool = Field(default=True, alias="DB_SSL_DISABLED")
    database_url: str = Field(default="", alias="DATABASE_URL")

    collector_name: str = Field(default="opc-collector-01", alias="COLLECTOR_NAME")
    collector_sqlite_path: str = Field(default="./data/opc_buffer.sqlite", alias="COLLECTOR_SQLITE_PATH")
    collector_scan_tick_seconds: int = Field(default=1, alias="COLLECTOR_SCAN_TICK_SECONDS")
    collector_config_poll_seconds: int = Field(default=15, alias="COLLECTOR_CONFIG_POLL_SECONDS")
    collector_command_poll_seconds: int = Field(default=10, alias="COLLECTOR_COMMAND_POLL_SECONDS")
    collector_mysql_batch_size: int = Field(default=5000, alias="COLLECTOR_MYSQL_BATCH_SIZE")
    collector_opc_read_chunk_size: int = Field(default=200, alias="COLLECTOR_OPC_READ_CHUNK_SIZE")
    collector_opc_connect_timeout_seconds: float = Field(default=10, alias="COLLECTOR_OPC_CONNECT_TIMEOUT_SECONDS")
    collector_opc_read_timeout_seconds: float = Field(default=10, alias="COLLECTOR_OPC_READ_TIMEOUT_SECONDS")
    collector_opc_browse_timeout_seconds: float = Field(default=30, alias="COLLECTOR_OPC_BROWSE_TIMEOUT_SECONDS")
    collector_machine_backoff_initial_seconds: int = Field(default=5, alias="COLLECTOR_MACHINE_BACKOFF_INITIAL_SECONDS")
    collector_machine_backoff_max_seconds: int = Field(default=300, alias="COLLECTOR_MACHINE_BACKOFF_MAX_SECONDS")

    password_encryption_key: str = Field(default="dev-password-key-32-bytes-minimum", alias="PASSWORD_ENCRYPTION_KEY")
    opc_client_certificate_path: str = Field(default="", alias="OPC_CLIENT_CERTIFICATE_PATH")
    opc_client_private_key_path: str = Field(default="", alias="OPC_CLIENT_PRIVATE_KEY_PATH")
    opc_client_private_key_password: str = Field(default="", alias="OPC_CLIENT_PRIVATE_KEY_PASSWORD")
    opc_server_certificate_path: str = Field(default="", alias="OPC_SERVER_CERTIFICATE_PATH")

    mock_opc_machine_count: int = Field(default=10, alias="MOCK_OPC_MACHINE_COUNT")
    mock_opc_tag_count: int = Field(default=500, alias="MOCK_OPC_TAG_COUNT")
    mock_opc_offline_machine_codes: str = Field(default="", alias="MOCK_OPC_OFFLINE_MACHINE_CODES")
    mock_opc_failed_tag_rate: float = Field(default=0.01, alias="MOCK_OPC_FAILED_TAG_RATE")
    mock_opc_slow_ms: int = Field(default=0, alias="MOCK_OPC_SLOW_MS")

    def _resolved_ssl_ca(self) -> str:
        if not self.db_ssl_ca:
            return certifi.where()
        ca_path = Path(self.db_ssl_ca)
        if ca_path.is_file():
            return str(ca_path)
        repo_path = Path(_default_env_file()).parent / self.db_ssl_ca
        if repo_path.is_file():
            return str(repo_path)
        return self.db_ssl_ca

    def _drivername(self) -> str:
        if self.database_url:
            from sqlalchemy.engine import make_url

            return make_url(self.database_url).drivername
        return "mysql+mysqlconnector"

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return f"mysql+mysqlconnector://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def redacted_sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url.replace(self.db_password, "***") if self.db_password else self.database_url
        return f"mysql+mysqlconnector://{self.db_user}:***@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def sqlalchemy_connect_args(self) -> dict[str, object]:
        args: dict[str, object] = {"connect_timeout": 10}
        if not self.db_ssl_disabled:
            ssl_ca = self._resolved_ssl_ca()
            if self._drivername().endswith("mysqlconnector"):
                args["ssl_disabled"] = False
                args["ssl_ca"] = ssl_ca
            else:
                args["ssl"] = {"ca": ssl_ca}
        return args


@lru_cache(maxsize=1)
def get_settings() -> CollectorSettings:
    return CollectorSettings()
