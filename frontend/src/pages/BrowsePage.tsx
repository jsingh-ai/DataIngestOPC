import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { apiFetch } from "../api/client";
import { VirtualTable } from "../components/VirtualTable";
import type { BrowseCacheItem, PaginatedResponse } from "../types/api";

export function BrowsePage(): JSX.Element {
  const { machineId } = useParams();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const queryString = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (search) params.set("search", search);
    return params.toString();
  }, [page, pageSize, search]);

  const browseQuery = useQuery({
    queryKey: ["browse-cache", machineId, queryString],
    queryFn: () => apiFetch<PaginatedResponse<BrowseCacheItem>>(`/api/machines/${machineId}/browse-cache?${queryString}`),
  });
  const refreshMutation = useMutation({
    mutationFn: () => apiFetch(`/api/machines/${machineId}/browse-tags`, { method: "POST", body: JSON.stringify({ max_nodes: 2000, max_depth: 6 }) }),
    onSuccess: async () => {
      setActionError(null);
      await queryClient.invalidateQueries({ queryKey: ["browse-cache", machineId] });
    },
    onError: (error) => setActionError((error as Error).message),
  });
  const addMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/api/machines/${machineId}/add-tags-from-cache`, {
        method: "POST",
        body: JSON.stringify({
          tags: selectedIds.map((cacheId) => ({ cache_id: cacheId })),
        }),
      }),
    onSuccess: async () => {
      setActionError(null);
      setSelectedIds([]);
      await queryClient.invalidateQueries({ queryKey: ["browse-cache", machineId] });
      await queryClient.invalidateQueries({ queryKey: ["tags", machineId] });
    },
    onError: (error) => setActionError((error as Error).message),
  });
  const clearMutation = useMutation({
    mutationFn: () => apiFetch(`/api/machines/${machineId}/browse-cache`, { method: "DELETE" }),
    onSuccess: async () => {
      setActionError(null);
      setSelectedIds([]);
      await queryClient.invalidateQueries({ queryKey: ["browse-cache", machineId] });
    },
    onError: (error) => setActionError((error as Error).message),
  });

  if (browseQuery.isLoading) {
    return <section className="page"><div className="panel">Loading browse cache...</div></section>;
  }
  if (browseQuery.isError) {
    return <section className="page"><div className="panel error-text">{(browseQuery.error as Error).message}</div></section>;
  }

  const totalPages = Math.max(1, Math.ceil((browseQuery.data?.total ?? 0) / pageSize));

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="brand-kicker">Browse Cache</div>
          <h2>OPC UA Browse</h2>
        </div>
        <div className="action-row">
          <input value={search} placeholder="Search browse cache" onChange={(event) => setSearch(event.target.value)} />
          <button className="ghost-button" onClick={() => browseQuery.refetch()}>Refresh Grid</button>
          <button className="ghost-button" onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending}>
            {refreshMutation.isPending ? "Browsing..." : "Refresh Browse Cache"}
          </button>
          <button className="primary-button" onClick={() => addMutation.mutate()} disabled={!selectedIds.length || addMutation.isPending}>
            {addMutation.isPending ? "Adding..." : "Add Selected Tags"}
          </button>
          <button className="ghost-button" onClick={() => clearMutation.mutate()} disabled={clearMutation.isPending}>
            {clearMutation.isPending ? "Clearing..." : "Clear Cache"}
          </button>
        </div>
      </div>
      <div className="panel">
        {actionError ? <div className="error-text">{actionError}</div> : null}
        <VirtualTable
          rows={browseQuery.data?.items ?? []}
          columns={[
            {
              key: "select",
              header: "Select",
              width: "72px",
              render: (row) => (
                <input
                  type="checkbox"
                  checked={selectedIds.includes(row.cache_id)}
                  onChange={(event) =>
                    setSelectedIds((current) =>
                      event.target.checked ? [...current, row.cache_id] : current.filter((id) => id !== row.cache_id),
                    )
                  }
                />
              ),
            },
            { key: "browse_path", header: "Browse Path", width: "260px", render: (row) => row.browse_path ?? "" },
            { key: "opc_node_id", header: "Node ID", width: "280px", render: (row) => row.opc_node_id },
            { key: "display_name", header: "Display", width: "160px", render: (row) => row.display_name ?? "" },
            { key: "browse_name", header: "Browse Name", width: "140px", render: (row) => row.browse_name ?? "" },
            { key: "node_class", header: "Class", width: "110px", render: (row) => row.node_class ?? "" },
            { key: "data_type", header: "Type", width: "110px", render: (row) => row.data_type ?? "" },
            { key: "already_added", header: "Added", width: "90px", render: (row) => String(row.already_added) },
          ]}
        />
        <div className="action-row">
          <button className="ghost-button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1}>Previous</button>
          <span>Page {page} / {totalPages}</span>
          <button className="ghost-button" onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={page >= totalPages}>Next</button>
          <select value={pageSize} onChange={(event) => { setPage(1); setPageSize(Number(event.target.value)); }}>
            <option value={100}>100</option>
            <option value={250}>250</option>
            <option value={500}>500</option>
            <option value={1000}>1000</option>
          </select>
        </div>
      </div>
    </section>
  );
}
