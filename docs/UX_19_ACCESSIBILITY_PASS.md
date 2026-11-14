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

## Failures

| # | Route | Element | Criterion | Problem | Proposed fix |
|---|---|---|---|---|---|
| 1 | every Framework page | sidebar `#observablehq-sidebar > ol` | 1.3.1 | axe `list`: the sidebar list holds non-`li` children (Framework 1.13.4 template) | In `framework/scripts/postbuild.mjs`, wrap the stray children in `li` or give the `ol` `role="none"` with `role="list"` on a wrapper; recheck on Framework upgrade |
| 2 | /expert.html | `#metrics` | 1.3.1 | axe `definition-list`: the `dl` contains elements other than `dt`/`dd` groups | Wrap each term pair in a `div` (allowed) or move notes out of the `dl` |
| 3 | /monitoring | `section.institution-map-panel`, `details#facet-gaps` | 1.4.10 | Page is 326 px wide at 320 px (scrolls sideways) | Let the map panel and the facet-gaps summary shrink (`min-width: 0`, wrap long words) |
| 4 | /experts | "Full profile" links on each card | 2.5.8 | Targets under 24 px high and close together | Pad to `min-height: 24px` (`display: inline-block; padding-block: .2rem`) |
| 5 | /network | topic, sector and colour selects; institution, year, search inputs; min-works slider | 2.5.8 | Form controls under 24 px high | Set `min-height: 2rem` on `.controls select, .controls input` in `network.css` |
| 6 | /institution, /evidence | sort buttons in the publication table header (Published, Title, Journal, Citations) | 2.5.8 | Buttons under 24 px high | `min-height: 24px` on `.ev-sort` in `ev_table.css` |
| 7 | /institution, /evidence | first link in each row's link cell (`td .ev-links a`) | 2.5.8 | axe `target-size`: DOI/OA links under 24 px with too little spacing | Space the links (`gap: .5rem`) or pad them |
| 8 | /institutions | map cluster markers (`g.monitoring-marker`) at statewide zoom | 2.5.8 | Several markers render under 24 px and overlap | Give clusters a 12 px minimum radius, or rely on the 2.5.8 equivalent-control exception and say so: the tier table lists every institution |
| 9 | /institutions | tier-table name button for long names (e.g. "Inter-American Tropical Tuna Commission") | 2.5.8 | Button height under 24 px when the name wraps tightly | `min-height: 24px` on `.tier-name` |
| 10 | /funding | one `input` with no id or name; the organisation link "AI-Materials Institute (AI-MI)" | 2.5.8 | Controls under 24 px | Identify the input (likely a chart control), pad it and the standalone organisation links |
| 11 | / | "Start here" links; /experts "Current affiliation" glossary link | 2.5.8 | Standalone links (not in a sentence) under 24 px | Pad standalone links, or move them into sentences |
| 12 | /evidence, /about | in-page jump links (Trends, Evidence heatmap, Publications; About section links) | 2.5.8 | Standalone links under 24 px | Render as a padded inline list (`li a { display:inline-block; padding:.25rem 0 }`) |

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
