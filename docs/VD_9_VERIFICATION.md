# VD-9 verification: chart and map colour system

Date: 2026-11-16

## Result

`framework/src/components/shared/palette.js` (new, force-tracked; not copied by
`sync_shared.mjs`) is the single source for JavaScript chart colours:

- `SECONDARY` (bars and lines, 7 slots, Okabe-Ito order): `#0072B2 #D55E00
  #009E73 #CC79A7 #E69F00 #56B4E9 #7A4E9B`.
- `SECONDARY_ALL_PAIRS` (maps and the network): the first six.
- `OTHER` `#8a969c`: one grey for every "Other" or unknown slot.
- `SEQ`: the seven `--seq-100..700` tokens; `rampFill(t)` interpolates across all
  steps; `countFill(count, max)` gives zero the sunken fill and starts any
  non-zero count at seq-200.
- `CHROME`: grid `--atlas-line`, axis `--atlas-muted`, text, surface, sunken;
  neutral steps for the Funding Sankey sectors, funder and network edges.

Replaced sets:

| Where | Before | After |
|---|---|---|
| Monitoring map matrices (`svg_map.js`) | 8 ad-hoc hues, failing (CVD ΔE 1.6 stormwater/surface water) | surface water `#0072B2`, stormwater `#56B4E9`, wastewater effluent `#D55E00`, sediment `#E69F00`, fish `#009E73`; atmospheric deposition and both snow matrices share `#CC79A7` as one deposition group (snow captures atmospheric deposition; the legend still names each matrix); unknown `OTHER` |
| Funding agencies (`funding_viz_model.js`) | 10 hues, failing (CVD ΔE 1.1 OPC/EPA) | NSF, NIH, NOAA, EPA, CA Ocean Protection Council, NIST, USDA take `SECONDARY` in order; the rest fold into `OTHER`. Sankey agencies stay neutral; topics carry colour |
| Funding heatmap | blue ramp | teal `countFill` |
| Evidence heatmap (`ev_heatmap_model.js`) | two-point teal interpolation | `countFill` across the seven steps; cell border `--atlas-line` |
| Network communities (`network_model.js`) | 8 slots | 6 (`SECONDARY_ALL_PAIRS`) plus `OTHER` |
| Funding gridlines (`funding_viz.js`) | `#c8d8dc` | `CHROME.grid` |

## Palette validation

Run with the dataviz skill's `validate_palette.js` (light mode, white surface):

- `SECONDARY`, adjacent pairs: ALL CHECKS PASS. CVD warn 7.6 (deutan,
  `#CC79A7`/`#009E73`); contrast warn for `#E69F00` 2.25 and `#56B4E9` 2.31, so
  legends, direct labels or a table view are required (all charts keep them).
- First six, `--pairs all`: ALL CHECKS PASS with the same CVD warn. The 7- and
  8-slot sets fail all pairs (`#7A4E9B`/`#0072B2` deutan ΔE 3.8, normal 14.0;
  `#8C6D1F`/`#D55E00` protan 1.8), hence six colours on maps and the network.
- Teal ramp, `--ordinal`: monotone lightness, adjacent ΔL >= 0.06 and single hue
  pass; light-end contrast fails (seq-100 1.15:1 on white) by design, because
  seq-100 is the near-zero step. Mitigation: non-zero heatmap counts start at
  seq-200 and empty cells use the sunken fill with a hairline border.

## Verification

- Tests: `tests/test_vd9_palette.py` (palette equals `tokens.css`, slot order,
  ramp monotone, no hex literals in the six chart modules) and updated network,
  funding, heatmap and monitoring runtime tests. The monitoring drift guard now
  compares matrix keys with the classic page, not colour values.
- Design-token ratchet: 175 Framework stylesheet hex uses (baseline lowered by one).
- Assembled local site, rendered colours: Evidence heatmap cells on the teal ramp
  with empty `#eaf1ef`; Monitoring map `#0072B2` and `#CC79A7` (the matrices in
  the current data); Network legend six Okabe-Ito colours plus `#8a969c`;
  Funding agency bars use `SECONDARY` and `OTHER`.
- axe clean, no overflow or console errors on the touched routes; `ux_tasks.py`
  6/6 passed.

## Lighthouse (local, mobile preset)

Local scores are lower than live for every route (unthrottled static server, no
compression) and are not comparable with the live baseline. Accessibility was
100 on all eight routes. `/network` CLS 0.421 also occurs live at HEAD without
this change (shifted node `section.net-page`), so it predates VD-9; it is
recorded as a follow-up in TODO.

## Deployed

Pushed `3d15e753`..`2cc15d30` on 2026-11-16; CI `43964970928`, Pages `43964971620` and legacy Pages `43964967242` passed. Live check on https://plastiverse.live/: Overview cards show the six new counts; network legend six Okabe-Ito colours plus `#8a969c`; Monitoring map `#0072B2`/`#CC79A7`; Funding "503 of 524 awards match".
