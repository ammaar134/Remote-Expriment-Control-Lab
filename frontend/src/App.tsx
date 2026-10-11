import { readable, navigate } from "./format";
import { Status } from "./RunStatus";
export { Status } from "./RunStatus";
import { RunEvidence } from "./RunEvidence";
import { Chart } from "./Chart";
import { RecipeLibrary } from "./RecipeLibrary";
import { ReviewWorkspace } from "./ReviewWorkspace";
import { useEffect, useRef, useState } from "react";
import {
  api,
  recipeKey,
  type Device,
  type Recipe,
  type Run,
  type Sample,
  type Start,
  type RecipeVersion,
  type ChartData,
} from "./api";
import {
  InstrumentSculpture,
  ArrowIcon,
  WaveMark,
} from "./InstrumentSculpture";

const defaults: Recipe = {
  sample_rate_hz: 50,
  seed: 7,
  steps: [
    { setpoint: 0.25, duration_ms: 10000 },
    { setpoint: 0.8, duration_ms: 10000 },
    { setpoint: 0.35, duration_ms: 10000 },
  ],
};
export function StopControl({
  device,
  busy,
  onStop,
}: {
  device: Device | null;
  busy: boolean;
  onStop: () => void;
}) {
  const available = device?.connected && device.observation.state === "RUNNING";
  return (
    <button
      className="stop-button"
      disabled={!available || busy}
      onClick={onStop}
    >
      <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12">
        <rect x="1" y="1" width="10" height="10" fill="currentColor" />
      </svg>{" "}
      {busy ? "Stop requested…" : "Stop experiment"}
    </button>
  );
}
export function App({
  onSignOut,
  signingOut = false,
}: { onSignOut?: () => void; signingOut?: boolean } = {}) {
  const [route, setRoute] = useState(
    window.location.hash.slice(1) || "configure",
  );
  const [routeView, selectedId] = route.split("/");
  const view = ["configure", "monitor", "review"].includes(routeView)
    ? routeView
    : "configure";
  const [device, setDevice] = useState<Device | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [recipe, setRecipe] = useState<Recipe>(defaults);
  const [name, setName] = useState("Stepped response");
  const [alpha, setAlpha] = useState(0.15);
  const [recipeVersion, setRecipeVersion] = useState<RecipeVersion | null>(
    null,
  );
  const [chartWindow, setChartWindow] = useState("all");
  const [scenario, setScenario] = useState("normal");
  const [error, setError] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const pending = useRef<Start | null>(null);
  const activeId =
    view === "monitor" ? selectedId || device?.observation.run_id : undefined;
  const recipeChanged =
    recipeVersion &&
    (recipeVersion.name !== name.trim() ||
      recipeVersion.alpha !== alpha ||
      recipeKey(recipeVersion.recipe) !== recipeKey(recipe));

  useEffect(() => {
    const change = () => setRoute(window.location.hash.slice(1) || "configure");
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    setConnectionError("");
    setError("");
    if (view === "review") return;
    async function refresh() {
      try {
        const [nextDevice, nextRuns] = await Promise.all([
          api<Device>("/device"),
          api<Run[]>("/runs"),
        ]);
        if (!cancelled) {
          setDevice(nextDevice);
          setRuns(nextRuns);
          setConnectionError("");
          if (nextDevice.observation.state !== "RUNNING") setStopping(false);
        }
      } catch {
        if (!cancelled) {
          setConnectionError(
            "Connection to the lab was interrupted. The device state is currently unknown.",
          );
          setDevice((previous) =>
            previous ? { ...previous, connected: false } : null,
          );
        }
      } finally {
        if (!cancelled) timer = setTimeout(refresh, 600);
      }
    }
    void refresh();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [view]);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let finished = false;
    setRun(null);
    setSamples([]);
    if (!activeId) return;
    async function refresh() {
      try {
        const detail = await api<Run>("/runs/" + activeId);
        const end =
          (detail.persisted_seq + 1) /
          (detail.snapshot?.recipe.sample_rate_hz || 50);
        const from =
          chartWindow === "all" ? 0 : Math.max(0, end - Number(chartWindow));
        const chart = await api<ChartData>(
          "/runs/" + activeId + "/chart?from_s=" + from,
        );
        if (!cancelled) {
          setRun(detail);
          setSamples(chart.points);
          finished = ["complete", "partial"].includes(detail.recording);
        }
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      } finally {
        if (!cancelled && !finished) timer = setTimeout(refresh, 600);
      }
    }
    void refresh();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [activeId, chartWindow]);

  const duration = recipe.steps.reduce(
    (sum, step) => sum + step.duration_ms / 1000,
    0,
  );
  const valid =
    name.trim().length > 0 &&
    duration > 0 &&
    duration <= 60 &&
    recipe.steps.every(
      (s) =>
        Number.isFinite(s.setpoint) &&
        s.setpoint >= 0 &&
        s.setpoint <= 1 &&
        s.duration_ms > 0 &&
        s.duration_ms % (1000 / recipe.sample_rate_hz) === 0,
    ) &&
    Number.isInteger(recipe.seed) &&
    recipe.seed > 0 &&
    recipe.seed <= 2147483647 &&
    alpha > 0 &&
    alpha <= 1;
  const ready =
    device?.connected &&
    !device.recovering &&
    !runs.some((item) => ["recording", "draining"].includes(item.recording)) &&
    ["IDLE", "STOPPED", "COMPLETED"].includes(device.observation.state);
  async function start() {
    if (starting) return;
    setStarting(true);
    setError("");
    pending.current ??= {
      command_id: crypto.randomUUID(),
      name: name.trim(),
      recipe,
      alpha,
      scenario,
      recipe_version_id: recipeVersion?.id || null,
    };
    try {
      const result = await api<{ run_id: string }>("/runs", pending.current);
      pending.current = null;
      navigate("monitor", result.run_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setStarting(false);
    }
  }
  async function stop() {
    if (stopping || !device?.observation.run_id) return;
    setStopping(true);
    setError("");
    try {
      await api("/runs/" + device.observation.run_id + "/stop", {
        command_id: crypto.randomUUID(),
      });
    } catch (err) {
      setError((err as Error).message);
      setStopping(false);
    }
  }
  async function reset() {
    setError("");
    try {
      await api("/device/reset", { command_id: crypto.randomUUID() });
    } catch (err) {
      setError((err as Error).message);
    }
  }
  function updateStep(
    index: number,
    key: "setpoint" | "duration_ms",
    value: number,
  ) {
    setRecipe((old) => ({
      ...old,
      steps: old.steps.map((s, i) =>
        i === index ? { ...s, [key]: value } : s,
      ),
    }));
    pending.current = null;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#configure">
          <span className="brand-mark">
            <WaveMark />
          </span>
          <span>
            Remote Experiment
            <b>Control Lab</b>
          </span>
        </a>
        <nav aria-label="Main navigation">
          {["configure", "monitor", "review"].map((item) => (
            <button
              key={item}
              className={view === item ? "nav-item active" : "nav-item"}
              aria-current={view === item ? "page" : undefined}
              onClick={() => navigate(item)}
            >
              {item[0].toUpperCase() + item.slice(1)}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="mini-dot" /> Simulation workspace
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            LAB / <b>{view.toUpperCase()}</b>
          </span>
          <span className={"connection " + (device?.connected ? "online" : "")}>
            <i />
            {view === "review"
              ? "Saved data · instrument not required"
              : device?.connected
                ? "Instrument connected"
                : "Instrument disconnected"}
          </span>
          {onSignOut && (
            <button
              className="sign-out"
              onClick={onSignOut}
              disabled={signingOut}
            >
              {signingOut ? "Signing out…" : "Sign out"}
            </button>
          )}
        </header>
        <div className="workspace">
          <div className="page-heading">
            <div>
              <h1>
                {view === "configure"
                  ? "Shape the experiment."
                  : view === "monitor"
                    ? "Follow the response."
                    : "Return to the evidence."}
              </h1>
              <p className="subtitle">
                {view === "configure"
                  ? "Set a recipe. Observe the signal. Keep the evidence."
                  : view === "monitor"
                    ? "Live measurements, observed execution, and durable recording."
                    : "Return to the exact configuration and measurements you recorded."}
              </p>
            </div>
            <span className="simulation-label">
              One instrument · Two channels
            </span>
          </div>
          {(error || connectionError) && (
            <div className="alert" role="alert">
              {error || connectionError}
            </div>
          )}
          {device?.error && !connectionError && (
            <div className="alert" role="status">
              {device.error}
            </div>
          )}
          {device?.observation.state === "FAULTED" && (
            <div className="alert">
              Instrument fault:{" "}
              {readable(device.observation.reason || "unknown")}.
              <button className="text-button" onClick={() => void reset()}>
                Acknowledge fault
              </button>
            </div>
          )}

          {view === "configure" && (
            <div className="configure-grid">
              <section className="panel recipe-panel">
                <div className="panel-title">
                  <div>
                    <h2>Experiment recipe</h2>
                    <p>A first-order response with seeded measurement noise.</p>
                  </div>
                </div>
                <label>
                  Recipe name
                  <input
                    value={name}
                    aria-invalid={!name.trim()}
                    aria-describedby={!name.trim() ? "name-error" : undefined}
                    maxLength={80}
                    onChange={(e) => {
                      setName(e.target.value);
                      pending.current = null;
                    }}
                  />
                </label>
                {!name.trim() && (
                  <p id="name-error" className="field-error">
                    Give this recipe a name.
                  </p>
                )}
                <RecipeLibrary
                  name={name}
                  recipe={recipe}
                  alpha={alpha}
                  selected={recipeVersion}
                  valid={valid}
                  onLoad={(version) => {
                    setRecipeVersion(version);
                    setName(version.name);
                    setRecipe(version.recipe);
                    setAlpha(version.alpha);
                    pending.current = null;
                  }}
                />
                <div className="field-row">
                  <label>
                    Sample rate
                    <select
                      value={recipe.sample_rate_hz}
                      onChange={(e) => {
                        setRecipe({
                          ...recipe,
                          sample_rate_hz: +e.target.value,
                        });
                        pending.current = null;
                      }}
                    >
                      {[10, 20, 25, 50, 100].map((rate) => (
                        <option value={rate} key={rate}>
                          {rate} Hz
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Random seed
                    <input
                      type="number"
                      min="1"
                      max="2147483647"
                      value={recipe.seed}
                      aria-invalid={
                        !Number.isInteger(recipe.seed) ||
                        recipe.seed < 1 ||
                        recipe.seed > 2147483647
                      }
                      aria-describedby="seed-note"
                      onChange={(e) => {
                        setRecipe({ ...recipe, seed: +e.target.value });
                        pending.current = null;
                      }}
                    />
                  </label>
                </div>
                <p className="field-note" id="seed-note">
                  Seed: a whole number from 1 to 2,147,483,647. The same recipe
                  and seed reproduce the simulated noise.
                </p>
                <div className="steps-heading">
                  <h3>Step sequence</h3>
                  <span>Normalized input · 0–1</span>
                </div>
                <div className="step-labels">
                  <span>STEP</span>
                  <span>SETPOINT (a.u.)</span>
                  <span>DURATION (s)</span>
                  <span />
                </div>
                {recipe.steps.map((step, index) => (
                  <div className="step-row" key={index}>
                    <span className="step-index">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <input
                      aria-label={"Step " + (index + 1) + " setpoint"}
                      type="number"
                      min="0"
                      max="1"
                      step="0.05"
                      value={step.setpoint}
                      aria-invalid={
                        !Number.isFinite(step.setpoint) ||
                        step.setpoint < 0 ||
                        step.setpoint > 1
                      }
                      aria-describedby="steps-note"
                      onChange={(e) =>
                        updateStep(index, "setpoint", +e.target.value)
                      }
                    />
                    <input
                      aria-label={"Step " + (index + 1) + " duration"}
                      type="number"
                      min="0.1"
                      max="60"
                      step="0.1"
                      value={step.duration_ms / 1000}
                      aria-invalid={
                        step.duration_ms <= 0 ||
                        step.duration_ms % (1000 / recipe.sample_rate_hz) !== 0
                      }
                      aria-describedby="steps-note"
                      onChange={(e) =>
                        updateStep(
                          index,
                          "duration_ms",
                          Math.round(+e.target.value * 1000),
                        )
                      }
                    />
                    <button
                      aria-label={"Remove step " + (index + 1)}
                      className="remove-step"
                      disabled={recipe.steps.length === 1}
                      onClick={() => {
                        setRecipe({
                          ...recipe,
                          steps: recipe.steps.filter((_, i) => i !== index),
                        });
                        pending.current = null;
                      }}
                    >
                      <svg
                        aria-hidden="true"
                        width="16"
                        height="16"
                        viewBox="0 0 16 16"
                        fill="none"
                      >
                        <path
                          d="m4 4 8 8M12 4l-8 8"
                          stroke="currentColor"
                          strokeWidth="1.5"
                        />
                      </svg>
                    </button>
                  </div>
                ))}
                <button
                  className="text-button add-step"
                  disabled={recipe.steps.length === 8}
                  onClick={() => {
                    setRecipe({
                      ...recipe,
                      steps: [
                        ...recipe.steps,
                        { setpoint: 0.5, duration_ms: 1000 },
                      ],
                    });
                    pending.current = null;
                  }}
                >
                  Add a step
                </button>
                <p className="field-note" id="steps-note">
                  Use setpoints from 0 to 1 and positive durations aligned to{" "}
                  {1000 / recipe.sample_rate_hz} ms samples. Total duration must
                  be 60 seconds or less.
                </p>
                <label className="filter-label">
                  EMA smoothing <span>{alpha.toFixed(2)}</span>
                  <input
                    type="range"
                    min="0.01"
                    max="1"
                    step="0.01"
                    value={alpha}
                    onChange={(e) => {
                      setAlpha(+e.target.value);
                      pending.current = null;
                    }}
                  />
                  <small>
                    Lower values reduce noise and respond more slowly.
                  </small>
                </label>
              </section>
              <div className="configure-side">
                <section className="instrument-card">
                  <label className="instrument-picker">
                    Instrument
                    <select value="sim-01" onChange={() => undefined}>
                      <option value="sim-01">
                        Response simulator · sim-01
                      </option>
                    </select>
                  </label>
                  <div className="instrument-top">
                    <h2>Response simulator</h2>
                    <span className="mini-label">SIM-01</span>
                  </div>
                  <InstrumentSculpture />
                  <p className="sculpture-caption">
                    Signal model · illustrative geometry
                  </p>
                  <div className="instrument-state">
                    <span>Observed state</span>
                    <Status
                      state={
                        device?.connected ? device.observation.state : "UNKNOWN"
                      }
                    />
                  </div>
                </section>
                <section className="panel launch-panel">
                  <h2>Ready to observe</h2>
                  <div className="run-numbers">
                    <div>
                      <strong>
                        {duration.toFixed(1)}
                        <small>s</small>
                      </strong>
                      <span>Duration</span>
                    </div>
                    <div>
                      <strong>
                        {Math.round(
                          duration * recipe.sample_rate_hz,
                        ).toLocaleString()}
                      </strong>
                      <span>Expected samples</span>
                    </div>
                  </div>
                  <div
                    className="recipe-preview"
                    aria-label="Recipe setpoint preview"
                  >
                    {recipe.steps.map((s, i) => (
                      <div key={i} style={{ flex: s.duration_ms }}>
                        <span
                          style={{
                            height: Math.max(0, Math.min(1, s.setpoint)) * 45,
                          }}
                        />
                        <small>{s.setpoint.toFixed(2)}</small>
                      </div>
                    ))}
                  </div>
                  {!valid && (
                    <p className="validation" role="status">
                      Use bounded values and whole sample periods; maximum total
                      duration is 60 seconds.
                    </p>
                  )}
                  {!ready && (
                    <p className="hint">
                      Start becomes available when the connected instrument is
                      ready.
                    </p>
                  )}
                  {recipeChanged && (
                    <p className="validation">
                      Save a new recipe version before starting with these
                      changes.
                    </p>
                  )}
                  <button
                    className="primary-button"
                    onClick={() => void start()}
                    disabled={!valid || !ready || starting || !!recipeChanged}
                  >
                    {starting
                      ? "Starting…"
                      : pending.current
                        ? "Retry the same Start"
                        : "Start experiment"}
                    <ArrowIcon />
                  </button>
                  <p className="fine-print">
                    Configuration is saved before Start is sent.
                  </p>
                </section>
                {device?.faults_enabled && (
                  <section className="fault-panel">
                    <details>
                      <summary>
                        Failure demonstrations <span>Local simulation</span>
                      </summary>
                      <p>
                        The scenario is saved with the recipe. It affects only
                        this simulated run.
                      </p>
                      <label htmlFor="failure-scenario">Scenario</label>
                      <select
                        id="failure-scenario"
                        value={scenario}
                        onChange={(event) => {
                          setScenario(event.target.value);
                          pending.current = null;
                        }}
                      >
                        <option value="normal">Normal acquisition</option>
                        <option value="lost_start_ack">
                          Lose the first Start reply
                        </option>
                        <option value="telemetry_reconnect">
                          Interrupt telemetry for one second
                        </option>
                        <option value="controller_disconnect">
                          Disconnect the controller
                        </option>
                        <option value="database_write_failure">
                          Roll back one database write
                        </option>
                      </select>
                    </details>
                  </section>
                )}
              </div>
            </div>
          )}

          {view === "monitor" && (
            <>
              <div className="monitor-bar">
                <div>
                  <h2>{run ? "Recorded execution" : "Observed instrument"}</h2>
                  <Status
                    state={
                      run?.execution ||
                      (device?.connected ? device.observation.state : "UNKNOWN")
                    }
                    recording={run?.recording}
                    finalSeq={run?.final_seq}
                    persistedSeq={run?.persisted_seq}
                  />
                </div>
                <StopControl
                  device={
                    activeId && device?.observation.run_id !== activeId
                      ? null
                      : device
                  }
                  busy={stopping}
                  onStop={() => void stop()}
                />
              </div>
              {(!device?.connected || (device.observation_age_s ?? 99) > 2) && (
                <div className="alert">
                  Observations are stale. Execution cannot be confirmed from
                  this screen.
                </div>
              )}
              <section className="panel signal-panel">
                <div className="signal-heading">
                  <div>
                    <h2>{run?.snapshot?.name || "Live response"}</h2>
                    <p>
                      {run
                        ? "Run " +
                          run.id.slice(0, 8) +
                          " · logical elapsed time"
                        : "Start an experiment from Configure."}
                    </p>
                  </div>
                  <span className="mini-label">RAW + FILTERED</span>
                </div>
                <label className="chart-window">
                  Chart window
                  <select
                    value={chartWindow}
                    onChange={(event) => setChartWindow(event.target.value)}
                  >
                    <option value="all">Full run</option>
                    <option value="10">Last 10 seconds</option>
                    <option value="5">Last 5 seconds</option>
                  </select>
                </label>
                <Chart samples={samples} />
                <div className="signal-footer">
                  <span>
                    {(run?.persisted_seq ?? -1) + 1} committed samples
                  </span>
                  <span>
                    Final sequence: {run?.final_seq ?? "not yet known"}
                  </span>
                  <span>
                    Output:{" "}
                    {device?.observation.output?.toFixed(2) ?? "unknown"} a.u.
                  </span>
                </div>
              </section>
              {device && (
                <section
                  className="diagnostics"
                  aria-label="Recording diagnostics"
                >
                  <div>
                    <span>Retained on device</span>
                    <strong>
                      {device.observation.retained_samples ?? "—"}{" "}
                      <small>
                        / {device.observation.retention_capacity ?? 512}
                      </small>
                    </strong>
                  </div>
                  <div>
                    <span>Commit acknowledged</span>
                    <strong>
                      {device.observation.acknowledged_seq ?? "—"}
                      <small> sequence</small>
                    </strong>
                  </div>
                  <div>
                    <span>Command retries</span>
                    <strong>{device.diagnostics?.command_retries ?? 0}</strong>
                  </div>
                  <div>
                    <span>Data reconnects</span>
                    <strong>
                      {device.diagnostics?.telemetry_reconnects ?? 0}
                    </strong>
                  </div>
                </section>
              )}
              {run && <RunEvidence run={run} />}
            </>
          )}

          {view === "review" && <ReviewWorkspace selectedId={selectedId} />}
          <footer className="workspace-footer">
            <span>Simulated measurements · No physical actuation</span>
            <span>Control / Observe / Understand</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
