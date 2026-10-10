export type Step = { setpoint: number; duration_ms: number };
export type Recipe = { sample_rate_hz: number; seed: number; steps: Step[] };
export type Start = {
  command_id: string;
  name: string;
  recipe: Recipe;
  alpha: number;
  scenario?: string;
};
export type Device = {
  id: string;
  name: string;
  connected: boolean;
  boot_id: string;
  error: string;
  observation_age_s: number | null;
  recovering?: boolean;
  faults_enabled?: boolean;
  diagnostics?: { command_retries: number; telemetry_reconnects: number };
  observation: {
    state: string;
    run_id: string;
    final_seq: number;
    output: number | null;
    reason: string;
    retained_samples?: number;
    retention_capacity?: number;
    acknowledged_seq?: number;
    telemetry_ready?: boolean;
  };
};
export type Sample = {
  seq: number;
  logical_s: number;
  setpoint: number;
  response: number;
  reference: number;
  filtered: number;
};
export type Run = {
  id: string;
  name?: string;
  execution: string;
  recording: string;
  reason: string;
  persisted_seq: number;
  final_seq: number | null;
  created_at: string;
  snapshot?: {
    name: string;
    recipe: Recipe;
    filter: { alpha: number; version: string };
    engine_version: string;
    protocol_version: number;
    scenario?: string;
  };
  events?: { id: number; kind: string; created_at: string; detail: unknown }[];
};
let sessionGeneration = 0;
export function resetApiSession() {
  sessionGeneration++;
}
export async function api<T>(path: string, payload?: unknown): Promise<T> {
  const generation = sessionGeneration;
  const response = await fetch(
    "/api" + path,
    payload === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
  );
  if (!response.ok) {
    if (response.status === 401 && generation === sessionGeneration) {
      window.dispatchEvent(new Event("lab:sign-in-required"));
    }
    const error = await response
      .json()
      .catch(() => ({ detail: "The server could not be reached" }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "Check the recipe values and try again",
    );
  }
  return response.json() as Promise<T>;
}
