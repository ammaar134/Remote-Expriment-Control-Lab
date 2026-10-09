# Remote Experiment Control Lab

A local laboratory-control portfolio project using React/TypeScript, Python/FastAPI,
a separate C++ instrument simulator, and PostgreSQL.

**Status:** Phase 1 is in progress. No runnable application is claimed yet.
See [progress](docs/PROGRESS.md), [architecture](docs/ARCHITECTURE.md), and
[protocol](docs/PROTOCOL.md).

The simulator models a bounded first-order signal response with seeded measurement
noise. There is no connection to physical equipment. Its Stop action is a simulated
control, not a hardware emergency stop.

## Milestones

1. One instrument: configure, start, live raw/filtered samples, confirmed stop, saved review.
2. Failure handling: reconciliation, retransmission, durable acknowledgements, fault tests.
3. Operator experience: recipe versions, export, replay, accessibility and visual review.
4. Two instances of the same engine: educational clock offset/drift comparison.
5. Clean-start verification, engineering review and a concise walkthrough.

Each milestone includes meaningful checks and a short discussion checkpoint.
The application remains local-only. A repository license has not been selected.
