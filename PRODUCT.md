# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

A single operator learning and demonstrating remote experiment control, including
from a laptop connected to the hosted application.

## Product Purpose

Configure, run, monitor, stop and review a simulated signal-response experiment.
The browser observes a separate C++ engine through Python; PostgreSQL records
immutable configuration and actual measurements.

## Operating Context

The working Configure/Monitor/Review console is the first screen; Timing extends
it with a two-device comparison. No introductory
showcase is needed. Local Docker and authenticated free cloud hosting are supported.

## Capabilities and Constraints

Two independent simulated instruments; bounded sample rate, duration and retention. Execution,
connection and recording completeness are separate facts. No real hardware or
hard real-time guarantees. Phase 2 recovery and failure demonstrations remain
available.

Phase 3 adds immutable saved recipe versions, filtered and paginated run history,
bounded chart windows, whole-recording statistics, provenance, full-resolution CSV
and companion metadata downloads, and saved-data replay with playback controls.
Replay reads recorded evidence without issuing instrument commands or
reconstructing missing measurements; the API and database must remain reachable.

Timing reuses the C++ engine in two processes, with configurable simulated clock
offset and drift. Independent Start results, probe evidence, original/receipt
timestamps and derived alignment remain inspectable. Injected settings and
measured estimates are separate; insufficient measurements are labelled. The
comparison is educational and does not imply simultaneous hardware execution.

The Phase 5 handover documents setup, architecture, failure reasoning, consequential
decisions and a five-minute demonstration. PROGRESS.md records verification and
release status; the operator chooses the next discussion after these two phases.

## Brand Commitments

Remote Experiment Control Lab. User requests a distinctive, sophisticated yet
minimal redesign, a new palette, and appropriate 3D inspiration from 21st.dev.
The user delegates design selection while retaining the working console first.

## Product Principles

- Show observed state rather than desired state.
- Keep control actions clear and available without decorative distraction.
- Keep measurements and their provenance intact.
- Label simulation and partial or unknown outcomes honestly.

## Accessibility & Inclusion

Keyboard operation, visible focus, readable contrast, mobile layouts, text state
labels, and reduced-motion support are required by the adopted brief.
