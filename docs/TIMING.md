# Two-device timing

Open Timing, keep the educational defaults, and Start comparison. Two copies of
the same C++ executable run as sim-01 and sim-02. Each acquires 20 samples/second;
the default observation lasts 30 seconds. Original device time, Python receipt
time and estimated aligned time are selectable. The chart samples at most 300
existing points per device; the JSON download retains every committed point and
every probe. Review links expose each independent run's CSV and provenance.

## Clock model and measurements

`DeviceClock` anchors host UTC at Start and advances by local monotonic elapsed
time multiplied by `1 + drift_ppm / 1,000,000`, plus `offset_ms / 1000`. Defaults
are -750 ms/-3000 ppm and +1200 ms/+5000 ppm: deliberately exaggerated educational
settings, not realistic hardware accuracy. Bounds are ±5 seconds and ±10,000 ppm.
The OS clock, sample schedule, logical ticks and deterministic signal stay unchanged.
`device_elapsed_s` is the real local monotonic duration since that engine boot;
it is neither its simulated civil clock nor a timestamp comparable across boots.
Settings are immutable in the run snapshot. Existing saved timestamps are untouched.

The `clock_probe` command returns simulated device receive/send UTC. Python saves
its own send/receive UTC and a monotonic round-trip duration. Timestamps enclose
the application exchange; they are not kernel or network-interface timestamps.
Probes include device/boot/run identity, response attempts and group-local elapsed
time. No arbitrary monotonic epochs from different processes are subtracted.

`timing.estimate` uses `(device_receive + device_send - client_send - client_receive)/2`
as the offset at the client UTC midpoint. This is the four-timestamp relationship
described in [RFC 5905 §8](https://www.rfc-editor.org/rfc/rfc5905#section-8), used here
as a small educational estimator, not an NTP implementation. An asymmetric path
biases that midpoint. Receipt minus source time is not one-way network latency.

Reject retried probes, negative or >250 ms round trips, reversed device timestamps,
and UTC/monotonic disagreement >20 ms within an exchange. Across a group, >50 ms
UTC/elapsed disagreement invalidates alignment. Fewer than three valid probes
means insufficient offset evidence. Fit offset against UTC with least squares;
report drift only with eight probes, at least 20 seconds of span, uncertainty
≤1500 ppm and a slope magnitude below 2%. These thresholds are policy for this
demo, not universal clock quality standards.

Uncertainty is maximum half-RTT plus maximum fit residual plus 2 microseconds;
the slope allowance is twice that divided by observation span. These are heuristic
delay allowances, not confidence intervals or guaranteed bounds under arbitrary
asymmetry, clock jumps or changing oscillator drift. Without supported drift,
use constant offset and widen its allowance by observed offset variation.
The UI rounds offset to 0.1 ms and drift to whole ppm. The estimator never reads
injected settings; tests check known truth, asymmetric paths and insufficient data.
Injected offset applies at Start; measured offset applies at the probe midpoint.

Alignment inverts that fitted clock relationship and only supplies values inside
the observed probe window. Missing aligned values stay null. It creates a derived
view and never rewrites source/receipt timestamps. Aligned curves are not proof of
simultaneous physical execution. Free hosting and Python/C++ scheduling are soft
real-time, with no precision-hardware synchronization guarantee.

## Coordinated Start and failures

A persisted comparison ID makes identical HTTP retries idempotent. Each member
has a deterministic, different Start command ID and its own run, boot, configuration,
command-dispatch event, TCP send/reply timestamps and resolved result. TCP timestamps
describe the final exchange; `attempts` distinguishes retransmission. A dispatch
event and unknown outcome survive a missing reply; there is no invented ACK time.

Start attempts run independently. Wait for both bounded results before compensating
a failed or unconfirmed start with best-effort Stop on every created member run.
Stop commands/results remain in the run event log and comparison result. Missing
confirmation stays unconfirmed. No atomic transaction, consensus, barrier, PTP or
simultaneous-start claim is made. A comparison marked complete means the probe
window ended; each run still reports its own execution and recording state.

Operator Stop ends probing and sends separate Stop commands. A short window can
produce insufficient drift evidence. API restart marks unfinished comparisons
interrupted and does not replay Start; per-device reconciliation and controller
leases determine execution/recording outcomes. The hosted supervisor couples the
lifetimes of both engines and the API; a child failure restarts the container.

Migration 003 adds comparison requests/results and append-only probe evidence.
It does not rewrite any previous run or sample. One database owner controls both
devices with independent action/TCP locks and ingestion tasks. All API mutations
retain the existing session/origin protections. Simulated clock settings are
educational configuration; deliberate connection/database faults remain local-only.
