from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MachineConfig:
    machine_id: int
    machine_code: str
    display_name: str
    opc_endpoint: str
    security_policy: str | None
    security_mode: str | None
    opc_username: str | None
    opc_password: str | None
    enabled: bool


@dataclass(slots=True)
class TagConfig:
    tag_id: int
    machine_id: int
    tag_key: str
    display_name: str
    opc_node_id: str
    scan_interval_seconds: int
    enabled: bool


@dataclass(slots=True)
class SampleRecord:
    sample_ts_utc: datetime
    machine_id: int
    tag_id: int
    value_num: float | None
    value_str: str | None
    value_bool: bool | None
    quality_code: str | None
    source_ts_utc: datetime | None
    ingest_ts_utc: datetime


@dataclass(slots=True)
class CommandRecord:
    command_id: int
    command_type: str


@dataclass(slots=True)
class NodeReadResult:
    ok: bool
    value: object | None
    quality_code: str
    source_ts_utc: datetime | None
    server_ts_utc: datetime | None
    error_message: str | None = None


@dataclass(slots=True)
class TagStatusRecord:
    tag_id: int
    machine_id: int
    status: str
    last_sample_ts_utc: datetime | None
    last_good_ts_utc: datetime | None
    last_bad_ts_utc: datetime | None
    last_quality_code: str | None
    last_error_message: str | None
