# Architecture decisions - Phase 1

These decisions describe the implemented Phase 1 slice. See PROGRESS.md for
validation results and the boundary of the current milestone.

## Ownership and data flow

- React sends operator intent and displays observations. It never confirms execution.
- One FastAPI process validates immutable run snapshots, coordinates commands,
  ingests samples, applies the EMA filter and writes PostgreSQL transactions.
- One separately running C++ process owns instrument execution, ticks, simulated
  output, deterministic measurement generation and local fault/stop behavior.
- PostgreSQL owns durable snapshots, commands, events and raw/derived samples.

Browser -> FastAPI -> C++ control connection.
C++ telemetry connection -> FastAPI -> PostgreSQL -> browser/review.

Monorepo: frontend/, backend/, instrument/, protocol/, tests/, docs/.
Docker Compose supplies a Linux C++ toolchain and a real PostgreSQL service on Windows
or Linux. Only the UI/API are published, on loopback.

## Consequential choices

Use versioned newline-delimited JSON over two TCP connections. This gives inspectable
messages and real process boundaries; gRPC would supply generated types but adds
tooling and obscures the byte-stream lessons. Sharing bounded fixtures and tests
will check the contract across languages.

Use one Asio io_context thread for C++ state and timers, with asynchronous socket
I/O. A dedicated acquisition thread is a credible alternative for heavier workloads,
but creates synchronization obligations this small 100 Hz simulator does not need.
No blocking network or database work belongs in that event loop.

Use Python asyncio for orchestration and PostgreSQL ingestion. A PostgreSQL advisory
lock will prevent two orchestrators from claiming the same instrument. One API worker
is a deliberate limit. HTTP polling can deliver the first live display; later richer
streaming must never govern ingestion.

## Invariants

1. At most one active run per instrument.
2. A persisted immutable snapshot precedes transmission of Start.
3. Retrying an identical command ID/payload cannot execute a second run within its
   documented boot/session scope; conflicting payload reuse is rejected.
4. STOPPED means ticking has ceased and the commanded simulated output is zero.
5. Disconnected is not the same as stopped; unknown is not confirmed failure.
6. Terminal execution and complete recording are different. Completeness requires
   every sequence from zero through the reported final sequence to be committed.
7. Buffers, frames, retries and run sizes have explicit bounds.
8. Raw samples remain immutable; filtering creates derived values.
9. Browser disconnection does not change backend ownership.
10. A new engine boot never silently restarts an experiment.

## Device state table

| State | Start | Stop for current run | Other transition |
| --- | --- | --- | --- |
| IDLE | RUNNING if valid and telemetry ready | reject: no run | none |
| RUNNING | reject: busy (identical retry returns cached result) | STOPPED after cancelling ticks and zeroing output | COMPLETED at final tick; FAULTED on control/data loss |
| COMPLETED | RUNNING for a new run | return terminal observation unchanged | none |
| STOPPED | RUNNING for a new run | return terminal observation unchanged | none |
| FAULTED | reject until reset | return fault observation unchanged | explicit reset -> IDLE |

Stop with an old run ID is rejected and cannot affect a newer run.
There is no engine STOPPING state: one event-loop handler cancels the tick timer and
sets output to zero before publishing STOPPED. The backend/UI still distinguish
Stop requested from that confirmed observation.

## Phase boundary

Phase 1 faults on control/telemetry disconnect or bounded-queue exhaustion; it does
not claim replay of unacknowledged telemetry. Phase 2 adds cumulative post-commit
acknowledgements, bounded same-boot retransmission and fuller restart reconciliation.
Run records preserve partial/unknown outcomes until evidence resolves them.
