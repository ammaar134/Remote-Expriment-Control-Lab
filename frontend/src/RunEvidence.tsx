import { useEffect, useState } from "react";
import { api, type Run, type RunEvent } from "./api";
import { readable, time } from "./format";
export function RunEvidence({ run }: { run: Run }) {
  const [page, setPage] = useState<{
    events: RunEvent[];
    more: boolean;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    setPage(null);
    setError("");
  }, [run.id]);
  const events = page?.events || run.events || [];
  const more = page?.more ?? run.events_more;
  async function nextPage() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      setPage(
        await api(
          `/runs/${run.id}/events?after=${events[events.length - 1]?.id || 0}`,
        ),
      );
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel evidence">
      <div className="panel-title">
        <h2>Run evidence</h2>
        <span className="count">Configuration saved at Start</span>
      </div>
      {run.recording === "partial" && (
        <div className="alert">
          Recording is incomplete: {readable(run.reason)}. Missing measurements
          are not reconstructed.
        </div>
      )}
      <div className="evidence-grid">
        <div>
          <h3>Provenance</h3>
          <dl>
            <dt>Run ID</dt>
            <dd className="mono">{run.id}</dd>
            <dt>Instrument</dt>
            <dd>{run.device_id || "Not recorded"}</dd>
            <dt>Boot ID</dt>
            <dd className="mono">{run.boot_id || "Not recorded"}</dd>
            <dt>Recipe version</dt>
            <dd className="mono">
              {run.snapshot?.recipe_version
                ? `v${run.snapshot.recipe_version.revision} · `
                : "Legacy version · "}
              {run.recipe_id}
            </dd>
            <dt>Recipe</dt>
            <dd>
              {run.snapshot?.recipe.steps.length} steps ·{" "}
              {run.snapshot?.recipe.sample_rate_hz} Hz
            </dd>
            <dt>Scenario</dt>
            <dd>{readable(run.snapshot?.scenario || "normal")}</dd>
            <dt>Random seed</dt>
            <dd>{run.snapshot?.recipe.seed}</dd>
            <dt>Filter</dt>
            <dd>
              {run.snapshot?.filter.version} · α {run.snapshot?.filter.alpha}
            </dd>
            <dt>Engine / protocol</dt>
            <dd>
              {run.snapshot?.engine_version || "Not recorded"} /{" "}
              {run.snapshot?.protocol_version ?? "Not recorded"}
            </dd>
            <dt>Model</dt>
            <dd>
              {run.snapshot?.model?.version || "Not recorded"} · τ{" "}
              {run.snapshot?.model?.tau_s ?? "—"} s
            </dd>
            <dt>Build</dt>
            <dd className="mono">{run.snapshot?.build || "Not recorded"}</dd>
            <dt>Created (UTC)</dt>
            <dd>{new Date(run.created_at).toISOString()}</dd>
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
          {run.snapshot && (
            <table className="saved-recipe">
              <caption>Saved step sequence</caption>
              <thead>
                <tr>
                  <th scope="col">Step</th>
                  <th scope="col">Setpoint (a.u.)</th>
                  <th scope="col">Duration (s)</th>
                </tr>
              </thead>
              <tbody>
                {run.snapshot.recipe.steps.map((step, index) => (
                  <tr key={index}>
                    <th scope="row">{index + 1}</th>
                    <td>{step.setpoint}</td>
                    <td>{step.duration_ms / 1000}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div>
          <h3>Event timeline</h3>
          <ol className="timeline">
            {events.map((event) => (
              <li key={event.id}>
                <div className="event-heading">
                  <span>{readable(event.kind)}</span>
                  <time dateTime={event.created_at} title={event.created_at}>
                    {time(event.created_at)}
                  </time>
                </div>
                <details>
                  <summary>Event detail</summary>
                  <pre>{JSON.stringify(event.detail, null, 2)}</pre>
                </details>
              </li>
            ))}
          </ol>
          {!events.length && (
            <p className="field-note">No events at this position.</p>
          )}
          {(more || page) && (
            <div className="event-pagination">
              {page && (
                <button className="text-button" onClick={() => setPage(null)}>
                  First events
                </button>
              )}
              {more && (
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() => void nextPage()}
                >
                  {busy ? "Loading…" : "Next events"}
                </button>
              )}
            </div>
          )}
          {error && (
            <p role="alert" className="field-error">
              {error}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
