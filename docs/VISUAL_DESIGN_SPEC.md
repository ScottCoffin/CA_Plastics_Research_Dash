# Visual design spec: Pacific Contour (VD)

Status: proposed 2026-11-14 at the owner's request ("the Observable Framework version of the site
lacks any meaningful design elements. It should have colour and other components that make it
look modern and comfortable."). Integrated as `.agent/TODO.md` section VD: VD-0 (this assessment
and spec) is done; VD-1 to VD-13 are open. Owner decisions VD-D1 to VD-D8 are in
`.agent/QUESTIONS.md` with the defaults in use; owner task H24 asks for a review of the style tile.

Reference files:
- [design/style_tile.html](design/style_tile.html): the visual reference. Open it in a browser.
  Its token names and class names are part of this contract. It loads Barlow Semi Condensed
  from Google Fonts only as a preview convenience; the site self-hosts the font (VD-2).
- [design/baseline_2026-11-14.json](design/baseline_2026-11-14.json): per-route measurements
  taken before any VD change.
- [../scripts/build_design_motif.py](../scripts/build_design_motif.py): builds the coastline
  motif and the logo mark from the committed California land polygon.

Readers: the implementing session (lead plus workers) and the owner.

## 0. Operating rules

1. One VD task per checkpoint, sealed as in `CLAUDE.md` and committed as `VD-<n>: <summary>`.
2. Presentation only. A VD task never changes data, schemas or the pipeline. If a change needs
   data, stop, write a HANDOFF note and leave it to a separate task (VD-13 is the known case).
3. Precedence: this spec, then the style tile, then [EM_spec.md](EM_spec.md) Section 2 (the
   do-not-regress list, repeated in Section 8 here).
4. Light theme only (owner decision 2026-11-12, UX-26). Do not add dark tokens.
5. No runtime requests to other hosts: no Google Fonts and no CDN. Font and SVG files are vendored
   assets; record each licence in `docs/REUSE.md` before committing the file. No new npm or
   Python dependencies.
6. Observable Framework stays at 1.13.4. Fix template limits through `observablehq.config.js` or
   `framework/scripts/postbuild.mjs`, never by editing `node_modules`.
7. Known Framework pitfalls still apply: pages stay at the top level of `framework/src/` (data
   paths resolve through `siteRoot()` in `components/atlas.js`), and no top-level JavaScript
   variable may be named `view`.
8. Delegation: VD-1 to VD-4 touch shared files, so run them one at a time. After VD-4, the page
   tasks (VD-5 to VD-8) own disjoint files and can go to up to three workers in parallel.
9. Every task ends with the verification in Section 9. "Looks right" is not acceptance.

## 1. Assessment, 2026-11-14

Method. Tools, all local:
- `~/tools/ux-audit/ux_audit.py` (Playwright, axe-core 4.10.3, Lighthouse 12.8.2 mobile preset in
  Edge) on the 12 app routes of https://plastiverse.live/.
- A design probe (Playwright Chromium at 1440 x 900 and 390 x 844). It recorded computed styles,
  the fonts actually rendered (DevTools `CSS.getPlatformFontsForNode`) and first-screen
  colourfulness (Hasler and Süsstrunk M: below 15 reads as not colourful, 15 to 33 as slightly
  colourful).
- A source inventory of `framework/src`, the dataviz skill's palette validator on every
  categorical colour set, and WCAG contrast computed for every proposed colour pair.

Screenshots are in `scratch/design_audit_2026-11-14/` (gitignored); the numbers are in the
baseline JSON.

### Findings

| ID | Finding | Evidence and cause |
|---|---|---|
| F1 | Dated, mixed typography | On Windows, headings, body text and buttons render in Palatino Linotype; the sidebar and header render in Arial. `globalStylesheets: []` removes Framework's Source Serif 4 link (correctly, since there are no CDNs), so `--serif` falls back down its stack. Framework's `--sans-serif` lists `helvetica` before `segoe ui`, and Windows substitutes Arial for Helvetica. Body text is 17 px serif. |
| F2 | Almost no colour | First-screen colourfulness M is 14 to 23, with 2 to 5% saturated pixels, on all 12 routes. On most first screens the only colour is one green button or blue links. The classic `expert.html` profile scores 37 (35% saturated): its deep-teal header band is the direction this spec extends. |
| F3 | Two visual languages | Ported pages (Experts, Institutions, Monitoring, Funding, Institution) sit inside a bordered panel, define their own green, navy and orange palette, and use 44 px serif fields. Native pages use Framework's `air` defaults: blue links (`#3b5fc0`) and grey cards. The CSS has 78 distinct hard-coded hex colours (293 uses) in 15 stylesheets, plus 53 in component JavaScript, 27 distinct font sizes and 17 border radii. The seven-colour palette is redefined in 10 files (5 Framework stylesheets and 5 classic pages). |
| F4 | Plain shell | The header shows "California research atlas" in Arial, a second name for the product, with no mark. The sidebar is a flat list of 10 links with no groups or icons; the active item is blue text. On phones the sidebar toggle floats half-way down the left edge. |
| F5 | Three control styles | Large serif fields on ported pages, compact fields on the Evidence map, and browser-default controls on the network page, with labels touching their inputs. The Experts "Career stage" checkbox wraps into three columns. Funding stacks its two buttons in one grid cell. |
| F6 | Data starts below the fold | At 1440 x 900 the Experts first screen holds only its 11 filters. The Evidence map opens with three paragraphs and a notice. The network page shows two paragraphs, nine controls and another paragraph before the graph. Funding puts the heading "Awards" directly under "Funding", then two caveat paragraphs. On phones each of these first screens is prose or filters only. |
| F7 | Callouts without meaning | Four unrelated box styles: a blue box with a dark bar (Evidence "New"), mint with a green bar (Monitoring caveat), grey with a blue bar (Policy caveat, Overview refresh) and a light-blue box. |
| F8 | Weak Overview | Section cards are grey, with 15 px normal-weight titles and no icons. The "Start here" links are underlined serif text in outlined boxes that wrap to two rows. On phones the four stat tiles stack one per row and fill the first screen. Lighthouse CLS is 0.17: the tiles render late and push "Start here" down. |
| F9 | Chart colour sets disagree | Topic colours (`site/assets/topics.js`) pass the validator. The network community set (Okabe-Ito order) passes with a colour-blind warning. The monitoring matrix map set fails (CVD ΔE 1.6 between stormwater and surface water; normal-vision ΔE 7.6; two low-chroma slots), and so does the funding agency set (CVD ΔE 1.1 between CA Ocean Protection Council and EPA). Heatmaps are teal on the Evidence map and blue on Funding. |
| F10 | Raw vocabulary on screen | Institution types, sectors and work types show as slugs: `community-college`, `intergovernmental-organization`, `local-agency`, `nonprofit/NGO`, `book-chapter`, `conference-abstract`. |
| F11 | No icons | Zero icons on every route. |
| F12 | Strengths to keep | Lighthouse accessibility is 100 on 11 routes and 96 on the Evidence map; SEO is 100; there are no console errors. axe flags only the known Framework sidebar `list` and `region` rules (UX-32). Lower Lighthouse performance on Experts, Institutions, Evidence and Network (75 to 80) comes from main-thread JavaScript (total blocking time 0.8 to 1.4 s), not from styling: CSS is 6 to 12 KB per page and no fonts load. The refresh must therefore stay CSS-first and add nothing to the JavaScript critical path. |

### Baseline per route

Lighthouse mobile preset; colourfulness at 1440 x 900.

| Route | Perf | A11y | LCP s | TBT ms | CLS | Colourfulness M | Saturated % | Targets < 24 px |
|---|---|---|---|---|---|---|---|---|
| `/` | 93 | 100 | 1.01 | 21 | 0.170 | 18.0 | 2.9 | n/a |
| `/experts` | 77 | 100 | 2.37 | 944 | 0 | 15.9 | 3.0 | 23 |
| `/network` | 80 | 100 | 1.93 | 824 | 0 | 19.2 | 3.2 | 413 |
| `/institutions` | 75 | 100 | 1.17 | 1362 | 0 | 18.4 | 4.1 | 29 |
| `/institution` | 98 | 100 | 2.22 | 69 | 0 | 14.9 | 2.3 | 3 |
| `/monitoring` | 100 | 100 | 1.13 | 81 | 0 | 15.2 | 2.1 | 2 |
| `/funding` | 91 | 100 | 1.18 | 366 | 0 | 16.1 | 2.7 | 8 |
| `/evidence` | 77 | 96 | 1.20 | 1055 | 0.037 | 21.0 | 3.7 | 33 |
| `/policy` | 100 | 100 | 0.99 | 0 | 0.031 | 19.8 | 3.4 | 8 |
| `/resources` | 100 | 100 | 0.98 | 33 | 0 | 17.3 | 2.7 | 2 |
| `/about` | 98 | 100 | 1.34 | 162 | 0 | 23.2 | 4.7 | 18 |
| `/glossary` | 100 | 100 | 1.00 | 32 | 0 | 21.2 | 3.9 | 3 |
| `expert.html` (classic) | | | | | | 36.9 | 34.7 | |

## 2. Direction: Pacific Contour

The Atlas already has one page in the target language: the classic `expert.html` profile, with
its deep-teal band, white title, uppercase eyebrow and metric tiles on a mint page. Pacific
Contour carries that language to every page and grounds it in California:

- **Colour.** Pacific teal (`#075a46`, already the favicon and the ported pages' brand colour)
  and navy ink on a sea-mist page. A sunset orange is kept for focus rings and "new" marks.
  Interface colour comes from one teal family; data colour keeps its own validated sets, so a hue
  on a chart always means data.
- **Type.** Barlow Semi Condensed for headings, eyebrows and navigation. It is a grotesk drawn
  from the lettering of California's licence plates, highway signs, buses and trains. Body
  text, figures and controls use the system interface face. No serif.
- **Ornament.** The state's own coastline with seaward offset lines, generated from the
  committed Natural Earth land polygon (public domain). It is the only decorative element: bold
  in the Overview hero, faint in page headers. The offsets are real kilometres but decorative;
  never call them depth.
- **Composition.** Summary before detail: a short page header, the key filters in one row, then
  results or a chart on the first screen. Explanations move into callouts beside the numbers
  they qualify, or into a disclosure.
- **One bold place.** Only the Overview hero uses the deep band. Other pages use a light
  page-header band, white cards on the mist page and colour where it carries meaning.

## 3. Tokens

Tokens live in a new `framework/src/design/tokens.css`, imported by `framework/src/style.css`
after `observablehq:theme-air.css`. Values are exact; contrast is the WCAG ratio, computed.

### 3.1 Colour

| Token | Value | Role | Contrast |
|---|---|---|---|
| `--atlas-ink` | `#17324d` | Headings | 13.1 on white, 12.1 on page |
| `--atlas-text` | `#1d2a33` | Body text | 14.7 on white, 13.5 on page |
| `--atlas-muted` | `#4a5d6c` | Secondary text | 6.8 on white, 6.3 on page, 6.0 on sunken |
| `--atlas-faint` | `#5b6e7a` | Tertiary text and placeholders | 5.3 on white, 4.9 on page |
| `--atlas-boundary` | `#6f8590` | Field and control borders | 3.9 on white, 3.6 on page |
| `--atlas-line` | `#d5e0dd` | Hairlines and dividers (decorative) | n/a |
| `--atlas-page` | `#f3f6f5` | Page background (sea mist) | |
| `--atlas-surface` | `#ffffff` | Cards, panels, sidebar | |
| `--atlas-sunken` | `#eaf1ef` | Table heads, filter-panel heads | |
| `--atlas-brand` | `#075a46` | Links, icons, active navigation | 8.2 on white, 7.5 on page |
| `--atlas-brand-strong` | `#043e32` | Hero band, hover, text on tints | 12.1 on white, 9.9 on brand-tint |
| `--atlas-brand-action` | `#0e6e56` | Primary button fill | white text 6.2 |
| `--atlas-brand-tint` | `#d8eee7` | Selected and active fills | |
| `--atlas-brand-wash` | `#eef7f4` | Icon tiles, page-header band, info callout | brand-strong text 11.1 |
| `--atlas-on-brand` | `#ffffff` | Text on brand fills | 8.2 on brand, 12.1 on brand-strong |
| `--atlas-on-brand-muted` | `#b2ddd0` | Secondary text on the hero | 8.1 on brand-strong |
| `--atlas-accent` | `#c45100` | Focus ring, hero call to action, "new" marks | 4.6 on white, 4.3 on page; white text 4.6 |
| `--atlas-accent-strong` | `#a94400` | Accent hover | white text 6.0 |
| `--atlas-accent-wash` | `#fff1e6` | "New" callout and badge | `#6b2a00` text 9.7 |
| `--atlas-caution-wash` | `#fff6e0` | Caution callout | `#7a4f00` text 6.6 |
| `--atlas-caution-ink` | `#7a4f00` | Caution text | |
| `--atlas-caution-line` | `#e8c77a` | Caution border | |
| `--atlas-good-wash` / `--atlas-good-ink` | `#e7f6e7` / `#0b4f0b` | "Effective"-type status badge | 8.8 |

Data colours are not interface tokens (Section 7): topic slots stay in `site/assets/topics.js`;
the sequential ramp is `--seq-100` to `--seq-700` = `#e3f2ed #b9e0d3 #86c7b2 #4fa68c #23876d
#0e6e56 #043e32`.

### 3.2 Type

| Token | Value |
|---|---|
| `--atlas-font-display` | `"Barlow Semi Condensed", "Segoe UI Semibold", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` |
| `--atlas-font-body` | `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif` |
| `--atlas-font-mono` | `ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace` |

| Role | Face and weight | Size / line height | Notes |
|---|---|---|---|
| Hero title | display 700 | `clamp(2rem, 1.3rem + 2.2vw, 2.9rem)` / 1.02 | Overview only |
| Page title (h1) | display 700 | `clamp(1.8rem, 1.4rem + 1.4vw, 2.4rem)` / 1.05 | `text-wrap: balance` |
| Section (h2) | display 700 | 1.375rem / 1.2 | |
| Subsection (h3) | body 650 | 1.125rem / 1.3 | |
| Eyebrow, nav group label | display 600, caps, +0.1em | 0.75rem / 1.2 | |
| Body | body 400 | 1rem / 1.6 | running text at most 70ch |
| Small and caption | body 400 | 0.82 to 0.875rem / 1.45 | muted colour |
| Stat value | body 650, proportional figures | 2rem / 1.1 | |
| Table numbers | body, `tabular-nums` | 0.9rem | right-aligned |
| IDs, DOIs | mono | 0.82rem | |

### 3.3 Space, shape, depth, motion

- Space scale (4 px base): 4, 8, 12, 16, 20, 24, 32, 40, 56. Lay out siblings with `gap`.
- Radius by role: controls 8 px (`--atlas-radius-control`), cards and panels 12 px
  (`--atlas-radius-card`), chips and pills 999 px. No other radii.
- Shadow by role: `--atlas-shadow-raised` (`0 1px 2px rgba(16,42,36,.06), 0 1px 1px
  rgba(16,42,36,.04)`) on stat tiles; `--atlas-shadow-float` (`0 2px 6px rgba(16,42,36,.07),
  0 12px 28px rgba(16,42,36,.10)`) on hover lift, popovers and the hero search. Nothing else
  casts a shadow.
- Focus: a 3 px `--atlas-accent` ring (`box-shadow: 0 0 0 3px`) on every interactive element.
- Motion: 120 to 150 ms colour, shadow and 1 to 2 px lift transitions only. Under
  `prefers-reduced-motion: reduce`, every transition and animation is off.

### 3.4 Framework variables

Map Framework's variables onto the tokens so that native Framework markup (cards, links, notes,
the sidebar) follows them:

```css
:root {
  --serif: var(--atlas-font-body);          /* Framework body text uses --serif */
  --sans-serif: var(--atlas-font-body);     /* sidebar, header, cards, inputs */
  --monospace: var(--atlas-font-mono);
  --theme-foreground: var(--atlas-text);
  --theme-foreground-focus: var(--atlas-brand);  /* Framework link and focus colour */
  --theme-background-a: var(--atlas-surface);
  --theme-background: var(--atlas-page);
  --theme-background-alt: var(--atlas-surface);  /* .card becomes white on the mist page */
  --theme-foreground-muted: var(--atlas-muted);  /* replaces the UX-22 colour-mix */
  --theme-foreground-faint: var(--atlas-faint);
  --theme-foreground-faintest: var(--atlas-line);
}
body { font: 400 16px/1.6 var(--atlas-font-body); }
h1, h2 { font-family: var(--atlas-font-display); color: var(--atlas-ink); }
```

Keep the UX-22 underline rules for links in running text. After the change, re-measure contrast:
axe `color-contrast` must stay at 0 nodes on every route.

## 4. Shell

### 4.1 Sidebar (VD-3)
- Group the pages in `observablehq.config.js` (VD-D4). Sections without `open` or `collapsible`
  are always open:
  `Explore`: Experts, Collaboration network, Institutions; `Data`: Monitoring, Funding, Evidence
  map; `Context`: Policy, Related resources; `Reference`: About, Glossary. The site title link
  stays first and is labelled Overview in the active state.
- Icons: one 18 px icon per link via CSS `mask-image` on `a::before`, keyed by the link's `href`
  suffix. Take the icon shapes from the style tile's sprite (`#i-home`, `#i-person`, `#i-network`,
  `#i-building`, `#i-drop`, `#i-coins`, `#i-grid`, `#i-scale`, `#i-link`, `#i-info`, `#i-book`)
  and encode them as data-URI SVGs. Before writing selectors, check the built hrefs in
  `framework/dist/*.html`.
- Brand block: the title link gets the coastline mark (`ca_mark.svg`, pre-coloured, as a data
  URI) and the product name in the display face.
- States: hover = brand-wash fill. Active = brand-tint pill, weight 650, brand icon and a 3 px
  inset `--atlas-brand` bar on the left of the pill, so the state does not rest on a pale fill
  alone. Add `aria-current="page"` in `postbuild.mjs` if Framework does not emit it.
- Group labels: eyebrow style, not links.
- Recheck the axe `list` and `region` rows (UX-32): grouping changes the sidebar markup.

### 4.2 Header (VD-3)
- Use the function form, which Framework 1.13.4 supports:
  `header: ({title, path}) => "..."`. It renders inside `#observablehq-header`. Raise
  `--observablehq-header-height` to fit a 40 px control; the main column offset follows from it.
- Contents, left to right:
  - A "Skip to content" link to `#observablehq-main`, visible on focus. It is the first focusable
    element on every page; today 11 sidebar links come before the content.
  - The mark and "CA Plastics Research Atlas" (VD-D8; it replaces "California research atlas").
    Show them only when the sidebar is hidden (narrow screens or toggled closed). Otherwise show
    the nav group and page title as a quiet breadcrumb.
  - An expert search field (VD-D6) on the right.
- The search submits to `./experts#search=<query>` through a small inline handler in config
  `head`. Without JavaScript the form still opens `./experts`. The Experts page keeps filters in
  the hash (verified: `#institution_type=UC&now=ca`). Before shipping, confirm that the search
  key is `search` (the field's `name`).

### 4.3 Mobile
- Restyle Framework's sidebar toggle label (today a "|→" glyph floating half-way down the left
  edge) as a 40 x 40 menu button fixed in the header's left slot. Add
  `env(safe-area-inset-left)` and `env(safe-area-inset-top)` to its offsets. Read the element
  ids from the built HTML; axe shows `#observablehq-sidebar-close` inside the sidebar `<ol>`.
- At 390 px the header shows the menu button, the mark and an icon-only search button that
  expands the field.

### 4.4 Footer
- Config `footer`. Keep the independence disclaimer word for word. Add links to About,
  Glossary, How to cite (the About anchor; check its id), Report a correction and the source code.
  Use two columns from 720 px up, stacked below that. Keep the footer link underline rule.

## 5. Components (VD-4)

Global stylesheet `framework/src/design/components.css`, imported by `style.css`. Build a living
reference at `/styleguide` (VD-D5: not in the sidebar, `noindex` through front matter `head`,
excluded from the sitemap and `llms.txt`). It renders every component below with real Atlas
copy. Icons come from `framework/src/components/shared/icons.js`: the style tile's sprite
(24 symbols, drawn for the Atlas, repository licence) plus `icon(name, {label})`, which returns
`<svg class="icon" aria-hidden="true"><use href="#i-name"/></svg>`. Inject the sprite once per page.

| Component | Classes | Rules |
|---|---|---|
| Page header | `.atlas-page-head`, `__eyebrow`, `__lead`, `__meta`, `.motif` | Brand-wash band, 12 px radius, faint coastline motif at the right. Eyebrow = nav group with its icon. h1. Lead at most two sentences. Meta row of pills: count, refresh date, glossary link. |
| Pill | `.atlas-pill`, `--brand` | 28 px high; counts in `<strong>`; icon optional. |
| Buttons | `.atlas-btn` plus `--primary`, `--secondary`, `--ghost`, `--icon` | 40 px high (icon button 40 x 40); primary = brand-action fill; secondary = white with boundary border; ghost = brand text. One primary per panel. |
| Fields | `.atlas-field`, `.atlas-label`, `.atlas-hint`, `.atlas-input`, `.atlas-select`, `.atlas-search`, `.atlas-check` | 40 px controls, boundary border, 8 px radius. Custom select chevron. Search field with a leading icon. Checkbox 20 px with `accent-color`. The label sits above the control, never beside it touching. |
| Filter panel | `.atlas-filters`, `__head`, `__body`, `__grid`, `__more`, `.atlas-active-filters`, `.atlas-filter-chip` | Head = "Filters", an "N on" count and "Clear all". Primary fields in one responsive grid row. The rest go under `<details class="atlas-filters__more">` "More filters (N)", which opens automatically when a hidden filter is active. Active filters show as removable chips (remove button 24 px, labelled "Remove <filter> filter"). |
| Result line | `.atlas-result-line` | "1,205 of 2,614 experts" in the display face, with the volume caption next to it. |
| Callouts | `.atlas-callout` plus `--info`, `--caution`, `--new`, `--dev` | Icon and text; one meaning each. Info = definitions and volume notes. Caution = limits on what data shows. New = recent items. Dev = "In development". Replaces the four current box styles. |
| Badges | `.atlas-badge` plus `--good`, `--accent`, `--muted` | Status always carries an icon and a word. Institution-type badges use display labels (VD-10). |
| Topic chips | `.topic-chip` (from `topics.js`) | Unchanged; they are the main colour on most pages. |
| Stat tile | `.atlas-kpis`, `.atlas-kpi`, `__label`, `__value`, `__note`, `--loading` | Label in eyebrow style with an icon; value 2rem. Fixed minimum height, plus a shimmer while loading, so filling in shifts nothing. |
| Cards | `.atlas-card`, `.atlas-entry`, `.atlas-task` | White, line border, 12 px radius. Link cards lift 1 to 2 px with the float shadow on hover. Entry cards have an icon tile, title, one-line text and an optional meta count. |
| Table | `.atlas-table-wrap`, `.atlas-table`, `.r` | Sunken sticky head; numbers right-aligned with `tabular-nums`; row hover; wrapper scrolls horizontally on its own. |
| Chart card | `.atlas-chart`, `__head`, `.atlas-segmented` | Title, source line, and a Chart/Table segmented control. Every chart has a table view (dataviz rule); this replaces the separate "View ... as a table" links. |
| Disclosure | `.atlas-disclosure` (`<details>`) | Same look as the filter head; used for "About this page" text and for Monitoring's sections. |
| Skeleton | `.atlas-skeleton` | Shimmer block; off under reduced motion. |

## 6. Page refinements

Every page gets the page header, the shared controls and callouts, and no outer bordered panel
around the whole page (today's ported pages have one). Per route:

- **Overview `/` (VD-5).**
  - Hero band (brand-strong, coastline motif at the right through a CSS mask of a white-stroke
    SVG variant, so no JavaScript) holding:
    - eyebrow "California · 32.5° to 42° N · Plastics research since 1950";
    - h1 "CA Plastics Research Atlas", with the existing one-sentence purpose;
    - an expert search with an accent button;
    - the refresh time in `<time>`.
  - Four stat tiles overlap the hero's lower edge, with reserved height (fixes CLS 0.17).
  - "Start here" becomes three task cards with icons.
  - "Explore the Atlas" becomes eight entry cards with icons. Meta counts appear only where
    `build_metadata.json` `counts` has them (authors, works, institutions, CA institutions);
    other cards show no number until VD-13.
  - On phones: tiles 2 x 2, cards in one column.
  - S3.7 later adds its own content (featured visual, What's new, citation badge) inside this
    frame.
- **Experts (VD-6a).**
  - Primary filters: Search, Domain or matrix tag, Institution type, Sort by. Under More filters
    (7): Institution, Current affiliation, Career stage, From year, To year, CA basis, OA.
  - Active filter chips; the result line with the volume caption kept visible.
  - Export as the primary button; Reset as secondary.
  - "What do the expert terms mean?" becomes a disclosure.
  - Expert rows: name in the display face, affiliation, badges, topic chips, metrics in a muted
    row.
  - The drawer uses the shared header, buttons and tables.
  - Target: at least three expert rows visible at 1440 x 900.
- **Collaboration network (VD-6b).**
  - Controls move into a toolbar panel. Primary: Find an expert, Colour by, Size by, Research
    topic. Under More filters: Institution sector, Institution contains, From and To year,
    Minimum co-authored works, Now in California only.
  - Zoom, reset, full screen and layout buttons become 40 px icon buttons over the canvas, each
    with a visible tooltip and an accessible name.
  - The legend becomes chips; the detail panel becomes a card.
  - The two explanatory paragraphs become a two-sentence lead plus a "How to read the network"
    disclosure. The volume caveat stays visible.
  - Targets under 24 px go from 413 to 0.
- **Institutions and Institution (VD-6c).**
  - Type chips use display labels (VD-10); the leaderboard toggle becomes a segmented control.
  - Tier rows become cards with the rank-range bar in brand colour; tier headers use the
    display face.
  - Map controls become icon buttons; the land fill moves to a mist tint.
  - The institution page gets a page header with a type badge, stat tiles and its sections as
    cards.
  - Keep the "not a quality ranking" and tier-overlap text visible (do-not-regress).
- **Monitoring (VD-7a).**
  - The caveat becomes a caution callout with its text visible.
  - Accordion sections become `.atlas-disclosure` with counts in the head. The filter panel and
    map card use the shared styles.
  - Fix the 320 px reflow row from UX-19 while here.
- **Funding (VD-7b).**
  - Page header (eyebrow "Data", h1 "Funding", lead); the "Awards" h2 directly under the h1 goes.
  - The amount-basis text becomes a caution callout and the volume note an info callout, both
    visible.
  - Filter panel with primary fields Search, Funder agency, Topic tag and the fiscal-year range;
    the rest under More filters.
  - Stat tiles; chart cards with the Chart/Table control. Heatmaps use the teal ramp (VD-9).
- **Evidence map (VD-7c).**
  - The four intro paragraphs become a two-sentence lead plus a "How to use this page"
    disclosure. "In development" becomes a dev callout; the auxiliary-topic note becomes an info
    callout; "New in the last 2 weeks" becomes a new callout.
  - Topic checkboxes show the topic dot.
  - Heatmap and table become chart cards. The UX-30 selection banner uses filter-chip styling;
    behaviour is unchanged.
- **Policy, Related resources, About, Glossary (VD-8).**
  - Policy becomes a vertical timeline: a date rail, status badges with icons (use only the
    statuses the data has; read them from code, not by opening `site/data`) and source links
    with an external-link icon. The caveat stays visible.
  - Resources become cards with steward and reuse badges.
  - About: "How to cite" becomes a card with the DOI in mono; the limitations stay visible.
  - Glossary: terms in the display face with anchor links, and the `:target` term highlighted
    in brand-wash.
- **Classic and generated pages (VD-11).**
  - `site/expert.html` takes the tokens, fonts, header look and footer until UX-13 moves it into
    the shell.
  - Static SEO pages (`scripts/build_seo_pages.py`) get a small inline token stylesheet, so a
    visitor arriving from a search engine sees the same identity.

## 7. Charts, maps and data colour (VD-9)

Follow the dataviz method: pick the form first, assign colour by its job, then validate.

- **Topics.** Keep the eight topic hues and the hatched subtopics exactly as in
  `site/assets/topics.js`. They are the Atlas's identity colours for data.
- **Other categories** (agencies, sectors, monitoring matrices, network communities): use one
  secondary categorical set in fixed order, with at most 7 named slots plus an "Other" grey;
  never cycle hues. Start from the network's Okabe-Ito order (`COMMUNITY_COLOURS` in
  `network_model.js`, which passes adjacency with a warning, so direct labels or a legend are
  required). Run the validator (`scripts/validate_palette.js` in the dataviz skill) and record
  its output in the task's verification doc:
  - stacked bars and lines on the default adjacent pairs;
  - maps and scatter plots with `--pairs all`. If the set cannot pass all pairs, encode by
    group (at most 3 or 4 colours) and add marker shape.
  - Replace the failing monitoring map set (`svg_map.js`) and funding agency set
    (`funding_viz_model.js`).
  - Never use a topic hue and a secondary hue for different meanings in the same chart. In the
    Sankey, agencies stay neutral and topics carry colour.
- **Magnitude.** One sequential teal ramp (`--seq-100` to `--seq-700`) for every heatmap and
  choropleth, replacing Funding's blue ramp. Check that lightness steps down monotonically, and
  that the lightest step reads as near zero.
- **Chart chrome.** Gridlines `--atlas-line`; axes and tick labels `--atlas-muted`; values and
  labels in text colours, never in series colours; 4 px rounded data ends; thin bars; a 2 px
  surface gap between stacked segments; direct labels where at most four series appear; hover
  tooltips on marks; Chart/Table control on every chart card.
- **Single source.** A `framework/src/components/shared/palette.js` exports the secondary set,
  the ramp and the chrome colours for JavaScript charts. A test asserts that its values equal
  `tokens.css`, and the token check (VD-1) stops new hex literals in component JavaScript.

## 8. Do not regress

From [EM_spec.md](EM_spec.md) Section 2 and later tasks:
- The independence disclaimer in every footer, word for word.
- Volume captions on every count view (UX-16): "Counts show volume, not strength..."
- Institutions: "It is not a quality ranking" and the tier-overlap explanation.
- Map keyboard operation (arrows pan, +/- zoom, Zoom in / Zoom out / Reset view).
- Monitoring caveats; the Funding amount basis and empty state; the Policy caveat; About
  limitations, corrections and the release DOI.
- Every table alternative to a chart.
- Glossary links from terms; `<html lang>`, pinch zoom and meta descriptions from
  `postbuild.mjs`.
- URL formats: Experts hash filters, `institution#inst=`, `expert.html#author=`, legacy
  redirects.
- The UX-30 Evidence map selection feedback; the Experts drawer layering fix in `style.css`.
- No horizontal overflow at 375 px; the public-text check (`scripts/check_public_text.py`); the
  six UX-18 tasks.

## 9. Verification

Per task, on a local build of the assembled site (`scripts/serve_framework_preview.py
--assembled <dir>`; see MEMORY for the copy and assemble steps):

1. `cd framework && npm run build`, then `py -3.14 scripts/check_at5.py --dist dist`.
2. The full gate from `CLAUDE.md` (links, scaffolds, lint, tests, build, `git diff --check`, and
   the clean-worktree pytest).
3. `py -3.14 scripts/check_public_text.py` and `py -3.14 scripts/check_design_tokens.py` (from
   VD-1).
4. `py -3.14 ~/tools/ux-audit/ux_audit.py <local-base> <routes> --out scratch/ux_vd<n>
   --lighthouse` on the routes the task touched. axe may report no rule id beyond the baseline
   (`list`, `region` until UX-32). Lighthouse performance may drop at most 3 points per route,
   accessibility none, and CLS must stay under 0.1.
5. Screenshots at 1440 x 900 and 390 x 844 of the touched routes, compared with the style tile
   and the baseline screenshots, with the differences listed in the verification doc.
6. `py -3.14 scripts/ux_tasks.py --base <local-base>`: all six tasks pass.
7. Write a `docs/VD_<n>_VERIFICATION.md` with commands, numbers and screenshot paths.

Global acceptance (VD-12), measured with `scripts/design_snapshots.py` (new; a local Playwright
script like `scripts/ux_tasks.py`, with screenshots to `scratch/`):
- No route renders Palatino Linotype, Times New Roman or Arial (DevTools platform fonts).
  Headings render in Barlow Semi Condensed; body text in the system face.
- The CSS token check passes with 0 hex literals outside `tokens.css` in Framework stylesheets,
  and the component JavaScript count below baseline.
- Every route has a page header and at least one icon. Every chart has a table view.
- Lighthouse on every route: CLS under 0.1, accessibility at or above baseline, performance no
  more than 3 points below baseline. Font transfer at most 60 KB; added CSS at most 12 KB gzip.
- First-screen colourfulness reported for every route next to the baseline, as information.
  The expected range is 25 to 40 on the Overview and above 20 elsewhere; it is not a hard gate.
- The owner reviews the before and after screenshots (H25).

## 10. Tasks

Sizes: S at most 2 hours, M at most a day, L more. Order: VD-1, VD-2, VD-3, VD-4, then VD-5 to
VD-8 in any order (disjoint files), with VD-9 before VD-7b and VD-10 before VD-6c, then VD-11
and VD-12. UX-32 runs after VD-4, because the shared component sizes clear most of its 24 px
rows. VD-13 is a data task and may run any time.

| ID | Task | Owns | Acceptance (plus Section 9) | Size |
|---|---|---|---|---|
| VD-1 | Tokens and foundations | `framework/src/design/tokens.css` (new); `style.css`; the palette blocks in `experts.css`, `funding.css`, `institution.css`, `institutions.css`, `monitoring.css` (alias the local variables to tokens); `scripts/check_design_tokens.py` and its test (new); one CI step | Ratchet baseline committed; CSS hex uses below 293; native links teal; axe `color-contrast` 0 | M |
| VD-2 | Type and surfaces | Barlow Semi Condensed 600 and 700 latin WOFF2 plus OFL text (VD-D2); `@font-face` with `font-display: swap` and a preload of 700; base styles; `docs/REUSE.md` entry | Platform fonts as in Section 9; fonts at most 60 KB; CLS and LCP within limits. First verify that Framework copies CSS `url()` assets into `dist`; if not, serve the fonts from `site/assets/fonts/` and reference `/assets/fonts/...` | S/M |
| VD-3 | App shell | `observablehq.config.js` (sections, header, footer, head); `framework/src/design/shell.css`; `postbuild.mjs` only if needed | Grouped nav with icons and active state on every route; skip link first in tab order; header search lands on filtered Experts; menu button in the header at 390 px | M |
| VD-4 | Shared components and icons | `framework/src/design/components.css`; `framework/src/components/shared/icons.js`; `framework/src/styleguide.md` (VD-D5) plus its sitemap and `llms.txt` exclusion | `/styleguide` shows every Section 5 component; axe clean there; targets of at least 24 px | M |
| VD-5 | Overview | `framework/src/index.md`; Overview CSS; motif variant through `scripts/build_design_motif.py --mask` (to add); `framework/src/assets/design/` | CLS under 0.1 on `/` (median of 3 Lighthouse runs); LCP at most 1.1 s; motif at most 20 KB; 390 px layout as specified | M |
| VD-6a | Experts | `experts.md`, `experts.css`, `experts.js` (markup only) | At least 3 rows on the first screen at 1440 x 900; hash format unchanged; UX-18 tasks pass | M |
| VD-6b | Collaboration network | `network.md`, `network.css`, `network.js` (markup only) | Targets under 24 px: 0; controls labelled; canvas interactions unchanged | M |
| VD-6c | Institutions and Institution | `institutions.md` and `.css`, `institution.md` and `.css`, their JS (markup only) | Display labels; map keyboard operation unchanged | M |
| VD-7a | Monitoring | `monitoring.md`, `monitoring.css`, `monitoring.js` (markup only) | Caveats visible; no reflow at 320 px | M |
| VD-7b | Funding | `funding.md`, `funding.css`, `funding_viz.css` | Single h1 head; Chart/Table on every chart; amount basis visible | M |
| VD-7c | Evidence map | `evidence.md` and the `ev_*`, `v3_flow`, `v4_trend` CSS | Lead at most 2 sentences; UX-30 behaviour unchanged | M |
| VD-8 | Policy, Resources, About, Glossary | Those four `.md` files and their CSS | Timeline readable at 390 px; `:target` highlight | M |
| VD-9 | Chart and map colour | `shared/palette.js` (new); `svg_map.js`, `funding_viz_model.js`, `network_model.js`, `ev_heatmap_model.js` colour constants; tests | Validator output recorded; no failing set; one sequential ramp | M |
| VD-10 | Display labels | `framework/src/components/shared/labels.js` (new) and its use in chips, selects, legends and cells | No slug from the F10 list on screen; URL values unchanged; test covers every vocabulary value in code | S |
| VD-11 | Classic and generated pages | `site/expert.html` styles; the `scripts/build_seo_pages.py` template | Same fonts and palette as the app; profile hash links unchanged | S/M |
| VD-12 | Design QA and owner review | `scripts/design_snapshots.py` (new); `docs/VD_12_VERIFICATION.md` | Global acceptance in Section 9; owner H25 review done | M |
| VD-13 | Overview counts (data, optional) | `scripts/build_export_site.py`: add network experts and links, awards, monitoring samples and sources, and plastic-related works to `build_metadata.json` `counts`; `docs/SITE_DATA.md` | Counts match their pages; Overview entry cards show them | S |

## 11. Decisions (defaults in use; owner answers in QUESTIONS)

| ID | Question | Default |
|---|---|---|
| VD-D1 | Adopt the Pacific Contour direction (style tile)? | Yes |
| VD-D2 | Self-host Barlow Semi Condensed 600 and 700 (SIL OFL 1.1, about 40 KB) for headings? | Yes. If declined, headings use the system face at weight 700 |
| VD-D3 | Icons: the style tile's 24 line icons, drawn for the Atlas? | Yes; no third-party icon set |
| VD-D4 | Sidebar groups Explore, Data, Context, Reference? | Yes |
| VD-D5 | An unlisted `/styleguide` page (noindex; not in sitemap or `llms.txt`)? | Yes |
| VD-D6 | Expert search in the header on every page? | Yes |
| VD-D7 | Long page intros move into a collapsed "About this page" disclosure, while the do-not-regress caveats stay visible as callouts? | Yes |
| VD-D8 | Header name "CA Plastics Research Atlas" instead of "California research atlas"? | Yes |

## 12. Limits of this spec

- The assessment used automated tools and one reviewer's reading of screenshots. Visitors have
  not seen the direction; the UX-20 sessions (H18) are the place to test it.
- Measurements are from Windows with Chromium. Rendered fonts on macOS, iOS and Android were not
  measured; the fallback stacks are written so each platform uses its own system face.
- Colourfulness is a rough proxy for "has colour", not a quality score; it is reported, not
  gated.
- Contrast values were computed for the listed pairs only. New pairs need their own check.
- Page copy changes are limited to moving text into disclosures and callouts. Rewording is not
  part of this spec; UXD-4 (Experts or Authors) remains open separately.
