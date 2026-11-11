# CA Plastics Research Atlas

A public, auto-updating atlas of California plastic-related researchers,
monitoring data, and research funding. The project is in bootstrap development;
`spec.md` is the product and implementation specification.

https://plastiverse.live/ (formerly https://scottcoff.in/CA_Plastics_Research_Dash/, which redirects)

## Labelling the query audit sample (AT-1)

A local Streamlit app steps through the 354 works in `docs/QUERY_AUDIT_REVIEW.csv`
so they can be labelled for the search-query precision audit. It needs Streamlit
(`py -3.14 -m pip install streamlit` if it is missing). From the repository root:

```powershell
py -3.14 -m streamlit run scripts/review_query_audit_app.py
```

The app opens at http://localhost:8501. Enter your initials in the sidebar, then mark
each work **Relevant**, **Not relevant** or **Unsure**. A noise term (the word that
pulled in an off-topic work, such as "plasticity") is optional. Every click saves to
`docs/QUERY_AUDIT_REVIEW.csv`, so you can stop and resume at any time. A label covers
every row of the same work. The default view shows only unlabelled works; choose
**Show: All** to revisit earlier labels. **Back to last reviewed** reopens the work you just labelled.

For the v3 repeat audit, open the second file instead:

```powershell
py -3.14 -m streamlit run scripts/review_query_audit_app.py -- --csv docs/QUERY_AUDIT_REVIEW_V3.csv
```

Details: `docs/QUERY_AUDIT.md`.

## Development

Requires Python 3.11 or newer.

```powershell
make setup
make test
make lint
make build
```

If GNU Make is unavailable, run the equivalent commands directly:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src
```

The daily works refresh is also runnable locally with
`py -3.14 scripts/run_daily_works.py --start-year YYYY --allow-candidate`.
HTTP 429 and configured budget stops defer cleanly; GitHub Actions commits
generated outputs only when `ENABLE_DATA_COMMITS=true`.

Agents must follow `spec.md` Part B and start with `.agent/README.md`.

## License

Code: MIT (`LICENSE`). Derived data: CC BY 4.0 (`LICENSE-DATA.md`). Third-party
sources keep their own terms; see `docs/REUSE.md`. Cite with `CITATION.cff`.
