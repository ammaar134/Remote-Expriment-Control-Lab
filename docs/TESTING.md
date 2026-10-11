# Verification

All commands below run from the repository root unless stated otherwise.
Do not run wire-level tests alongside the API: each engine permits one controller.

## Timing and final gates

`python3 tests/timing_smoke.py` acquires 520 samples from each real C++ process,
checks distinct boots, measured drift, immutable original timestamps, derived
alignment, idempotent group requests and separate command timing. It then stops
both devices and, on the local URL only, stops the second Compose engine to prove
partial-start compensation. It restarts that engine in a finally block. The test
creates synthetic history and must run while the lab is not being used manually.

`backend/tests/test_timing.py` checks known clock truth, asymmetric-delay bias,
insufficient span, jitter, retries, UTC discontinuities, no extrapolation,
immutable probe/request storage and group restart behavior. C++ tests verify
clock offset/drift/reanchoring and bounds without changing logical ticks.
Playwright's timing flow runs both real engines, switches all three time bases,
downloads evidence, refreshes saved comparisons, checks early Stop and measures
overflow at 1440, 1270 and 390px. `UPDATE_PHASE45_SCREENSHOTS=1` captures those
real results under ignored `.impeccable/review` for visual review.

CI builds from a clean Ubuntu 24 checkout and disposable database. It runs C++
tests/sanitizers, real TCP/backpressure/lease tests, Python/PostgreSQL tests,
format/types, frontend behavior/build/audit, complete API/reliability/review/timing
flows, Chromium, then authenticated hosted-image restart/ownership tests. This
also verifies the documented Compose setup without requiring local Docker repair.

For a final Python package audit, install `pip-audit==2.10.1` in a separate tools
environment and run `pip-audit -r backend/requirements.lock --require-hashes --disable-pip`.
The production lock is fully pinned/hashed. Run `npm audit --audit-level=high` in
frontend, and Gitleaks against staged changes and complete Git history. Audits
report known advisories at their execution time, not an absence of all defects.

## C++ and actual TCP

```sh
docker compose stop lab
docker compose up -d --build db instrument
docker run --rm --network experiment-lab_default -v "$PWD/tests:/tests:ro" python:3.12-slim-bookworm python /tests/protocol_smoke.py
docker run --rm --network experiment-lab_default -v "$PWD/tests:/tests:ro" python:3.12-slim-bookworm python /tests/backpressure_smoke.py
docker run --rm --network experiment-lab_default -v "$PWD/tests:/tests:ro" python:3.12-slim-bookworm python /tests/lease_smoke.py
docker compose up -d --wait lab
```

PowerShell: use an absolute host path with `--mount type=bind,source=...,target=/tests,readonly`.
The protocol test covers fragmented/coalesced framing, unsupported versions,
duplicate/conflicting Start, real sample sequences, stale/repeated Stop, telemetry
replay with original timestamps, cumulative ACK bounds and maximum frame size.
The lease check holds a silent controller connection and verifies a fault-stop.
Backpressure checks build a real socket backlog,
require Stop within one second on this test environment, then force overflow and
verify the <=512 retained-sample limit, bounded output queue and zero output. This is a test deadline, not a general
latency guarantee.

```sh
docker build --target build -f instrument/Dockerfile -t experiment-lab-instrument-build .
docker run --rm experiment-lab-instrument-build sh -c 'cmake -S . -B checked -DLAB_SANITIZERS=ON && cmake --build checked -j2 && ctest --test-dir checked --output-on-failure'
```

## Database, API and browser

The README provides these commands. PostgreSQL tests use isolated temporary
schemas, removed by rollback or by dropping only the test's UUID-named schema.
They do not erase saved history. They verify snapshot immutability, sample
uniqueness, concurrent active-run rejection, duplicate delivery, whole-batch
rollback on a gap, and commit visibility from an independent connection before ACK.

The API smoke test verifies a 100-sample normal run, the EMA equation, immutable
configuration, duplicate/conflicting HTTP commands and a confirmed stopped run.
The finalization unit test verifies terminal execution before final data, drain
timeout and eventual completion when the missing final sample is present.

Playwright exercises the real four-component application, refresh during
acquisition, saved review, confirmed Stop, and 1440x1050 / 390x844 layouts.
With local faults enabled, it also verifies visible reconnect evidence and a
complete 150-sample recording after telemetry interruption. This test skips on
the hosted app, where deliberate faults are disabled.

## Local reliability demonstrations

Enable faults explicitly (the default is off):

```sh
export LAB_ENABLE_FAULTS=1
docker compose up -d --build --wait lab
python3 tests/reliability_smoke.py
```

PowerShell uses `$env:LAB_ENABLE_FAULTS='1'`. Remove the variable and recreate
the services to return to normal mode. The script refuses non-local URLs. It
creates named synthetic runs, restarts only this project's API/instrument, and
checks six scenarios: lost Start reply, telemetry interruption, controller loss,
rolled-back database write, API restart and changed engine boot. It verifies
exact contiguous data, unchanged seeded measurements and EMA, fault output zero,
saved reconciliation events and honest partial/unknown state after engine restart.

`tests/hosted_smoke.py` builds on the hosted Docker image using an isolated test
database. It checks authentication/origin guards, idle session renewal, exclusive
ownership handoff, actual ownership-session loss, preserved history after container
replacement and shutdown on child failure. No cloud credentials are required.

## Phase 3 review checks

`python3 tests/review_smoke.py` uses the local Compose application. It acquires a
real 200-sample run from a saved recipe revision, rejects a mutated revision, stops
only the project's instrument, then checks full CSV values, metadata, bounded charts
and replay with no new commands. A `finally` block restarts the instrument. Do not
run this disruptive local test against a cloud service or an operator's active run.

`backend/tests/test_review.py` applies the upgrade to real legacy PostgreSQL rows,
then checks concurrent duplicate saves, stale edits, immutability, filters, exact
CSV floats/formula escaping, missing tails, empty runs and engine-independent replay.
Use a direct connection for these tests because fixtures use session search paths.
The pure downsampling test retains extrema across all three channels at 6,000 samples.

`frontend/e2e/review.spec.ts` covers saved revisions/Start provenance, search,
CSV/metadata downloads and keyboard replay controls. `LAB_EXPECT_OFFLINE=1` asserts
that the simulator is actually absent for its saved-review test. Use
`UPDATE_PHASE3_SCREENSHOTS=1` to save review/configure/replay captures in the ignored
`.impeccable/review` directory. The reviewed sizes are 1440, 1270 and 390 pixels.
The replay unit test checks cursor timing, pause, speed, seek and restart.

## Secret checks

Before committing, scan the staged diff with Gitleaks. Before the first push, scan
the complete local Git history. Never print discovered secret values.

```sh
git diff --cached | docker run --rm -i ghcr.io/gitleaks/gitleaks:v8.30.1 stdin --redact --no-banner
docker run --rm -v "$PWD:/repo:ro" ghcr.io/gitleaks/gitleaks:v8.30.1 git /repo --redact --no-banner
```

The database-write scenario injects a transaction error; the hosted test separately
terminates the real ownership session. Neither is a claim of surviving an
unbounded database outage without losing the engine's bounded volatile tail.
