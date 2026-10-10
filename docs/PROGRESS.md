# Progress

## Phase 2 checkpoint — 2026-10-10, Pacific/Auckland

Phase 2 and the concurrent redesign were explicitly authorized. The operator
keeps the working console first and delegated visual selection. Phase 3 has not
started; stop here for the checkpoint discussion after publication/deployment.

Repository: public ammaar134/Remote-Expriment-Control-Lab. Work branch:
`codex/phase-2`; publication to `main` and the existing free hosting are approved.
Core reliability commit: `2a79d1dce989c5ac31da6c590b87ada2abb62dc8`.
Its complete Linux CI passed, including C++ sanitizers:
https://github.com/ammaar134/Remote-Expriment-Control-Lab/actions/runs/38045003326.
Console/documentation publication and final exact-commit CI are being finalized.

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
sleep or restart. CSV/replay, fuller recipe management, richer analysis and two-
device timing belong to later phases. The ~607 kB uncompressed chart bundle still
has a build size warning. Repository license remains undecided.
