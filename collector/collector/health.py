from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MachineCycleHealth:
    machine_id: int
    status: str
    expected_tag_count: int
    successful_tag_count: int
    failed_tag_count: int
    opc_connected: bool
    mysql_connected: bool
    collection_duration_ms: int | None
    local_buffer_rows: int
    last_error_message: str | None
