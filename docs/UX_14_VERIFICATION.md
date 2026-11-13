# UX-14 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-14 (drop the duplicate "Labeled works" tile unless defined; refresh
time as "12 Nov 2026, 17:09 UTC" with the ISO value in `<time datetime>`; a "Start here" row).

## Changes
- `framework/src/components/atlas.js`: `formatRefresh()` gives "12 Nov 2026, 17:09 UTC";
  `aboutViewModel` returns `refreshDisplay` and `refreshIso`. "Labeled works" is shown only when it
  differs from Works (today both are 1,909, because every published work carries a label row), with
  a definition when it is shown.
- `framework/src/index.md` and `about.md`: "Last refresh: <time datetime=ISO>12 Nov 2026, 17:09
  UTC</time>"; example (fixture) data keeps its existing message.
- `framework/src/index.md` + `style.css`: "Start here" row with three task links: Find a
  California researcher (Experts), See who is funded for plastics research (Funding), Check plastic
  monitoring data (Monitoring).
- Test: `tests/test_ux14_overview.py` (node runtime checks of the view model; page markup).

## TODO-OWNER
- The Start here link wording was drafted by the agent; replace it if you prefer other copy.
