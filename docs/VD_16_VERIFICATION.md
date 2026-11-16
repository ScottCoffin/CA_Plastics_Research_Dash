# VD-16 verification: Chart/Table control on the Evidence map

Date: 2026-11-16

The Trends, Evidence heatmap and Pipeline flow cards each have an `.atlas-segmented`
Chart/Table control (`aria-pressed`) and a table pane with the chart's numbers (trend: year rows;
heatmap: row x column counts; flow: stage, status, step, count). `evidence.js` `wireChartViews()`
sets `data-view` on the card; CSS shows the matching pane, so filter-driven re-renders keep the
chosen view. The trend's former screen-reader-only table is now the visible table pane. The
heatmap mode toggle, UX-30 selection banner and focus behaviour are unchanged; no data loads were
added. The Publications card is the works table itself and has no toggle.

Verification: `tests/test_vd16_evidence_tables.py` (10) plus the VD-7c, evidence, heatmap, trend,
flow and table suites (55 passed). Assembled local site: clicking Table on Trends shows 27 rows
and on the heatmap 11 rows with `aria-pressed="true"`; Chart restores the chart; axe no
violations at desktop and 375 px; `ux_tasks.py` 6/6.
