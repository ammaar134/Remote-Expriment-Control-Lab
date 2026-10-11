import { useEffect, useState, type FormEvent } from "react";
import {
  api,
  downloadRun,
  type ChartData,
  type Run,
  type RunSummary,
  type ReplayData,
} from "./api";
import { Chart } from "./Chart";
import { WaveMark } from "./InstrumentSculpture";
import { navigate, time } from "./format";
import { Status } from "./RunStatus";
import { RunEvidence } from "./RunEvidence";
import { ReplayPlayer } from "./ReplayPlayer";

const emptyFilters = {
  q: "",
  execution: "",
  recording: "",
  device: "",
  since: "",
  until: "",
};

export function ReviewWorkspace({ selectedId }: { selectedId?: string }) {
  const [filters, setFilters] = useState(emptyFilters);
  const [query, setQuery] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [more, setMore] = useState(false);
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api<Run[]>(`/runs?${query}&offset=${offset}`)
      .then((rows) => {
        if (!cancelled) {
          setRuns(rows);
          setMore(rows.length === 50);
        }
      })
      .catch((failure: Error) => {
        if (!cancelled) setError(failure.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query, refresh, offset]);
  function search(event: FormEvent) {
    event.preventDefault();
    setQuery(
      new URLSearchParams(
        Object.entries(filters).filter(([, value]) => value),
      ).toString(),
    );
    setOffset(0);
    setRefresh((old) => old + 1);
  }
  function field(key: keyof typeof filters, value: string) {
    setFilters((old) => ({ ...old, [key]: value }));
  }
  return (
    <div className="review-grid">
      <section className="panel history" aria-label="Run history">
        <div className="panel-title">
          <h2>Recorded runs</h2>
          <button
            className="text-button"
            disabled={loading}
            onClick={() => setRefresh(refresh + 1)}
          >
            Refresh
          </button>
        </div>
        <form className="history-filters" onSubmit={search}>
          <label>
            Find a run
            <input
              type="search"
              maxLength={80}
              value={filters.q}
              onChange={(event) => field("q", event.target.value)}
              placeholder="Recipe or run name"
            />
          </label>
          <div className="filter-pair">
            <label>
              Outcome
              <select
                value={filters.execution}
                onChange={(event) => field("execution", event.target.value)}
              >
                <option value="">All outcomes</option>
                {[
                  "COMPLETED",
                  "STOPPED",
                  "FAULTED",
                  "UNKNOWN",
                  "RUNNING",
                  "REJECTED",
                ].map((state) => (
                  <option value={state} key={state}>
                    {state.toLowerCase()}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Recording
              <select
                value={filters.recording}
                onChange={(event) => field("recording", event.target.value)}
              >
                <option value="">All data</option>
                <option value="complete">Complete</option>
                <option value="partial">Partial</option>
                <option value="recording">Recording</option>
                <option value="draining">Finalizing</option>
              </select>
            </label>
          </div>
          <details>
            <summary>Date and instrument</summary>
            <label>
              From date (UTC)
              <input
                type="date"
                value={filters.since}
                onChange={(event) => field("since", event.target.value)}
              />
            </label>
            <label>
              Through date (UTC)
              <input
                type="date"
                value={filters.until}
                onChange={(event) => field("until", event.target.value)}
              />
            </label>
            <label>
              Instrument
              <select
                value={filters.device}
                onChange={(event) => field("device", event.target.value)}
              >
                <option value="">All instruments</option>
                <option value="sim-01">Response simulator · sim-01</option>
              </select>
            </label>
          </details>
          <div className="history-filter-actions">
            <button type="submit" className="secondary" disabled={loading}>
              Apply filters
            </button>
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setFilters(emptyFilters);
                setQuery("");
                setOffset(0);
                setRefresh(refresh + 1);
              }}
            >
              Clear
            </button>
          </div>
        </form>
        {loading && (
          <p role="status" className="empty-note">
            Loading saved runs…
          </p>
        )}
        {error && (
          <p role="alert" className="empty-note field-error">
            {error} Use Refresh to try again.
          </p>
        )}
        {!loading && !error && !runs.length && (
          <p className="empty-note">
            {query
              ? "No runs match these filters."
              : "Your first saved run will appear here."}
          </p>
        )}
        {!loading &&
          !error &&
          runs.map((item) => (
            <button
              className={
                "history-item " + (selectedId === item.id ? "selected" : "")
              }
              key={item.id}
              aria-current={selectedId === item.id ? "true" : undefined}
              onClick={() => navigate("review", item.id)}
            >
              <span>
                <strong>{item.name}</strong>
                <small>
                  {new Date(item.created_at).toLocaleDateString()} ·{" "}
                  {time(item.created_at)} · {item.device_id}
                </small>
              </span>
              <Status
                state={item.execution}
                recording={item.recording}
                finalSeq={item.final_seq}
                persistedSeq={item.persisted_seq}
              />
            </button>
          ))}
        <div className="history-pager">
          <button
            className="text-button"
            disabled={!offset || loading}
            onClick={() => setOffset(Math.max(0, offset - 50))}
          >
            Newer
          </button>
          <span>Page {Math.floor(offset / 50) + 1}</span>
          <button
            className="text-button"
            disabled={!more || loading || offset >= 10000}
            onClick={() => setOffset(offset + 50)}
          >
            Older
          </button>
        </div>
      </section>
      {selectedId ? (
        <ReviewDetail key={selectedId} id={selectedId} />
      ) : (
        <section className="panel review-empty">
          <WaveMark />
          <h2>A record worth keeping.</h2>
          <p>
            Select a run to inspect its measurements,
            <br />
            configuration and event history.
          </p>
        </section>
      )}
    </div>
  );
}

function ReviewDetail({ id }: { id: string }) {
  const [run, setRun] = useState<Run | null>(null);
  const [stats, setStats] = useState<RunSummary | null>(null);
  const [chart, setChart] = useState<ChartData | null>(null);
  const [windowSize, setWindowSize] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [busy, setBusy] = useState("");
  const [replay, setReplay] = useState<ReplayData | null>(null);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    async function load() {
      try {
        const [detail, summary] = await Promise.all([
          api<Run>(`/runs/${id}`),
          api<RunSummary>(`/runs/${id}/summary`),
        ]);
        const end =
          (detail.persisted_seq + 1) /
          (detail.snapshot?.recipe.sample_rate_hz || 50);
        const from =
          windowSize === "all" ? 0 : Math.max(0, end - Number(windowSize));
        const plot = await api<ChartData>(`/runs/${id}/chart?from_s=${from}`);
        if (!cancelled) {
          setRun(detail);
          setStats(summary);
          setChart(plot);
        }
      } catch (failure) {
        if (!cancelled) setError((failure as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [id, windowSize, retry]);
  async function download(kind: "export.csv" | "metadata.json") {
    if (busy) return;
    setBusy(kind);
    setError("");
    try {
      await downloadRun(id, kind);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function openReplay() {
    if (busy) return;
    setBusy("replay");
    setError("");
    try {
      setReplay(await api<ReplayData>(`/runs/${id}/replay`));
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy("");
    }
  }
  const terminal = run && ["complete", "partial"].includes(run.recording);
  const numeric = (value: number | null | undefined) =>
    value == null ? "—" : value.toFixed(4);
  return (
    <div className="review-detail">
      {error && (
        <div role="alert" className="alert">
          {error}
          <button className="text-button" onClick={() => setRetry(retry + 1)}>
            Retry
          </button>
        </div>
      )}
      {loading && (
        <p role="status" className="loading-note">
          Loading recorded evidence…
        </p>
      )}
      {run && (
        <>
          <div className="review-actions">
            <button
              className="secondary"
              disabled={!terminal || !!busy || loading}
              onClick={() => void download("export.csv")}
            >
              {busy === "export.csv" ? "Exporting…" : "Export CSV"}
            </button>
            <button
              className="text-button"
              disabled={!!busy || loading}
              onClick={() => void download("metadata.json")}
            >
              {busy === "metadata.json" ? "Downloading…" : "Download metadata"}
            </button>
            <button
              className="secondary"
              disabled={!terminal || !!busy || !!replay || loading}
              onClick={() => void openReplay()}
            >
              {busy === "replay" ? "Loading replay…" : "Replay saved run"}
            </button>
          </div>
          {!terminal && (
            <p className="field-note">
              Export and replay become available after recording finishes.{" "}
              <button
                className="text-button"
                onClick={() => navigate("monitor", id)}
              >
                Open Monitor
              </button>
            </p>
          )}
          {replay ? (
            <ReplayPlayer data={replay} onClose={() => setReplay(null)} />
          ) : (
            <>
              <section className="panel signal-panel">
                <div className="signal-heading">
                  <div>
                    <h2>{run.snapshot?.name}</h2>
                    <p>{new Date(run.created_at).toLocaleString()}</p>
                  </div>
                  <Status
                    state={run.execution}
                    recording={run.recording}
                    finalSeq={run.final_seq}
                    persistedSeq={run.persisted_seq}
                  />
                </div>
                <label className="chart-window">
                  Chart window
                  <select
                    value={windowSize}
                    onChange={(event) => setWindowSize(event.target.value)}
                  >
                    <option value="all">Full run</option>
                    <option value="10">Last 10 seconds</option>
                    <option value="5">Last 5 seconds</option>
                  </select>
                </label>
                <Chart samples={chart?.points || []} />
                <div className="signal-footer">
                  <span>{stats?.sample_count ?? 0} saved samples</span>
                  <span>
                    {chart?.points.length ?? 0} plotted · extrema preserved
                  </span>
                  <span>EMA α {run.snapshot?.filter.alpha}</span>
                </div>
              </section>
              {stats && (
                <section
                  className="panel run-summary"
                  aria-label="Full recording summary"
                >
                  <h2>Full recording summary</h2>
                  <p>
                    All {stats.sample_count} committed samples · a.u. ·
                    independent of the chart window.
                  </p>
                  <dl>
                    <div>
                      <dt>Raw mean</dt>
                      <dd>{numeric(stats.raw_mean)}</dd>
                    </div>
                    <div>
                      <dt>Raw standard deviation</dt>
                      <dd>{numeric(stats.raw_stddev)}</dd>
                    </div>
                    <div>
                      <dt>Filtered standard deviation</dt>
                      <dd>{numeric(stats.filtered_stddev)}</dd>
                    </div>
                    <div>
                      <dt>Raw range</dt>
                      <dd>
                        {numeric(stats.raw_min)} – {numeric(stats.raw_max)}
                      </dd>
                    </div>
                  </dl>
                  <p className="field-note">
                    Standard deviation describes the whole stepped signal, not
                    sensor noise alone. EMA smooths the response and adds lag.
                  </p>
                </section>
              )}
              <RunEvidence run={run} />
            </>
          )}
        </>
      )}
    </div>
  );
}
