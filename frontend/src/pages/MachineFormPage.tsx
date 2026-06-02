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
      await queryClient.invalidateQueries({ queryKey: ["machines"] });
      navigate("/machines");
    },
  });

  const testMutation = useMutation({
    mutationFn: () =>
      apiFetch<{ success: boolean; message: string }>(`/api/machines/${machineId}/test-connection`, { method: "POST" }),
  });

  function recomputeEndpoint(ipAddress: string, port: number) {
    return `opc.tcp://${ipAddress}:${port}`;
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate();
  }

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
      <form className="panel form-grid" onSubmit={handleSubmit}>
        {Object.entries(effectiveForm).map(([key, value]) =>
          key === "enabled" ? (
            <label key={key} className="checkbox-row">
              <input
                type="checkbox"
                checked={Boolean(value)}
                onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.checked }))}
              />
              Enabled
            </label>
          ) : (
            <label key={key}>
              {key}
              <input
                type={key === "port" ? "number" : key === "opc_password" ? "password" : "text"}
                value={String(value)}
                onChange={(event) => {
                  const nextValue = key === "port" ? Number(event.target.value) : event.target.value;
                  setForm((current) => {
                    const updated = { ...current, [key]: nextValue };
                    if (key === "ip_address" || key === "port") {
                      updated.opc_endpoint = recomputeEndpoint(
                        key === "ip_address" ? String(nextValue) : updated.ip_address,
                        key === "port" ? Number(nextValue) : updated.port,
                      );
                    }
                    return updated;
                  });
                }}
              />
            </label>
          ),
        )}
        <div className="action-row">
          <button className="primary-button" type="submit">
            Save
          </button>
          {isEdit ? (
            <button className="ghost-button" type="button" onClick={() => testMutation.mutate()}>
              Test Connection
            </button>
          ) : null}
          {testMutation.data ? <span>{testMutation.data.message}</span> : null}
        </div>
      </form>
    </section>
  );
}
