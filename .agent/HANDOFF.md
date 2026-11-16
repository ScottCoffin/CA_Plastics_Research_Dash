# Handoff — 2026-11-15 — UX-28 follow-up (Sankey drill-down)

## Done
- Owner request: the Funding Sankey's click drill-down is restored. Clicking a block, or pressing Enter or Space on it, redraws the Sankey and its table with only the awards that pass through that block. For example, NSF shows only NSF's downstream sectors, organisations and topics; a topic shows only its upstream flows, with that topic alone at full weight. Clicking the same block again, Escape, or "Show all flows" clears it. Clicking another block replaces the focus.
- `buildSankey(opts.focus)` and the `focusOfNode()` helper are in `funding_viz_model.js`. The organisation top-N cap is computed before the focus is applied, so "Other <sector>" blocks stay stable. Blocks are `role="button"` with `aria-pressed`, and the SVG is `role="group"`. The status line is a live region that is always mounted.
- Verified: the Node runtime and focused pytest checks; a built Framework page clicked in headless Edge (62 blocks fall to 35 on NSF; topic, Enter, Escape and clear all work; axe finds no violations in the viz; no page errors); and the full gate (1,659 passed, 9 expected skips).

## State of the repo
- Concurrent owner edits (`framework/src/**` other than funding_viz*, `tests/test_vd*.py`, `tests/framework_monitoring_runtime.mjs`, `scripts/ux_tasks.py`, `tests/test_ux_tasks_script.py`, `.agent/QUESTIONS.md`) are preserved and left out of this commit.

## Choice made without owner input
- The drill-down is Sankey-local: it does not set the page filter form or narrow the other charts or the award table. The classic page set global filters. The default is recorded here and not in QUESTIONS.md, because QUESTIONS.md has uncommitted owner edits. If the owner wants the global behaviour, map agency, sector and topic clicks to `#grants-agency`, `#grants-sector` and `#grants-tag`; organisation clicks have no form field.

## Next tasks (suggested)
- Unchanged from S2.6: add `fetch_orcid_author_ids.py` to `ingest_works.yml` before normalization; compute expert metrics for repaired authors from corpus authorships.

## Needs owner input
- H25 (VD-12 design review). Optional: confirm Sankey-local vs global drill-down.
