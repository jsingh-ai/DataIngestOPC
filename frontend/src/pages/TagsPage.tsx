import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { apiFetch } from "../api/client";
import { VirtualTable } from "../components/VirtualTable";
import type { PaginatedResponse, ScanProfile, Tag } from "../types/api";

type DraftMap = Record<number, Partial<Tag>>;

export function TagsPage(): JSX.Element {
  const { machineId } = useParams();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const [search, setSearch] = useState("");
  const [enabledFilter, setEnabledFilter] = useState("all");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [drafts, setDrafts] = useState<DraftMap>({});
  const [bulkScanProfileId, setBulkScanProfileId] = useState<string>("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [savingTagId, setSavingTagId] = useState<number | null>(null);

  const queryString = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (search) params.set("search", search);
    if (enabledFilter !== "all") params.set("enabled", String(enabledFilter === "enabled"));
    return params.toString();
  }, [enabledFilter, page, pageSize, search]);

  const tagsQuery = useQuery({
    queryKey: ["tags", machineId, queryString],
    queryFn: () => apiFetch<PaginatedResponse<Tag>>(`/api/machines/${machineId}/tags?${queryString}`),
  });
  const profilesQuery = useQuery({
    queryKey: ["scan-profiles"],
    queryFn: () => apiFetch<ScanProfile[]>("/api/scan-profiles"),
  });

  const refreshTags = async () => {
    setSelectedIds([]);
    setActionError(null);
    await queryClient.invalidateQueries({ queryKey: ["tags", machineId] });
  };

  const currentRows = tagsQuery.data?.items ?? [];
  const allPageIds = currentRows.map((row) => row.tag_id);
  const allSelectedOnPage = allPageIds.length > 0 && allPageIds.every((id) => selectedIds.includes(id));

  const patchTag = useMutation({
    mutationFn: ({ tagId, body }: { tagId: number; body: Partial<Tag> }) =>
      apiFetch(`/api/tags/${tagId}`, { method: "PATCH", body: JSON.stringify(body) }),
    onMutate: ({ tagId }) => {
      setActionError(null);
      setSavingTagId(tagId);
    },
    onSuccess: async (_, variables) => {
      setDrafts((current) => ({ ...current, [variables.tagId]: {} }));
      await refreshTags();
    },
    onError: (error) => {
      setActionError((error as Error).message);
    },
    onSettled: () => {
      setSavingTagId(null);
    },
  });

  const bulkEnable = useMutation({
    mutationFn: () => apiFetch("/api/tags/bulk-enable", { method: "POST", body: JSON.stringify({ tag_ids: selectedIds }) }),
    onSuccess: refreshTags,
    onMutate: () => setActionError(null),
    onError: (error) => setActionError((error as Error).message),
  });
  const bulkDisable = useMutation({
    mutationFn: () => apiFetch("/api/tags/bulk-disable", { method: "POST", body: JSON.stringify({ tag_ids: selectedIds }) }),
    onSuccess: refreshTags,
    onMutate: () => setActionError(null),
    onError: (error) => setActionError((error as Error).message),
  });
  const bulkScanProfile = useMutation({
    mutationFn: (scanProfileId: number | null) =>
      apiFetch("/api/tags/bulk-update-scan-profile", {
        method: "POST",
        body: JSON.stringify({ tag_ids: selectedIds, scan_profile_id: scanProfileId }),
      }),
    onSuccess: async () => {
      setBulkScanProfileId("");
      await refreshTags();
    },
    onMutate: () => setActionError(null),
    onError: (error) => setActionError((error as Error).message),
  });

  const totalPages = Math.max(1, Math.ceil((tagsQuery.data?.total ?? 0) / pageSize));

  const updateDraft = (tagId: number, patch: Partial<Tag>) => {
    setDrafts((current) => ({ ...current, [tagId]: { ...current[tagId], ...patch } }));
  };

  if (tagsQuery.isLoading) {
    return <section className="page"><div className="panel">Loading tags...</div></section>;
  }
  if (tagsQuery.isError) {
    return <section className="page"><div className="panel error-text">{(tagsQuery.error as Error).message}</div></section>;
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="brand-kicker">Step 2 of 2</div>
          <h2>Active Tags</h2>
          <p className="page-lead">
            These are the tags the collector actually reads. Rename them, turn them on or off, and choose how often each one should be sampled.
          </p>
        </div>
        <div className="action-row">
          <input value={search} placeholder="Search active tags" onChange={(event) => setSearch(event.target.value)} />
          <select value={enabledFilter} onChange={(event) => setEnabledFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="enabled">Enabled</option>
            <option value="disabled">Disabled</option>
          </select>
          <button className="ghost-button" onClick={() => tagsQuery.refetch()}>Refresh</button>
        </div>
      </div>
      <div className="panel machine-guide">
        <div className="guide-card">
          <div className="guide-title">1. Rename</div>
          <div className="guide-text">Make the tag names readable for operators and reports.</div>
        </div>
        <div className="guide-card">
          <div className="guide-title">2. Turn on / off</div>
          <div className="guide-text">Control whether the collector should read the tag.</div>
        </div>
        <div className="guide-card">
          <div className="guide-title">3. Choose speed</div>
          <div className="guide-text">Pick how often the collector should sample each tag.</div>
        </div>
        <div className="guide-card">
          <div className="guide-title">4. Bulk actions</div>
          <div className="guide-text">Select several tags and change them together.</div>
        </div>
      </div>
      <div className="panel stack">
        {actionError ? <div className="error-text">{actionError}</div> : null}
        <div className="action-row">
          <div>{selectedIds.length} selected</div>
          <div className="action-row">
            <button className="ghost-button" disabled={!selectedIds.length || bulkEnable.isPending} onClick={() => bulkEnable.mutate()}>
              {bulkEnable.isPending ? "Turning On..." : "Turn On Selected"}
            </button>
            <button className="ghost-button" disabled={!selectedIds.length || bulkDisable.isPending} onClick={() => bulkDisable.mutate()}>
              {bulkDisable.isPending ? "Turning Off..." : "Turn Off Selected"}
            </button>
            <select value={bulkScanProfileId} onChange={(event) => setBulkScanProfileId(event.target.value)} disabled={!selectedIds.length || bulkScanProfile.isPending}>
              <option value="">Set Sample Rate</option>
              {profilesQuery.data?.map((profile) => (
                <option key={profile.scan_profile_id} value={profile.scan_profile_id}>
                  {profile.profile_name}
                </option>
              ))}
            </select>
            <button
              className="ghost-button"
              disabled={!selectedIds.length || bulkScanProfile.isPending}
              onClick={() => bulkScanProfile.mutate(bulkScanProfileId ? Number(bulkScanProfileId) : null)}
            >
              {bulkScanProfile.isPending ? "Applying..." : "Set Sample Rate"}
            </button>
          </div>
        </div>
        <VirtualTable
          rows={currentRows}
          columns={[
            {
              key: "select",
              header: (
                <input
                  type="checkbox"
                  checked={allSelectedOnPage}
                  onChange={(event) =>
                    setSelectedIds((current) =>
                      event.target.checked
                        ? Array.from(new Set([...current, ...allPageIds]))
                        : current.filter((id) => !allPageIds.includes(id)),
                    )
                  }
                />
              ),
              width: "72px",
              render: (row) => (
                <input
                  type="checkbox"
                  checked={selectedIds.includes(row.tag_id)}
                  onChange={(event) =>
                    setSelectedIds((current) =>
                      event.target.checked ? [...current, row.tag_id] : current.filter((id) => id !== row.tag_id),
                    )
                  }
                />
              ),
            },
            {
              key: "enabled",
              header: "Collect",
              width: "90px",
              render: (row) => (
                <input
                  type="checkbox"
                  checked={drafts[row.tag_id]?.enabled ?? row.enabled}
                  onChange={(event) => updateDraft(row.tag_id, { enabled: event.target.checked })}
                />
              ),
            },
            { key: "tag_key", header: "Tag Code", width: "150px", render: (row) => row.tag_key },
            {
              key: "display_name",
              header: "Display Name",
              width: "180px",
              render: (row) => (
                <input
                  value={drafts[row.tag_id]?.display_name ?? row.display_name}
                  onChange={(event) => updateDraft(row.tag_id, { display_name: event.target.value })}
                />
              ),
            },
            { key: "opc_node_id", header: "OPC Node", width: "260px", render: (row) => row.opc_node_id },
            { key: "browse_path", header: "Found In", width: "220px", render: (row) => row.browse_path ?? "" },
            {
              key: "folder_path",
              header: "Folder Name",
              width: "180px",
              render: (row) => (
                <input
                  value={drafts[row.tag_id]?.folder_path ?? row.folder_path ?? ""}
                  onChange={(event) => updateDraft(row.tag_id, { folder_path: event.target.value })}
                />
              ),
            },
            {
              key: "scan_profile_id",
              header: "Sample Rate",
              width: "140px",
              render: (row) => (
                <select
                  value={String(drafts[row.tag_id]?.scan_profile_id ?? row.scan_profile_id ?? "")}
                  onChange={(event) => updateDraft(row.tag_id, { scan_profile_id: event.target.value ? Number(event.target.value) : null })}
                >
                  <option value="">Unset</option>
                  {profilesQuery.data?.map((profile) => (
                    <option key={profile.scan_profile_id} value={profile.scan_profile_id}>
                      {profile.profile_name}
                    </option>
                  ))}
                </select>
              ),
            },
            { key: "last_value", header: "Latest Value", width: "110px", render: (row) => row.last_value ?? "" },
            { key: "last_quality", header: "Health", width: "100px", render: (row) => row.last_quality ?? "" },
            { key: "status", header: "State", width: "100px", render: (row) => row.status },
            {
              key: "save",
              header: "Save",
              width: "90px",
              render: (row) => {
                const hasDraft = Object.keys(drafts[row.tag_id] ?? {}).length > 0;
                return (
                  <button
                    className="ghost-button"
                    disabled={!hasDraft || patchTag.isPending}
                    onClick={() => patchTag.mutate({ tagId: row.tag_id, body: drafts[row.tag_id] ?? {} })}
                  >
                    {savingTagId === row.tag_id && patchTag.isPending ? "Saving..." : "Save Changes"}
                  </button>
                );
              },
            },
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
