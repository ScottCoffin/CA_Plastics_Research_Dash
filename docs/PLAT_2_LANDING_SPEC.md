# PLAT-2 build spec: the Plastiverse Live global landing page

Status: design approved by the owner on 2026-11-17 ("love the concept, finalize it").
Decision: `ADR-PLAT2-SPECTRAL-STORY-2026-11-17` in `.agent/DECISIONS.md`.
Direction contract: `.impeccable/surfaces/framework-src-index-md.md`.

This document is for the agent that builds the page. The approved prototype is the visual source
of truth; this spec says what to keep exactly, what to change for production, and how to verify.

## 0. Read this first

| What | Where |
|---|---|
| Approved prototype (open it, scroll it) | `.impeccable/sketches/spectral_story.html` |
| Prototype sources and rebuild commands | `.impeccable/sketches/src/README.md` |
| Engine to port | `.impeccable/sketches/src/story_engine7.js` (timeline `TU`, all beats) |
| Page markup, copy and CSS to port | `.impeccable/sketches/src/story_template.html` (after `patch_beats5.py`) |
| Picnic images and prompts | `.impeccable/sketches/scene/{blanket,picnic_items}.png` (+ `.json` sidecars), web copies in `scene/web/` |
| Paper first pages and licence evidence | `.impeccable/sketches/papers/web/*.jpg`, `.impeccable/sketches/papers/credits.json` |
| Logo and its generation prompt | `src/Plastiverse Live_ From Pollution to Progress.png`, `src/plastiverse_logo_gen_prompt.md` |
| Platform plan (routes, regions) | `docs/PLATFORM_ARCHITECTURE.md` |
| Story concept (cite, do not copy figures) | Hartmann, Mennekes & Wagner (2026), doi:10.1021/acs.est.6c01796 |

To preview the prototype, serve it over HTTP. The canvas reads image pixels, so `file://` fails:
`cd .impeccable/sketches && py -3.14 -m http.server 8765 --bind 127.0.0.1`, then open
http://127.0.0.1:8765/spectral_story.html.

## 1. Scope and task split

| Task | What | Depends on |
|---|---|---|
| PLAT-1 | Move California to `/california` (clean break) so the root is free | none |
| PLAT-2a | Global data: Natural Earth world and California rasters, global country counts | none |
| **PLAT-2** | **This page** at `plastiverse.live/` (`framework/src/index.md`) | PLAT-1, PLAT-2a |
| PLAT-2b | Live global evidence-map counts (30 OpenAlex count queries a day) | owner signs off the cell definitions (H30) |
| PLAT-2c | `/ambassadors` placeholder page for the "become a local ambassador" button | none (copy in section 4.9) |
| VD-SM | Carry the Spectral Match tokens, logo and header into the California pages | PLAT-1, PLAT-2 |

Non-goals for PLAT-2: Norway data, the region abstraction (PLAT-3), and a real global
co-authorship network. The network beat stays illustrative; the owner removed its source label on 2026-11-17 (PLAT2-NETWORK).

## 2. Brand and tokens

All colours become Framework tokens in `framework/src/design/tokens.css`. No hex literals go in
component CSS: `scripts/check_design_tokens.py` caps them at 0.

The palette comes from the logo.

| Token (proposed) | Value | Role |
|---|---|---|
| `--pv-ground` | #F6F8F9 | Light page ground (after the bulb's light burst) |
| `--pv-night` | #000000 | Story ground before the burst; footer |
| `--pv-ink` | #17263D | Text (logo midnight navy) |
| `--pv-ink-2` | #4D5D73 | Secondary text on light |
| `--pv-line` | #C4D0D6 | Hairlines, grid |
| `--pv-mint` | #C5EADF | Secondary text on dark; light data step |
| `--pv-slate` | #436487 | Data marks on light (chart dots, network, map top step) |
| `--pv-slate-2` | #86A9BF | Middle data step |
| `--pv-wash` | #E9F1EF | Lowest data step |
| `--pv-coral` | #FA6B68 | Brand accent: "LIVE", California, live markers, dark-ground accents |
| `--pv-coral-ink` | #D9443F | Coral for text, arrows and focus rings on the light ground (contrast) |
| `--pv-sun` | #FFF49A | Bulb before the burst; mark on dark |
| `--pv-gold` | #E2B714 | Bulb after the burst; mark on light |
| `--pv-cream` | #FFF8DF | Reserve (logo highlight) |

Contrast rules:
- On light grounds, coral appears only as fills and large text. Text, arrows and focus rings use `--pv-coral-ink`.
- Mint is for the dark ground only.
- Verify every pair with axe. The target is 0 violations.

Fonts:
- Schibsted Grotesk (400, 500, 600, 700) for text.
- Martian Mono (400; width 87.5) for data labels and source lines only.
- Self-host latin woff2 subsets in `site/assets/fonts/` with their OFL licence texts, declared like Archivo in `framework/observablehq.config.js`.
- No Google Fonts link (no external CDNs, C5/S3.7). The prototype's Google Fonts link must not ship.

Logo:
- **Header:** a small gold sunburst mark (the logo's central node: a disc plus 16 alternating rays) and the wordmark "PLASTIVERSE LIVE". The wordmark is uppercase Schibsted Grotesk 700 with 0.09em tracking; "LIVE" is coral-ink on light and coral on dark. The SVG is in the prototype header.
- **Footer:** black, with the full logo raster (`logo_564.png` at 282 px wide, or a webp of it) and descriptive alt text.
- **Favicon:** derive it from the sunburst mark.
- **Variants:** for a new logo variant, use `src/plastiverse_logo_gen_prompt.md`, never an ad hoc prompt.

Craft floor (Impeccable): no eyebrow above headings; mono only for data and source lines; no gradient text; no hard offset shadows.

## 3. Page structure

1. **Header**, fixed and 60 px tall:
   - Brand on the left; on the right: "Evidence map" (`#evidence`), a "Regions" disclosure (picker), "Methods", "About", and a solid "Get updates" button.
   - It turns black with light text (`.on-dark`) while the story ground is dark, and switches back when the light burst passes 80%.
   - At 430 px or less, hide "Get updates" (it is in the footer). At 860 px or less, hide the text links but keep "Regions".
2. **Story**: one section with a sticky full-viewport stage (canvas plus DOM captions) and a total scroll length of 3080vh (31.5 scroll units). Details in section 4.
3. **Live evidence map**, `#evidence`:
   - Heading "The live evidence map." and the lede.
   - Worldwide / California / Norway toggles.
   - A topic-by-matrix table whose cells shade by count; gap cells are hatched.
   - Until PLAT-2b ships, the counts are labelled illustrative.
4. **Regions**, `#regions`:
   - "From global to local: open a regional atlas."
   - A world pixel map (countries shaded by works, California in breathing coral, Norway dashed).
   - The region picker: California live, opening `/california/`; Norway in preparation.
5. **What a regional atlas does**: the seven features, with links to the California pages.
6. **Footer**, black: the logo, "Get updates" (weekly email soon, RSS, ntfy), "Plastiverse Live, created by Scott Coffin. Not a State product.", "Story framing after Hartmann, Mennekes & Wagner (2026).", and a collapsed `<details>` "Image credits" (11 px) listing the paper first pages.

## 4. The story

Positions are in scroll units, where one unit is about 95% of a viewport height (story height = 31.5 × 95vh + 100vh).
`TU` in `story_engine7.js` is the authority; this table restates it. A caption fades in or out over 0.25 units.
Text never overlaps an image (section 4.10).

| # | Units | Visual | Text (exact copy) |
|---|---|---|---|
| 0 | load | Black stage. The picnic (section 4.1) fades in item by item: blanket first (450 ms), then each item (260 ms each, all within about 1.3 s). Then the scroll cue appears. | none |
| 1 | 0.25–1.45 | The picnic moves down and stays nearly full screen below the title | `h1` "Plastic is everywhere…" (in 0.45, out 1.45) |
| 2 | 1.3–3.0 | Each item pops up and shatters (section 4.2); the blanket tears last | none |
| 3 | 2.95–3.7 | All fragments and particles swirl into one mixed cloud on the right | none |
| 4 | 4.0–5.4 | Cloud drifts | `h2` "Microplastics were first described in the ocean more than 50 years ago." plus source line "Carpenter et al. (1972), "Polystyrene spherules in coastal waters," Science 178:749. doi:10.1126/science.178.4062.749" |
| 5 | 5.4–7.3 | 15 real CC BY paper first pages drop in one by one (5.6–6.4), fanned, over the cloud; out 7.0–7.3 | `h2` (same place and size as #4) "Now picture every particle as a published study. Thousands more arrive every year." |
| 6 | 7.3–10.5 | Mandala (section 4.3) with fine radial links (8.3–10.5) and a dust halo | `h2` "Connected, studies become knowledge." (8.5); bottom-left, later (9.2) "Grouped by what they study and linked by who did the work, scattered results start to form a picture." |
| 7 | 10.5–13.2 | Particles fill a light bulb in their own colours (10.5–11.2); glow 12.1–12.6 turns them butter yellow; radial light burst 12.6–13.2 turns the page light and the particles gold | `h2` "Put to work, knowledge becomes understanding." (11.6–12.9) |
| 8 | 13.4–17.0 | Particles stream out of the bulb by rank and build the unit chart left to right (one dot = 150 works) | none |
| 9 | 17.4–20.65 | Axis and decade labels, then three arrow annotations one at a time (17.85–18.75) | Source line, mono, one line at full width under the axis (17.45): "Plastics-pollution research works per year, worldwide. OpenAlex, query plastic-v3.1, fetched <date>. One dot = <unit> works." Then middle-left over the empty early years (19.2): `h2` "Plastic pollution research is expanding at an unprecedented pace." with one line "The world needs innovative tools to turn data into knowledge and solutions to effectively react to this global crisis." |
| 10 | 20.7–23.45 | Dots re-sort into the evidence grid (rows: occurrence, effects, methods, fate and transport, solutions; columns: ocean, freshwater, soil, air, food and biota, people) | `h2` "See where the evidence is, worldwide, and where it is missing." (21.8); then (22.3) "A live evidence map sorts every study by what it examines and where." |
| 11 | 23.5–26.25 | Collaboration network: 7 communities on damped springs; every 2.3 s one community is plucked and wobbles back | `h2` "See who works with whom, and forge new connections." (24.6); then (25.1) "Collaboration networks show the research communities and the people who bridge them." (source line removed by the owner 2026-11-17) |
| 12 | 26.25–28.55 | Dots settle into the world pixel map; country shading underneath | `h2` "The problem is global." (27.3); then (27.75) "Plastics research now comes from almost every country." plus a source line (real counts: "Works by country, OpenAlex, <date>." Until then: "Illustrative shading until the global country counts are built.") |
| 13 | 28.55–end | Zoom to California at local scale (coral and slate cells) | `h2` "Local knowledge and connections matter." (29.6); `p` (30.0) "Regional atlases zoom in on the people, monitoring, funding and policy of one place. Powered by local researchers and community leaders."; button (30.35) "Join the movement, and become a local ambassador →" to `/ambassadors`; then (30.7) "California is live; Norway is next." |

### 4.1 The picnic (beat 0)

- **Images:** the blanket photo (`scene/blanket.png`) with its black backdrop keyed to transparent (alpha = clamp((luminance − 14) / 26)), plus 21 item cut-outs from `scene/picnic_items.png` (alpha components above 110 at a 4 px grid).
- **Layout:** `LAYOUT` in the engine places each cut-out on the blanket. Each row is sheet centre → blanket position, rotation, scale; plates come before the sandwiches that sit on them.
- **Shadows:** items cast soft shadows.
- **Sizing:** the picnic fills the viewport below the 60 px header, minus margins. With the title it sits just below the title's text box.
- **Composition:** compose the picnic offline (section 6). The first paint is a static composed picnic image, which is the LCP element. The canvas takes over once it is ready.

### 4.2 Shattering (beat 2)

Each item, in a random order, takes 0.4 units to pop. While it pops it:
- grows by 30%;
- lifts 7% of the viewport height;
- turns;
- lengthens and softens its shadow.

At the top of the pop it breaks:
- **Hairline cracks:** it splits into Voronoi shards cut from its own pixels (6–18 per item, by area), which separate by 3% for 0.06 units.
- **Fly-out:** the shards fly outward along their centre directions for 0.45 units, spinning (±1.6 rad), with shadows.
- **Crumble:** each shard crumbles (0.35 units, staggered per shard) into a spray of small fragments in its own colours (3,800 decorative crumbs in total) and into the data particles.

The blanket starts at 2.5: it tears into 26 patches that drift slightly and fray into red and white fibres. The crumbs fade as the cloud forms, and the data particles stay.

Crack edges must be clean: cut shard masks at 2 px or finer, never on the 4 px sampling grid.

### 4.3 Knowledge mandala (beat 6)

- **Rings:** concentric rings with even spacing, starting at s0 × 0.75.
- **Colour order:** pieces are sorted by hue, then lightness, into clean wedges around the circle, so the colours stay grouped.
- **Pieces:** every piece points radially and fibres are drawn straight. Size runs from 1.25× at the centre to 0.85× at the edge.
- **Links:** faint radial links (48 wedges, consecutive by radius).
- **Dust:** a halo of 3,000 tiny dots outside the disc, twinkling gently.
- **Look:** modelled on Mandy Barker's SOUP works; never reproduce her photographs.

### 4.4 Bulb and burst (beat 7)

- **Bulb:** a glass outline (the three paths in `#bulbsrc`) filled by a hex grid of particles, assigned by mandala angle so the colour wedges carry into the bulb. The outline and filament are drawn faintly, then in yellow once it turns on.
- **Colour sequence:** particles keep their own colours until the glow, turn butter yellow (`--pv-sun`) during the glow, then gold (`--pv-gold`) after the burst.
- **Burst:** a light disc grows from the bulb centre to cover the viewport, with 40 rays and a warm ring. The stage background switches to the light ground only after the disc covers it.

### 4.5 Chart (beats 8–9)

- **Data:** `site/data/global/trend_global.json` (`by_year`, `query_version`, `fetched_at`); years 1970 to the current year. The unit is a round number of works per dot giving about 900 dots: currently 150.
- **Dots:** columns of three dots per year. Dots leave the bulb in rank order (stagger 1.4 units).
- **Space for the text and labels:** on desktop, column heights are capped so no dot enters the headline box, and the chart reserves headroom above the tallest column for the 2026 label.
- **Annotations:** wrapped labels (head 600, title 400, 13 px; at most 250 px wide) placed clear of dots and the headline. Each has a coral-ink elbow arrow (quadratic curve with an arrowhead) and no vertical rules.
  - **Carpenter et al. 1972**, "Polystyrene spherules in coastal waters": right of the 1972 column, near the base.
  - **Thompson et al. 2004**, "Lost at sea: where is all the plastic?": left of the 2004 column, above the base.
  - **Hartmann et al. 2026**, "Lost in a sea of information: the microplastics publication deluge", plus mono "2026 to date: <n> works": directly left of the 2026 column top.
- **Phones:** the headline and lede go below the chart instead of middle-left.

### 4.6 Evidence grid (beat 10)

- **Layout:** the grid sits to the right of the caption column. Row labels are on the left; column labels are above, abbreviated on phones (occur., fresh, biota, fate).
- **Cell counts:** illustrative until PLAT-2b. The grid footnote says "worldwide; illustrative cell counts until the live counts are built".

### 4.7 Network (beat 11)

- **Data:** illustrative, so keep the source line.
- **Highlight:** community 2 is coral.
- **Motion:** each node follows its target on a damped spring (k 0.05, damping 0.88), with a ±2.5 px idle wobble and the periodic pluck.
- **Reduced motion:** no springs and no plucks.

### 4.8 World map and California (beats 12–13)

- **World map:** an Equal Earth pixel raster of Natural Earth admin-0, with antimeridian unwrapping and a sphere clip. Country shading uses `global_counts.json` (PLAT-2a) in four steps (wash, mint, slate-2, slate); California is coral.
- **California raster:** at local scale, from the California outline.

### 4.9 Ambassador placeholder (PLAT-2c)

The `/ambassadors` page holds one paragraph:

"Plastiverse Live grows region by region with local researchers and community leaders who guide what
we collect and check it. Ambassador onboarding opens soon. To get involved now, email
theplastiverse@gmail.com."

Show the address as text, with a mailto link beside it.

### 4.10 Text never overlaps images (owner rule)

Layout measures the caption text boxes (DOM ranges) and places every visual in a safe zone:
- **Desktop:** visuals sit right of the widest side caption plus 40 px, or right of 40% of the width, whichever is greater.
- **Phones (≤ 860 px):** visuals sit between the bottom of the top caption and the top of the bottom caption.
- **Chart:** the top caption sits over the empty early years, and the dots are capped to stay below it.
- **World map:** it sits below its caption.

Keep this rule in production and test it (section 9).

## 5. Engine architecture (production)

- **Files:** port the prototype engine to `framework/src/components/landing_story.js` and `landing_story.css`, and load them from `framework/src/index.md`. Use no animation library (in line with ADR-VD30) and only plain canvas 2D.
- **Modules:**
  - `timeline` (TU in units, divided by TOT);
  - `layout` (safe zones, recomputed on resize);
  - `picnic` (offline assets, runtime transforms);
  - `particles` (about 900 data particles plus decorative crumbs and dust);
  - `beats` (chart, grid, network, map, zoom);
  - `captions` (fade windows from `data-a`/`data-b` in units).
- **Render loop:**
  - Run `requestAnimationFrame` only while the story is on screen (IntersectionObserver), and pause on `visibilitychange`.
  - Cap the device pixel ratio at 2.
  - Skip crumbs outside their window.
- **Captions:** real DOM text in the stage, never drawn on the canvas.
  - The canvas is `aria-hidden`.
  - The picnic has a visually hidden description.
  - Chart annotations are canvas text, so duplicate them in a visually hidden list.
- **Reduced motion** (`prefers-reduced-motion: reduce`): no sticky scroll. Render the story as a vertical sequence of static figures, one per beat, each with its caption beside or below it:
  - the picnic;
  - the cloud;
  - the papers;
  - the mandala;
  - the lit bulb;
  - the annotated chart;
  - the grid;
  - the network;
  - the map;
  - California.

  Use the same safe-zone rule. These can be generated offline as stills (section 6) or drawn once on small canvases.
- **Skip link:** "Skip to the evidence map" stays visible in the stage, bottom right. It uses mint on dark and `--pv-ink-2` once the stage is light.

## 6. Asset pipeline

Write `scripts/build_landing_assets.py`. It is deterministic, with fixed seeds, and writes to `site/assets/landing/`:

1. **Picnic:**
   - Key the blanket's backdrop, cut the items, and apply `LAYOUT`.
   - Write `picnic_first_paint.webp`: the composed picnic, about 1600 px wide, as the LCP image.
   - Write `picnic_items.webp`: an item atlas with alpha.
   - Write `picnic.json`: item transforms, Voronoi seeds per item and per blanket, and particle samples (positions and colours).
   - The browser builds shard masks from the seeds at 2 px. If profiling shows more than 50 ms of main-thread work, precompute the shard atlas too.
2. **Paper pages:** `papers/p*.webp`, about 560 px tall, from `.impeccable/sketches/papers/web/`, plus `papers.json` built from `credits.json` (title, DOI, licence sentence). Only CC BY pages; CC BY-NC is excluded. Download stamps are already redacted; keep the redaction evidence.
3. **Logo:** `logo_282.webp` and `logo_564.webp`.
4. **Provenance:** every shipping raster carries its provenance, and the sidecars travel with it.
   - Generated images list the model, the prompt and the date.
   - Paper pages list the DOI and the licence sentence.
   - The logo points to `src/plastiverse_logo_gen_prompt.md`.

Budgets:
- The first paint image is at most 250 KB.
- All landing images total at most 2.5 MB.
- `landing_story.js` is at most 60 KB minified.

## 7. Data

| Need | Source | Status |
|---|---|---|
| Works per year (chart) | `site/data/global/trend_global.json` | exists (daily) |
| Country counts (map shading) | `site/data/global/global_counts.json` (OpenAlex `group_by=authorships.countries`; total, by year, new this week) | PLAT-2a |
| World and California rasters | `scripts/build_world_map.py` from Natural Earth 110m admin-0 (public domain) to `site/assets/world/` | PLAT-2a; method as in `.impeccable/sketches/src/build_geo.py` and `story.py` |
| Evidence grid counts | 30 OpenAlex count queries a day (5 × 6 cells), about USD 0.03 a day, never paid filters | PLAT-2b, gated on owner cell definitions |
| Network | illustrative | labelled |
| Paper first pages | Zotero PDFs, CC BY only | done (`credits.json`) |

## 8. Responsive behaviour

The design was checked at 1440 × 900 and 390 × 844. Rules on screens 860 px wide or less:
- Captions use the full width.
- Visuals sit between the captions.
- The picnic box is 1.5× the viewport width, centred and cropped at the sides.
- The chart headline sits below the chart.
- Grid labels are abbreviated.
- The ambassador button wraps.

## 9. Verification (acceptance)

Write `scripts/check_plat2.py`. It is offline (Playwright against the built site) and checks:

1. **Copy:** every caption string in section 4 is present verbatim in the DOM.
2. **No overlap:**
   - Scroll to the middle of each beat and to its end, at 1440 × 900 and 390 × 844.
   - Read each visible caption's text-range boxes, and the visual's bounding box from a test hook (`window.__landingDebug.visualRect()`).
   - Assert no intersection. Paper pages count as visuals during beat 5.
3. **Accessibility:** axe reports 0 violations on the landing page. Headings run h1 to h2 in order, and the skip link works.
4. **Reduced motion:** with `reducedMotion: "reduce"`, there is no sticky stage, all ten stills are present and every caption is visible.
5. **Performance:**
   - Lighthouse (mobile) on the landing: performance ≥ 90, accessibility 100, CLS ≤ 0.05, LCP ≤ 2.5 s.
   - Same-machine A/B when judging regressions (MEMORY).
6. **External requests:** no network requests to any host except the site's own (no fonts CDN).
7. **Contact sheet:** write it to `scratch/`, like `.impeccable/sketches/src/snap3.py`, and look at it before the finish review.

Then run the full gate from CLAUDE.md and the UX audit (`~/tools/ux-audit/ux_audit.py <base> / --lighthouse`).

## 10. Finish (Impeccable)

Run the `impeccable-finish-reviewer` against the direction contract and this prototype. Fix what it orders, then run the `impeccable-documenter` to write `DESIGN.md` from the shipped page. Only then is PLAT-2 done.

## 11. Known prototype shortcuts to replace

- Google Fonts link: self-host instead.
- Runtime fracture work: move it to the offline pipeline (section 6).
- Illustrative evidence counts and map shading: replace with real data or keep the labels. The network beat carries no label (owner, 2026-11-17).
- "prototype" badge: remove.
- Header links that point to `#`: Methods and About go to the California pages until global versions exist.
- Missing favicon (404): add one.
- Picker and feature links: point them at `/california/...` after PLAT-1.
- Engine code: a single prototype file of minified-style code. Write readable modules with comments where the intent is not obvious. Keep the timeline table as the one place to tune dwell.
