# UX-19 manual accessibility pass (WCAG 2.2 AA): failure table

Date: 2026-11-14. Build: the switched site (Framework app at the root), assembled locally with
`scripts/assemble_site.py` and served by `scripts/serve_framework_preview.py --assembled`.
Method: human-assisted. `scripts/ux19_a11y_pass.py` automates the checklist steps in
`docs/EM_spec.md` UX-19 on 14 routes (axe-core 4.10.3 with WCAG 2.0/2.1/2.2 A and AA tags; a full
keyboard Tab walk checking visible focus, focus hidden under the header and traps; pointer-only
controls; live regions on filtered pages; 24 px targets; reflow at 320 px, the same as 400% zoom of
a 1280 px window; title, lang, heading order, viewport). The lead then re-checked every suspected
failure in the browser and removed false positives (listed at the end).
Per the spec, this task records failures only; nothing was fixed here.

Not covered by machine checks and still owed by a person with assistive technology (owner H22):
NVDA or Narrator reading of filter labels and result announcements, Windows High Contrast, and
text spacing (1.4.12).

## Failures (current result, rerun 2026-11-16, UX-32)

None open. Every remaining row is an accepted exception (below). The script lists at most 8
undersized targets per route, so counts below were measured uncapped in the browser.

## Accepted exceptions

| Route | Elements | WCAG exception | Reason |
|---|---|---|---|
| /funding | 42 Sankey node groups (`g`, e.g. "EPA (Funder agency): 12 awards. Press Enter...") | 2.5.8 equivalent control | Every chart has a Chart/Table control with the same data and filter action (VD-7b). The Sankey is not resized |
| /institutions | Statewide map cluster markers (`g.monitoring-marker.institution-marker`) | 2.5.8 equivalent control | Every institution is listed with the same select action in the tier table, whose 168 name buttons are all at least 24 px |
| /funding | "Dataset" link in the open-calls note | 2.5.8 inline | The link sits in a sentence |

## Rerun 2026-11-16 (UX-32)

Command (after `npm run build` in `framework/`, a fresh copy of `site/`, `build_seo_pages.py` and
`assemble_site.py` into `scratch/ux32/site`, served on 127.0.0.1):

`py -3.14 scripts/ux19_a11y_pass.py --base http://127.0.0.1:8810/CA_Plastics_Research_Dash/ --out scratch/ux32/final`

Fixed:
- Sidebar toggle checkbox set to `display: none` in `framework/src/design/shell.css`; the header menu
  button still drives it with `click()` (checked at 390 px).
- Tier-table name buttons: the `.tier-row` grid gives the name column an 11rem minimum and lets the
  type, count and rank columns shrink and wrap (the longer VD-10 type labels had squeezed names to
  4-21 px wide). 168 of 168 buttons now measure at least 24 x 24 px at 1280 and 375 px.
- Expert links in the institution leads table (`#institution-root th a`) and publication-table sort
  buttons (`.ev-sort`), min-height 24 px.
- Award-title links in the Funding table (`.grants-table tbody th a`), min-height 1.5rem.
- Institution and monitoring map markers: `:focus-visible` outline on the marker group.
- Funding top-N range slider (`funding_viz.css`), height 24 px.
- /expert.html: "All experts" link and "Plastics-related only" checkbox at 24 px; the metrics note moved
  inside its `dd`, so each `div` group holds only `dt` and `dd` (axe `definition-list` passes).

Script fixes (`scripts/ux19_a11y_pass.py`): the keyboard walk names implicitly labelled inputs by
their label or value (identical `input ''` keys for a row of topic checkboxes were reported as a
possible 2.1.2 trap; focus does move), and the 4.1.3 live-region check ignores the shared header's
expert search, which navigates to Experts rather than filtering the page.

Result: axe 0 violations on all 14 routes; 12 routes have no rows; /institutions and /funding list
only the accepted exceptions above.

## Checked and passing

- Page title, `lang="en"`, zoom allowed, exactly one `h1` and no skipped heading levels: all 14 routes.
- Visible focus (2.4.7) and focus not hidden by the header (2.4.11): every control reached by Tab
  on all routes (map markers use a 5 px focus stroke on the marker body).
- No keyboard trap (2.1.2) and no pointer-only controls (2.1.1) on any route; the network chart's
  keyboard route is the expert search and the "View as table" list.
- Live regions (4.1.3): every page with filters announces its result count (`role="status"`).
- Text contrast: no axe `color-contrast` failures on any route.
- Reflow at 320 px: every route except /monitoring (row 3).
- No page errors on any route. /expert.html reached the 400-step Tab limit because its
  publication list is long, not because of a trap.

## Non-colour encodings (manual review by the lead)

- Topics: chips show the topic name; hatching marks risk assessment, plastisphere and the auxiliary
  plastic-associated chemicals topic (which is also dashed and italic). Pass.
- Institution tiers: the tier number is text. Pass.
- Evidence heatmap: every cell shows its count and has an accessible name; selection adds a
  check mark and a ring, not only colour. Pass.
- Funding: the Sankey and bar charts label funders in text; tooltips are SVG titles. Pass.
- Network clusters: colour plus the legend; the table view lists each expert's cluster. Pass with a
  note: cluster colours alone cannot be told apart, but no task depends on that.

## False positives removed after browser re-checks

- "Possible keyboard trap" on /evidence and /institution: a run of filter checkboxes (labelled by
  their wrapping `label`) looked identical to the walker; focus does move on.
- "No visible focus" on map markers: focus is shown by a stroke on the marker body, which the
  automated check does not read.
- 24 px target hits on the footer links ("Glossary", "Report a correction"): they sit inside a
  sentence, which 2.5.8 exempts.

Raw output: `scratch/ux19/results.json` and `scratch/ux19/failures.md` (gitignored), regenerated by
`py -3.14 scripts/ux19_a11y_pass.py --out scratch/ux19` against an assembled local site.
