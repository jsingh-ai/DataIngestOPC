from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=1000)
    search: str | None = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


class MachineBase(BaseModel):
    machine_code: str = Field(max_length=64)
    display_name: str = Field(max_length=128)
    ip_address: str = Field(max_length=64)
    port: int = Field(default=4840, ge=1, le=65535)
    opc_endpoint: str = Field(max_length=255)
    security_policy: str | None = Field(default=None, max_length=64)
    security_mode: str | None = Field(default=None, max_length=64)
    opc_username: str | None = Field(default=None, max_length=128)
    enabled: bool = False
    notes: str | None = Field(default=None, max_length=512)


class MachineCreate(MachineBase):
    opc_password: str | None = None


class MachineUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    ip_address: str | None = Field(default=None, max_length=64)
    port: int | None = Field(default=None, ge=1, le=65535)
    opc_endpoint: str | None = Field(default=None, max_length=255)
    security_policy: str | None = Field(default=None, max_length=64)
    security_mode: str | None = Field(default=None, max_length=64)
    opc_username: str | None = Field(default=None, max_length=128)
    opc_password: str | None = None
    enabled: bool | None = None
    status: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=512)


class MachineSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    machine_id: int
    machine_code: str
    display_name: str
    ip_address: str
    port: int
    opc_endpoint: str
    security_policy: str | None
    security_mode: str | None
    opc_username: str | None
    enabled: bool
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    tag_count: int = 0
    online_status: str = "unknown"
    last_heartbeat_ts_utc: datetime | None = None


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    machine_status: str


class BrowseRequest(BaseModel):
    max_depth: int | None = Field(default=None, ge=1, le=20)
    max_nodes: int | None = Field(default=None, ge=1, le=10000)


class BrowseSummaryResponse(BaseModel):
    discovered_count: int
    variable_count: int
    cache_upserts: int
    message: str


class ScanProfileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_profile_id: int
    profile_name: str
    interval_seconds: int | None
    enabled: bool


class TagCreate(BaseModel):
    tag_key: str = Field(max_length=128)
    display_name: str = Field(max_length=128)
    opc_node_id: str = Field(max_length=512)
    browse_path: str | None = Field(default=None, max_length=1024)
    folder_path: str | None = Field(default=None, max_length=512)
    data_type: str | None = Field(default=None, max_length=64)
    engineering_unit: str | None = Field(default=None, max_length=64)
    scan_profile_id: int | None = None
    enabled: bool = True


class TagUpdate(BaseModel):
    tag_key: str | None = Field(default=None, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)
    browse_path: str | None = Field(default=None, max_length=1024)
    folder_path: str | None = Field(default=None, max_length=512)
    data_type: str | None = Field(default=None, max_length=64)
    engineering_unit: str | None = Field(default=None, max_length=64)
    scan_profile_id: int | None = None
    enabled: bool | None = None
    archived: bool | None = None


class TagSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tag_id: int
    machine_id: int
    tag_key: str
    display_name: str
    opc_node_id: str
    browse_path: str | None
    folder_path: str | None
    data_type: str | None
    engineering_unit: str | None
    scan_profile_id: int | None
    enabled: bool
    archived: bool
    created_at: datetime
    updated_at: datetime
    last_value: str | None = None
    last_quality: str | None = None
    last_seen: datetime | None = None
    status: str = "unknown"


class BulkTagIds(BaseModel):
    tag_ids: list[int]

    @field_validator("tag_ids")
    @classmethod
    def validate_tag_ids(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("tag_ids cannot be empty")
        return value


class BulkTagScanProfileUpdate(BulkTagIds):
    scan_profile_id: int | None


class BrowseCacheSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cache_id: int
    machine_id: int
    opc_node_id: str
    browse_path: str | None
    display_name: str | None
    browse_name: str | None
    node_class: str | None
    data_type: str | None
    is_variable: bool
    already_added: bool
    last_seen_at: datetime | None


class AddTagFromCacheItem(BaseModel):
    cache_id: int
    tag_key: str | None = None
    display_name: str | None = None
    folder_path: str | None = None
    engineering_unit: str | None = None
    scan_profile_id: int | None = None
    enabled: bool = True


class AddTagsFromCacheRequest(BaseModel):
    tags: list[AddTagFromCacheItem]


class AddTagsFromCacheResponse(BaseModel):
    created_count: int
    skipped_duplicates: int
    created_tag_ids: list[int]
    skipped_cache_ids: list[int]


class CollectorCommandSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    command_id: int
    command_type: str
    command_payload: dict[str, Any] | None
    status: str
    requested_by: str | None
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    result_message: str | None


class CollectorActionResponse(BaseModel):
    command_id: int
    command_type: str
    status: str
    active_config_version: int | None = None


class CollectorStatusResponse(BaseModel):
    active_config_version: int
    pending_reload: bool
    recent_commands: list[CollectorCommandSummary]


class MachineHealthSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    machine_id: int
    machine_code: str
    display_name: str
    enabled: bool
    status: str
    collector_status: str | None = None
    opc_connected: bool | None = None
    mysql_connected: bool | None = None
    last_heartbeat_ts_utc: datetime | None = None
    expected_tag_count: int = 0
    successful_tag_count: int = 0
    failed_tag_count: int = 0
    collection_duration_ms: int | None = None
    local_buffer_rows: int = 0
    last_error_message: str | None = None


class TagCurrentValueResponse(BaseModel):
    machine_id: int
    tag_id: int
    sample_ts_utc: datetime
    value_num: float | None
    value_str: str | None
    value_bool: bool | None
    quality_code: str | None
    source_ts_utc: datetime | None
    ingest_ts_utc: datetime
