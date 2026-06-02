import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch } from "../api/client";
import type { CollectorCommand, PaginatedResponse } from "../types/api";

export function CollectorPage(): JSX.Element {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const commandsQuery = useQuery({
    queryKey: ["collector-commands"],
    queryFn: () => apiFetch<PaginatedResponse<CollectorCommand>>("/api/collector/commands"),
  });
  const statusQuery = useQuery({
    queryKey: ["collector-status"],
    queryFn: () => apiFetch<{ active_config_version: number; pending_reload: boolean }>("/api/collector/status"),
  });
  const reloadMutation = useMutation({
    mutationFn: () => apiFetch("/api/collector/reload-config", { method: "POST" }),
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({ queryKey: ["collector-commands"] });
      await queryClient.invalidateQueries({ queryKey: ["collector-status"] });
    },
    onError: (error) => setActionError((error as Error).message),
  });
  const restartMutation = useMutation({
    mutationFn: () => apiFetch("/api/collector/restart", { method: "POST" }),
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({ queryKey: ["collector-commands"] });
    },
    onError: (error) => setActionError((error as Error).message),
  });

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="brand-kicker">Collector Control</div>
          <h2>Collector</h2>
        </div>
        <div className="action-row">
          <button className="ghost-button" onClick={() => statusQuery.refetch()}>
            Refresh
          </button>
          <button className="ghost-button" onClick={() => reloadMutation.mutate()} disabled={reloadMutation.isPending}>
            {reloadMutation.isPending ? "Reloading..." : "Reload Config"}
          </button>
          <button
            className="primary-button"
            disabled={restartMutation.isPending}
            onClick={() => window.confirm("Restart the collector process? Use this only for manual recovery.") && restartMutation.mutate()}
          >
            {restartMutation.isPending ? "Restarting..." : "Restart Collector"}
          </button>
        </div>
      </div>
      <div className="panel stack">
        {actionError ? <div className="error-text">{actionError}</div> : null}
        <div>Active Config Version: {statusQuery.data?.active_config_version ?? "-"}</div>
        <div>Pending Reload: {String(statusQuery.data?.pending_reload ?? false)}</div>
        <div>Reload Config is the normal path for machine/tag edits. Restart Collector is for manual recovery.</div>
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Type</th>
              <th>Status</th>
              <th>Requested At</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {commandsQuery.data?.items.map((row) => (
              <tr key={row.command_id}>
                <td>{row.command_id}</td>
                <td>{row.command_type}</td>
                <td>{row.status}</td>
                <td>{row.requested_at}</td>
                <td>{row.result_message ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
