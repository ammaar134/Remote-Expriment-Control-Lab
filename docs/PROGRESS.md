# Progress

- Last working milestone: Phase 1 single-device workflow through React, FastAPI,
  the separate C++ simulator and PostgreSQL. Complete and stopped runs demonstrated.
- Current gate: Phase 1 discussion completed; wait for an explicit request to start
  Phase 2. The real app is deployed on free cloud hosting so it
  can be operated from another computer. The live workflow is verified; the earlier
  document preview was insufficient. Fast pace requested; no interview scheduling.
- Repository: public ammaar134/Remote-Expriment-Control-Lab; local codex/phase-1.
  Initial publication to main approved. Verify the current remote commit and its
  GitHub Actions result when resuming; do not infer remote CI from local checks.
- Commits: 7e5716b contains the independently tested engine/protocol slice;
  1dd0edf contains the application checkpoint. Final C++, Python, frontend,
  API and real-browser checks passed against 1dd0edf with a clean working tree.
- Runtime: http://127.0.0.1:8000 via Docker Compose; database history is persistent.
  Docker startup was restored with reversible local socket-directory backups.

## Cloud deployment

- Live URL: https://remote-experiment-control-lab.onrender.com.
- Render service srv-db4jf9mi0phs73ctof0g is Free, Singapore, one Docker instance,
  automatic deployment off. Neon Free project young-hall-53222910 is Singapore,
  PostgreSQL 17, database experiment_lab, fixed 0.25 CU. Use the existing resources.
- Deployed application commit: 201f5d0b49f4f73b8babe34ab0b9bbf543c6d83d.
  Exact-commit Linux CI passed:
  https://github.com/ammaar134/Remote-Expriment-Control-Lab/actions/runs/37970946408.
- Direct/unpooled DATABASE_URL with full TLS verification is stored only in Render.
  Sign in as operator using LAB_PASSWORD from the service's Environment page.
  Do not print secrets or request them in chat. See docs/HOSTING.md.
- Verified the real HTTPS deployment on 2026-10-10 (Pacific/Auckland):
  authenticated API/database ready and C++ connected; signed-out UI/API/docs denied;
  cross-origin mutations denied; API smoke passed with 100 ordered durable samples,
  EMA, immutable snapshot, duplicate/conflicting Start and confirmed/repeated Stop.
- Playwright through the real URL passed Configure -> Start -> live samples ->
  refresh -> complete saved Review -> confirmed Stop. Desktop and 390-pixel mobile
  screenshots were visually checked. Four synthetic runs (two completed, two
  stopped) have complete recordings, with 462 samples in total.
- Final redeploy dep-db4jopss728c73fj042g is live. A new C++ boot was observed;
  authenticated history remained readable with identical sample counts/bounds.
  Completed and stopped API-smoke runs survived with 100 and 29 ordered samples.
- Cloud began with empty history; no local database history was uploaded.
  Local Compose services and secrets were preserved. Phase 2 remains paused.
- Free-plan limits: Render can sleep/restart; Neon has a monthly compute allowance.
  Platform interruption can interrupt a run; Phase 2 recovery is not implemented.
  No paid resources or upgrades were created.

## Latest validation (2026-10-10, Pacific/Auckland)

Passed against the Phase 1 implementation:

- C++ build and six doctest cases, also under address/undefined-behavior sanitizers.
- Real TCP framing, duplicate/conflicting commands, stale/repeated Stop,
  disconnect and oversized-frame checks.
- Real telemetry backlog: Stop within the test's one-second deadline; bounded
  queue overflow faulted with simulated output zero.
- Four Python tests, including real PostgreSQL immutability/uniqueness constraints
  and terminal-state-before-final-data reconciliation; Ruff and mypy passed.
- React/TypeScript production build, six behavior tests and Prettier checks.
- API smoke: complete run with 100 durable ordered samples, EMA verification,
  duplicate/conflicting Start and a confirmed stopped run.
- Playwright using installed Edge: live acquisition, browser refresh, saved review,
  confirmed Stop and desktop/mobile layouts. Genuine screenshots visually checked.
- npm audit: zero reported vulnerabilities. Staged scans and the two-commit full
  history scan reported no leaks; repeat for subsequent commits.

All local functional checks passed. Commit de28ae5 passed every Linux CI gate,
including real Chromium flow: https://github.com/ammaar134/Remote-Expriment-Control-Lab/actions/runs/37920817898.
That revision fixed an ambiguous chart/legend selector. The checkpoint follow-up
clarifies data status and adds tests for missing counts and unknown final sequence.
Check the latest commit's CI result at
https://github.com/ammaar134/Remote-Expriment-Control-Lab/actions.
Production frontend build reports a roughly 603 kB uncompressed JavaScript chunk;
loading optimization remains for Phase 3. Local browser validation uses Edge.

## Checkpoint discussion

- Command acceptance, observed RUNNING, and a committed sample prove different
  things. The browser displays observations; C++ owns execution; PostgreSQL owns
  durable records. Closing the browser does not stop a healthy backend-owned run.
- A terminal engine status can arrive before final telemetry on the other socket.
  For final sequence 99 with committed sequences 0-98, show completed execution
  with Data: finalizing. After the existing three-second drain deadline, show
  Data: partial with one missing sample. Receipt/commit of the final sample allows
  Data: complete. Unknown final sequence must not invent a missing count.
- The user delegated this presentation decision; it is implemented in Status and
  covered by behavior tests. No claim about the user's proficiency is implied.
- The sequence-99 example above is hypothetical, not an observed lost sample.
  A follow-up database audit found all 18 existing runs complete. A fresh
  `py tests/api_smoke.py` passed; the subsequent audit found 20 complete runs and
  zero inconsistencies between sample counts, bounds, persisted and final sequence.
- The user reported that the inline preview did not load on their remote laptop.
  A private ChatGPT Page now stores the read-only captured preview and native
  Configure/Review screenshots as a fallback. Cloud content and file access were
  verified. The user confirmed it opens but needs a live cloud app, so hosting
  is now the pending prerequisite. The private Page link stays out of this repo.
  Phase 2 has not started.

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

- Next: Phase 2 only when explicitly requested; cloud deployment is complete.
  Publishing target main is approved.
- Phase 2 adds durable telemetry acknowledgements/retransmission and broad failure
  reconciliation/injection. A dropped Phase 1 stream cannot recover missing data.
- CSV/replay, complete recipe management and two-device timing are later phases.
- One controlling API worker; cloud deployment verified; repository license undecided.
- Pointers: docs/ARCHITECTURE.md, docs/PROTOCOL.md, docs/DATA.md,
  instrument/src/engine.cpp, backend/lab/orchestrator.py, frontend/src/App.tsx.
