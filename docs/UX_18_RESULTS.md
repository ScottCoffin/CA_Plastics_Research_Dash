# UX-18: naive-user task results

Scripted by `scripts/ux_tasks.py` (Python Playwright, Chromium, headless). Each task starts in a
fresh browser context, navigates by visible text, role and label, and records its steps.
Run on 2026-11-12 against a local `framework/dist-i` build served by
`scripts/serve_framework_preview.py --port 8780`. Results: 6 of 6 passed, exit code 0.

| # | Task | Result | Steps | Last element (on failure) | Finding |
|---|------|--------|-------|---------------------------|---------|
| 1 | Overview to a California-led author's profile | Pass | 6 | first expert name | The Overview has no list of CA-led authors. The route that worked was "Find a California researcher", then CA basis "CA-led", then the first expert's name, which opened the profile drawer (Roland Geyer). |
| 2 | Experts: topic and year range, export CSV, row count matches | Pass | 6 | Export filtered CSV | Tag set to the first topic option, years 2015 to 2024: "599 experts shown" and the CSV has 599 data rows and 15 columns. |
| 3 | Institutions: why two institutions share a tier | Pass | 3 | Stanford University | Tier 1 (8 institutions, fractional works 25.8 to 44.0) lists University of California, Davis and Stanford University. The page says same-tier institutions "cannot be reliably ordered, because their bootstrap rank ranges overlap". |
| 4 | Monitoring: one matrix, download the CSV | Pass | 4 | Download observations (CSV) | Matrix "atmospheric deposition (dry, passive sampler)" gives 4 CSV data rows, all mentioning that matrix. The download button sits inside the collapsed "Sample observations" section, so the script had to open it first. |
| 5 | Funding: California-led awards, NIH amount basis | Pass | 4 | NIH RePORTER subtotal row | With "Led from California" = Yes and Funder agency = NIH, the per-source table gives the basis as "award_amount, reported as the fiscal-year total cost. Not verified as life-of-award." (reported $62,144,920). The basis is not shown on the award rows, only in a tooltip (title attribute). |
| 6 | From index.html, reach /app/ | Pass | 2 | A newer version of this atlas is available. | The only route to /app/ is a banner link on index.html, which is visible. |

## Rerun

```bash
cd framework && ATLAS_FW_OUT=dist-i npm run build
cd .. && py -3.14 scripts/serve_framework_preview.py --port 8780 --dist dist-i &
py -3.14 scripts/ux_tasks.py --base http://127.0.0.1:8780/CA_Plastics_Research_Dash/ --out scratch/ux18 [--headed]
```

Output: `scratch/ux18/<task>.png` per task, `scratch/ux18/experts.csv` and
`scratch/ux18/monitoring.csv` (downloads), and `scratch/ux18/results.json`. The script exits 1 if
any task fails. Stop the server afterwards and delete `framework/dist-i`.

## Limits

- The 20 s per-task limit is checked between steps and applies to each Playwright action. A single
  action that hangs is cut off only by that action timeout.
- Tasks check the page as built. Filters and counts depend on the snapshot in the build.
- Pytest covers only the script's structure (`tests/test_ux_tasks_script.py`). No browser runs in
  pytest, so these results come from the manual run above.
