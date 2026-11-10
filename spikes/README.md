# Spikes

`spikes/` holds isolated experiments that answer a single technical question
for the Add-on A1 roadmap. Spike code is not shipped site code: nothing under
`spikes/` is imported by `src/`, built into `site/`, or run by CI, and it is
excluded from the product test suite.

Each spike lives in its own folder, `spikes/<spk_id>_<topic>/`, and has:

- a runnable entry point (`run_spike.py`) that reproduces the measurement;
- its results written to `docs/SPK_<n>_<TOPIC>.md`, which records the decision;
- generated artifacts (data, raw JSON) written only under `scratch/`, which is gitignored.

Spikes may use network access and extra tooling only when the owner has
authorized it for that spike. Their dependencies are pinned per run (for
example through `uv run --no-project --with <pkg>==<ver>`) and are never added
to `pyproject.toml`.

Current spikes:

- `spk2_parquet/`: Parquet writer versus DuckDB-Wasm read compatibility (gate G-PARQ).
  Run with `py -3.14 spikes/spk2_parquet/run_spike.py` from the repo root.
