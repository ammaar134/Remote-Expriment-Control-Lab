import { useEffect, useRef, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  api,
  type Device,
  type Recipe,
  type Run,
  type Sample,
  type Start,
} from "./api";

const defaults: Recipe = {
  sample_rate_hz: 50,
  seed: 7,
  steps: [
    { setpoint: 0.25, duration_ms: 10000 },
    { setpoint: 0.8, duration_ms: 10000 },
    { setpoint: 0.35, duration_ms: 10000 },
  ],
};
const readable = (text: string) => text.toLowerCase().replaceAll("_", " ");
const time = (value: string) =>
  new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
function navigate(view: string, id?: string) {
  window.location.hash = view + (id ? "/" + id : "");
}

export function Status({
  state,
  recording,
}: {
  state: string;
  recording?: string;
}) {
  return (
    <div className="status-pair">
      <span className={"pill " + state.toLowerCase()}>{readable(state)}</span>
      {recording && (
        <span className={"pill recording-" + recording}>
          Data: {readable(recording)}
        </span>
      )}
    </div>
  );
}
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
      <span aria-hidden="true">■</span>{" "}
      {busy ? "Stop requested…" : "Stop experiment"}
    </button>
  );
}
function SignalChart({ samples }: { samples: Sample[] }) {
  // Display at most 1000 points, retaining a recent tail. Raw records stay in PostgreSQL.
  const stride = Math.max(1, Math.ceil(samples.length / 1000));
  const display = samples.filter(
    (_, index) => index % stride === 0 || index === samples.length - 1,
  );
  return (
    <div
      className="chart"
      role="img"
      aria-label={
        samples.length
          ? "Raw response, filtered response and reference over logical time"
          : "Chart awaiting recorded samples"
      }
    >
      {samples.length ? (
        <ResponsiveContainer width="100%" height={290} minWidth={0}>
          <LineChart
            data={display}
            margin={{ top: 12, right: 16, left: 0, bottom: 4 }}
          >
            <CartesianGrid
              strokeDasharray="3 5"
              vertical={false}
              stroke="#e2e8e6"
            />
            <XAxis
              dataKey="logical_s"
              type="number"
              domain={[0, "dataMax"]}
              tickFormatter={(v) => Number(v).toFixed(0) + "s"}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[-0.1, 1.1]}
              width={42}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              labelFormatter={(v) =>
                "Logical time: " + Number(v).toFixed(2) + " s"
              }
            />
            <Legend iconType="plainline" />
            <Line
              dataKey="response"
              name="Raw response (a.u.)"
              stroke="#96bbb0"
              dot={false}
              strokeWidth={1}
              isAnimationActive={false}
            />
            <Line
              dataKey="filtered"
              name="EMA (a.u.)"
              stroke="#087f6b"
              dot={false}
              strokeWidth={2.5}
              isAnimationActive={false}
            />
            <Line
              dataKey="reference"
              name="Reference (a.u.)"
              stroke="#d59c49"
              dot={false}
              strokeWidth={1.3}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="chart-empty">
          <span className="wave">∿</span>
          <strong>Ready for a response</strong>
          <p>Recorded measurements will appear here when a run starts.</p>
        </div>
      )}
    </div>
  );
}

export function App() {
  const [route, setRoute] = useState(
    window.location.hash.slice(1) || "configure",
  );
  const [view, selectedId] = route.split("/");
  const [device, setDevice] = useState<Device | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [recipe, setRecipe] = useState<Recipe>(defaults);
  const [name, setName] = useState("Stepped response");
  const [alpha, setAlpha] = useState(0.15);
  const [error, setError] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const pending = useRef<Start | null>(null);
  const activeId =
    selectedId || (view === "monitor" ? device?.observation.run_id : undefined);

  useEffect(() => {
    const change = () => setRoute(window.location.hash.slice(1) || "configure");
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
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
  }, []);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let after = -1;
    setRun(null);
    setSamples([]);
    if (!activeId) return;
    async function refresh() {
      try {
        const [detail, points] = await Promise.all([
          api<Run>("/runs/" + activeId),
          api<Sample[]>("/runs/" + activeId + "/samples?after=" + after),
        ]);
        if (!cancelled) {
          setRun(detail);
          if (points.length) {
            after = points[points.length - 1].seq;
            setSamples((old) => [...old, ...points].slice(-6000));
          }
        }
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      } finally {
        if (!cancelled) timer = setTimeout(refresh, 600);
      }
    }
    void refresh();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [activeId]);

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
          <span className="brand-mark">∿</span>
          <span>
            EXPERIMENT
            <br />
            <b>CONTROL LAB</b>
          </span>
        </a>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          {["configure", "monitor", "review"].map((item, index) => (
            <button
              key={item}
              className={view === item ? "nav-item active" : "nav-item"}
              onClick={() => navigate(item)}
            >
              <span className="nav-number">0{index + 1}</span>
              {item[0].toUpperCase() + item.slice(1)}
              <span className="nav-arrow">↗</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="mini-dot" /> LOCAL SIMULATION
          <p>
            A small window into the signals.
            <br />
            No physical equipment connected.
          </p>
        </div>
        <div className="sidebar-footer">
          ONE INSTRUMENT
          <br />
          <span>Build 0.1 / Phase 1</span>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            LAB / <b>{view.toUpperCase()}</b>
          </span>
          <span className={"connection " + (device?.connected ? "online" : "")}>
            <i />
            {device?.connected
              ? "Instrument connected"
              : "Instrument disconnected"}
          </span>
        </header>
        <div className="workspace">
          <div className="page-heading">
            <div>
              <p className="eyebrow">REMOTE EXPERIMENT CONTROL</p>
              <h1>
                {view === "configure"
                  ? "Make a little discovery."
                  : view === "monitor"
                    ? "Follow the response."
                    : "Every run tells a story."}
              </h1>
              <p className="subtitle">
                {view === "configure"
                  ? "Set a recipe. Observe the signal. Keep the evidence."
                  : view === "monitor"
                    ? "Live measurements, observed execution, and durable recording."
                    : "Return to the exact configuration and measurements you recorded."}
              </p>
            </div>
            <span className="simulation-label">SIMULATED / a.u.</span>
          </div>
          {(error || connectionError) && (
            <div className="alert" role="alert">
              {error || connectionError}
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
                  <span className="section-index">01</span>
                  <div>
                    <h2>Experiment recipe</h2>
                    <p>A first-order response with seeded measurement noise.</p>
                  </div>
                </div>
                <label>
                  Recipe name
                  <input
                    value={name}
                    maxLength={80}
                    onChange={(e) => {
                      setName(e.target.value);
                      pending.current = null;
                    }}
                  />
                </label>
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
                      onChange={(e) => {
                        setRecipe({ ...recipe, seed: +e.target.value });
                        pending.current = null;
                      }}
                    />
                  </label>
                </div>
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
                      ×
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
                  + Add a step
                </button>
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
                  <div className="instrument-top">
                    <span className="chip-icon">⌁</span>
                    <span className="mini-label">SIM-01</span>
                  </div>
                  <h2>Response simulator</h2>
                  <p>
                    Two channels. One reproducible signal.
                    <br />
                    An intentionally simple instrument.
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
                  <p className="eyebrow">RUN PREVIEW</p>
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
                          style={{ height: Math.max(4, s.setpoint * 90) }}
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
                  <button
                    className="primary-button"
                    onClick={() => void start()}
                    disabled={!valid || !ready || starting}
                  >
                    {starting
                      ? "Starting…"
                      : pending.current
                        ? "Retry the same Start"
                        : "Start experiment"}
                    <span>↗</span>
                  </button>
                  <p className="fine-print">
                    Configuration is saved before Start is sent.
                  </p>
                </section>
              </div>
            </div>
          )}

          {view === "monitor" && (
            <>
              <div className="monitor-bar">
                <div>
                  <span className="eyebrow">OBSERVED INSTRUMENT</span>
                  <Status
                    state={
                      device?.connected ? device.observation.state : "UNKNOWN"
                    }
                    recording={run?.recording}
                  />
                </div>
                <StopControl
                  device={device}
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
                <SignalChart samples={samples} />
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
              {run && <RunEvidence run={run} />}
            </>
          )}

          {view === "review" && (
            <div className="review-grid">
              <section className="panel history">
                <div className="panel-title">
                  <h2>Recorded runs</h2>
                  <span className="count">{runs.length}</span>
                </div>
                {!runs.length && (
                  <p className="empty-note">
                    Your first saved run will appear here.
                  </p>
                )}
                {runs.map((item) => (
                  <button
                    className={
                      "history-item " + (activeId === item.id ? "selected" : "")
                    }
                    key={item.id}
                    onClick={() => navigate("review", item.id)}
                  >
                    <span>
                      <strong>{item.name}</strong>
                      <small>
                        {new Date(item.created_at).toLocaleDateString()} ·{" "}
                        {time(item.created_at)}
                      </small>
                    </span>
                    <Status state={item.execution} recording={item.recording} />
                  </button>
                ))}
              </section>
              <div>
                {run ? (
                  <>
                    <section className="panel signal-panel">
                      <div className="signal-heading">
                        <div>
                          <p className="eyebrow">SAVED OBSERVATIONS</p>
                          <h2>{run.snapshot?.name}</h2>
                        </div>
                        <Status
                          state={run.execution}
                          recording={run.recording}
                        />
                      </div>
                      <SignalChart samples={samples} />
                      <div className="signal-footer">
                        <span>{samples.length} saved samples</span>
                        <span>Seed {run.snapshot?.recipe.seed}</span>
                        <span>EMA α {run.snapshot?.filter.alpha}</span>
                      </div>
                    </section>
                    <RunEvidence run={run} />
                  </>
                ) : (
                  <section className="panel review-empty">
                    <span className="wave">⌁</span>
                    <h2>A record worth keeping.</h2>
                    <p>
                      Select a run to inspect its measurements,
                      <br />
                      configuration and event history.
                    </p>
                  </section>
                )}
              </div>
            </div>
          )}
          <footer className="workspace-footer">
            <span>Simulated measurements · No physical actuation</span>
            <span>Control / Observe / Understand</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
function RunEvidence({ run }: { run: Run }) {
  return (
    <section className="panel evidence">
      <div className="panel-title">
        <h2>Run evidence</h2>
        <span className="mini-label">IMMUTABLE CONFIGURATION</span>
      </div>
      {run.recording === "partial" && (
        <div className="alert">
          Recording is incomplete: {readable(run.reason)}. Missing measurements
          are not reconstructed.
        </div>
      )}
      <div className="evidence-grid">
        <div>
          <p className="eyebrow">PROVENANCE</p>
          <dl>
            <dt>Run ID</dt>
            <dd className="mono">{run.id}</dd>
            <dt>Recipe</dt>
            <dd>
              {run.snapshot?.recipe.steps.length} steps ·{" "}
              {run.snapshot?.recipe.sample_rate_hz} Hz
            </dd>
            <dt>Outcome</dt>
            <dd>
              {readable(run.execution)} /{" "}
              {readable(run.reason || "awaiting observation")}
            </dd>
            <dt>Recording</dt>
            <dd>
              {run.persisted_seq + 1} committed · final sequence{" "}
              {run.final_seq ?? "unknown"}
            </dd>
          </dl>
        </div>
        <div>
          <p className="eyebrow">EVENT TIMELINE</p>
          <ol className="timeline">
            {run.events?.map((event) => (
              <li key={event.id}>
                <span>{readable(event.kind)}</span>
                <time>{time(event.created_at)}</time>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
