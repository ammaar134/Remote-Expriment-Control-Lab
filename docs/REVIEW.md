# Recipes and saved-data review

## Configure and save

Select the available `sim-01` response simulator. Give the recipe a name, choose
the sample rate and seed, and edit its ordered setpoints and durations. A run is
limited to eight steps, sixty seconds and 6,000 samples. Durations must align with
the selected sample period. The EMA alpha belongs to the saved version too.

Save recipe creates version 1. Load a saved recipe to reuse it. After changing it,
Save new version creates the next revision; earlier revisions and past runs do
not change. A stale edit is rejected if that version already has a child. Load
the newer version or use Save as new recipe to begin a separate family.
An unsaved new draft is also saved automatically as version 1 when Start is sent.

The browser retains a request ID after a failed save so retrying the same save
does not create duplicates. Changing the draft creates a new intent. The server
compares the entire payload when an ID is reused. Start references the chosen
version and rejects altered content instead of silently changing that version.

## Find and inspect

Review searches run/recipe names, execution outcome, recording status, instrument,
and inclusive UTC calendar dates. Apply filters submits the search; Clear removes
it. History is fetched in pages of fifty, with a maximum offset of 10,000. Review
does not poll the live instrument. Refresh reloads the list; reopening a run or
refreshing the browser reloads its evidence. An ongoing run links back to Monitor.

The full-run, last-ten-second and last-five-second chart windows use the API's
bounded chart query. It includes endpoints and each channel's minimum and maximum
in index buckets, with at most 800 points by default (1,200 maximum). These are
actual saved values. A narrowed window does not alter the database or exports.
Summary statistics use all committed samples, regardless of the chart window.
Population standard deviation over a stepped response describes signal variation;
it must not be presented as isolated measurement-noise reduction.

Run evidence includes run/device/boot/version identity, recipe, seed, filter and
model versions, engine/protocol versions, build identity, outcome and event detail.
Legacy snapshots stay unchanged; their migrated recipes start at revision 1.
Event history pages hold at most 200 records.

## Download

Export CSV becomes available when recording is complete or partial. It includes
every committed sample in sequence, never chart downsampling or display rounding.
Columns identify the run, device, boot and recipe version, then logical seconds,
source UTC, receipt UTC, monotonic device elapsed seconds, input, raw channels and
EMA values in arbitrary units. Quality columns disclose incomplete recording,
gaps before a sample, the known unrecorded tail and outcome reason. An unknown
final sequence leaves the tail count blank. A zero-sample run exports its header.

Download metadata is the companion JSON record: immutable configuration,
provenance, whole-recording statistics, timestamp meaning, commands and events.
It is also available for zero-sample and ongoing runs. Its bounded event/command
lists explicitly flag truncation after 2,000 events or 200 commands; the event
endpoint allows further pages. Save both files when retaining an experiment.

CSV uses standard delimiter/newline quoting and full float representations.
Potential formulas in user-controlled text receive a leading apostrophe for
spreadsheet safety; that escape is documented in the metadata. It does not change
the name stored in PostgreSQL. Files use a UUID-based filename.

## Replay

Replay saved run reads the saved samples and events. Play, pause, seek, speed
(0.5x–4x) and restart move a browser cursor. No Start, Stop or other instrument
command is sent, and replay does not create another run. The API and database must
be reachable, but the engine can be offline. This differs from starting the same
recipe/seed, which performs a new simulated acquisition and creates a new run.

Samples follow their saved logical times. Event positions are approximate offsets
from recorded UTC timestamps, clamped to the last sample time so a later recovery
event does not create hours of empty playback. Original event timestamps remain
visible and in metadata. An empty recording still shows saved events with no
invented measurements. The replay payload contains up to 6,000 samples and 2,000
events and declares event truncation. Missing data is never resimulated.

## State and database constraints

`ReplayPlayer` holds playback state separately from live control. Pausing cancels
its interval; seeking sets a saved-data cursor and pauses; restarting moves it to
zero. `ReviewWorkspace` never calls `/api/device`, so replay cannot accidentally
start the simulator or renew a controller lease.

Migration `002_recipe_revisions.sql` makes `(family_id, revision)` unique and
permits only one child for each parent version. Combined with append-only triggers,
this prevents ambiguous revisions and rewrites of existing evidence. The existing
single-orchestrator session lock and transactional saves serialize competing API
requests; constraints remain a database-level backstop.

## Phase 3 implementation and design continuity

Phase 3 extends the existing Science Gallery Console. The working Configure,
Monitor and Review surfaces retain the mineral ground, ink-blue shell, copper
emphasis, self-hosted Manrope, quiet borders and original illustrative wireframe.
The established `DESIGN.md` and `.impeccable/design.json` are preserved unchanged;
their historical finish-review account describes the earlier identity build.

The frontend now separates these responsibilities from the main console:

| Source | Responsibility |
| --- | --- |
| `frontend/src/RecipeLibrary.tsx` | Saved recipe loading, immutable revisions and save feedback within Configure. |
| `frontend/src/ReviewWorkspace.tsx` | History filters and pagination, selected-run loading, chart windows, whole-recording summary, downloads and replay entry. |
| `frontend/src/ReplayPlayer.tsx` | Independent saved-data cursor, playback controls and evidence at the selected position. |
| `frontend/src/RunEvidence.tsx` | Shared provenance, saved step sequence and paginated event timeline. |
| `frontend/src/RunStatus.tsx` | Separate execution and recording labels, including known missing samples. |
| `frontend/src/Chart.tsx` and `frontend/src/SignalChart.tsx` | Lazy chart loading and the shared measurement plot. |
| `frontend/src/format.ts` | Shared display formatting and workspace navigation. |

`frontend/src/App.tsx` still coordinates the console and live control;
`frontend/src/styles.css` and `frontend/src/InstrumentSculpture.tsx` retain the
incumbent visual rules and illustrative geometry. This component inventory
supplements the earlier source list in `DESIGN.md` without replacing its identity
record.

At viewport widths up to 760px, the current Review history panel has a maximum
height of 520px and contains both the filter form and recorded-run list. Its
contents scroll within that region. The earlier 290px mobile history description
in `DESIGN.md` refers to the prior history-only surface. The combined Phase 3
panel is an implementation adaptation; it is not a new global spacing or identity
token. The desktop history maximum remains 760px.

The Phase 3 finish review is recorded in
`.impeccable/review/phase3-review.md`. Its supplied captures cover Review at 1440px,
1270px and 390px, replay at 1440px, and Configure at 1440px and 390px. This does
not establish a new approved comp or a full UX/accessibility certification.
The retained direction contract records seed `b85cfff1`; no separate quality-bar
card, approved comp or original concept-roll output was retained, so those
historical inputs cannot be independently corroborated by this pass.
