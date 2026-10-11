import { useEffect, useRef, useState } from "react";
import type { ReplayData } from "./api";
import { Chart } from "./Chart";
import { RunEvidence } from "./RunEvidence";

export function ReplayPlayer({
  data,
  onClose,
}: {
  data: ReplayData;
  onClose: () => void;
}) {
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const cursor = useRef(0);
  const duration = data.duration_s;
  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const timer = setInterval(() => {
      const now = performance.now();
      cursor.current = Math.min(
        duration,
        cursor.current + ((now - last) / 1000) * speed,
      );
      last = now;
      setPosition(cursor.current);
      if (cursor.current >= duration) setPlaying(false);
    }, 100);
    return () => clearInterval(timer);
  }, [playing, speed, duration]);
  function seek(next: number) {
    setPlaying(false);
    cursor.current = next;
    setPosition(next);
  }
  const observed = data.samples.filter(
    (sample) => (sample.replay_s || 0) <= position,
  );
  const events = data.events.filter(
    (event) => (event.replay_s || 0) <= position,
  );
  const latest = observed[observed.length - 1];
  return (
    <div className="replay-workspace">
      <section
        className="panel signal-panel replay-panel"
        aria-label="Saved run replay"
      >
        <div className="signal-heading">
          <div>
            <h2>Replay · saved observations</h2>
            <p>No instrument commands are sent.</p>
          </div>
          <button className="text-button" onClick={onClose}>
            Exit replay
          </button>
        </div>
        <Chart
          samples={data.chart.filter(
            (sample) => (sample.replay_s || 0) <= position,
          )}
        />
        <div className="replay-controls">
          <button
            className="secondary"
            disabled={duration === 0}
            onClick={() => {
              if (position >= duration) {
                cursor.current = 0;
                setPosition(0);
              }
              setPlaying(!playing);
            }}
          >
            {playing ? "Pause replay" : "Play replay"}
          </button>
          <button className="text-button" onClick={() => seek(0)}>
            Restart replay
          </button>
          <label>
            Playback speed
            <select
              value={speed}
              onChange={(event) => setSpeed(Number(event.target.value))}
            >
              {[0.5, 1, 2, 4].map((value) => (
                <option value={value} key={value}>
                  {value}×
                </option>
              ))}
            </select>
          </label>
          <output aria-label="Replay position">
            {position.toFixed(2)} / {duration.toFixed(2)} s
          </output>
        </div>
        <label className="replay-seek">
          Seek replay
          <input
            type="range"
            min={0}
            max={duration || 1}
            step={0.01}
            value={position}
            disabled={duration === 0}
            onChange={(event) => seek(Number(event.target.value))}
          />
        </label>
        <div className="signal-footer">
          <span>
            {observed.length} / {data.samples.length} recorded samples shown
          </span>
          <span>Raw {latest ? latest.response.toFixed(4) : "—"} a.u.</span>
          <span>EMA {latest ? latest.filtered.toFixed(4) : "—"} a.u.</span>
        </div>
        <p className="replay-note">
          Playback follows saved sample time. Event positions are approximate;
          later events appear at the end. Original timestamps remain in the
          metadata.
        </p>
        {data.events_truncated && (
          <p className="field-error">
            This replay includes the first 2,000 events. The saved event
            timeline supports further pages.
          </p>
        )}
      </section>
      <RunEvidence run={{ ...data.run, events, events_more: false }} />
    </div>
  );
}
