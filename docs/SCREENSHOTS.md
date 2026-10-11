# Screenshot evidence

Captured 2026-10-11 (Pacific/Auckland) with Playwright/Edge. These are actual
application renders with synthetic C++ observations stored in the hosted Neon
database. They are not generated mockups; no credentials appear in the captures.

- Configure desktop, Monitor, Review desktop/mobile: live release `cfe9c58`,
  captured through the real acquisition/refresh/review/Stop browser workflow.
- Timing desktop/mobile: final candidate production frontend against the same
  authenticated live API and completed real 26-second comparison. Current draft
  settings show 30 seconds; saved evidence correctly shows its 26-second window.
  Measurements are from the selected recording, while device state in the setup
  region is the current state after a later operator Stop.
- Configure mobile and Replay: final candidate production frontend against the
  same saved cloud data. Configure was recaptured after loading settled. Replay
  intentionally shows its paused zero-time state, before the first saved sample.

For the candidate captures, Playwright served locally built static assets on the
live origin while all API requests used the real authenticated cloud service.
This validated the corrected responsive timing graph before publication; it did
not modify saved data. Final release checks confirm the published build separately.

Widths: desktop 1440px, Timing additionally 1270px, mobile 390px. Full-page captures
start at the document top. Timing uses a responsive SVG coordinate width so axis
labels retain a measured 12px size at each viewport instead of scaling into tiny
text. The 1270px and mobile chart-detail review evidence remain in ignored
`.impeccable/review/`; documented representative renders are in `screenshots/`.

Impeccable's inherited identity contract and third-party reference provenance are
in DESIGN_BRIEF.md. The app's only supplied font is self-hosted Manrope; the graph,
icons and wireframe are original code. No new raster asset is shipped in the app.
