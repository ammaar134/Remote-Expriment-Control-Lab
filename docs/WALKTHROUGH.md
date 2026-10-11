# Demonstration and engineering handover

## Five-minute demonstration

1. **0:00 — Configure.** Open the hosted URL and sign in. Show a three-step recipe,
   sampling rate, seed and EMA alpha. Save a recipe version. Explain that its
   snapshot cannot be rewritten after Start.
2. **0:45 — Monitor.** Start a short run. Point out raw, EMA and reference traces,
   execution state, connectivity and recording state. Refresh the browser: the
   controller still owns acquisition. Stop and wait for observed STOPPED/zero output.
3. **1:30 — Review.** Open the saved run, inspect steps/provenance, compare statistics
   with a shorter chart window, export CSV/metadata, then play/pause/seek replay.
   Replay moves through saved observations and sends no instrument commands.
4. **2:30 — Timing.** Start the default 30-second comparison. Explain the deliberately
   large injected offsets/drifts. Show the independent starts and emerging probes.
   Switch original, receipt and estimated aligned time. Read the measured drift and
   uncertainty, then download evidence. Aligned curves do not prove simultaneous
   execution; the first/last points may lie outside the measured alignment window.
5. **3:45 — Failure and limits.** Open a saved partial comparison or, locally, run
   the partial-start smoke case. Show separate outcomes and the peer's Stop result.
   Discuss a changed engine boot losing its volatile tail. Finish with the
   immutable saved prefix, bounded queues and honest partial/unknown states.

No fault-injection endpoint is enabled on the public hosted app. Use the local
Compose tests for disruptive demonstrations. All demo values are synthetic.

## Trace a run through the code

| Entry point | Responsibility and evidence |
| --- | --- |
| `frontend/src/App.tsx`, `start` | Retains an HTTP command ID across a failed retry; browser intent is not execution confirmation. |
| `backend/lab/orchestrator.py`, `start` | Validates readiness and immutable recipe version; commits run/snapshot/command before sending Start. |
| `backend/lab/instrument.py`, `call` | Serializes one bounded control exchange, retries the same bytes/IDs and records send/reply times. |
| `instrument/src/server.cpp`, `handle` | Checks identity, boot, deduplication and state before applying a command. |
| `instrument/src/engine.cpp`, `tick` | Advances deterministic logical state and seeded noise; wall-clock jitter only paces delivery. |
| `instrument/src/server.cpp`, `pump` / `acknowledge` | Retains uncommitted samples, batches them, and releases only an acknowledged prefix. |
| `backend/lab/orchestrator.py`, `ingest` | Checks identity and sequence, applies EMA, commits raw/filtered values and cursor, then ACKs. |
| `orchestrator.py`, `observe_terminal` / `reconcile` | Separates terminal execution from complete recording and compares boot/run identity after reconnect. |
| `backend/lab/review.py` | Queries saved history, summary, original exports and replay without entering the control path. |
| `backend/lab/timing.py`, `acquire` / `estimate` | Records independent starts/probes, compensates partial starts, derives alignment from observed exchanges only. |
| `backend/lab/hosted.py` | Supervises two engines and one API; loss of a child leads to fresh-boot reconciliation. |

## Reason through failures

- **Start reply lost:** retrying with a new ID could create a second intention.
  The identical command returns its cached result within the documented scope.
  Unknown response remains unknown until observed evidence resolves it.
- **Database write fails:** the transaction rolls back; no ACK releases those
  samples. A same-boot reconnect can replay bounded retention. A prolonged outage
  fills the retention window and fault-stops rather than overwriting evidence.
- **Engine replaced:** its boot changes and volatile retention is gone. Preserve
  the committed prefix; do not silently rerun. Missing evidence remains partial.
- **One Start rejected:** retain both results, issue best-effort Stop for created
  peer runs, and inspect each response. A coordinated request is not atomic.
- **Clock estimate looks precise:** ask how many probes, what observation span,
  what RTT/jitter, whether UTC stepped, and whether path asymmetry is plausible.
  Injected truth is not an estimator input and aligned time is not source time.

## Small extension exercise

Change the default comparison offset without changing measurement behavior:
adjust the initial clocks in `TimingWorkspace.tsx`, keep the API/C++ bounds and
immutable snapshots, run the build and timing browser test, and compare measured
offset at the probe midpoint rather than expecting it to equal the Start offset.
For a larger change, add a new signal model with an explicit version, C++ tests,
snapshot provenance and compatible saved Review. Never regenerate old evidence.

## What real hardware would need

An independently designed hardware safety circuit/emergency stop, validated safe
output states, device authentication, encrypted transport, calibrated sensors,
durable local acquisition, documented timing/driver guarantees, deployment
fencing, operator roles, backups/retention policy and failure testing on the actual
equipment. Hardware synchronization would require a suitable clock/trigger design
and measurement of its error. None is supplied by this simulator.

There is no claim of interview readiness from this handover. Architecture tracing,
failure reasoning and the extension exercise are available for the next discussion
at the operator's pace. The completed implementation is bounded by the limits in
TIMING.md, PROTOCOL.md and HOSTING.md.
