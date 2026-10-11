# Progress

## Phases 4 and 5 — implementation and handover, 2026-10-11 Pacific/Auckland

The operator explicitly authorized completing both phases together, then waiting
for their next instruction. Earlier checkpoint pauses below are historical.
Work branch: `codex/phase-4-5`; existing approval covers public `main` and the same
free Render/Neon service. No additional hosting resource is required.

Implemented two independent C++ engines, bounded simulated clock settings,
persisted independent Start/Stop outcomes, append-only round-trip probes, measured
offset/drift with insufficient-evidence handling, original/receipt/aligned views,
saved comparison history and full timing JSON. Added final decisions, timing,
testing, troubleshooting and walkthrough documents.

The first integration run proved real two-device acquisition and partial-start
compensation; its browser test found a selector accessible-name mismatch, fixed
in `cfe9c5892844440a309a823d517a3316964c45d5`. Full rerun:
https://github.com/ammaar134/Remote-Expriment-Control-Lab/actions/runs/38099407609.
That complete Linux run passed: C++/sanitizers/TCP, 41 Python tests, nine frontend
unit tests, eight browser tests, real two-engine timing/failure checks and the
authenticated hosted-image restart/ownership checks. Commit `cfe9c58` deployed
successfully as `dep-db5dr2d9fdbs73ch2gv0` at 2026-10-11T00:53:08Z. Five live Edge
workflows passed; the local-only fault test was correctly skipped on the public
host. The two sign-in regressions also passed.

The final interface delta keeps Timing chart labels readable at 1440, 1270 and
390px and adds a rendered-size browser assertion. The two bounded visual passes
and independent Impeccable finish review are complete: `disposition: ship`, with
no material fixes outstanding. The documenter reconciled the product and surface
brief while preserving both identity files. Captures and provenance are recorded
in SCREENSHOTS.md; historical concept/approval evidence is not newly asserted.

Final-commit CI and the published-build browser check follow this handover commit.
Consult its matching GitHub Actions run and Render deploy record for release
status; `.local/phase45-release.json` stores the local verification receipt without
credentials. All five planned implementation phases are delivered. The operator
asked to choose what comes next, so the walkthrough is available in WALKTHROUGH.md
without imposing a new discussion gate or claiming interview readiness.

Migration 003 preserved eight legacy test-branch runs, 3,516 samples and snapshot
digest `70feac0713ba5c8bf93cfd7e19767e52`. Production baseline before release:
11 runs, 3,995 samples, zero unfinished, snapshot digest
`3f4722480fdbcf7056462c3281beb6cd` at 2026-10-11T00:40:25Z.
After deployment and browser workflows, all original runs, samples and that digest
were unchanged. The database held 18 runs / 5,545 samples / zero unfinished runs
and two comparisons / zero active comparisons; application error logs were empty.
Native Python/type/format checks, frontend build/unit tests, Edge sign-in regressions,
npm audit, Python production-lock audit and full-history Gitleaks passed. Docker
Desktop remains unavailable locally; the clean Linux CI runner supplies complete
C++/container validation. No destructive Docker repair was performed.

## Phase 3 implementation checkpoint — 2026-10-11, Pacific/Auckland

The operator confirmed the sign-in correction works and authorized Phase 3.
Branch: `codex/phase-3`. Existing approval covers `main` and the free Render/Neon deployment.
Phase 4 remains paused until the Phase 3 checkpoint.

Implemented: immutable reusable recipe revisions, filtered history, bounded
extrema-preserving chart queries, whole-recording statistics, exact CSV/metadata
exports, and read-only saved-observation replay. Configure/Monitor/Review expose
these workflows with field validation, event paging and responsive layouts.

Core commit `f9e6bcba3a2d9ffea10fee281a2f724c58939968` passed complete Linux CI:
https://github.com/ammaar134/Remote-Expriment-Control-Lab/actions/runs/38096861797.
This includes C++/socket/sanitizer, Python/PostgreSQL, browser and hosted-image gates.
The migration preserved eight runs, 3,516 samples and an identical snapshot digest
on an isolated Neon branch. No production history was altered during development.

Local checks: 34 Python tests, Ruff/mypy, production UI build, nine frontend unit
tests, formatting and dependency audit passed. Native Edge exported CSV/metadata
and exercised replay with the engine absent, asserting no control requests or live
device polling. Review was inspected at 1440, 1270 and 390px; Configure at desktop
and mobile; replay at desktop. Impeccable's full review found one documentation
correction and no material UI defect in that capture set. Its subsequent verdict
scored the documentation fix resolved and returned `ship` at that scope. The
documenter reconciled product/implementation records while preserving identity.
No new quality card/comp or original historical roll evidence is claimed.

Docker Desktop has an unrelated stale socket startup failure. Local checks used
native tools and the isolated Neon branch; complete container checks run in Linux
CI. The release procedure requires this interface commit's full CI and live browser
checks, beyond the earlier core result. Consult the matching Actions run and Render
deploy record for release status; `.local/phase3-release.json` stores the local
verification receipt without credentials. Phase 4 remains paused for discussion.

Checkpoint: `ReplayPlayer` pauses by removing its timer and moves only the saved-data
cursor. The unique `(family_id, revision)` constraint and unique parent prevent
ambiguous recipe revisions; append-only triggers prevent evidence rewrites.
Question: why keep full raw samples when a chart shows fewer points and an EMA?

## Phase 2 checkpoint — 2026-10-10, Pacific/Auckland

Phase 2 and the concurrent redesign were explicitly authorized. The operator
keeps the working console first and delegated visual selection. This checkpoint
was completed before the separately authorized Phase 3 work above.

Repository: public ammaar134/Remote-Expriment-Control-Lab. Work branch:
`codex/phase-2`; publication to `main` and the existing free hosting are approved.
Core reliability commit: `2a79d1dce989c5ac31da6c590b87ada2abb62dc8`.
Its complete Linux CI passed, including C++ sanitizers:
https://github.com/ammaar134/Remote-Expriment-Control-Lab/actions/runs/38045003326.
Console/documentation release `313f3a36e75c5c5c7312a2ce481f6b5536f6a0cb` passed
exact-commit CI and deployed successfully:
https://github.com/ammaar134/Remote-Expriment-Control-Lab/actions/runs/38045545375.

## Sign-in correction — 2026-10-11, Pacific/Auckland

The operator reported repeated native sign-in prompts/reloads and requested a
shorter password. Replace HTTP Basic challenges with a stable app form and a
12-hour signed cookie. The console does not mount or poll while signed out;
expired sessions unmount it without navigation. Failed sign-in preserves typed
details. Public static assets contain no experiment data; API routes and controls
remain protected. Local mode still needs no login. Login attempts are limited,
and a separate random signing key lets a 12-character password be used without
using that password directly as the session key. Actual credentials stay solely
in Render settings. That correction included no database migration or Phase 3 work.

Regression checks cover 16 seconds of interrupted/slow typing, wrong-password
feedback, no polling while signed out, session expiry, a manual connection retry,
cookie flags, origin guards, tampering, credential rotation and rate limiting.
The real hosted-image check reuses a cookie across replacement and process
restart, alongside the existing Start/Stop and saved-history checks.

## Implemented

- C++ retains at most 512 unacknowledged samples, releases only the acknowledged
  committed prefix, and replays the same samples/timestamps after data reconnect.
  Overflow and controller lease loss fault-stop with zero simulated output.
- Python retries the identical command, records the result, acknowledges only
  after PostgreSQL commit, restores EMA from the saved cursor, and reconciles boot
  and run identity before enabling control. An old cached reply cannot overwrite
  a newer live observation. Pre-Phase-2 HTTP Start IDs remain compatible.
- Same-boot recovery drains retained data after controller/API failures. Changed
  boot preserves the committed prefix and labels unresolved execution unknown and
  missing recording partial. Start is never replayed after a new boot.
- Local-only deliberate scenarios: lost Start reply, telemetry interruption,
  controller loss and rolled-back database write. Hosted mode refuses them.
- Console-first redesign: mineral background, ink-blue shell, copper accents,
  self-hosted Manrope, original projected wireframe with reduced-motion support,
  actual recovery diagnostics and the selected run's immutable step sequence.

## Verified evidence

- C++ build/CTest, real socket framing/deduplication/ACK/replay checks, retention
  overflow and responsive Stop, and silent-controller lease expiry passed locally.
- 21 Python tests passed with real PostgreSQL, including independent-connection
  visibility before ACK, duplicate ingestion, rollback on a sequence gap and stale
  cached reply handling. Ruff, formatting and mypy passed.
- Production frontend build, six behavior tests, formatting and npm audit passed.
  Both real Edge browser workflows passed; desktop and 390-pixel mobile captures
  are in docs/screenshots. CI separately runs Chromium.
- Hosted image checks passed: authentication/origin guards, private engine ports,
  idle connection renewal, real ownership-session loss and supervisor shutdown,
  exclusive deployment handoff, saved history after replacement and child failure.
- Impeccable full finish review requested four fixes; its subsequent verdict scored
  all four resolved and returned `ship` at that scope. A separate quality-bar card
  was not retained, so its ceiling assessment was limited to the saved contract.
  See DESIGN.md and docs/DESIGN_BRIEF.md for design and reference provenance.

Local reliability evidence from the final core run (synthetic, retained in the
local PostgreSQL history; not uploaded to the cloud):

| Scenario | Run | Observed evidence |
| --- | --- | --- |
| Lost Start reply | e85c2477-f169-4bf0-a9a1-4ed49e999d67 | One execution, two identical command attempts, 200 committed samples |
| Telemetry interruption | 0652e3c1-6604-4c3f-b5c7-4390b1c16de1 | Same-boot replay; 200 samples identical to baseline and correct EMA |
| Controller disconnect | 19803a84-6f34-4a4b-9979-dae0ff101c06 | Fault-stop, zero output, complete retained recording |
| Database transaction failure | 17171bee-db15-4c3a-88b2-3c361ee5892e | Transaction rolled back, no premature ACK, retained data recovered |
| API restart | 5b2cdc4e-e4ab-4e03-8d5e-eee50e920ac2 | Same boot reconciled, no automatic restart, complete retained recording |
| Engine restart | 3ef2f765-af18-4d06-8a09-bcbd0c73ee6a | Changed boot, immutable saved prefix, unknown execution and partial data |

## Cloud

Live URL: https://remote-experiment-control-lab.onrender.com.
Render service `srv-db4jf9mi0phs73ctof0g` is Free, Singapore, one Docker instance,
automatic deployment off. Neon Free project `young-hall-53222910`, database
`experiment_lab`, PostgreSQL 17, Singapore. Reuse these existing resources.
Direct/unpooled DATABASE_URL with full TLS verification stays in Render.
Sign in as `operator` using LAB_PASSWORD from the Render Environment page.
Never print secrets or request them in chat. See docs/HOSTING.md.

Pre-Phase-2 deployment: `ee7db8a65e81c524bd269e8a9682515fee0940d1`.
Before the Phase 2 release, the cloud audit found four saved runs, 462 samples and
zero active/pending recordings. The earlier private Page was only a screenshot
preview; the Render URL is the actual remotely controllable application.

## Walkthrough and checkpoint discussion

- `Instrument.call` encodes the request once and retries those same bytes. A lost
  response is not proof that Start failed. A new command ID could start twice.
- `Orchestrator.ingest` commits samples and the contiguous cursor in one database
  transaction, then sends ACK. A socket receipt alone is not durability.
- `Server::acknowledge` and `pump` retain only the bounded uncommitted
  tail and replay original data. The independent control connection remains usable.
- `Orchestrator.reconcile` compares boot/run identity before restoring ownership
  and never automatically starts an old experiment on a new engine boot.
- Execution and recording stay separate. Completed execution with missing tail
  data is finalizing, then partial after ten seconds; it becomes complete only
  when the contiguous committed cursor reaches the known final sequence.

Questions for this gate: Why must ACK follow commit? Why must a timed-out Start
retry keep its command ID, while a changed boot must not silently rerun it?

## Reproduce and limits

See docs/TESTING.md for normal, fault, TCP, sanitizer and hosted commands.
Local faults default off; tests use the explicit LAB_ENABLE_FAULTS=1 setting.
The write-failure demonstration injects a transaction exception; a separate
hosted test terminates the real database ownership session.

Retention is volatile and bounded: 512 samples is 5.12 seconds at 100 Hz. It cannot
promise lossless recovery from arbitrary outages or a replaced engine process.
This is one simulator and one controlling API worker, with best-effort scheduling.
No physical equipment or hardware emergency stop is implemented. Free hosting may
sleep or restart. Phase 3 now supplies CSV/replay, recipe versions and recording
statistics; two-device timing remains Phase 4. The chart loads separately from
the main UI, removing the earlier bundle-size warning. Repository license remains
undecided. See REVIEW.md for saved-data bounds and timing semantics.
