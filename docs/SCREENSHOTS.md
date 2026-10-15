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

## Published-app walkthrough — 2026-10-15 UTC

The additional `*-live.jpg` files were captured directly in cloud Chrome from
https://remote-experiment-control-lab.onrender.com/ with the published frontend
and its authenticated live API. No local asset substitution, generated mockups,
credentials or personal information are included. The original Phase 4/5 PNGs
and their provenance above are unchanged.

- `configure-live.jpg`: settled Configure, instrument connected, default recipe
  ready to start; 640 × 757 capture.
- `monitor-live.jpg`: live acquisition detail at approximately 10.92 logical
  seconds, with 530 committed samples, the second step transition and recording
  diagnostics; 1170 × 751 viewport capture. The page header is outside this view.
- `review-live.jpg`: completed saved Review, 1,500 samples and final sequence 1499;
  1170 × 2390 full-page capture.
- `replay-live.jpg`: the same saved run, paused at 20.00 / 30.00 seconds with
  1,000 / 1,500 observations shown; 1170 × 2212 full-page capture. Replay sends no
  instrument commands.

Run `4f225c7b-71d1-4d5c-89ac-680d045dabba` was created at
`2026-10-15T07:27:20.211Z`. Its visible provenance identifies build
`658372309b242fc20f20ac6c321467ad1c070c62`, instrument `sim-01`, normal scenario,
seed 7, 50 Hz, three 10-second steps (0.25, 0.8, 0.35) and EMA alpha 0.15.
The run completed naturally and recording was verified complete before Review
and Replay captures. The browser displays local event times in UTC−07:00;
the explicit Created (UTC) field is the authoritative timestamp above.

This documentation pass exercised Configure → Start → live Monitor → completed
Review → paused Replay. It did not run failure demonstrations, modify application
code or hosting settings, or claim a new full regression-suite pass.
