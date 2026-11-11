# EM-16 verification: link-out registry and weekly HTTP status check (registry part)

Scope: Add-on A2 §8 registry and checker only. The Related Resources UI tab is not built (depends on EM-5).

## Files
- `config/linkouts.yml`: 12 entries LO-1..LO-12, reuse_mode `link_only`, no Minderoo entry.
- `src/atlas/linkouts.py`: load and validate, injectable `check_links(urls, transport)`, `timeline_source_urls`, `run_live`.
- `scripts/check_linkouts.py`: offline validation by default; `--live` runs the status check.
- `.github/workflows/source_watch_s7_6.yml`: `check_linkouts.py --live` step after the CEDEN step; `docs/api_notes/linkouts_check.json` added to the `git add --` allowlist; `pyyaml` added to the CI pip install (already pinned in `requirements/lock.txt`).
- `tests/test_linkouts_em16.py`: validation failures, fake transport (HEAD, 405/403/501 GET fallback, redirect reported, network error), local-server check of the real transport, timeline URLs, YAML unchanged by `run_live`, workflow assertions.
- `docs/api_notes/linkouts_check.json`: baseline from the one authorized live run.

## Live run (2026-11-11 02:58 UTC, one run, about 17 public requests)
| ID | Status | Method | Notes |
|---|---|---|---|
| LO-1 | 403 | GET | HEAD refused, GET refused |
| LO-2 to LO-9 | 200 | HEAD | |
| LO-10, LO-11, LO-12 | 403 | GET | all dtsc.ca.gov URLs, including the timeline URLs, return 403 |

- LO-9: root kept as stated with `url_status: to_confirm`; the root returns 200.
- LO-12: live check failed (403), so per the brief `root_url` is set to null and `url_status` is `unavailable`. The JSON keeps the observed record for the old URL. The next weekly run records LO-12 as unchecked.
- The 403 responses are not confirmed broken links. DTSC likely blocks this client, and LO-1 may do the same. This needs owner review.

## Checks run
- `py -3.14 -m ruff check src scripts tests`: all checks passed.
- `py -3.14 -m ruff format --check src scripts tests`: 247 files already formatted.
- `py -3.14 -m pytest -q tests/test_linkouts_em16.py tests/test_ceden_watch_s7_8.py`: 38 passed.
- `py -3.14 scripts/check_linkouts.py`: OK, 12 registry entries, 3 timeline source URLs.
- `py -3.14 scripts/check_doc_links.py`: 113 Markdown files OK.
- `py -3.14 scripts/check_a2_scaffold.py`: passed.
- `git diff --check` on the edited YAML and workflow: clean.

## Limitations
- Evidence URLs in the registry are not live-checked; only root URLs and timeline `source_url` values are.
- `last_checked` is null in the YAML by design and is recorded only in the JSON.
- `trigger_rules` is set to `["weekly HTTP status check only"]` for every entry, which is my reading of the spec.

## Lead review (2026-11-11)

- Every dtsc.ca.gov URL (LO-10, LO-11, LO-12 and the three timeline sources) returned
  HTTP 403 to the automated check, even with the GET fallback. This is access refused to
  an automated client, not evidence that the pages are gone. LO-12 therefore keeps its
  candidate URL `https://dtsc.ca.gov/scp/priority-product-work-plan/` with
  `url_status: to_confirm`. Confirm it in a browser.
- Each result now carries an `outcome`: `ok` (2xx), `redirect` (3xx), `restricted`
  (401/403/429) or `broken` (other statuses and request errors). The live summary counts
  outcomes. The baseline `docs/api_notes/linkouts_check.json` predates the field; the
  next weekly run rewrites it.
