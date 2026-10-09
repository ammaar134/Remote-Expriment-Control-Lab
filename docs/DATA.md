# Signal, time and evidence

The recipe contains 1-8 steps, each with a normalized setpoint in [0,1] and an integer
duration in milliseconds. Rates are 10,20,25,50 or 100 Hz. Each duration must divide
into complete sample periods. Maximum run: 60 seconds / 6,000 samples.
Seed range: 1 through 2,147,483,647.

At each logical step, dt=1/rate and:
`x[n] = u[n] + (x[n-1] - u[n]) * exp(-dt/0.5)`, starting from x[-1]=0.
Sample zero occurs at dt, after one model step. Segment boundaries change the
setpoint on the first tick of the next segment.

Response = x + uniform noise in [-0.02,0.02); reference = 0.8*x + independent noise.
Both channels use arbitrary units (a.u.). Noise uses the documented xorshift32
operations in Noise::next; the second stream starts from seed XOR 0x9e3779b9.
Tests establish repeatability for this engine/toolchain. Floating-point exp results
can differ slightly between platforms, so bitwise cross-platform identity is not
promised. Real-time Stop can produce a different final sequence from the same seed.

The steady-clock timer paces emission; scheduling jitter does not enter the waveform.
A tick more than 250 ms overdue faults the run instead of trying to catch up forever.
The simulated commanded output is set to zero at normal completion, stop and fault.

Python initializes EMA with the first raw measurement, then computes
`filtered[n] = alpha*raw[n] + (1-alpha)*filtered[n-1]`.
Smaller alpha reduces noise but adds lag. It rejects gaps and out-of-order new
samples; repeated already-recorded values are checked and ignored. Filter parameters
and version belong to the immutable snapshot; raw samples are never overwritten.

A sample stores logical time, source UTC, engine monotonic elapsed time and Python
receipt UTC separately. Receipt time includes network/scheduling delay. No clock
alignment or one-way network latency claim is made in Phase 1.

runs.persisted_seq is the last contiguous transactionally committed sequence.
A terminal device observation supplies final_seq. Data is complete only when they
match (including -1 for a zero-sample stop); a three-second drain deadline marks
remaining gaps partial. Device execution, connectivity and recording status are
separate observations in the UI.

The browser fetches at most 6,000 samples/run, retaining at most that count in memory.
Plots show at most about 1,000 points; full raw values stay in PostgreSQL. Server-side
extrema-preserving downsampling and full-dataset analysis are later-phase work.
