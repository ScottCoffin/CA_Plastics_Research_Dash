---
name: Plastiverse Live
description: Global plastics-research platform; a black story ground that bursts into an airy light ground of navy ink, slate data and one coral live mark.
colors:
  coral: "#fa6b68"
  coral-ink: "#c53e39"
  slate: "#436487"
  slate-2: "#86a9bf"
  mint: "#c5eadf"
  wash: "#e9f1ef"
  sun: "#fff49a"
  gold: "#e2b714"
  ground: "#f6f8f9"
  paper: "#ffffff"
  night: "#000000"
  ink: "#17263d"
  ink-2: "#4d5d73"
  line: "#c4d0d6"
  grid: "#e4eaee"
  hatch: "#f0f3f5"
  on-dark: "#eef1f8"
  on-dark-line: "#252c40"
  credit: "#9fb0bf"
typography:
  display:
    fontFamily: "Schibsted Grotesk, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "clamp(40px, 5.6vw, 80px)"
    fontWeight: 400
    lineHeight: 1.03
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Schibsted Grotesk, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "clamp(30px, 3.9vw, 56px)"
    fontWeight: 400
    lineHeight: 1.03
    letterSpacing: "-0.03em"
  headline-section:
    fontFamily: "Schibsted Grotesk, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "clamp(30px, 3.6vw, 52px)"
    fontWeight: 400
    lineHeight: 1.05
    letterSpacing: "-0.03em"
  statement:
    fontFamily: "Schibsted Grotesk, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "clamp(19px, 1.8vw, 27px)"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Schibsted Grotesk, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "20px"
    fontWeight: 500
    letterSpacing: "-0.01em"
  lede:
    fontFamily: "Schibsted Grotesk, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "clamp(16px, 1.3vw, 19px)"
    fontWeight: 400
    lineHeight: 1.5
  body:
    fontFamily: "Schibsted Grotesk, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.5
  ui:
    fontFamily: "Schibsted Grotesk, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Schibsted Grotesk, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.45
  wordmark:
    fontFamily: "Schibsted Grotesk, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "18px"
    fontWeight: 700
    letterSpacing: "0.09em"
  data:
    fontFamily: "Martian Mono, ui-monospace, Cascadia Mono, Menlo, Consolas, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.5
  data-cell:
    fontFamily: "Martian Mono, ui-monospace, Cascadia Mono, Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    fontFeature: "tnum"
rounded:
  none: "0px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
  gutter: "clamp(16px, 3.4vw, 48px)"
  band: "clamp(72px, 10vw, 128px)"
  header: "60px"
components:
  header:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    height: "{spacing.header}"
  header-on-dark:
    backgroundColor: "{colors.night}"
    textColor: "{colors.on-dark}"
    height: "{spacing.header}"
  button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.ui}"
    rounded: "{rounded.none}"
    padding: "8px 14px"
    height: "40px"
  button-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  button-solid:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.ui}"
    rounded: "{rounded.none}"
    padding: "8px 14px"
    height: "40px"
  button-on-dark:
    backgroundColor: "{colors.night}"
    textColor: "{colors.on-dark}"
    rounded: "{rounded.none}"
    padding: "8px 14px"
  button-solid-on-dark:
    backgroundColor: "{colors.on-dark}"
    textColor: "{colors.night}"
    rounded: "{rounded.none}"
    padding: "8px 14px"
  picker:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    width: "min(420px, calc(100vw - 32px))"
  picker-row:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "10px 16px"
  footer:
    backgroundColor: "{colors.night}"
    textColor: "{colors.mint}"
    padding: "48px"
  evidence-cell:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.data-cell}"
    height: "64px"
---

# Design System: Plastiverse Live

## Overview

**Creative North Star: "From Night to Daylight"**

Plastiverse Live is told as one passage from darkness into light. The story opens on a pure black ground where real photographed plastics and real paper pages sit under hard light; once the knowledge bulb bursts, the page turns to an airy, nearly white ground and everything after is flat data drawn in navy ink and slate, with a single coral mark for what is live. The light half is the working half of the system: calm, square, hairline-ruled, generous with air, and quiet enough that the one coral mark carries the meaning.

The system is restrained by default and dramatic only once, in the landing story. Type is a regular-weight grotesk set large with tight tracking, so headlines read as plain statements rather than shouts; a narrow monospace appears only where a number or a source is being cited. There are no rounded corners, no decorative shadows, and no ornament on the light ground beyond a faint 24 px grid behind the regions band.

**Scope: platform-wide versus landing-only.** The tokens in this file are the `--pv-*` block at the end of `framework/src/design/tokens.css`; the older California system above it in that file is out of scope until VD-SM carries this one into the California pages.

- **Platform-wide** (every Plastiverse Live page, and what VD-SM carries into California): the colour tokens and their contrast rules, the Schibsted Grotesk and Martian Mono pairing and type ramp, square corners and hairline borders, the fixed 60 px header with the sunburst mark and "PLASTIVERSE **LIVE**" wordmark, the outline and solid buttons, the region picker, the black footer with the full logo, the coral-ink focus ring, and the 860 px collapse.
- **Landing-only** (the global landing at `/`): the sticky canvas scroll story, its timeline and easing, the black-to-light burst, the header's on-dark state, the story captions and their measured safe zones, the paper-page shadow, the scroll cue, the reduced-motion stills, the evidence matrix and the world pixel map as drawn here.

**Key Characteristics:**
- Two grounds: black for the story and the footer, a cool near-white for everything else.
- Navy ink, slate data, coral only for "live".
- Regular-weight headlines with -0.03em tracking; monospace only for data and sources.
- Square corners and 1 px hairlines; no rounded surfaces, no card shadows.
- Real photographs and paper pages before the light; flat data marks after it.

## Colors

A cool navy-and-slate palette taken from the logo, lit by one warm coral and a sunburst yellow.

### Primary
- **Live Coral** (`coral`): the brand accent. "LIVE" in the wordmark on dark, California on the world map (breathing), the live row's swatch in the region picker, the one highlighted mark in each feature pictogram, text selection, and accents on the black ground. On the light ground it appears only as a fill or as large text.
- **Coral Ink** (`coral-ink`): coral darkened for text on light. "LIVE" in the light header, "Open atlas" and feature links, the dashed "in preparation" swatch, Norway's dashed outline on the map, gap-cell labels, and every focus ring. The spec proposed #D9443F; it measured 4.06:1 on the ground and failed AA, so the shipped value is darker (4.6:1, ADR-PLAT2-BUILD-2026-11-17).

### Secondary
- **Data Slate** (`slate`): data marks on light: chart dots, network nodes, the top step of the country ramp, and the full-strength end of the evidence-cell shading.
- **Mid Slate** (`slate-2`): the middle data step and the secondary fills in feature pictograms.
- **Mint** (`mint`): secondary text on the black ground (story paragraphs, the scroll cue, the skip link, footer text) and a light data step in the country ramp.
- **Wash** (`wash`): the lowest data step (countries with under 30 works).

### Tertiary
- **Sun** (`sun`): the sunburst mark on dark and the bulb before the burst.
- **Gold** (`gold`): the sunburst mark on light and the bulb after the burst.

### Neutral
- **Ground** (`ground`): the light page ground after the burst, the header on light, and the body background of every Plastiverse Live page.
- **Paper** (`paper`): raised surfaces on the ground: buttons, the region picker, the base of evidence cells, paper pages in the story.
- **Night** (`night`): the story ground before the burst, the header while the story is dark, and the footer.
- **Ink** (`ink`): all primary text on light, button borders, the picker's outer rule, and the top rule of the feature list.
- **Ink 2** (`ink-2`): secondary text on light: ledes, captions' paragraphs, picker notes, source lines.
- **Line** (`line`): hairline dividers on light: header bottom border, picker rows, evidence-cell borders, feature-list separators.
- **Grid** (`grid`): the 24 px background grid behind the regions band.
- **Hatch** (`hatch`): the alternate stripe in hatched gap cells.
- **On-dark** (`on-dark`): headline text on the black ground and the inverted solid button in the dark header.
- **On-dark Line** (`on-dark-line`): hairlines on the black ground (dark header border, still-frame dividers).
- **Credit** (`credit`): the 11 px image-credit text in the footer.

`--pv-cream` is defined as a logo reserve but no surface uses it yet; it is not part of the working palette until one does.

### Named Rules
**The Coral Ink Rule.** On a light ground coral is a fill or large text only; any coral text, arrow or focus ring at body size uses coral-ink. On the black ground, coral itself is used.

**The One Live Mark Rule.** In every data graphic, coral marks the single live or featured thing (California, the live atlas row, the last mark of each pictogram); everything else is ink, slate or mint. If two things on one view are coral, one of them is wrong.

**The Mint After Dark Rule.** Mint is text only on the black ground. On light it may appear only as a data-ramp fill step, never as text.

## Typography

**Display Font:** Schibsted Grotesk (variable, weights 400 to 700; fallback system-ui, -apple-system, Segoe UI, Roboto, sans-serif)
**Body Font:** Schibsted Grotesk
**Label/Mono Font:** Martian Mono (static instance, weight 400 at width 87.5; fallback ui-monospace, Cascadia Mono, Menlo, Consolas, monospace)

**Character:** A sober news grotesk set at regular weight and tight tracking, so large statements stay calm; a narrow, slightly condensed mono marks the places where the page cites a count or a source.

Both faces are self-hosted latin woff2 subsets under `site/assets/fonts/` with their OFL texts and `PROVENANCE.md`. On the landing they are declared by `@font-face` in the page's front-matter `head`; a platform-wide rollout should declare them once in `framework/observablehq.config.js`, as the build spec intended.

### Hierarchy
- **Display** (400, clamp 40 to 80 px, 1.03, -0.03em): the story's opening statement. The very first caption runs one step smaller (clamp 36 to 72 px).
- **Headline** (400, clamp 30 to 56 px, 1.03, -0.03em): story caption headings, balanced wrapping. The chart caption runs smaller (clamp 26 to 42 px) so it sits over the empty early years.
- **Headline Section** (400, clamp 30 to 52 px, 1.05, -0.03em, max 18ch): section headings after the story ("The live evidence map.").
- **Statement** (400, clamp 19 to 27 px, 1.3, -0.01em): bottom-anchored story sentences and the closing "California is live; Norway is next."
- **Title** (500, 20 px, -0.01em): feature-list item names.
- **Lede** (400, clamp 16 to 19 px, 1.5, ink-2, max 56 to 60ch): the paragraph under a headline.
- **Body** (400, 17 px, 1.5): running text and picker rows.
- **UI** (400, 15 px): navigation links and buttons.
- **Label** (600, 13 px): picker header, link-actions ("Open atlas" at 14 px 600); notes at 13 px 400 in ink-2.
- **Wordmark** (700, 18 px, 0.09em, uppercase): "PLASTIVERSE LIVE" only.
- **Data** (Martian Mono 400, 11 px): source and citation lines, table headers, legends, chart axis labels.
- **Data Cell** (Martian Mono 400, 12 px, tabular figures): counts inside evidence cells.

### Named Rules
**The Mono Is Evidence Rule.** Martian Mono sets numbers, axis and table labels, legends and source lines, and nothing else: never a heading, button, link or label above a heading.

**The Regular-Weight Headline Rule.** Headlines are weight 400 with negative tracking; size, not weight, makes hierarchy. Weight 700 belongs to the wordmark alone.

## Layout

The light half of the platform is a single centred column (max 1344 px) inside a fluid side gutter (`gutter`, 16 px on phones to 48 px on wide screens) that also aligns the header, story captions and footer. Sections are full-bleed bands with generous vertical padding (`band`, 72 to 128 px) and a 60 px scroll margin so anchors clear the fixed header. Inside sections, two-column grids pair a heading block with content: the regions band puts the map beside a 300 to 400 px picker (gap 32 px); the feature band puts the heading beside a 1.5x list (gap 48 px). Spacing steps through 8, 12, 16, 24, 32 and 48 px.

Responsive behaviour turns on three breakpoints. At 860 px or less, two-column grids stack, story captions take the full width, header text links hide (the Regions button stays), and the map's country outlines drop. At 600 px or less, the evidence table drops its minimum width and switches to abbreviated labels so it fits without sideways scrolling. At 430 px or less, the header's solid "Get updates" button hides (the footer carries it). The header respects the top safe-area inset and the footer the bottom one.

**The Measured Safe Zone Rule (landing-only).** Story text never overlaps an image. Layout measures each caption's text box and places every visual right of the widest side caption plus 40 px (or 40% of the width, whichever is greater) on desktop, and between the top and bottom captions at 860 px or less.

## Elevation & Depth

The system is flat. Depth on the light ground comes from tone and rules: paper surfaces sit on the slightly cooler ground, edged by a 1 px ink rule when interactive (buttons, the picker) and by 1 px line hairlines when structural. Hover and selection are tonal shifts (an ink fill on buttons, a coral tint on picker rows), never lifts. The black ground needs no elevation at all; the header separates from it by an on-dark-line hairline.

### Shadow Vocabulary
- **Paper page** (`box-shadow: 0 10px 30px rgb(0 0 0 / .55)`): landing-only, on the real paper first pages as they stack over the black story ground. It is the one shadow in the system and exists to make photographed paper read as physical.

### Named Rules
**The Flat Light Rule.** Nothing on the light ground casts a shadow. A surface that needs separating gets a hairline or a paper fill.

## Shapes

Every corner is square (`rounded.none`): buttons, the picker, table cells, swatches, map pixels and pictogram bars. The form language is rectilinear and ruled: 1 px borders, a 24 px background grid, a pixel-grid world map, hatched 45-degree stripes for missing evidence and dashed outlines for regions in preparation. The only curves are data marks (dots, network nodes) and the sunburst mark's disc and rays. The favicon is the one rounded tile (5 px on 26 px), as an app-icon convention.

## Components

### Header (platform-wide)
Fixed, 60 px, full width, ground with a line hairline below. Left: the sunburst mark (a 5 px disc plus 16 alternating rays, 26 px box, 1.4 px round-capped strokes) in gold, then the wordmark with "LIVE" in coral-ink. Right: text links at 15 px with underline on hover, the Regions disclosure as an outline button with an inline SVG chevron, and "Get updates" as a solid button. On the black ground (`.on-dark`, landing-only) it turns night with on-dark text, the mark turns sun, "LIVE" turns coral, and buttons invert; colour changes ease over 0.3 s.

### Buttons (platform-wide)
- **Shape:** square (0 px), 1 px ink border, minimum height 40 px, padding 8 by 14 px, 15 px text, 8 px gap to an inline SVG icon.
- **Outline:** paper fill, ink text. **Solid:** ink fill, paper text. A larger call to action runs at 16 px with 11 by 18 px padding and may wrap.
- **Hover:** outline fills with ink and its text turns paper; no motion.
- **Focus:** 2 px coral-ink outline, 3 px offset.
- **Disabled:** 55% opacity, not-allowed cursor, no hover change.
- **On dark:** outline goes transparent with on-dark text and border; solid becomes an on-dark fill with night text.

### Region picker (platform-wide)
A paper panel with a 1 px ink border (420 px wide, or full width less 32 px). A label-weight header row with a count on the right, then rows on a 14 px swatch, name, action grid with line hairlines between them. The live row has a 7% coral tint, a solid coral swatch, a bold name and a coral-ink "Open atlas" with an arrow; in-preparation rows use a dashed coral-ink swatch, requestable rows a plain ink-2 outline, and their actions sit in ink-2. Hover deepens the tint to 12% coral. A 13 px ink-2 note closes the panel. It drops from the header as a disclosure and sits inline in the regions band.

### Footer (platform-wide)
Black (night) band, 48 px padding plus the bottom safe area, wrapping columns with 24 by 48 px gaps, 14 px mint text, paper headings at 600 and paper underlined links. The full logo raster leads at 282 px wide with descriptive alt text. Image credits sit in a collapsed `<details>` at 11 px in credit.

### Feature list
An ordered list ruled with an ink line on top and line hairlines between items. Each row is a 56 by 40 px SVG pictogram (ink 1.2 px strokes, slate-2 fills, one coral mark), a 20 px title over a 15 px ink-2 description, and a 14 px 600 coral-ink text link underlined on hover.

### Evidence matrix (landing-only as drawn; the pattern carries)
A fixed-layout table whose cells mix slate into paper in proportion to the count (`--v`), with mono counts; strong cells switch to paper text. Missing evidence is a hatched cell (paper and hatch stripes at 45 degrees) labelled "gap" in coral-ink. Headers are 11 px mono in ink-2. Region toggles above it are outline/solid buttons with `aria-pressed`.

### World pixel map (landing-only)
A square-pixel world on a canvas with SVG overlays: countries step through wash, mint, slate-2 and slate by works; California is a coral fill breathing to 1.2x scale over 2.8 s; Norway is a 1.1 px coral-ink dashed outline. A mono legend below shows the four-step ramp.

### Scroll story (landing-only)
One sticky full-viewport stage (canvas plus DOM captions) over a 31.5-unit scroll, each unit about 95% of a viewport height. The timeline table `TU` in `landing_story.js` is the one place to tune dwell; motion uses cubic ease-out and ease-in-out. Captions fade in and out by beat; headings are on-dark and paragraphs mint while the ground is black, ink and ink-2 after the burst. The first viewport is a composed picnic image that fades in over 0.45 s and hands over to the canvas on the first scroll. A mint scroll cue (a 1 px line pulsing over 1.6 s) and a "Skip to the evidence map" link sit at the bottom corners. Under reduced motion the stage is replaced by a column of full-height stills, one per beat, each with its caption, and all animation and transition stop.

## Do's and Don'ts

### Do:
- **Do** use the `--pv-*` tokens for every colour in CSS; canvas code mirrors them as constants.
- **Do** use coral-ink for any coral text, arrow or focus ring on a light ground.
- **Do** give every interactive element the 2 px coral-ink focus ring with a 3 px offset.
- **Do** set headlines at weight 400 with -0.03em tracking and balanced wrapping.
- **Do** keep corners square and separate surfaces with 1 px ink or line rules.
- **Do** draw icons as inline SVG using `currentColor` or the token fills.
- **Do** label illustrative data as illustrative, in an 11 px mono source line under it.
- **Do** keep story text out of image boxes by measuring caption boxes, and test it.

### Don't:
- **Don't** put an eyebrow or kicker label above a heading.
- **Don't** use Martian Mono for headings, buttons or navigation.
- **Don't** set mint text on a light ground.
- **Don't** colour more than one thing coral in a data graphic.
- **Don't** round corners or add shadows on the light ground.
- **Don't** use gradient text or hard offset shadows.
- **Don't** load fonts or scripts from external CDNs; fonts are self-hosted.
