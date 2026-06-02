import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import type { MachineHealth, PaginatedResponse } from "../types/api";

export function HealthPage(): JSX.Element {
  const query = useQuery({
    queryKey: ["health-machines"],
    queryFn: () => apiFetch<PaginatedResponse<MachineHealth>>("/api/health/machines"),
  });

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="brand-kicker">Health</div>
          <h2>Collection Status</h2>
        </div>
        <button className="ghost-button" onClick={() => query.refetch()}>
          Refresh
        </button>
      </div>
      <div className="panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Machine</th>
              <th>Status</th>
              <th>OPC</th>
              <th>MySQL</th>
              <th>Heartbeat</th>
              <th>Expected</th>
              <th>OK</th>
              <th>Failed</th>
              <th>Duration</th>
              <th>Buffer</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {query.data?.items.map((row) => (
              <tr key={row.machine_id}>
                <td>{row.machine_code}</td>
                <td>{row.collector_status ?? row.status}</td>
                <td>{String(row.opc_connected)}</td>
                <td>{String(row.mysql_connected)}</td>
                <td>{row.last_heartbeat_ts_utc ?? "-"}</td>
                <td>{row.expected_tag_count}</td>
                <td>{row.successful_tag_count}</td>
                <td>{row.failed_tag_count}</td>
                <td>{row.collection_duration_ms ?? "-"}</td>
                <td>{row.local_buffer_rows}</td>
                <td>{row.last_error_message ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
