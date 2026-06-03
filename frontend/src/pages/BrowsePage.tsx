import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { apiFetch } from "../api/client";
import { VirtualTable } from "../components/VirtualTable";
import type { BrowseCacheItem, PaginatedResponse } from "../types/api";

type BrowseOperationKind = "discover" | "add";
type BrowseOperationState = "idle" | "running" | "success" | "error";
type BrowseStep = 0 | 1 | 2 | 3;

type BrowseTrailItem = {
  nodeId: string | null;
  label: string;
  browsePath: string | null;
};

type OperationResult = {
  success: boolean;
  message: string;
};

type DiscoverRequest = {
  nodeId: string | null;
  label: string;
  browsePath: string | null;
};

const ROOT_TRAIL_ITEM: BrowseTrailItem = {
  nodeId: null,
  label: "Root / Objects",
  browsePath: null,
};

function getFolderLabel(item: BrowseCacheItem): string {
  return item.browse_path ?? item.display_name ?? item.opc_node_id;
}

export function BrowsePage(): JSX.Element {
  const { machineId } = useParams();
  const queryClient = useQueryClient();
  const storageKey = machineId ? `opc-platform:browse-trail:${machineId}` : null;
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [trail, setTrail] = useState<BrowseTrailItem[]>([ROOT_TRAIL_ITEM]);
  const [operationKind, setOperationKind] = useState<BrowseOperationKind | null>(null);
  const [operationState, setOperationState] = useState<BrowseOperationState>("idle");
  const [operationStep, setOperationStep] = useState<BrowseStep>(0);
  const [operationMessage, setOperationMessage] = useState("");
  const resultRef = useRef<OperationResult | null>(null);

  const currentRoot = trail[trail.length - 1] ?? ROOT_TRAIL_ITEM;
  const currentFolderPath = currentRoot.browsePath;

  useEffect(() => {
    if (!storageKey) {
      return;
    }
    const savedTrail = window.localStorage.getItem(storageKey);
    if (!savedTrail) {
      return;
    }
    try {
      const parsed = JSON.parse(savedTrail) as BrowseTrailItem[];
      if (Array.isArray(parsed) && parsed.length > 0) {
        setTrail(
          parsed.map((item) => ({
            nodeId: item.nodeId ?? null,
            label: item.label || ROOT_TRAIL_ITEM.label,
            browsePath: item.browsePath ?? null,
          })),
        );
      }
    } catch {
      // Ignore malformed local storage.
    }
  }, [storageKey]);

  useEffect(() => {
    if (!storageKey) {
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(trail));
  }, [storageKey, trail]);

  const queryString = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (currentFolderPath) {
      params.set("folder_path", currentFolderPath);
    }
    return params.toString();
  }, [currentFolderPath, page, pageSize]);

  useEffect(() => {
    setPage(1);
    setSelectedIds([]);
  }, [currentRoot.nodeId]);

  const browseQuery = useQuery({
    queryKey: ["browse-cache", machineId, queryString],
    queryFn: () => apiFetch<PaginatedResponse<BrowseCacheItem>>(`/api/machines/${machineId}/browse-cache?${queryString}`),
  });

  const discoveredFolders = useMemo(() => {
    const seen = new Map<string, BrowseCacheItem>();
    for (const item of browseQuery.data?.items ?? []) {
      if (item.node_class === "Variable") {
        continue;
      }
      if (!seen.has(item.opc_node_id)) {
        seen.set(item.opc_node_id, item);
      }
    }
    return Array.from(seen.values()).sort((left, right) =>
      (left.browse_path ?? left.display_name ?? "").localeCompare(right.browse_path ?? right.display_name ?? ""),
    );
  }, [browseQuery.data?.items]);

  const canClear = (browseQuery.data?.total ?? 0) > 0;
  const canAdd = selectedIds.length > 0;
  const showBrowseSkeleton = browseQuery.isLoading || (browseQuery.isFetching && !browseQuery.data);

  function beginOperation(kind: BrowseOperationKind, label: string) {
    setOperationKind(kind);
    setOperationState("running");
    setOperationStep(1);
    setActionError(null);
    resultRef.current = null;
    if (kind === "discover") {
      setOperationMessage(`Loading folders inside ${label}...`);
    } else {
      setOperationMessage("Preparing selected rows for the active list...");
    }
  }

  function navigateToFolder(item: BrowseCacheItem) {
    const itemLabel = getFolderLabel(item);
    const isCurrentFolder = currentRoot.nodeId === item.opc_node_id;

    setSelectedIds([]);
    setActionError(null);

    if (isCurrentFolder) {
      setTrail((current) => (current.length > 1 ? current.slice(0, -1) : current));
      return;
    }

    setTrail((current) => [
      ...current,
      {
        nodeId: item.opc_node_id,
        label: itemLabel,
        browsePath: item.browse_path ?? null,
      },
    ]);

    discoverMutation.mutate({
      nodeId: item.opc_node_id,
      label: itemLabel,
      browsePath: item.browse_path ?? null,
    });
  }

  const discoverMutation = useMutation<
    {
      discovered_count: number;
      variable_count: number;
      cache_upserts: number;
      message: string;
    },
    Error,
    DiscoverRequest
  >({
    mutationFn: ({ nodeId, label }) =>
      apiFetch(`/api/machines/${machineId}/browse-tags`, {
        method: "POST",
        body: JSON.stringify({
          max_nodes: 500,
          max_depth: 1,
          root_node_id: nodeId,
          root_label: label,
        }),
      }),
    onMutate: (variables) => beginOperation("discover", variables.label),
    onSuccess: async (result) => {
      resultRef.current = {
        success: true,
        message: `${result.message} ${result.discovered_count} nodes found${result.variable_count ? `, ${result.variable_count} variables` : ""}.`,
      };
      await queryClient.invalidateQueries({ queryKey: ["browse-cache", machineId] });
    },
    onError: (error) => {
      resultRef.current = { success: false, message: (error as Error).message };
    },
  });

  const addMutation = useMutation<{
    created_count: number;
    skipped_duplicates: number;
    created_tag_ids: number[];
    skipped_cache_ids: number[];
  }>({
    mutationFn: () =>
      apiFetch(`/api/machines/${machineId}/add-tags-from-cache`, {
        method: "POST",
        body: JSON.stringify({
          tags: selectedIds.map((cacheId) => ({ cache_id: cacheId })),
        }),
      }),
    onMutate: () => beginOperation("add", currentRoot.label),
    onSuccess: async (result) => {
      resultRef.current = {
        success: true,
        message: `Added ${result.created_count} tag${result.created_count === 1 ? "" : "s"} to Active Tags.`,
      };
      setSelectedIds([]);
      await queryClient.invalidateQueries({ queryKey: ["browse-cache", machineId] });
      await queryClient.invalidateQueries({ queryKey: ["tags", machineId] });
    },
    onError: (error) => {
      resultRef.current = { success: false, message: (error as Error).message };
    },
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

  useEffect(() => {
    if (operationState !== "running") {
      return;
    }
    let step2Timer: number | undefined;
    let step3Timer: number | undefined;
    let finishTimer: number | undefined;

    if (operationKind === "discover") {
      step2Timer = window.setTimeout(() => {
        setOperationStep(2);
        setOperationMessage(`Walking folders inside ${currentRoot.label}...`);
      }, 650);
      step3Timer = window.setTimeout(() => {
        setOperationStep(3);
        setOperationMessage("Building the folder and tag list...");
      }, 1250);
    } else {
      step2Timer = window.setTimeout(() => {
        setOperationStep(2);
        setOperationMessage("Saving the selected rows into Active Tags...");
      }, 650);
      step3Timer = window.setTimeout(() => {
        setOperationStep(3);
        setOperationMessage("Updating the active tag list...");
      }, 1250);
    }

    finishTimer = window.setTimeout(() => {
      const outcome = resultRef.current;
      if (!outcome) {
        setOperationState("error");
        setOperationStep(3);
        setOperationMessage("The action did not return a result.");
        setActionError("The action did not return a result.");
        return;
      }
      setOperationState(outcome.success ? "success" : "error");
      setOperationStep(3);
      setOperationMessage(outcome.message);
      if (!outcome.success) {
        setActionError(outcome.message);
      }
    }, 1900);

    return () => {
      if (step2Timer) {
        window.clearTimeout(step2Timer);
      }
      if (step3Timer) {
        window.clearTimeout(step3Timer);
      }
      if (finishTimer) {
        window.clearTimeout(finishTimer);
      }
    };
  }, [currentRoot.label, operationKind, operationState]);

  if (browseQuery.isError) {
    return <section className="page"><div className="panel error-text">{(browseQuery.error as Error).message}</div></section>;
  }

  const totalPages = Math.max(1, Math.ceil((browseQuery.data?.total ?? 0) / pageSize));
  const totalRows = browseQuery.data?.total ?? 0;
  const showActionsBelowTable = canClear || canAdd;
  const discoverButtonLabel = currentRoot.nodeId ? "Refresh Folder" : "Load Folders";

  return (
    <section className="page">
      {operationState !== "idle" ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="browse-operation-title">
          <div className={`modal-card modal-${operationState}`}>
            <div className="modal-header">
              <div>
                <div className="brand-kicker">{operationKind === "discover" ? "Browse Folders" : "Add Tags"}</div>
                <h3 id="browse-operation-title">
                  {operationState === "running"
                    ? operationKind === "discover"
                      ? "Reading the machine..."
                      : "Adding selected tags..."
                    : operationState === "success"
                      ? "Completed"
                      : "Needs Attention"}
                </h3>
                <p className="modal-lead">
                  {operationKind === "discover"
                    ? "This is read-only discovery. It only looks at the machine and builds the folder list."
                    : "This saves selected rows into the active tag list used by the collector."}
                </p>
              </div>
              <div className={`status-pill status-pill-${operationState}`}>
                {operationState === "running" ? "Working" : operationState === "success" ? "Done" : "Review"}
              </div>
            </div>
            <div className="modal-body">
              <div className={`modal-summary modal-summary-${operationState}`}>
                <div className="modal-summary-title">{operationMessage}</div>
                <div className="modal-summary-text">
                  {operationState === "success"
                    ? operationKind === "discover"
                      ? "Folders and tags are ready. Open folders to go deeper or add the rows you want."
                      : "Your selected tags are now in the active list."
                    : operationState === "error"
                      ? "Check the machine endpoint, folder path, or selected rows, then try again."
                      : "The steps below will move one by one so you can follow along."}
                </div>
              </div>
              <div className="step-grid">
                <div className={`step-card ${operationStep >= 1 ? "step-active" : ""}`}>
                  <div className="step-bullet">1</div>
                  <div>
                    <div className="step-title">{operationKind === "discover" ? "Connect to the machine" : "Prepare the selection"}</div>
                    <div className="step-subtitle">
                      {operationKind === "discover"
                        ? "Open the read-only OPC session for the folder you picked."
                        : "Gather the rows you selected and prepare them for the active list."}
                    </div>
                  </div>
                </div>
                <div className={`step-card ${operationStep >= 2 ? "step-active" : ""}`}>
                  <div className="step-bullet">2</div>
                  <div>
                    <div className="step-title">{operationKind === "discover" ? "Walk the folder tree" : "Save active tags"}</div>
                    <div className="step-subtitle">
                      {operationKind === "discover"
                        ? "Move through the selected folder and collect its children."
                        : "Write the selected rows into the live tag list the collector uses."}
                    </div>
                  </div>
                </div>
                <div
                  className={`step-card ${
                    operationStep >= 3 ? (operationState === "success" ? "step-done" : operationState === "error" ? "step-error" : "step-active") : ""
                  }`}
                >
                  <div className="step-bullet">3</div>
                  <div>
                    <div className="step-title">{operationKind === "discover" ? "Build the list" : "Refresh the tag view"}</div>
                    <div className="step-subtitle">
                      {operationKind === "discover"
                        ? "Populate the discovered folder rows so you can keep drilling down."
                        : "Refresh the active tag list after saving."}
                    </div>
                  </div>
                </div>
              </div>
              <div className="modal-actions">
                {operationState === "error" ? (
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => {
                      if (operationKind === "discover") {
                        discoverMutation.mutate({
                          nodeId: currentRoot.nodeId,
                          label: currentRoot.label,
                          browsePath: currentRoot.browsePath,
                        });
                      } else {
                        addMutation.mutate();
                      }
                    }}
                  >
                    Try Again
                  </button>
                ) : null}
                {operationState !== "running" ? (
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => {
                      setOperationState("idle");
                      setOperationKind(null);
                      setOperationStep(0);
                      setOperationMessage("");
                      resultRef.current = null;
                    }}
                  >
                    Continue
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="page-header">
        <div>
          <div className="brand-kicker">Step 1 of 2</div>
          <h2>Discover Tags</h2>
          <p className="page-lead">Load the machine, open folders one by one, then add the rows you want into Active Tags.</p>
        </div>
      </div>

      <div className="panel browse-discovery-panel">
        <div className="browse-discovery-copy">
          <div className="guide-title">Read the machine first</div>
          <div className="guide-text">
            Discovery is read-only. It does not write anything back to the PLC. Click a folder to open it, then keep going until tags appear.
          </div>
        </div>
        <div className="browse-discovery-actions">
          <button
            className="primary-button browse-discover-button"
            onClick={() =>
              discoverMutation.mutate({
                nodeId: currentRoot.nodeId,
                label: currentRoot.label,
                browsePath: currentRoot.browsePath,
              })
            }
            disabled={discoverMutation.isPending}
          >
            {discoverMutation.isPending ? "Loading..." : discoverButtonLabel}
          </button>
          <div className="browse-discovery-status">
            Current folder: <strong>{currentRoot.label}</strong>
          </div>
        </div>
      </div>

      <div className="panel machine-guide">
        <div className="guide-card">
          <div className="guide-title">1. Load</div>
          <div className="guide-text">Read the machine and show the top folders first.</div>
        </div>
        <div className="guide-card">
          <div className="guide-title">2. Open folders</div>
          <div className="guide-text">Click a plus to open a folder. Click it again to close it.</div>
        </div>
        <div className="guide-card">
          <div className="guide-title">3. Add</div>
          <div className="guide-text">Move the chosen rows into the active tag list used by the collector.</div>
        </div>
        <div className="guide-card">
          <div className="guide-title">Read-only</div>
          <div className="guide-text">Browsing only looks. It does not write back to the machine.</div>
        </div>
      </div>

      <div className="panel">
        {actionError ? <div className="error-text">{actionError}</div> : null}
        <div className="browse-summary">
          <div>
            <div className="browse-summary-label">Found</div>
            <div className="browse-summary-value">{totalRows} nodes</div>
          </div>
          <div>
            <div className="browse-summary-label">Selected</div>
            <div className="browse-summary-value">{selectedIds.length} rows</div>
          </div>
          <div>
            <div className="browse-summary-label">Current root</div>
            <div className="browse-summary-value">{currentRoot.label}</div>
          </div>
        </div>

        <div className="browse-breadcrumbs">
          {trail.map((step, index) => (
            <button
              key={`${step.label}-${index}`}
              type="button"
              className={`browse-breadcrumb ${index === trail.length - 1 ? "browse-breadcrumb-active" : ""}`}
              onClick={() => {
                setTrail((current) => current.slice(0, index + 1));
                setSelectedIds([]);
              }}
            >
              {step.label}
            </button>
          ))}
          {trail.length > 1 ? (
            <button
              type="button"
              className="browse-breadcrumb browse-breadcrumb-secondary"
              onClick={() => {
                setTrail((current) => current.slice(0, -1));
                setSelectedIds([]);
              }}
            >
              Up one level
            </button>
          ) : null}
        </div>

        {discoveredFolders.length ? (
          <div className="browse-folder-tray">
            <div className="browse-folder-label">Folders you can open</div>
            <div className="browse-folder-list">
              <button
                className={`browse-folder-chip ${currentRoot.nodeId === null ? "browse-folder-chip-active" : ""}`}
                type="button"
                onClick={() => {
                  setTrail([ROOT_TRAIL_ITEM]);
                  setSelectedIds([]);
                  setActionError(null);
                }}
              >
                {currentRoot.nodeId === null ? "−" : "+"} Root / Objects
              </button>
              {discoveredFolders.map((item) => (
                <button
                  key={item.opc_node_id}
                  className={`browse-folder-chip ${currentRoot.nodeId === item.opc_node_id ? "browse-folder-chip-active" : ""}`}
                  type="button"
                  onClick={() => navigateToFolder(item)}
                >
                  {currentRoot.nodeId === item.opc_node_id ? "−" : "+"} {getFolderLabel(item)}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {showBrowseSkeleton ? (
          <div className="browse-loading">
            <div className="browse-loading-header">
              <div className="browse-loading-title">Populating folders...</div>
              <div className="browse-loading-pill">Read-only</div>
            </div>
            <div className="browse-loading-text">
              The machine is being read now. First you will see folders, then you can open a folder to get to the tags.
            </div>
            <div className="browse-loading-tree" aria-hidden="true">
              <div className="browse-loading-node browse-loading-node-wide" />
              <div className="browse-loading-node browse-loading-node-medium" />
              <div className="browse-loading-node browse-loading-node-small" />
              <div className="browse-loading-node browse-loading-node-medium" />
              <div className="browse-loading-node browse-loading-node-wide" />
            </div>
          </div>
        ) : null}

        {!showBrowseSkeleton && totalRows === 0 ? (
          <div className="browse-empty">
            No folders or tags are shown yet. Click <strong>{discoverButtonLabel}</strong> to read the machine and start the folder tree.
          </div>
        ) : null}

        {!showBrowseSkeleton ? (
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
                    disabled={row.node_class !== "Variable"}
                    checked={selectedIds.includes(row.cache_id)}
                    onChange={(event) =>
                      setSelectedIds((current) =>
                        event.target.checked ? [...current, row.cache_id] : current.filter((id) => id !== row.cache_id),
                      )
                    }
                  />
                ),
              },
              {
                key: "browse_path",
                header: "Folder / Path",
                width: "280px",
                render: (row) =>
                  row.node_class !== "Variable" ? (
                    <button type="button" className="browse-path-button" onClick={() => navigateToFolder(row)}>
                      {currentRoot.nodeId === row.opc_node_id ? "−" : "+"} {row.browse_path ?? ""}
                    </button>
                  ) : (
                    <span>{row.browse_path ?? ""}</span>
                  ),
              },
              {
                key: "opc_node_id",
                header: "Node ID",
                width: "280px",
                render: (row) => <span className="mono-cell">{row.opc_node_id}</span>,
              },
              { key: "display_name", header: "Name", width: "160px", render: (row) => row.display_name ?? "" },
              { key: "browse_name", header: "Browse Name", width: "140px", render: (row) => row.browse_name ?? "" },
              { key: "node_class", header: "Class", width: "110px", render: (row) => row.node_class ?? "" },
              { key: "data_type", header: "Type", width: "110px", render: (row) => row.data_type ?? "" },
              { key: "already_added", header: "Already Added", width: "120px", render: (row) => String(row.already_added) },
            ]}
          />
        ) : null}

        {showActionsBelowTable ? (
          <div className="browse-footer-actions">
            <button className="primary-button" onClick={() => addMutation.mutate()} disabled={!canAdd || addMutation.isPending}>
              {addMutation.isPending ? "Adding..." : "Add Selected to Active Tags"}
            </button>
            <button className="ghost-button" onClick={() => clearMutation.mutate()} disabled={!canClear || clearMutation.isPending}>
              {clearMutation.isPending ? "Clearing..." : "Clear Cache"}
            </button>
          </div>
        ) : null}

        <div className="action-row">
          <button className="ghost-button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1}>
            Previous
          </button>
          <span>
            Page {page} / {totalPages}
          </span>
          <button className="ghost-button" onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={page >= totalPages}>
            Next
          </button>
          <select
            value={pageSize}
            onChange={(event) => {
              setPage(1);
              setPageSize(Number(event.target.value));
            }}
          >
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
