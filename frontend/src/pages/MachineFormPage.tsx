import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiFetch } from "../api/client";
import type { Machine } from "../types/api";

const initialForm = {
  machine_code: "",
  display_name: "",
  ip_address: "",
  port: 4840,
  opc_endpoint: "",
  security_policy: "",
  security_mode: "",
  opc_username: "",
  opc_password: "",
  enabled: false,
  notes: "",
};

type ToastKind = "success" | "error" | "info";

type ToastItem = {
  id: number;
  kind: ToastKind;
  message: string;
};

type TestState = "idle" | "running" | "success" | "error";

export function MachineFormPage(): JSX.Element {
  const { machineId } = useParams();
  const isEdit = Boolean(machineId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const machineQuery = useQuery({
    queryKey: ["machine", machineId],
    queryFn: () => apiFetch<Machine>(`/api/machines/${machineId}`),
    enabled: isEdit,
  });
  const [form, setForm] = useState(initialForm);
  const [connectionTested, setConnectionTested] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [testState, setTestState] = useState<TestState>("idle");
  const [testMessage, setTestMessage] = useState<string>("");

  function pushToast(kind: ToastKind, message: string) {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((current) => [...current, { id, kind, message }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 4000);
  }

  const effectiveForm = useMemo(() => {
    if (machineQuery.data && isEdit) {
      return {
        ...form,
        machine_code: form.machine_code || machineQuery.data.machine_code,
        display_name: form.display_name || machineQuery.data.display_name,
        ip_address: form.ip_address || machineQuery.data.ip_address,
        port: form.port || machineQuery.data.port,
        opc_endpoint: form.opc_endpoint || machineQuery.data.opc_endpoint,
        security_policy: form.security_policy || machineQuery.data.security_policy || "",
        security_mode: form.security_mode || machineQuery.data.security_mode || "",
        opc_username: form.opc_username || machineQuery.data.opc_username || "",
        enabled: form.enabled || machineQuery.data.enabled,
        notes: form.notes || machineQuery.data.notes || "",
      };
    }
    return form;
  }, [form, isEdit, machineQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      isEdit
        ? apiFetch(`/api/machines/${machineId}`, { method: "PATCH", body: JSON.stringify(effectiveForm) })
        : apiFetch("/api/machines", { method: "POST", body: JSON.stringify(effectiveForm) }),
    onSuccess: async () => {
      pushToast("success", "Machine saved.");
      await queryClient.invalidateQueries({ queryKey: ["machines"] });
      window.setTimeout(() => {
        navigate("/machines");
      }, 350);
    },
    onError: (error) => {
      pushToast("error", (error as Error).message || "Failed to save machine.");
    },
  });

  const testMutation = useMutation({
    mutationFn: () =>
      isEdit
        ? apiFetch<{ success: boolean; message: string }>(`/api/machines/${machineId}/test-connection`, {
            method: "POST",
          })
        : apiFetch<{ success: boolean; message: string }>("/api/machines/test-connection", {
            method: "POST",
            body: JSON.stringify(effectiveForm),
          }),
    onMutate: () => {
      setTestState("running");
      setTestMessage("Connecting to OPC UA machine...");
    },
    onSuccess: (result) => {
      setConnectionTested(Boolean(result.success));
      setTestState(result.success ? "success" : "error");
      setTestMessage(result.message);
      pushToast(result.success ? "success" : "error", result.message);
    },
    onError: (error) => {
      setConnectionTested(false);
      setTestState("error");
      setTestMessage((error as Error).message || "Connection test failed.");
      pushToast("error", (error as Error).message || "Connection test failed.");
    },
  });

  function recomputeEndpoint(ipAddress: string, port: number) {
    return `opc.tcp://${ipAddress}:${port}`;
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate();
  }

  const saveDisabled = !connectionTested || saveMutation.isPending;
  const testDisabled = testMutation.isPending;
  const showTestModal = testState !== "idle";

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="brand-kicker">Machine Config</div>
          <h2>{isEdit ? "Edit Machine" : "Add Machine"}</h2>
        </div>
        <Link className="ghost-button" to="/machines">
          Back
        </Link>
      </div>
      <div className="toast-stack" aria-live="polite" aria-atomic="true">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.kind}`}>
            {toast.message}
          </div>
        ))}
      </div>
      {showTestModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="machine-test-title">
          <div className={`modal-card modal-${testState}`}>
            <div className="modal-header">
              <div>
                <div className="brand-kicker">OPC Connection Test</div>
                <h3 id="machine-test-title">
                  {testState === "running" ? "Connecting..." : testState === "success" ? "Connection Ready" : "Connection Failed"}
                </h3>
              </div>
              <button
                className="ghost-button"
                type="button"
                onClick={() => {
                  if (testState !== "running") {
                    setTestState("idle");
                  }
                }}
                disabled={testState === "running"}
              >
                {testState === "running" ? "Working..." : "Close"}
              </button>
            </div>
            <div className="modal-body">
              <ol className="step-list">
                <li className={testState === "running" ? "step-active" : testState === "success" ? "step-done" : ""}>
                  Open OPC UA session
                </li>
                <li className={testState === "running" ? "step-active" : testState === "success" ? "step-done" : ""}>
                  Check root browse/read access
                </li>
                <li className={testState === "success" ? "step-done" : testState === "error" ? "step-error" : ""}>
                  Verify the machine is safe to add
                </li>
              </ol>
              <div className={`modal-message modal-message-${testState}`}>{testMessage}</div>
              {testState === "success" ? (
                <div className="modal-next">
                  Connection verified. You can now add the machine and save it.
                </div>
              ) : null}
              {testState === "error" ? (
                <div className="modal-next">
                  Fix the endpoint, credentials, or security settings, then run the test again.
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
      <form className="panel form-grid" onSubmit={handleSubmit} autoComplete="off">
        <label>
          machine_code
          <input
            type="text"
            value={effectiveForm.machine_code}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => {
              setConnectionTested(false);
              setForm((current) => ({ ...current, machine_code: event.target.value }));
            }}
          />
        </label>
        <label>
          display_name
          <input
            type="text"
            value={effectiveForm.display_name}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => {
              setConnectionTested(false);
              setForm((current) => ({ ...current, display_name: event.target.value }));
            }}
          />
        </label>
        <label>
          ip_address
          <input
            type="text"
            value={effectiveForm.ip_address}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => {
              const ip_address = event.target.value;
              setConnectionTested(false);
              setForm((current) => ({
                ...current,
                ip_address,
                opc_endpoint: recomputeEndpoint(ip_address, current.port),
              }));
            }}
          />
        </label>
        <label>
          port
          <input
            type="number"
            value={effectiveForm.port}
            autoComplete="off"
            onChange={(event) => {
              const port = Number(event.target.value);
              setConnectionTested(false);
              setForm((current) => ({
                ...current,
                port,
                opc_endpoint: recomputeEndpoint(current.ip_address, port),
              }));
            }}
          />
        </label>
        <label>
          opc_endpoint
          <input
            type="text"
            value={effectiveForm.opc_endpoint}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => {
              setConnectionTested(false);
              setForm((current) => ({ ...current, opc_endpoint: event.target.value }));
            }}
          />
        </label>
        <label>
          security_policy
          <input
            type="text"
            value={effectiveForm.security_policy}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => {
              setConnectionTested(false);
              setForm((current) => ({ ...current, security_policy: event.target.value }));
            }}
          />
        </label>
        <label>
          security_mode
          <input
            type="text"
            value={effectiveForm.security_mode}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => {
              setConnectionTested(false);
              setForm((current) => ({ ...current, security_mode: event.target.value }));
            }}
          />
        </label>
        <label>
          opc_username
          <input
            type="text"
            value={effectiveForm.opc_username}
            autoComplete="new-password"
            spellCheck={false}
            name="opc-username"
            onChange={(event) => {
              setConnectionTested(false);
              setForm((current) => ({ ...current, opc_username: event.target.value }));
            }}
          />
        </label>
        <label>
          opc_password
          <input
            type="password"
            value={effectiveForm.opc_password}
            autoComplete="new-password"
            name="opc-password"
            onChange={(event) => {
              setConnectionTested(false);
              setForm((current) => ({ ...current, opc_password: event.target.value }));
            }}
          />
        </label>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={effectiveForm.enabled}
            onChange={(event) => {
              setConnectionTested(false);
              setForm((current) => ({ ...current, enabled: event.target.checked }));
            }}
          />
          enabled
        </label>
        <label>
          notes
          <input
            type="text"
            value={effectiveForm.notes}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => {
              setConnectionTested(false);
              setForm((current) => ({ ...current, notes: event.target.value }));
            }}
          />
        </label>
        <div className="action-row">
          <button className="ghost-button" type="button" onClick={() => testMutation.mutate()} disabled={testDisabled}>
            {testMutation.isPending ? "Testing..." : "Test Connection"}
          </button>
          <button className="primary-button" type="submit" disabled={saveDisabled}>
            Save
          </button>
          {connectionTested ? <span>Connection verified</span> : <span>Test connection before saving.</span>}
        </div>
      </form>
    </section>
  );
}
