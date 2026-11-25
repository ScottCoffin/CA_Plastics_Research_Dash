# BQ-V.5 verification: graph accessibility pass

Scope: the global graph viewer (`framework/src/components/graph_viewer.js`, `graph_viewer_model.js`,
`graph_viewer.css`) as mounted on `/dev_graph` (unlisted development page) and on `/explore`, Network
tab (`#view=network`, hash prefix `gv.`). Explore's own code was not changed.

## Gaps found and fixed

| Gap | Fix |
|---|---|
| Canvas container was `aria-hidden` and not focusable | Stage is `role="application"`, `tabindex="0"`, with a focus ring and a visually hidden key list (`aria-describedby`). The label names the graph, node and link counts and the table. sigma's canvases are `aria-hidden`. |
| No keyboard control of the graph | `+`/`=` zoom in, `-`/`_` zoom out, `0` resets, arrow keys pan by 15% of the view, `Escape` clears the selection. |
| Selecting a node did not move focus | Search, table names and strongest-link buttons move focus to the details heading (`tabindex="-1"`). |
| Escape did not return focus | `Escape` on the graph or details clears the selection and returns focus to the control that made it, else the graph (or the table toggle when the table is shown). |
| No announcement of selection | `aria-live="polite"` status inside the details region: "Selected <name>, <n> works." or "Selection cleared." |
| Search results could only be entered with the first arrow key | Arrow up and down move between results; up from the first result returns to the search box. |
| Details body was a `<p>` that received lists (invalid HTML) | Now a `<div>`. |
| Table had no caption and no link count or neighbour column | Caption (visually hidden); columns Name, Country or type, Works, Links (sortable), Community, Strongest links (top three neighbours by shared works). Sort buttons sit in scoped headers with `aria-sort`. |
| Sort and link targets were under 24 px | `.gv-sort` and `.gv-link` have a 1.5rem (24 px) minimum height. |

Unchanged and already passing: the legend is a real list with text labels (colour is never the only cue); the
table is reachable when WebGL fails (fallback) and by the "Show as table" control; reduced motion makes camera
moves instant (`matchMedia`) and disables CSS transitions.

## Keyboard map

| Key | Where | Action |
|---|---|---|
| Tab / Shift+Tab | page order | Search box, Colour by, Zoom in, Zoom out, Reset view, Show as table, graph (stage), then the table when shown |
| Enter / Space | buttons | Activate (zoom, reset, table toggle, sort, result, link) |
| Type, then ArrowDown | search box | Focus the first result |
| ArrowDown / ArrowUp | results | Move between results; ArrowUp on the first returns to the search box |
| Enter | search box | Select the first match (focus moves to the details heading) |
| Enter | result | Select that name (focus moves to the details heading) |
| Escape | search box | Close the results |
| Escape | results | Close the results and return to the search box |
| + / = and - / _ | graph focused | Zoom in and out |
| ArrowLeft / Right / Up / Down | graph focused | Pan the view |
| 0 | graph focused | Reset the view (also clears the selection) |
| Escape | graph or details focused | Clear the selection; focus returns to the control that made it |

## Checks run

Build: `cd framework && ATLAS_FW_OUT=dist-v5 npm run build`, exit 0. Served through
`scripts/serve_framework_preview.py --assembled` (site copy in `scratch/`); Chromium driven from Python
Playwright; axe-core 4 (`~/tools/ux-audit`) injected with tags wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa.

### axe results (after the fixes)

| Page | Width | Viewer state | Violations |
|---|---|---|---|
| `/dev_graph` | 1440 | ready | 0 |
| `/dev_graph` | 390 | ready | 0 |
| `/explore#view=network` | 1440 | ready | 0 |
| `/explore#view=network` | 390 | ready | 1: `label-content-name-mismatch` on `#scope-btn` (explore.js, the scope picker; not the viewer) |

The one remaining violation is in `framework/src/explore.js` line 196: the scope button's `aria-label`
("Menu: <view>, <scope>. Open views and scope") does not contain its visible text ("<view> · <scope>" plus
the count). Proposed fix for the owner of explore.js: make the label start with the visible text, for
example `${label} · ${scopeName()}, open views and scope`. This file is outside BQ-V.5 scope and was not changed.

### Keyboard walk (Playwright, both pages, both widths)

- Tab from the search box reaches Colour by, Zoom in, Zoom out, Reset view, Show as table, then the graph
  (focus ring `outline-style: solid`). Then focus leaves the viewer.
- Search: typing "a", ArrowDown focuses the first result, a second ArrowDown moves on, ArrowUp returns to
  the first, Enter moves focus to the details heading ("Aarhus University"), the live region reads
  "Selected Aarhus University, 280 works.", Escape clears the selection, announces "Selection cleared." and
  focuses the search box.
- Graph keys (default motion): `+` changes the zoom in the hash, arrow keys move `x`/`y`, `0` resets the
  hash toward the home view (animated moves are slow in headless Chromium, so the default-motion values
  are only indicative).
- Graph keys with reduced motion (instant moves): `+` gives z 0.6667, `-` gives z 1, ArrowRight x 0.5 to 0.65,
  ArrowLeft back to 0.5, ArrowUp y 0.5 to 0.35, ArrowDown back to 0.5, `0` gives z 1 x 0.5 y 0.5.
- Table: "Show as table" (Enter) shows the table with caption, `scope="col"` on all headers, 200 rows
  (the TABLE_LIMIT), and the sort button on Links sets `aria-sort` to "Links" with a sort order.
- No control under 24 px high on either page (buttons, selects, search inputs, sort buttons, results).
- No page errors.

### Contrast (computed from the design tokens, WCAG 2.2)

| Pair | Ratio |
|---|---|
| Muted label (`--atlas-muted`) on surface | 8.44:1 |
| Muted label on page (`--atlas-page`) | 7.59:1 |
| Text on surface | 15.17:1 |
| Link (`--atlas-brand-action`) on surface | 11.44:1 |
| Focus ring (`--atlas-accent`) on page | 4.38:1 (non-text, 3:1 needed) |
| Input border (`--atlas-boundary`) on surface | 3.35:1 (non-text, 3:1 needed) |

## Tests

- `tests/test_bq_v5_a11y.py` (new, 9 static checks of the aria, table and CSS contract).
- `tests/test_graph_viewer.py` (focusable stage instead of `aria-hidden`), `tests/framework_graph_viewer_runtime.mjs`
  (links sort key, 21 checks), `tests/test_ga2_explore.py`.

## Remaining limits

- Keyboard reaches the graph as one stop; individual nodes are not reachable by arrow keys on the canvas.
  The table (Show as table) is the keyboard route to every node, and it lists the first 200 matches.
- Vertical arrow direction follows the camera's y coordinate; the mapping was checked in the hash, not by
  looking at the rendered picture.
- The legend is display-only (no legend filters exist). Downloads are not part of the viewer.
- Sigma's node label colour was not set explicitly; labels sit on the page ground and were not measured.
- The one axe violation above is in explore.js (scope picker) and blocks a clean axe run on `/explore` at 390 px until fixed.
