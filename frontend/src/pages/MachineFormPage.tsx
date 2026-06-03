import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiFetch } from "../api/client";
import type { Machine } from "../types/api";

type MachineFormValues = {
  machine_code: string;
  display_name: string;
  ip_address: string;
  port: number;
  opc_username: string;
  opc_password: string;
};

const initialForm: MachineFormValues = {
  machine_code: "",
  display_name: "",
  ip_address: "",
  port: 4840,
  opc_username: "",
  opc_password: "",
};

type ToastKind = "success" | "error" | "info";

type ToastItem = {
  id: number;
  kind: ToastKind;
  message: string;
};

type TestState = "idle" | "running" | "success" | "error";
type TestStep = 0 | 1 | 2 | 3;

function buildOpcEndpoint(ipAddress: string, port: number) {
  const trimmedIp = ipAddress.trim();
  return `opc.tcp://${trimmedIp}:${port}`;
}

function normalizeOptional(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

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
  const [prefilled, setPrefilled] = useState(false);
  const [connectionTested, setConnectionTested] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [testState, setTestState] = useState<TestState>("idle");
  const [testMessage, setTestMessage] = useState<string>("");
  const [testStep, setTestStep] = useState<TestStep>(0);
  const outcomeRef = useRef<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    if (!isEdit || !machineQuery.data || prefilled) {
      return;
    }
    setForm({
      machine_code: machineQuery.data.machine_code,
      display_name: machineQuery.data.display_name,
      ip_address: machineQuery.data.ip_address,
      port: machineQuery.data.port,
      opc_username: machineQuery.data.opc_username ?? "",
      opc_password: "",
    });
    setPrefilled(true);
  }, [isEdit, machineQuery.data, prefilled]);

  function pushToast(kind: ToastKind, message: string) {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((current) => [...current, { id, kind, message }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 4000);
  }

  const endpoint = buildOpcEndpoint(form.ip_address, form.port);
  const savedMachine = machineQuery.data;

  const createPayload = {
    machine_code: form.machine_code.trim(),
    display_name: form.display_name.trim(),
    ip_address: form.ip_address.trim(),
    port: form.port,
    opc_endpoint: endpoint,
    security_policy: null,
    security_mode: null,
    opc_username: normalizeOptional(form.opc_username),
    opc_password: normalizeOptional(form.opc_password),
    enabled: false,
    notes: null,
  };

  const updatePayload = {
    display_name: form.display_name.trim(),
    ip_address: form.ip_address.trim(),
    port: form.port,
    opc_endpoint: endpoint,
    security_policy: savedMachine?.security_policy ?? null,
    security_mode: savedMachine?.security_mode ?? null,
    opc_username: normalizeOptional(form.opc_username),
    opc_password: normalizeOptional(form.opc_password),
    enabled: savedMachine?.enabled ?? false,
    notes: savedMachine?.notes ?? null,
  };

  const saveMutation = useMutation({
    mutationFn: () =>
      isEdit
        ? apiFetch(`/api/machines/${machineId}`, { method: "PATCH", body: JSON.stringify(updatePayload) })
        : apiFetch("/api/machines", { method: "POST", body: JSON.stringify(createPayload) }),
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
            body: JSON.stringify(createPayload),
          }),
    onMutate: () => {
      setTestState("running");
      setTestStep(1);
      setTestMessage("Starting connection check...");
      outcomeRef.current = null;
    },
    onSuccess: (result) => {
      outcomeRef.current = { success: Boolean(result.success), message: result.message };
    },
    onError: (error) => {
      outcomeRef.current = { success: false, message: (error as Error).message || "Connection test failed." };
    },
  });

  useEffect(() => {
    if (testState !== "running") {
      return;
    }
    let step2Timer: number | undefined;
    let step3Timer: number | undefined;
    let finishTimer: number | undefined;

    step2Timer = window.setTimeout(() => {
      setTestStep(2);
      setTestMessage("Opening the OPC UA session...");
    }, 650);

    step3Timer = window.setTimeout(() => {
      setTestStep(3);
      setTestMessage("Checking read access and confirming it is safe to add...");
    }, 1250);

    finishTimer = window.setTimeout(() => {
      const outcome = outcomeRef.current;
      if (!outcome) {
        setTestState("error");
        setConnectionTested(false);
        setTestMessage("The connection test did not return a result.");
        pushToast("error", "The connection test did not return a result.");
        return;
      }
      setConnectionTested(outcome.success);
      setTestState(outcome.success ? "success" : "error");
      setTestMessage(outcome.message);
      pushToast(outcome.success ? "success" : "error", outcome.message);
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
  }, [testState]);

  function updateField<K extends keyof MachineFormValues>(field: K, value: MachineFormValues[K]) {
    setConnectionTested(false);
    setTestState("idle");
    setTestMessage("");
    setTestStep(0);
    setForm((current) => ({ ...current, [field]: value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!testMutation.isPending) {
      testMutation.mutate();
    }
  }

  const saveDisabled = !connectionTested || saveMutation.isPending;
  const testDisabled = testMutation.isPending;
  const showTestModal = testState !== "idle";

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <div className="brand-kicker">Machine Setup</div>
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
                <div className="brand-kicker">OPC Connection Check</div>
                <h3 id="machine-test-title">
                  {testState === "running" ? "Connecting..." : testState === "success" ? "Connection Verified" : "Connection Needs Attention"}
                </h3>
                <p className="modal-lead">
                  {testState === "success"
                    ? "The machine is reachable and ready to be added."
                    : testState === "error"
                      ? "Review the details below and try again."
                      : "We are checking the endpoint now."}
                </p>
              </div>
              <div className={`status-pill status-pill-${testState}`}>
                {testState === "success" ? "Ready" : testState === "error" ? "Review" : "Checking"}
              </div>
            </div>
            <div className="modal-body">
              <div className={`modal-summary modal-summary-${testState}`}>
                <div className="modal-summary-title">
                  {testState === "success" ? "Everything looks good." : testState === "error" ? "Something needs attention." : "Verifying connection details."}
                </div>
                <div className="modal-summary-text">{testMessage}</div>
              </div>

              <div className="step-grid">
                <div className={`step-card ${testState === "running" ? "step-active" : testState === "success" ? "step-done" : ""}`}>
                  <div className="step-bullet">1</div>
                  <div>
                    <div className="step-title">Open the machine</div>
                    <div className="step-subtitle">Use the IP address, port, and optional username you entered.</div>
                  </div>
                </div>
                <div className={`step-card ${testStep >= 2 ? (testState === "success" ? "step-done" : "step-active") : ""}`}>
                  <div className="step-bullet">2</div>
                  <div>
                    <div className="step-title">Confirm read access</div>
                    <div className="step-subtitle">The dashboard only checks that it can read safely. It does not write anything.</div>
                  </div>
                </div>
                <div className={`step-card ${testStep >= 3 ? (testState === "success" ? "step-done" : testState === "error" ? "step-error" : "step-active") : ""}`}>
                  <div className="step-bullet">3</div>
                  <div>
                    <div className="step-title">Ready to add</div>
                    <div className="step-subtitle">
                      {testState === "success"
                        ? "The Add Machine button is now available."
                        : "Fix the connection details and test again."}
                    </div>
                  </div>
                </div>
              </div>

              <div className="modal-actions">
                {testState === "error" ? (
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => {
                      setTestStep(0);
                      testMutation.mutate();
                    }}
                    disabled={testDisabled}
                  >
                    Retry Test
                  </button>
                ) : null}
                {testState === "success" ? (
                  <button className="primary-button" type="button" onClick={() => saveMutation.mutate()} disabled={saveDisabled}>
                    {saveMutation.isPending ? "Adding..." : isEdit ? "Save Machine" : "Add Machine"}
                  </button>
                ) : null}
                {testState !== "running" ? (
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => {
                      setTestState("idle");
                      setTestMessage("");
                      setTestStep(0);
                    }}
                  >
                    Edit Details
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <form className="panel machine-form-panel" onSubmit={handleSubmit} autoComplete="off">
        <div className="form-section">
          <div className="section-heading">
            <h3>Machine Details</h3>
            <p>Use a short code, a friendly name, and the machine IP address.</p>
          </div>
          <div className="form-grid">
            {!isEdit ? (
              <label>
                <span className="field-label">Machine Code</span>
                <span className="field-hint">Temporary code or short name, like Radius Code.</span>
                <input
                  type="text"
                  value={form.machine_code}
                  placeholder="Radius Code"
                  autoComplete="off"
                  spellCheck={false}
                  required
                  onChange={(event) => updateField("machine_code", event.target.value)}
                />
              </label>
            ) : (
              <div className="readonly-field">
                <span className="field-label">Machine Code</span>
                <div className="readonly-value">{savedMachine?.machine_code ?? "Loading..."}</div>
                <span className="field-hint">This code stays fixed after the machine is created.</span>
              </div>
            )}

            <label>
              <span className="field-label">Display Name</span>
              <span className="field-hint">Required. Example: Pinch 10.</span>
              <input
                type="text"
                value={form.display_name}
                placeholder="Pinch 10"
                autoComplete="off"
                spellCheck={false}
                required
                onChange={(event) => updateField("display_name", event.target.value)}
              />
            </label>

            <label>
              <span className="field-label">IP Address</span>
              <span className="field-hint">Example: 192.168.10.xxx.</span>
              <input
                type="text"
                value={form.ip_address}
                placeholder="192.168.10.xxx"
                autoComplete="off"
                spellCheck={false}
                required
                onChange={(event) => updateField("ip_address", event.target.value)}
              />
            </label>

            <label>
              <span className="field-label">Port</span>
              <span className="field-hint">Most machines use 4840.</span>
              <input
                type="number"
                value={form.port}
                min={1}
                max={65535}
                autoComplete="off"
                required
                onChange={(event) => updateField("port", Number(event.target.value) || 4840)}
              />
            </label>

            <div className="readonly-field field-wide">
              <span className="field-label">OPC UA Endpoint</span>
              <div className="readonly-value">{endpoint}</div>
              <span className="field-hint">Generated automatically from the IP address and port.</span>
            </div>
          </div>
        </div>

        <div className="form-section">
          <div className="section-heading">
            <h3>OPC Access</h3>
            <p>Leave username and password blank unless that machine requires them.</p>
          </div>
          <div className="form-grid">
            <label>
              <span className="field-label">OPC Username</span>
              <span className="field-hint">Optional. Some PLCs only need a username.</span>
              <input
                type="text"
                value={form.opc_username}
                placeholder="Optional"
                autoComplete="new-password"
                spellCheck={false}
                name="opc-username"
                onChange={(event) => updateField("opc_username", event.target.value)}
              />
            </label>

            <label>
              <span className="field-label">OPC Password</span>
              <span className="field-hint">Optional. Leave blank for username-only or open access.</span>
              <input
                type="password"
                value={form.opc_password}
                placeholder="Optional"
                autoComplete="new-password"
                name="opc-password"
                onChange={(event) => updateField("opc_password", event.target.value)}
              />
            </label>
          </div>
        </div>

        <div className="action-row">
          <button className="primary-button" type="submit" disabled={testDisabled}>
            {testMutation.isPending ? "Testing..." : "Test Connection"}
          </button>
        </div>
      </form>
    </section>
  );
}
