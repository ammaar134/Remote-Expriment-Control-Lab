# Instrument protocol v1 - initial contract

Status: implemented Phase 1 contract. See protocol/examples.jsonl for wire examples.

UTF-8 JSON objects terminated by LF over dedicated control and telemetry TCP
connections. TCP may split or combine frames: parsers accumulate bytes until LF.
Maximum frame: 65,536 bytes including LF. Oversized or malformed frames close the
connection; losing the controlling connection faults an active run.

Every message carries v=1, type, instrument_id and, after handshake, boot_id.
C++ creates a new boot ID on process start. A different boot invalidates in-memory
command history and telemetry assumptions.

Control starts with handshake; telemetry starts with subscribe using the observed
boot ID. One controlling connection and one telemetry subscriber per engine.
Commands use request_id for request/response correlation; start/stop/reset also use
command_id. Start and Stop identify run_id. Status and heartbeat do not mutate runs.

## Command semantics

Start accepts an immutable recipe and begins execution in the state-owner handler.
The response reports applied/running; it does not prove a sample was persisted.
An identical command_id and semantic JSON payload returns the original response.
Conflicting reuse returns COMMAND_CONFLICT. The cache is bounded to 256 commands;
records live for at least 120 seconds and records for the active run remain protected.
When no entry can be safely evicted, reject with COMMAND_CAPACITY rather than
silently forgetting a retry record.

Stop targets exactly one run. It is applied when the timer is cancelled and
simulated control output is zero; the response includes state and final_seq.
A repeated Stop may observe COMPLETED or FAULTED without changing history.
No samples is final_seq=-1. Samples use contiguous zero-based sequence numbers.

Ambiguous response timeout remains unknown. Reconcile by status and retry only
the identical command within the same boot/retention scope. Never issue a fresh
Start ID to recover a timeout. No automatic re-execution after a process restart.

## Recipe and signal

One to eight steps: setpoint in [0,1], duration_ms a positive multiple of the sample
period. sample_rate_hz is one of 10,20,25,50,100; total duration <=60 seconds and
total samples <=6,000. Default: 30 seconds at 50 Hz. Seed is an integer from 1 through 2,147,483,647.
First sample is seq=0 at logical time dt, after the first model step.

Response follows x[n]=u[n]+(x[n-1]-u[n])*exp(-dt/tau), x[-1]=0, tau=0.5 seconds.
Channels: response and reference, both in arbitrary units (a.u.).
Raw response is x plus uniform seeded noise; reference is 0.8*x plus independent
noise. The engine documents its exact PRNG in code and tests determinism within
the same engine version/numeric tolerance. Scheduling jitter paces emission but
does not enter the signal model.

Telemetry batches carry run/boot identity, samples, sequences, logical time,
device source UTC time and device monotonic elapsed time. Python records receipt
UTC independently. Never subtract unrelated process monotonic epochs.

## Stop, lease and bounds

Phase 1 polls status every 400 ms, renewing a 5-second controller lease checked
by the engine. Detected disconnect faults immediately; half-open peers fault when
the lease expires (best-effort scheduling, not a real-time guarantee).
Telemetry output queues are bounded; saturation or telemetry disconnect faults an
active run and sets simulated output to zero. Control is never queued behind data.

Terminal status can precede the final data frame. Python compares the highest
contiguous committed sequence with final_seq before declaring complete recording.
A bounded drain deadline converts unresolved gaps to visible partial data.

Phase 2 extends this version with post-commit cumulative telemetry ACKs and
same-boot retransmission. Neither guarantee is advertised in Phase 1.
