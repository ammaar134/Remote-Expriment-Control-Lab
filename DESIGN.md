---
name: "Remote Experiment Control Lab"
description: "A science-gallery visual system for an operating experiment console."
colors:
  blue: "#293e78"
  blue-hover: "#1d2d59"
  copper: "#a94927"
  chart-raw: "#5e719f"
  chart-filtered: "#263e7d"
  chart-reference: "#b35531"
  stop-red: "#923d32"
  stop-hover: "#74312a"
  ink: "#24304c"
  muted: "#5e687e"
  ground: "#edf0f3"
  panel: "#f9fafb"
  white: "#fff"
  shell: "#25365f"
  line: "#d4dae3"
  field-line: "#cbd2df"
  status-neutral-text: "#354366"
  status-neutral-bg: "#e2e6ef"
  status-live-text: "#254b88"
  status-live-bg: "#e0e9f8"
  status-complete-text: "#2e624e"
  status-complete-bg: "#e0eee8"
  status-stopped-text: "#605421"
  status-stopped-bg: "#eee9d5"
  status-fault-text: "#963d35"
  status-fault-bg: "#f6e5e1"
  status-uncertain-text: "#804420"
  status-uncertain-bg: "#f4e6d6"
typography:
  display:
    fontFamily: "Manrope, \"Segoe UI\", sans-serif"
    fontSize: "clamp(30px, 3.4vw, 45px)"
    fontWeight: 600
    lineHeight: 1.16
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Manrope, \"Segoe UI\", sans-serif"
    fontSize: "18px"
    fontWeight: 700
    lineHeight: 1.5
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Manrope, \"Segoe UI\", sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.5
  body:
    fontFamily: "Manrope, \"Segoe UI\", sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Manrope, \"Segoe UI\", sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.5
  data:
    fontFamily: "Manrope, \"Segoe UI\", sans-serif"
    fontSize: "24px"
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: "-0.02em"
  provenance:
    fontFamily: "Consolas, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  badge: "4px"
  control: "5px"
  navigation: "6px"
  panel: "8px"
spacing:
  inline-xs: "4px"
  inline-sm: "8px"
  compact: "12px"
  content: "18px"
  group: "24px"
  section: "32px"
components:
  button-primary:
    backgroundColor: "{colors.blue}"
    textColor: "{colors.white}"
    rounded: "{rounded.control}"
    padding: "13px 16px"
    width: "100%"
  button-primary-hover:
    backgroundColor: "{colors.blue-hover}"
  button-stop:
    backgroundColor: "{colors.stop-red}"
    textColor: "{colors.white}"
    rounded: "{rounded.control}"
    padding: "13px 20px"
  button-stop-hover:
    backgroundColor: "{colors.stop-hover}"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.blue}"
    padding: "10px 0"
  button-text-hover:
    textColor: "{colors.copper}"
  field:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "12px 13px"
    width: "100%"
  navigation:
    backgroundColor: "transparent"
    textColor: "#c6d0e5"
    rounded: "{rounded.navigation}"
    padding: "12px 22px"
  navigation-active:
    backgroundColor: "#e6eaf2"
    textColor: "{colors.shell}"
  status:
    backgroundColor: "{colors.status-neutral-bg}"
    textColor: "{colors.status-neutral-text}"
    rounded: "{rounded.badge}"
    padding: "5px 9px"
  panel:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.panel}"
  instrument-card:
    backgroundColor: "{colors.shell}"
    textColor: "#e4eafa"
    rounded: "{rounded.panel}"
    padding: "23px 25px 18px"
  history-item:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    padding: "18px 20px"
    width: "100%"
  history-item-selected:
    backgroundColor: "#e0e7f4"
  saved-recipe:
    textColor: "{colors.ink}"
    width: "100%"
---

# Design System: Remote Experiment Control Lab

## Overview

**Creative North Star: "The Science Gallery Console"**

The Science Gallery Console combines a cool mineral ground with an ink-blue shell, copper highlights and precise measurements. Manrope gives controls and headings a shared, quiet character; fine borders and tonal changes separate work areas without floating surfaces.

The working console remains the first screen. Configure, Monitor and Review share the same compact operational language: measured values use tabular numerals, status labels remain explicit, and the original wireframe sculpture is labelled illustrative. It supplies spatial character without representing instrument state.

This record describes the completed replacement visual world in the current source. The finish-review handoff recorded an initial fix disposition, then a pass / ship verdict after the saved recipe steps, proportional preview, raw trace contrast and SVG control icons were corrected. That review scope is not a full UX or accessibility certification.

**Key Characteristics:**

- Cool mineral surfaces and an ink-blue working shell.
- Copper marks emphasis, focus and reference relationships.
- Flat bordered panels with compact, gently rounded controls.
- Tabular measurements, explicit state text and saved evidence.
- One original projected SVG sculpture, with reduced-motion support.

Source of truth: `frontend/src/styles.css`, `frontend/src/App.tsx` and `frontend/src/InstrumentSculpture.tsx`. The selected direction is recorded in `docs/DESIGN_BRIEF.md`; `PRODUCT.md` supplies the durable operating and inclusion constraints. Frontmatter values describe shipped styles. Synthesized tonal ramps in the sidecar are panel previews, not additional shipping color tokens.

The public [Geometric Sphere preview by Dhileep Kumar GM](https://21st.dev/@dhileepkumargm/components/geometric-sphere) was a visual reference. Its account-locked implementation was not used; the projected SVG geometry is original. Manrope is self-hosted from `frontend/public/fonts/Manrope.ttf` under the bundled SIL Open Font License at `frontend/public/fonts/OFL-Manrope.txt`. No raster assets ship with this visual system; review screenshots are evidence, not application imagery.

## Colors

The palette pairs cool mineral neutrals with deep blue and restrained copper; semantic state pairs remain distinct from the identity palette.

### Primary

- **Instrument Blue** (`blue`): primary actions, range controls, focus borders, recipe preview edges and actionable text; `blue-hover` deepens the primary action on hover.
- **Copper** (`copper`): the visible keyboard outline, insertion caret, numbered steps and text-action hover.
- **Measurement inks** (`chart-raw`, `chart-filtered`, `chart-reference`): the lighter blue raw response, deeper blue EMA and copper reference are intentionally separate values. Preserve the respective line widths and labels described under Components.

### Secondary

- **Stop Red** (`stop-red`, `stop-hover`): the explicit Stop action.
- **State pairs** (`status-*-text` and `status-*-bg`): neutral, running/recording, completed/complete, stopped, faulted/rejected and unknown/partial/draining. Never detach the tint from its state text.

### Neutral

- **Ink** (`ink`) and **Slate** (`muted`): primary text and supporting explanation.
- **Mineral Ground** (`ground`), **Panel Paper** (`panel`) and **White** (`white`): page canvas, bounded work areas and editable fields.
- **Blue Shell** (`shell`): the identity/navigation band and instrument card.
- **Fine Line** (`line`) and **Field Line** (`field-line`): panel divisions and input boundaries. Dark surfaces use lighter contextual text and rules specified in the component snippets.

### Named Rules

**The Operational Accent Rule.** Use blue for primary controls and measurement structure; use copper for focus, step indices and reference emphasis. State colors communicate labelled outcomes.

## Typography

**Display Font:** Manrope, with Segoe UI and sans-serif fallbacks.
**Body Font:** the same self-hosted variable Manrope family.
**Label/Mono Font:** Manrope for labels and tabular measurements; Consolas/monospace for run identifiers.

The type system is compact and readable, with a modest title-to-body contrast. The self-hosted face declares weights 200–800 and `font-display: swap`; the interface primarily uses 400–700. Headings use slight negative tracking, while short operational metadata may use positive tracking.

### Hierarchy

- **Display:** the responsive page heading; its exact clamp, weight and line height are in frontmatter.
- **Headline:** section headings. The instrument and launch cards use local 15px headings; the instrument heading uses weight 500.
- **Title:** compact subsection headings.
- **Body:** the root text role. Subtitles use 13px, fall to 12px on mobile and stop at 70ch.
- **Label:** form labels. Supporting metadata uses 10–12px rather than creating another display tier.
- **Data:** launch totals. Diagnostics use 18px/600; step values, timestamps, preview labels and saved recipe cells use tabular numerals.
- **Provenance:** machine identifiers, wrapping where necessary.

### Named Rules

**The Measured Type Rule.** Keep changing measurements tabular. Reserve monospace for machine provenance such as run IDs; ordinary controls and numbers remain in Manrope.

## Layout

A horizontal identity band leads into a compact connection strip and centered workspace. The main region has a maximum width of 1536px. Desktop workspace gutters are 4.8%, with 36px top padding. The header uses 4.5% gutters and a 98px minimum height.

Configure uses `minmax(0, 1.25fr) minmax(320px, 0.85fr)` columns and a 32px gap. Recipe controls occupy the wider panel; the instrument and launch summary stack beside them with an 18px gap. Form fields use two equal columns. The recipe panel uses 28px by 32px padding.

Review uses `minmax(230px, 0.7fr) minmax(0, 1.8fr)` columns with a 24px gap. Saved evidence uses two columns in Monitor and a single evidence column in Review. Four diagnostic columns become two on mobile.

At a maximum width of 1050px, the header note and simulation side label disappear, the Configure grid narrows to `minmax(0, 1.1fr) minmax(295px, 0.85fr)` and its gap becomes 22px. At 760px, navigation wraps to a full-width row, Configure and Review become single columns, and workspace gutters become 6% with 28px top padding. Recipe padding becomes 22px by 18px. The history list is capped at 290px on mobile, compared with 760px on desktop. Evidence and chart panels tighten their horizontal padding to 16px.

Use the recorded spacing tokens as the recurring rhythm, not a claim that all spacing is on one rigid scale. The source also uses local adjustments around typography, chart labels and the sculpture.

## Elevation & Depth

The system is flat at rest: tonal surfaces and one-pixel borders establish structure. There are no floating panel shadows. The selected history row uses an inset outline, not apparent elevation. Perspective comes from the original projected wireframe and its faint elliptical ground mark.

### Shadow Vocabulary

- **Selected history boundary:** `inset 0 0 0 1px #8295be`; the only authored CSS box-shadow.
- **Illustrative ground mark:** an SVG ellipse at opacity 0.09 inside the instrument sculpture; not a reusable card shadow.

### Named Rules

**The Flat Surface Rule.** Separate panels with tone and fine borders. The selected history inset is a selection boundary, while the sculpture alone supplies illustrative spatial depth.

## Shapes

Panels and the instrument card use the largest recorded radius; inputs and action buttons use the control radius, navigation is slightly softer, and status badges are compact rounded rectangles. Thin boundaries and aligned columns carry the precision. Circles belong to connection dots, the identity mark and the sphere rather than to every control.

Control icons are inline SVG: the Start arrow, Stop square and Remove cross. The signature sphere combines twelve projected meridians, seven parallels, a copper orbital ellipse and a small satellite point. It is constructed from geometry rather than a raster or an imported 3D scene.

## Components

### Buttons

Quiet, definite actions with visible state.

- **Primary:** full-width blue with white text, the recorded control radius and padding, and a minimum height of 48px. A right-aligned SVG arrow anchors the Start label.
- **Stop:** red with a white SVG square and a minimum height of 46px; the mobile layout reduces its padding and type size.
- **Text action:** underlined blue text, turning copper on hover. Keep this subordinate to Start and Stop.
- **Interaction:** backgrounds and text colors transition over 160ms with `ease-out`. Disabled buttons have opacity 0.48 and a not-allowed cursor. Keyboard focus uses a two-pixel copper outline, offset by four pixels. Reduced motion disables transitions and animations.

### Inputs / Fields

White, fine-lined editable surfaces.

Inputs and selects fill their available width and have a minimum height of 44px. Their border darkens to the source hover treatment and shifts to blue on focus; the copper focus-visible outline remains distinct. Step inputs have accessible per-step labels. The EMA range control uses blue native accent coloring and displays its current value. Validation and disabled Start states communicate unavailable actions with explanatory text.

### Navigation

A compact horizontal group in the blue shell. Default items are pale blue text on transparent backgrounds; hover adds a lighter blue surface, while the active item uses a pale surface, shell-colored text and weight 700. On mobile, the three items share a full-width row. Retain native button keyboard behavior and the global focus outline.

### Status labels

Small rectangles keep execution and recording separate. Running and recording use the blue pair, completion uses green, stopped uses ochre, fault/rejection uses red, and unknown/partial/finalizing uses amber. Labels can wrap. Missing sample counts belong to the recording label when known. The instrument card has its own pale badge treatment.

### Panels and recorded-run list

Work panels use panel paper, a fine border and the panel radius. Padding reflects content density: the recipe editor is roomier than compact summaries. History rows are full-width buttons with a dividing rule, muted timestamps, status labels and a tonal hover/selection surface. Selected rows add the inset boundary described above.

### Recipe preview and saved recipe

The preview is a compact proportional diagram: segment flex weights equal duration in milliseconds, and bar height equals the clamped normalized setpoint multiplied by 45px. The preview region is 65px tall with four-pixel gaps, a blue top edge and numeric values below. It does not add a minimum bar height that exaggerates small inputs.

Saved evidence includes a semantic table captioned “Saved step sequence”, with step, setpoint and duration columns drawn from the immutable snapshot. Its fine row rules, left alignment and tabular numerals retain the same measurement language.

### Signal chart

A 290px responsive chart displays raw response, EMA and reference over logical time. Raw, filtered and reference lines use the frontmatter measurement inks with widths 1px, 2.5px and 1.3px respectively. All three use no point markers or animation. Horizontal grid lines are dashed; the y-domain is -0.1 to 1.1. The legend labels the traces, and the tooltip supplies logical time. Display sampling does not rewrite the saved measurements.

### Instrument sculpture

The original SVG occupies a 183px region, reduced to 175px on mobile. Horizontal pointer movement changes its projection around the resting turn of 0.35 radians; pointer exit returns it to rest. With reduced motion enabled, pointer movement does not rotate it. The sculpture is hidden from assistive technology, while its visible caption identifies the geometry as illustrative and the adjacent text separately reports observed state.

The sidecar renders the resting SVG without requiring React or a 3D library; runtime pointer interaction remains in `InstrumentSculpture.tsx`.

## Do's and Don'ts

### Do:

- **Do** keep the working controls, observed state and saved evidence visually primary.
- **Do** use text labels alongside state colors and distinguish execution from recording.
- **Do** preserve the proportional recipe preview: duration controls width and normalized setpoint controls height.
- **Do** retain the saved step table with step, setpoint and duration columns.
- **Do** keep focus visible and honor reduced-motion preferences.
- **Do** label the sphere as illustrative and keep its appearance separate from instrument state.

### Don't:

- **Don't** use the sculpture as a loading, connection or measurement indicator.
- **Don't** replace the self-hosted Manrope display face with a system display face.
- **Don't** substitute text glyphs or icon fonts for the implemented inline SVG control icons.
- **Don't** add lifted card shadows or promotional overlines to the operational console.
- **Don't** infer complete recording from a completed execution label.

Not canonized or repaired in this documentation pass: no additional implementation defects were adjudicated. The four finish-review findings were already corrected; small operational metadata and the existing chart accessibility treatment are recorded as implementation facts, not a blanket UX or accessibility endorsement.
