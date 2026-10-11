export type Step = { setpoint: number; duration_ms: number };
export type Recipe = { sample_rate_hz: number; seed: number; steps: Step[] };
export function recipeKey(recipe: Recipe) {
  return JSON.stringify([
    recipe.sample_rate_hz,
    recipe.seed,
    recipe.steps.map((step) => [step.setpoint, step.duration_ms]),
  ]);
}
export type Start = {
  command_id: string;
  name: string;
  recipe: Recipe;
  alpha: number;
  scenario?: string;
  recipe_version_id?: string | null;
};
export type RecipeVersion = {
  id: string;
  family_id: string;
  revision: number;
  parent_id: string | null;
  name: string;
  recipe: Recipe;
  alpha: number;
  created_at: string;
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
  source_utc?: string;
  received_utc?: string;
  device_elapsed_s?: number;
  replay_s?: number;
};
export type Run = {
  id: string;
  device_id?: string;
  boot_id?: string;
  recipe_id?: string;
  name?: string;
  execution: string;
  recording: string;
  reason: string;
  persisted_seq: number;
  final_seq: number | null;
  created_at: string;
  finished_at?: string;
  events_more?: boolean;
  snapshot?: {
    name: string;
    recipe: Recipe;
    filter: { alpha: number; version: string };
    engine_version: string;
    protocol_version: number;
    scenario?: string;
    recipe_version?: { id: string; family_id: string; revision: number };
    build?: string;
    model?: { version: string; tau_s: number; noise: string };
    channels?: { name: string; unit: string }[];
  };
  events?: RunEvent[];
};
export type RunEvent = {
  id: number;
  kind: string;
  created_at: string;
  detail: unknown;
  replay_s?: number;
};
export type ChartData = {
  points: Sample[];
  sample_count: number;
  method: string;
  recording: string;
};
export type RunSummary = {
  version: string;
  sample_count: number;
  missing_samples: number | null;
  raw_min: number | null;
  raw_max: number | null;
  raw_mean: number | null;
  raw_stddev: number | null;
  filtered_mean: number | null;
  filtered_stddev: number | null;
  reference_mean: number | null;
  last_logical_s: number | null;
};
export type ReplayData = {
  run: Run;
  summary: RunSummary;
  samples: Sample[];
  chart: Sample[];
  events: RunEvent[];
  events_truncated: boolean;
  duration_s: number;
  mode: string;
  clock: string;
};
let sessionGeneration = 0;
export function resetApiSession() {
  sessionGeneration++;
}
export async function downloadRun(
  runId: string,
  kind: "export.csv" | "metadata.json",
) {
  const generation = sessionGeneration;
  const response = await fetch(`/api/runs/${runId}/${kind}`);
  if (!response.ok) {
    if (response.status === 401 && generation === sessionGeneration)
      window.dispatchEvent(new Event("lab:sign-in-required"));
    const error = await response
      .json()
      .catch(() => ({ detail: "Download interrupted. Try again." }));
    throw new Error(error.detail || "Download could not be completed");
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `run-${runId}${kind === "export.csv" ? ".csv" : "-metadata.json"}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
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
