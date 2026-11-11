# Reproducibility package (S10.3)

This document covers three things: rebuilding the offline outputs from committed
fixtures (`make reproduce`), the documented live rebuild that needs network access
and API keys, and the release process that archives a versioned snapshot on Zenodo.
Commands are for Git Bash on Windows and use `py -3.14`.

## 1. Fixture rebuild from scratch (offline)

```bash
/c/rtools45/usr/bin/make.exe PYTHON="py -3.14" APPDATA="$APPDATA" USERPROFILE="$USERPROFILE" reproduce
# or directly
py -3.14 scripts/rebuild_from_fixtures.py
```

`scripts/rebuild_from_fixtures.py` runs the existing library builders on committed
inputs only: `tests/fixtures/s2_2_openalex_works.json`, `tests/fixtures/s8_1_grants.json`,
the committed institution registry `data/processed/institutions.parquet`, and the
`config/` query, taxonomy, and author-override files. Every output goes to a temporary
directory. Nothing is written to `site/`, `data/`, `curation/`, or `docs/`.

The script builds the outputs twice in two fresh temporary directories. It exits
non-zero unless every file is byte-identical between the runs. It then prints a
manifest of path, bytes, and SHA-256 for each file.

| Stage | Covered by the fixture rebuild | Inputs |
|---|---|---|
| S2.2 OpenAlex normalization (works, authors, authorships, institutions, QC) | Yes | works fixture (synthetic, 4 works) |
| S2.3 provisional labels | Yes | normalized fixture plus `config/queries.yml`, `config/taxonomy.yml` |
| S3.1 site payloads (`index.json`, `authors/`, `institutions.*`, `aggregates.json`, `build_metadata.json`) | Yes | normalized fixture and labels |
| S8.1 grant normalization, S8.6 de-duplication | Yes | grants fixture (synthetic, 8 records) |
| S8.10 `grants.json` export | Yes | de-duplicated fixture grants |
| S11.4 Atom feed (`feed.xml`) | Yes | exported `index.json` and `grants.json` |

The fixture rebuild does not cover the following, and it does not claim that they
reproduce:

- **Live ingestion** (OpenAlex, NIH RePORTER, NSF, USAspending, CA Sea Grant, state
  funders, FAAST): these call external APIs or sites and need keys or polite crawling.
  The fixture stands in for their output only.
- **Real corpus outputs**: the fixtures are synthetic or small. The committed
  `site/data/*.json` reflect the live data at the time of their last build, not the
  fixtures.
- **Monitoring** (`build_monitoring_export.py`): needs the local normalized SF Bay
  sample table (`samples.json`), which is not in the repository.
- **Open calls, status page, dataset and grant links, institution and geography
  builders, gazetteer, and RWQCB regions**: each needs live inputs, a local
  workbook or database, or the live history log. They are excluded from the fixture
  rebuild.
- **Byte-identity with the committed site**: the fixture outputs are a separate
  build and are not compared with `site/`.

## 2. Full live rebuild (documented, not run by CI)

Run the steps in this order. Each step writes ignored local outputs under `data/`.
Run only the steps you need. Read the linked notes before any live call.

| Order | Command | Network and keys | Cost and limits |
|---|---|---|---|
| 1 | `py -3.14 scripts/build_institutions.py` | Reads the local registry and override files. Only `--refresh-openalex` and `--refresh-counts` make live calls. | The default run is offline. Live refreshes are budgeted. See `config/budget.yml`. |
| 2 | `py -3.14 scripts/ingest_openalex.py --start-year YYYY --end-year YYYY --allow-candidate` | Live. Requires `OPENALEX_API_KEY` in the environment, which is never stored in the repository. | Budgeted. See `config/budget.yml` and `docs/api_notes/openalex_costs.md`. Paid spend requires explicit owner approval. |
| 3 | `py -3.14 scripts/normalize_openalex.py` | Offline. Reads `data/interim/works_raw.parquet` and writes `data/processed/normalized/`. | None. Without live raw data, falls back to the committed S2.2 fixture. |
| 4 | `py -3.14 scripts/label_works.py` | Offline. | None. |
| 5 | `py -3.14 scripts/build_export_site.py` | Offline. Writes `site/data/` directly. | None. Run it only as a deliberate publication step, not as a check. |
| 6 | `py -3.14 scripts/ingest_nih_reporter.py`, `ingest_nsf_awards.py`, `ingest_usaspending.py`, `ingest_ca_sea_grant.py`, `ingest_state_funders.py`, `ingest_faast.py` | Live public sources. NIH RePORTER, NSF, and USAspending are keyless. Crawlers are rate-limited and check robots.txt. | Source notes are in `docs/api_notes/`. Most sources take `--max-requests` to cap requests. See each script's help text. |
| 7 | `py -3.14 scripts/dedupe_grants.py` | Offline. Reads `data/interim/grants/`. | None. |
| 8 | `py -3.14 scripts/build_grants_export.py` | Offline. Writes `site/data/grants.json`. | None. |
| 9 | `py -3.14 scripts/build_feed.py` | Offline. Reads `site/data/index.json` and `grants.json`. Writes `site/feed.xml`. | None. |
| 10 | `py -3.14 scripts/build_status_page.py` | May read GitHub Actions run history, using `GITHUB_TOKEN` when it is set. | Read-only. No paid spend. |
| 11 | `py -3.14 scripts/build_release_snapshot.py --version YYYY.MM.DD` | Offline. Writes `dist/atlas-snapshot-<version>.zip`. | None. |

Validation after a live rebuild: `py -3.14 -m pytest -q`, the full gate in `CLAUDE.md`,
and `py -3.14 scripts/check_s10_3.py`. The fixture rebuild (`make reproduce`) must still
pass, because it is the offline reference for the code.

## 3. Release snapshot contents

`scripts/build_release_snapshot.py` writes `dist/atlas-snapshot-<version>.zip`. The
`dist/` path is ignored by `.gitignore`. The ZIP contains:

- `site/data/*.json` (top-level payloads) and `site/feed.xml`: public, derived data
  under CC BY 4.0.
- `curation/gold_*.csv` and `curation/splits_v1*.{csv,json}`: gold set and split files,
  CC BY 4.0.
- `config/queries.yml` and `config/taxonomy.yml`: query and taxonomy definitions, MIT.
- `MANIFEST.json`: each file's path, bytes, SHA-256, and licence, plus the source commit.
- `README.txt`: the citation and licence summary.

The builder refuses to package anything under `data/raw`, `data/interim`, or
`data/logs`, any `.env` file, and any JSON key or CSV header whose name starts with
`abstract`. It fails rather than dropping data.

Two checks of the current outputs (2026-11-10):

- No public payload contains an abstract field. `site/data/grants.json` has no
  abstract key, and the slim `index.json` carries no abstract text.
- `site/data/authors/*.json` is not packaged. These files hold full work rows, including
  abstracts, so they are outside the release set.

Snapshot licence status: confirmed by the owner on 2026-11-10. Code is MIT (`LICENSE`)
and derived data are CC BY 4.0 (`LICENSE-DATA.md`); the manifest records this.

## 4. Release to Zenodo

Zenodo archives each GitHub release of this repository once the repository is
enabled in Zenodo. Zenodo mints a DOI for each archived release. A DOI cannot be
deleted, so tags and releases are made only after the owner confirms the steps below.

Metadata is in `.zenodo.json` (`upload_type` `software`, licence `MIT`,
`isSupplementTo` https://plastiverse.live/). Zenodo reads this file for the record.

### Owner steps (one time, then per release)

a. Sign in at https://zenodo.org with GitHub.
b. In Zenodo, open Account, then GitHub. Toggle `ScottCoffin/CA_Plastics_Research_Dash` on.
c. Tell the agent that the repository is enabled, and confirm the release to make.
   The agent then does the following:
   1. Confirms the licence decision recorded in `LICENSE`, `.zenodo.json`, and the
      snapshot manifest, and resolves any mismatch first.
   2. Runs `make reproduce`, the full gate, and `py -3.14 scripts/check_s10_3.py`.
   3. Runs `py -3.14 scripts/build_release_snapshot.py --version YYYY.MM.DD`.
   4. Creates the tag `vYYYY.MM.DD` and a GitHub release with the snapshot ZIP attached.
      Zenodo archives the release and mints the DOI.
d. Add the DOI badge to `README.md` once Zenodo reports the DOI. The badge uses the
   concept DOI or the version DOI that the Zenodo record shows:

   ```markdown
   [![DOI](https://zenodo.org/badge/DOI/<doi-of-the-record>.svg)](https://doi.org/<doi-of-the-record>)
   ```

Until the release is made, no DOI exists and `README.txt` shows "DOI: assigned by
Zenodo on deposit".

### Before the first release (open items)

- `LICENSE` is a placeholder. The MIT code licence and CC BY 4.0 data licence in
  `.zenodo.json` and in the manifest need owner confirmation. The Zenodo licence
  identifier `MIT` may need to match Zenodo's own vocabulary. Check the record during
  the first deposit.
- The release notes should say which upstream sources are included, following
  `docs/REUSE.md`.

## Archived releases

| Release | Zenodo DOI | Notes |
|---|---|---|
| v2026.11.11 | [10.5281/zenodo.24124017](https://doi.org/10.5281/zenodo.24124017) (concept [10.5281/zenodo.24124016](https://doi.org/10.5281/zenodo.24124016)) | First Zenodo-archived snapshot (source commit f76de3b) |
| v2026.11.10 | none | Published before the Zenodo link was active; GitHub release only |
