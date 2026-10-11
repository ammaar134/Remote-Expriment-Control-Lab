import { useEffect, useRef, useState } from "react";
import { api, type Device, type Run } from "./api";
import { navigate, readable } from "./format";
import { Status } from "./RunStatus";

type Clock = { offset_ms: number; drift_ppm: number };
type Point = {
  seq: number;
  response: number;
  logical_s: number;
  source_utc: string;
  received_utc: string;
  aligned_utc: string | null;
};
type Model = {
  offset_ms: number | null;
  drift_ppm: number | null;
  uncertainty_ms: number | null;
  drift_uncertainty_ppm: number | null;
  reason: string;
  accepted: number;
  total: number;
  span_s?: number;
};
type Member = {
  device_id: string;
  injected: Clock;
  estimate: Model;
  run: Run | null;
  points: Point[];
  start: {
    outcome: string;
    detail?: string;
    requested_utc: string;
    resolved_utc: string;
    stop_result?: unknown;
    response?: {
      transport_timing?: {
        sent_utc: string;
        received_utc: string;
        roundtrip_s: number;
      };
    };
  } | null;
};
type Comparison = {
  id: string;
  status: string;
  created_at: string;
  members: Member[];
  limitations: string;
};
type History = Pick<Comparison, "id" | "status" | "created_at">;
type TimeBasis = "source_utc" | "received_utc" | "aligned_utc";
const active = (status: string) => ["starting", "collecting"].includes(status);
const value = (n: number | null | undefined, decimals = 1) =>
  n == null ? "Insufficient evidence" : n.toFixed(decimals);
const utc = (date: string) =>
  new Date(date).toISOString().replace("T", " ").replace("Z", " UTC");

export function TimingPlot({
  members,
  basis,
  origin,
  firstFive,
}: {
  members: Member[];
  basis: TimeBasis;
  origin: string;
  firstFive: boolean;
}) {
  const zero = Date.parse(origin);
  const lines = members.map((m) =>
    m.points.flatMap((p) => {
      const timestamp = p[basis];
      if (!timestamp) return [];
      const x = (Date.parse(timestamp) - zero) / 1000;
      return firstFive && p.logical_s > 5 ? [] : [{ x, y: p.response }];
    }),
  );
  const all = lines.flat();
  if (!all.length)
    return (
      <div className="empty-state">
        {basis === "aligned_utc"
          ? "Alignment appears after at least three valid clock probes. Original observations remain available."
          : "Measurements appear after the devices start. Saved comparisons remain available below."}
      </div>
    );
  const lo = Math.min(0, ...all.map((p) => p.x)),
    hi = Math.max(1, ...all.map((p) => p.x));
  const x = (v: number) => 48 + ((v - lo) / (hi - lo)) * 670;
  const y = (v: number) => 224 - v * 190;
  return (
    <figure className="timing-figure">
      <svg
        viewBox="0 0 750 278"
        role="img"
        aria-label={`Response against ${basis === "source_utc" ? "original device time" : basis === "received_utc" ? "receipt time" : "estimated aligned time"}; sim-01 solid blue, sim-02 dashed copper`}
      >
        {[0, 0.5, 1].map((v) => (
          <g key={v}>
            <line
              x1="48"
              x2="718"
              y1={y(v)}
              y2={y(v)}
              className="timing-gridline"
            />
            <text x="38" y={y(v) + 4} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {[0, 1, 2, 3, 4].map((i) => (
          <text key={i} x={48 + (i * 670) / 4} y="248" textAnchor="middle">
            {(lo + ((hi - lo) * i) / 4).toFixed(1)}
          </text>
        ))}
        {lines.map((line, i) => (
          <path
            key={i}
            d={line
              .map(
                (p, j) =>
                  `${j ? "L" : "M"}${x(p.x).toFixed(2)},${y(p.y).toFixed(2)}`,
              )
              .join(" ")}
            fill="none"
            stroke={i ? "var(--copper)" : "var(--blue)"}
            strokeWidth="2"
            strokeDasharray={i ? "6 4" : undefined}
          />
        ))}
        <text x="48" y="18">
          Response (a.u.)
        </text>
        <text x="382" y="274" textAnchor="middle">
          Seconds from comparison request (UTC)
        </text>
      </svg>
      <figcaption>
        <span className="timing-key">sim-01 · solid blue</span>
        <span className="timing-key second">sim-02 · dashed copper</span>
      </figcaption>
    </figure>
  );
}

export function TimingWorkspace({ selectedId }: { selectedId?: string }) {
  const [clocks, setClocks] = useState<Clock[]>([
    { offset_ms: -750, drift_ppm: -3000 },
    { offset_ms: 1200, drift_ppm: 5000 },
  ]);
  const [duration, setDuration] = useState(30);
  const [devices, setDevices] = useState<Device[]>([]);
  const [history, setHistory] = useState<History[]>([]);
  const [offset, setOffset] = useState(0);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [basis, setBasis] = useState<TimeBasis>("source_utc");
  const [firstFive, setFirstFive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const pending = useRef<unknown>(null);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    setComparison(null);
    async function refresh() {
      try {
        const [d, h, c] = await Promise.all([
          api<Device[]>("/devices"),
          api<History[]>(`/timing?offset=${offset}`),
          selectedId
            ? api<Comparison>(`/timing/${selectedId}`)
            : Promise.resolve(null),
        ]);
        if (!cancelled) {
          setDevices(d);
          setHistory(h);
          setComparison(c);
          setConnectionError("");
        }
      } catch (err) {
        if (!cancelled) setConnectionError((err as Error).message);
      } finally {
        if (!cancelled) timer = setTimeout(() => void refresh(), 1500);
      }
    }
    void refresh();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [selectedId, offset]);
  const valid =
    Number.isInteger(duration) &&
    duration >= 1 &&
    duration <= 60 &&
    clocks.every(
      (c) =>
        Number.isFinite(c.offset_ms) &&
        Math.abs(c.offset_ms) <= 5000 &&
        Number.isFinite(c.drift_ppm) &&
        Math.abs(c.drift_ppm) <= 10000,
    );
  const ready =
    devices.length === 2 &&
    devices.every(
      (d) =>
        d.connected &&
        !d.recovering &&
        ["IDLE", "COMPLETED", "STOPPED"].includes(d.observation.state),
    );
  const working =
    history.some((h) => active(h.status)) ||
    (!!comparison && active(comparison.status));
  async function start() {
    setBusy(true);
    setError("");
    pending.current ??= {
      request_id: crypto.randomUUID(),
      duration_s: duration,
      clocks,
    };
    try {
      const result = await api<{ id: string }>("/timing", pending.current);
      pending.current = null;
      setOffset(0);
      navigate("timing", result.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function stop() {
    setBusy(true);
    setError("");
    try {
      await api(`/timing/${selectedId}/stop`, {});
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function reset(id: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/device/reset?device_id=${id}`, {
        command_id: crypto.randomUUID(),
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="timing-workspace">
      {(error || connectionError) && (
        <div className="alert" role="alert">
          {error || connectionError}
        </div>
      )}
      <section className="panel timing-setup" aria-labelledby="timing-settings">
        <div className="panel-title">
          <div>
            <h2 id="timing-settings">Two clocks, one observation.</h2>
            <p>
              Large educational offsets make clock differences visible. The
              operating-system clocks stay unchanged.
            </p>
          </div>
        </div>
        <div className="timing-settings">
          {clocks.map((c, i) => (
            <fieldset key={i} disabled={busy || working}>
              <legend>
                {`sim-0${i + 1}`}{" "}
                <span>
                  {devices[i]?.connected
                    ? readable(devices[i].observation.state)
                    : "Disconnected"}
                </span>
              </legend>
              <div className="field-row">
                {(["offset_ms", "drift_ppm"] as const).map((key) => (
                  <label key={key}>
                    {key === "offset_ms"
                      ? "Injected offset (ms)"
                      : "Injected drift (ppm)"}
                    <input
                      type="number"
                      min={key === "offset_ms" ? -5000 : -10000}
                      max={key === "offset_ms" ? 5000 : 10000}
                      step={1}
                      value={c[key]}
                      onChange={(e) => {
                        setClocks(
                          clocks.map((item, j) =>
                            j === i
                              ? { ...item, [key]: e.target.valueAsNumber }
                              : item,
                          ),
                        );
                        pending.current = null;
                      }}
                    />
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
        </div>
        <div className="timing-actions">
          <label>
            Observation duration (s)
            <input
              type="number"
              min={1}
              max={60}
              value={duration}
              disabled={working || busy}
              onChange={(e) => {
                setDuration(e.target.valueAsNumber);
                pending.current = null;
              }}
            />
          </label>
          <button
            className="primary-button"
            disabled={!ready || !valid || busy || working}
            onClick={() => void start()}
          >
            {busy ? "Sending request…" : "Start comparison"}
          </button>
          {comparison && active(comparison.status) && (
            <button
              className="stop-button"
              disabled={busy}
              onClick={() => void stop()}
            >
              Stop both devices
            </button>
          )}
        </div>
        {!valid && (
          <p className="field-error">
            Use 1–60 whole seconds, offsets within ±5,000 ms and drift within
            ±10,000 ppm.
          </p>
        )}
        <p className="field-note">
          Independent Start commands, not an atomic or simultaneous start. A
          failed start triggers best-effort Stop on its peer. Use 30 seconds to
          measure drift.
        </p>
        {devices
          .filter((d) => d.observation.state === "FAULTED")
          .map((d) => (
            <div className="alert" key={d.id}>
              {d.id}: {readable(d.observation.reason)}.{" "}
              <button
                className="text-button"
                disabled={busy}
                onClick={() => void reset(d.id)}
              >
                Acknowledge {d.id} fault
              </button>
            </div>
          ))}
      </section>
      <section className="panel timing-history">
        <label>
          Saved comparison
          <select
            value={selectedId || ""}
            onChange={(e) => navigate("timing", e.target.value)}
          >
            <option value="">Choose a comparison</option>
            {selectedId && !history.some((h) => h.id === selectedId) && (
              <option value={selectedId}>Selected comparison</option>
            )}
            {history.map((h) => (
              <option key={h.id} value={h.id}>
                {utc(h.created_at)} · {h.status}
              </option>
            ))}
          </select>
        </label>
        <div className="button-row">
          <button
            className="secondary"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            Newer
          </button>
          <button
            className="secondary"
            disabled={history.length < 20}
            onClick={() => setOffset(offset + 20)}
          >
            Older
          </button>
        </div>
      </section>
      {selectedId && !comparison && (
        <div className="panel empty-state" role="status">
          Loading saved timing evidence…
        </div>
      )}
      {!selectedId && (
        <div className="panel empty-state">
          Start a comparison to observe two independent clocks, or choose a
          saved comparison to inspect its measurements.
        </div>
      )}
      {comparison && (
        <>
          <section className="panel timing-results">
            <div className="panel-title">
              <div>
                <h2>Clock evidence</h2>
                <p>
                  {readable(comparison.status)} · {utc(comparison.created_at)}
                </p>
              </div>
              <a
                className="text-button"
                href={`/api/timing/${comparison.id}/evidence.json`}
                download
              >
                Download timing evidence
              </a>
            </div>
            <div className="timing-members">
              {comparison.members.map((m) => (
                <article key={m.device_id}>
                  <h3>{m.device_id}</h3>
                  <p>
                    {m.start
                      ? `Start ${m.start.outcome}`
                      : "Start awaiting result"}
                    {m.start?.detail && ` · ${m.start.detail}`}
                  </p>
                  {m.run && (
                    <div className="button-row">
                      <Status
                        state={m.run.execution}
                        recording={m.run.recording}
                        finalSeq={m.run.final_seq}
                        persistedSeq={m.run.persisted_seq}
                      />
                      <a href={`#review/${m.run.id}`}>Review recording</a>
                    </div>
                  )}
                  <table className="timing-measurements">
                    <caption>
                      Injected settings and independent estimates
                    </caption>
                    <thead>
                      <tr>
                        <th>Quantity</th>
                        <th>Injected</th>
                        <th>Measured</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <th>Offset (ms)</th>
                        <td>{m.injected.offset_ms}</td>
                        <td>{value(m.estimate.offset_ms)}</td>
                      </tr>
                      <tr>
                        <th>Drift (ppm)</th>
                        <td>{m.injected.drift_ppm}</td>
                        <td>{value(m.estimate.drift_ppm, 0)}</td>
                      </tr>
                    </tbody>
                  </table>
                  <p className="field-note">
                    Injected offset is at Start; measured offset is at the probe
                    window’s midpoint.
                  </p>
                  <p>{m.estimate.reason}</p>
                  <p className="field-note">
                    {m.estimate.accepted}/{m.estimate.total} accepted probes ·{" "}
                    {value(m.estimate.span_s)} s window
                  </p>
                  {m.estimate.uncertainty_ms != null && (
                    <p className="field-note">
                      Offset uncertainty estimate ±
                      {value(m.estimate.uncertainty_ms)} ms
                      {m.estimate.drift_uncertainty_ppm != null &&
                        `; drift ±${value(m.estimate.drift_uncertainty_ppm, 0)} ppm`}
                      . Delay assumptions apply; not a confidence interval.
                    </p>
                  )}
                  {m.start && (
                    <details>
                      <summary>Independent command timing</summary>
                      <dl className="timing-command">
                        <dt>Request created</dt>
                        <dd>{utc(m.start.requested_utc)}</dd>
                        <dt>Result resolved</dt>
                        <dd>{utc(m.start.resolved_utc)}</dd>
                        {m.start.response?.transport_timing && (
                          <>
                            <dt>TCP command sent</dt>
                            <dd>
                              {utc(m.start.response.transport_timing.sent_utc)}
                            </dd>
                            <dt>Reply received</dt>
                            <dd>
                              {utc(
                                m.start.response.transport_timing.received_utc,
                              )}
                            </dd>
                          </>
                        )}
                      </dl>
                      {!!m.start.stop_result && (
                        <pre>
                          {JSON.stringify(m.start.stop_result, null, 2)}
                        </pre>
                      )}
                    </details>
                  )}
                </article>
              ))}
            </div>
          </section>
          <section className="panel timing-chart">
            <div className="panel-title">
              <div>
                <h2>Same signal, different time bases.</h2>
                <p>
                  Up to 300 recorded points per device. No original timestamp is
                  changed.
                </p>
              </div>
            </div>
            <div className="timing-chart-controls">
              <label>
                Time basis
                <select
                  value={basis}
                  onChange={(e) => setBasis(e.target.value as TimeBasis)}
                >
                  <option value="source_utc">Original device time</option>
                  <option value="received_utc">
                    Orchestrator receipt time
                  </option>
                  <option value="aligned_utc">Estimated aligned time</option>
                </select>
              </label>
              <label>
                Display window
                <select
                  value={firstFive ? "five" : "all"}
                  onChange={(e) => setFirstFive(e.target.value === "five")}
                >
                  <option value="five">First 5 logical seconds</option>
                  <option value="all">Whole recording</option>
                </select>
              </label>
            </div>
            <TimingPlot
              members={comparison.members}
              basis={basis}
              origin={comparison.created_at}
              firstFive={firstFive}
            />
            <p className="field-note">
              Origin: {utc(comparison.created_at)}. Aligned points exist only
              inside the measured probe window.
            </p>
            <p className="timing-limitations">{comparison.limitations}</p>
          </section>
        </>
      )}
    </div>
  );
}
