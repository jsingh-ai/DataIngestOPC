import { useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/client";
import type { Machine, PaginatedResponse } from "../types/api";

function getSetupBadge(machine: Machine): { label: string; kind: "success" | "warning" | "muted" } {
  if (machine.status === "connection_tested") {
    return { label: "Setup tested", kind: "success" };
  }
  if (machine.status === "error") {
    return { label: "Setup needs attention", kind: "warning" };
  }
  return { label: "Setup draft", kind: "muted" };
}

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
  const deleteMutation = useMutation({
    mutationFn: (machineId: number) => apiFetch(`/api/machines/${machineId}`, { method: "DELETE" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["machines"] });
    },
  });
  const testMutation = useMutation({
    mutationFn: (machine: Machine) =>
      apiFetch<{ success: boolean; message: string; attempt_id?: string | null; debug_log?: string[] }>(
        `/api/machines/${machine.machine_id}/test-connection`,
        { method: "POST" },
      ),
    onSuccess: (result, machine) => {
      window.alert(
        [
          `Test result for ${machine.display_name}: ${result.success ? "success" : "failure"}`,
          result.message,
          result.attempt_id ? `attempt_id=${result.attempt_id}` : null,
        ]
          .filter(Boolean)
          .join("\n"),
      );
    },
    onError: (error) => {
      window.alert((error as Error).message || "Connection test failed.");
    },
  });

  const groupedMachines = useMemo(() => {
    const groups = new Map<string, Machine[]>();
    for (const machine of machinesQuery.data?.items ?? []) {
      const labelSource = machine.display_name.trim() || machine.machine_code.trim();
      const groupName = (labelSource.split(/\s+/)[0] || "Other").trim();
      const current = groups.get(groupName) ?? [];
      current.push(machine);
      groups.set(groupName, current);
    }
    return Array.from(groups.entries())
      .map(([groupName, machines]) => ({
        groupName,
        machines: machines.sort((a, b) => a.display_name.localeCompare(b.display_name)),
      }))
      .sort((a, b) => a.groupName.localeCompare(b.groupName));
  }, [machinesQuery.data?.items]);

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="brand-kicker">Plant Overview</div>
          <h2>Machines</h2>
          <p className="page-lead">
            Start here. Set up the machine, discover tags, add the ones you want, and then manage the tags the collector reads.
          </p>
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
      <div className="panel machine-guide">
        <div className="guide-card">
          <div className="guide-title">1. Set up the machine</div>
          <div className="guide-text">Change the machine name, IP address, and connection settings.</div>
        </div>
        <div className="guide-card">
          <div className="guide-title">2. Discover tags</div>
          <div className="guide-text">Read the PLC and see what tags exist before adding anything.</div>
        </div>
        <div className="guide-card">
          <div className="guide-title">3. Add active tags</div>
          <div className="guide-text">Move the tags you want into the list the collector actually reads.</div>
        </div>
        <div className="guide-card">
          <div className="guide-title">4. Pause or start collection</div>
          <div className="guide-text">Turn the whole machine on or off for collection without changing its setup.</div>
        </div>
      </div>
      <div className="machine-groups">
        {groupedMachines.map((group) => (
          <details key={group.groupName} className="machine-group" open={group.machines.length === 1}>
            <summary className="machine-group-summary">
              <div>
                <div className="machine-group-title">{group.groupName}</div>
                <div className="machine-group-subtitle">
                  {group.machines.length} machine{group.machines.length === 1 ? "" : "s"} in this group
                </div>
              </div>
              <div className="machine-group-hint">Click to expand or collapse</div>
            </summary>
            <div className="machine-group-body">
              <table className="data-table machine-table">
                <thead>
                  <tr>
                    <th>Machine Code</th>
                    <th>Display Name</th>
                    <th>IP Address</th>
                    <th>OPC Endpoint</th>
                    <th>Collection</th>
                    <th>Health</th>
                    <th>Tag Count</th>
                    <th>Last Seen</th>
                    <th>Setup</th>
                    <th>Discover</th>
                    <th>Manage Tags</th>
                    <th>Machine On/Off</th>
                    <th>Delete</th>
                  </tr>
                </thead>
                <tbody>
                  {group.machines.map((machine) => (
                    <tr key={machine.machine_id}>
                      <td>{machine.machine_code}</td>
                      <td>{machine.display_name}</td>
                      <td>{machine.ip_address}</td>
                      <td>{machine.opc_endpoint}</td>
                      <td>
                        <span className={`status-chip status-chip-${machine.enabled ? "success" : "muted"}`}>
                          {machine.enabled ? "On" : "Off"}
                        </span>
                      </td>
                      <td>
                        <span className={`status-chip status-chip-${machine.online_status === "online" ? "success" : "warning"}`}>
                          {machine.online_status === "online" ? "Online" : "Offline"}
                        </span>
                        <div className="subtle-cell">{machine.status}</div>
                        <div className="machine-health-row">
                          <span className={`status-chip status-chip-${getSetupBadge(machine).kind}`}>{getSetupBadge(machine).label}</span>
                        </div>
                      </td>
                      <td>{machine.tag_count}</td>
                      <td>{machine.last_heartbeat_ts_utc ?? "Not yet seen"}</td>
                      <td className="action-cell action-cell-single">
                        <Link className="row-action-button" to={`/machines/${machine.machine_id}`}>
                          Edit details
                        </Link>
                        <div className="cell-note">Use this when the machine IP, name, or endpoint changes.</div>
                      </td>
                      <td className="action-cell action-cell-single">
                        <Link className="row-action-button" to={`/machines/${machine.machine_id}/browse`}>
                          Discover tags
                        </Link>
                        <div className="cell-note">This only reads the machine and shows what tags exist.</div>
                      </td>
                      <td className="action-cell action-cell-single">
                        <Link className="row-action-button" to={`/machines/${machine.machine_id}/tags`}>
                          Manage active tags
                        </Link>
                        <div className="cell-note">Rename tags here and choose how often they should be read.</div>
                      </td>
                      <td className="action-cell action-cell-single">
                        <button className="row-action-button" onClick={() => testMutation.mutate(machine)}>
                          Test connection
                        </button>
                        <div className="cell-note">Checks the PLC before you browse tags.</div>
                      </td>
                      <td className="action-cell action-cell-single">
                        <button className="row-action-button" onClick={() => toggleMutation.mutate(machine)}>
                          {machine.enabled ? "Pause collection" : "Start collection"}
                        </button>
                        <div className="cell-note">This turns collection on or off for the whole machine.</div>
                      </td>
                      <td className="action-cell action-cell-single">
                        <button
                          className="danger-button"
                          onClick={() => {
                            if (
                              window.confirm(
                                `Delete machine ${machine.display_name}? This also deletes its tags, browse cache, and collection status.`,
                              )
                            ) {
                              deleteMutation.mutate(machine.machine_id);
                            }
                          }}
                        >
                          Delete Machine
                        </button>
                        <div className="cell-note">This permanently removes the machine and its related records.</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}
