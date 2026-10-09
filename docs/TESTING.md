# Verification

All commands below run from the repository root unless stated otherwise.
Do not run wire-level tests alongside the API: each engine permits one controller.

## C++ and actual TCP

```sh
docker compose stop lab
docker compose up -d --build db instrument
docker run --rm --network experiment-lab_default -v "$PWD/tests:/tests:ro" python:3.12-slim-bookworm python /tests/protocol_smoke.py
docker run --rm --network experiment-lab_default -v "$PWD/tests:/tests:ro" python:3.12-slim-bookworm python /tests/backpressure_smoke.py
docker compose up -d --wait lab
```

PowerShell: use an absolute host path with `--mount type=bind,source=...,target=/tests,readonly`.
The protocol test covers fragmented/coalesced framing, unsupported versions,
duplicate/conflicting Start, real sample sequences, stale/repeated Stop, telemetry
disconnect and maximum frame size. Backpressure checks build a real socket backlog,
require Stop within one second on this test environment, then force overflow and
verify the <=128 frame queue and zero output. This is a test deadline, not a general
latency guarantee.

```sh
docker build --target build -f instrument/Dockerfile -t experiment-lab-instrument-build .
docker run --rm experiment-lab-instrument-build sh -c 'cmake -S . -B checked -DLAB_SANITIZERS=ON && cmake --build checked -j2 && ctest --test-dir checked --output-on-failure'
```

## Database, API and browser

The README provides these commands. PostgreSQL tests create a temporary schema in
a transaction and roll it back; they do not erase saved history. They verify snapshot
immutability, sample uniqueness and concurrent active-run rejection.

The API smoke test verifies a 100-sample normal run, the EMA equation, immutable
configuration, duplicate/conflicting HTTP commands and a confirmed stopped run.
The finalization unit test verifies terminal execution before final data, drain
timeout and eventual completion when the missing final sample is present.

The Playwright test exercises the real four-component application, refresh during
acquisition, saved review, confirmed Stop, and 1440x1050 / 390x844 layouts.

## Secret checks

Before committing, scan the staged diff with Gitleaks. Before the first push, scan
the complete local Git history. Never print discovered secret values.

```sh
git diff --cached | docker run --rm -i ghcr.io/gitleaks/gitleaks:v8.30.1 stdin --redact --no-banner
docker run --rm -v "$PWD:/repo:ro" ghcr.io/gitleaks/gitleaks:v8.30.1 git /repo --redact --no-banner
```

Phase 2 expands failure injection, duplicate ingestion, persistence outages, restart
reconciliation and lost-ACK recovery. Those guarantees are not implied by Phase 1.
