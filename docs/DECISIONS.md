# Consequential decisions

## Separate engines, one controller owner

Two C++ processes reuse one proven engine and protocol. Each has its own boot,
state machine, sockets, retention and clock model. Python uses two Orchestrator
instances with separate locks; one PostgreSQL advisory session lock prevents
competing API owners. Reconciliation is scoped by device ID.

Alternative: a distributed controller and one service per device. That improves
isolation and scaling but requires owner leases, fencing and more operational
resources. This bounded two-device demo fits the approved free hosting. Its hosted
supervisor intentionally restarts all children when any child fails; this couples
availability and does not demonstrate geographically independent clocks.

## Durable ACK before memory release

Raw observations and the contiguous cursor commit in one transaction before an
ACK can release engine memory. Delivery may repeat; matching duplicates do not
advance filtering again. A 512-sample volatile window bounds memory and outages.
Commands have bounded per-boot deduplication and durable API request records.

Alternative: a durable device spool or broker. That could retain more data across
process loss, but adds disk/queue ownership, durability and recovery questions.
Here changed boots preserve the saved prefix and report partial/unknown evidence.
This is not an exactly-once or arbitrary-outage losslessness guarantee.

## Simulated clocks and evidence-based alignment

Clock parameters affect timestamp generation only. The same deterministic logical
ticks generate the waveform. Python measures four timestamps, fits a bounded
offset/drift estimate, and preserves originals alongside the derived view.
Insufficient windows or excessive jitter do not yield a drift number.

Alternative: changing OS clocks, hardware timestamping, PTP or a scheduled trigger
barrier. These require privileges, hardware and network assumptions outside this
educational simulator. Independent Start results and compensating Stop demonstrate
partial failure without claiming an atomic or simultaneous operation.

## Polling and bounded saved evidence

The browser polls observations; acquisition and database writes continue without
it. Review/replay read persisted data only. Main signal charts preserve extrema;
the timing comparison uses a disclosed 300-point stride per device for timestamp
placement. CSV and timing JSON preserve full committed observations.

Alternative: WebSockets and streaming chart state. Useful at larger scale, but
unnecessary for short 10–100 Hz runs. A bounded query plus independent statistics
keeps display reduction from silently becoming data reduction.

## Single-operator cloud access

The public shell opens a stable sign-in form; a signed HttpOnly cookie protects
API data and controls, and mutation Origin checks constrain browser requests.
Local Compose publishes only loopback HTTP and explicitly has no login.

Alternative: managed multi-user identity, roles, per-user run ownership and audit
policy. Those are appropriate before a shared real lab; they add complexity to a
single-operator demonstration and are not implied by this login screen.
