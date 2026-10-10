# Troubleshooting

- **Repeated sign-in prompts:** the hosted app uses an in-page form, not a native
  browser dialog. Close any old dialog and reopen the live URL after an upgrade.
  Wrong credentials appear inline; wait one minute after too many attempts.
  A session lasts 12 hours and survives refresh. Password/key rotation requires
  another sign-in. The free host may take roughly a minute to wake.

- Docker engine unavailable: start Docker Desktop (Linux containers) and check
  `docker info`. A Docker startup failure must be resolved before Compose tests.
  Never use factory reset or volume pruning as a routine startup step.
- Build needs network: first build fetches pinned npm/Python/C++ dependencies.
  Retry a failed download before changing versions.
- Port 8000 in use: stop the other owner or deliberately change the Compose loopback
  port and allowed browser origins together.
- API/database readiness: inspect `docker compose ps` and `docker compose logs --tail 50 lab`.
  Never paste credentials or entire environment dumps into issue reports.
- Another orchestrator owns this database: run one API worker and one API instance.
  PostgreSQL holds the ownership lock for the controlling connection's lifetime.
- Instrument fault: preserve/read the saved run evidence, then use Acknowledge fault.
  A new boot or reconnect never automatically repeats Start.
- Partial recording: keep the warning and final/persisted sequences. Same-boot
  reconnect can recover retained samples; a new engine boot cannot reconstruct
  a lost volatile tail. Never replace the warning with an assumed completion.
- Failure demonstrations are absent: they require explicit `LAB_ENABLE_FAULTS=1`
  on both local services. Hosted mode deliberately refuses these scenarios.
- Browser refresh: recording continues independently; reopen Monitor or saved Review.
- Tests cannot connect to TCP ports: stop the API first for protocol tests, since the
  engine permits only one controller and telemetry subscriber.

Normal `docker compose stop`, `up` and `down` preserve the named PostgreSQL volume.

**Destructive reset, only when you deliberately want to delete this project's entire
saved history:** `docker compose down --volumes`. Confirm the Compose project is
`experiment-lab` before using it; rerun setup/up to start empty. This command is not
part of normal startup or automated local verification.
