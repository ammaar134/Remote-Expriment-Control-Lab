# Progress

- Last working milestone: Phase 1 single-device workflow through React, FastAPI,
  the separate C++ simulator and PostgreSQL. Complete and stopped runs demonstrated.
- Current gate: Phase 1 checkpoint; wait for the user's discussion response before
  Phase 2. Fast pace requested; no interview scheduling needed.
- Repository: public ammaar134/Remote-Expriment-Control-Lab; local codex/phase-1.
  Initial publication to main approved. Verify the current remote commit and its
  GitHub Actions result when resuming; do not infer remote CI from local checks.
- Commits: 7e5716b contains the independently tested engine/protocol slice;
  1dd0edf contains the application checkpoint. Final C++, Python, frontend,
  API and real-browser checks passed against 1dd0edf with a clean working tree.
- Runtime: http://127.0.0.1:8000 via Docker Compose; database history is persistent.
  Docker startup was restored with reversible local socket-directory backups.

## Latest validation (2026-10-09)

Passed against the Phase 1 implementation:

- C++ build and six doctest cases, also under address/undefined-behavior sanitizers.
- Real TCP framing, duplicate/conflicting commands, stale/repeated Stop,
  disconnect and oversized-frame checks.
- Real telemetry backlog: Stop within the test's one-second deadline; bounded
  queue overflow faulted with simulated output zero.
- Four Python tests, including real PostgreSQL immutability/uniqueness constraints
  and terminal-state-before-final-data reconciliation; Ruff and mypy passed.
- React/TypeScript production build, three behavior tests and Prettier checks.
- API smoke: complete run with 100 durable ordered samples, EMA verification,
  duplicate/conflicting Start and a confirmed stopped run.
- Playwright using installed Edge: live acquisition, browser refresh, saved review,
  confirmed Stop and desktop/mobile layouts. Genuine screenshots visually checked.
- npm audit: zero reported vulnerabilities. Staged scans and the two-commit full
  history scan reported no leaks; repeat for subsequent commits.

No failing functional checks remain. Production frontend build reports a roughly
603 kB uncompressed JavaScript chunk; loading optimization remains for Phase 3.
Remote Linux CI is configured; its result must be checked for the exact remote SHA. Windows native-browser automation
was unavailable; the Playwright/Edge test provided actual browser validation.

## Reproduce

From the repository root (PowerShell; Docker running):

```powershell
py scripts/setup.py
docker compose up -d --build --wait
docker compose build backend-test
docker compose run --rm backend-test sh -c 'pytest -q && ruff check . && ruff format --check . && mypy lab'
py tests/api_smoke.py
$env:PLAYWRIGHT_CHANNEL='msedge'
node frontend/node_modules/@playwright/test/cli.js test --config frontend/playwright.config.ts
```

Frontend checks from `frontend/`: `npm ci`, `npm run format:check`,
`npm run build`, `npm test`, `npm audit --audit-level=high`. Use Node 24.21.0.
See docs/TESTING.md for exact standalone TCP and sanitizer commands; those socket
checks require stopping the API to release its controlling connection.

## Next and limits

- Next: trace Start and one sample, discuss execution versus recording completion.
  Phase 2 follows only after the gate. Publishing target main is now approved.
- Phase 2 adds durable telemetry acknowledgements/retransmission and broad failure
  reconciliation/injection. A dropped Phase 1 stream cannot recover missing data.
- CSV/replay, complete recipe management and two-device timing are later phases.
- One controlling API worker; local-only operation; repository license undecided.
- Pointers: docs/ARCHITECTURE.md, docs/PROTOCOL.md, docs/DATA.md,
  instrument/src/engine.cpp, backend/lab/orchestrator.py, frontend/src/App.tsx.
