import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/client";
import type { Machine, PaginatedResponse } from "../types/api";

export function MachinesPage(): JSX.Element {
  const queryClient = useQueryClient();
  const machinesQuery = useQuery({
    queryKey: ["machines"],
    queryFn: () => apiFetch<PaginatedResponse<Machine>>("/api/machines"),
  });
  const toggleMutation = useMutation({
    mutationFn: (machine: Machine) =>
      apiFetch(`/api/machines/${machine.machine_id}/${machine.enabled ? "disable" : "enable"}`, { method: "POST" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["machines"] });
    },
  });

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="brand-kicker">Control Plane</div>
          <h2>Machines</h2>
        </div>
        <div className="action-row">
          <button className="ghost-button" onClick={() => machinesQuery.refetch()}>
            Refresh
          </button>
          <Link className="primary-button" to="/machines/new">
            Add Machine
          </Link>
        </div>
      </div>
      <div className="panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>IP</th>
              <th>Endpoint</th>
              <th>Enabled</th>
              <th>Status</th>
              <th>Tags</th>
              <th>Heartbeat</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {machinesQuery.data?.items.map((machine) => (
              <tr key={machine.machine_id}>
                <td>{machine.machine_code}</td>
                <td>{machine.display_name}</td>
                <td>{machine.ip_address}</td>
                <td>{machine.opc_endpoint}</td>
                <td>{machine.enabled ? "Yes" : "No"}</td>
                <td>{machine.status}</td>
                <td>{machine.tag_count}</td>
                <td>{machine.last_heartbeat_ts_utc ?? "-"}</td>
                <td className="action-cell">
                  <Link to={`/machines/${machine.machine_id}`}>Edit</Link>
                  <Link to={`/machines/${machine.machine_id}/tags`}>Tags</Link>
                  <Link to={`/machines/${machine.machine_id}/browse`}>Browse</Link>
                  <button onClick={() => toggleMutation.mutate(machine)}>
                    {machine.enabled ? "Disable" : "Enable"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
