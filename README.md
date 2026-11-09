# CA Plastics Research Atlas

A public, auto-updating atlas of California plastic-related researchers,
monitoring data, and research funding. The project is in bootstrap development;
`spec.md` is the product and implementation specification.

https://scottcoff.in/CA_Plastics_Research_Dash/
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

The owner must confirm the code and derived-data licenses. See `LICENSE` and
question G-7 in `.agent/QUESTIONS.md`.
