export type PaginatedResponse<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type Machine = {
  machine_id: number;
  machine_code: string;
  display_name: string;
  ip_address: string;
  port: number;
  opc_endpoint: string;
  security_policy?: string | null;
  security_mode?: string | null;
  opc_username?: string | null;
  enabled: boolean;
  status: string;
  notes?: string | null;
  tag_count: number;
  online_status: string;
  last_heartbeat_ts_utc?: string | null;
};

export type ScanProfile = {
  scan_profile_id: number;
  profile_name: string;
  interval_seconds?: number | null;
  enabled: boolean;
};

export type Tag = {
  tag_id: number;
  machine_id: number;
  tag_key: string;
  display_name: string;
  opc_node_id: string;
  browse_path?: string | null;
  folder_path?: string | null;
  data_type?: string | null;
  engineering_unit?: string | null;
  scan_profile_id?: number | null;
  enabled: boolean;
  archived: boolean;
  last_value?: string | null;
  last_quality?: string | null;
  last_seen?: string | null;
  status: string;
};

export type BrowseCacheItem = {
  cache_id: number;
  machine_id: number;
  browse_path?: string | null;
  opc_node_id: string;
  display_name?: string | null;
  browse_name?: string | null;
  node_class?: string | null;
  data_type?: string | null;
  is_variable: boolean;
  already_added: boolean;
};

export type MachineHealth = {
  machine_id: number;
  machine_code: string;
  display_name: string;
  enabled: boolean;
  status: string;
  collector_status?: string | null;
  opc_connected?: boolean | null;
  mysql_connected?: boolean | null;
  last_heartbeat_ts_utc?: string | null;
  expected_tag_count: number;
  successful_tag_count: number;
  failed_tag_count: number;
  collection_duration_ms?: number | null;
  local_buffer_rows: number;
  last_error_message?: string | null;
};

export type CollectorCommand = {
  command_id: number;
  command_type: string;
  status: string;
  requested_by?: string | null;
  requested_at: string;
  completed_at?: string | null;
  result_message?: string | null;
};
