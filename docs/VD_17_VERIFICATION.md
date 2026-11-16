# VD-17 verification: no hex literals outside tokens.css

Date: 2026-11-16

Spec Section 9 gate: 0 hex literals outside `tokens.css` in Framework stylesheets. Before:
84 (`ev_heatmap.css` 29, `ev_table.css` 35, `monitoring.css` 16, `experts.css` 3,
`institutions.css` 1). After: 0. `scripts/check_design_tokens.py` now has every baseline at 0 and
`MAX_HEX_USES = 0`, so any new literal fails CI. One token added: `--atlas-map-water: #cfe5f2`
(state waters on the Monitoring and Institutions maps).

Visible changes (role-based mapping per spec Section 3.1): the old blue links, outline buttons
and toggles on the Evidence table and Monitoring become brand teal; focus rings become accent
`#c45100`; the "New" badge uses accent with white text (4.64:1); table heads use sunken; the
Monitoring land fill uses sunken with a boundary stroke. All mapped text pairs are at least 4.5:1
(lowest 4.63).

Verification: design-token tests now use their own mechanism baseline; `test_ux29` resolves the
badge's `var(--atlas-*)` colours from `tokens.css` before computing contrast (still AA); focused
suites 92 passed; assembled local site axe-clean on the touched routes; `ux_tasks.py` 6/6.
