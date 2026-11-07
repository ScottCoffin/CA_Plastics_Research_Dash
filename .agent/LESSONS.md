# Lessons (newest first; append-only)

## 2026-11-06 -- S3.4 institution view
- Reuse the S3.1 slim index for institution metrics: filter to
  `plastic_related === true`, derive the latest-five-year window from the
  dataset's latest year, and retain institutions without coordinates in the
  leaderboard rather than silently dropping them.
- A dependency-free grid clusterer is enough for the static MVP. Keep map
  markers keyboard-accessible and route their institution IDs through the
  existing Experts URL-hash state so the drawer/filter behavior stays shared.

## 2026-11-06 -- S3.5 About freshness
- Read refresh time and displayed counts from `build_metadata.json`, not the
  index row counts. Treat the `fixture` sentinel as example data and use an
  explicit unavailable state for absent metadata; the committed fixture is not
  a live refresh.
- For browser regression, cover the About view and the Institutions-to-Experts
  path through the existing hash filter and researcher drawer. Missing
  `/favicon.ico` requests were harmless in this smoke.

## 2026-11-06 - Slim static-site exports
- Keep index rows limited to filter/list fields and load abstracts and other
  detail on author click. A separate metadata file with raw and gzip sizes
  makes the C5 payload budget auditable without browser tooling.
- Build aggregates from the same slim work rows used by the index, and keep
  missing S2.3 labels as null rather than silently reclassifying works.

## 2026-11-06 - Guarded daily works refresh
- A daily-budget HTTP 429 is an expected scheduling outcome, not a reason to
  advance state or fail the whole workflow. Raise a typed rate-limit error,
  preserve the inclusive high-water boundary, and let the next run retry.
- Keep the write guard exact (`ENABLE_DATA_COMMITS == "true"`) and force-add
  only the named generated outputs; raw snapshots and API logs remain ignored.

## 2026-11-06 - Provisional work-label joins and rule ordering
- Join normalized work IDs back to raw OpenAlex records for topic display
  names; retain every normalized work when raw or topic rows are missing and
  reconcile both counts in the QC report.
- Apply exclusions before inclusions, require configured context for qualified
  terms, and keep tier-2 chemicals distinct from core. A nullable confidence
  field avoids implying calibrated probabilities for candidate rules.
- The Trendspotter reuse entry is MIT-licensed, but S2.3 uses an independent
  local facet implementation and copies no external code.

## 2026-11-06 - C3 normalization and California flags
- Keep the owner-reviewed institution registry immutable during works
  normalization. Emit a separate normalized institution table and retain raw
  unresolved links so missing coverage is measurable rather than silently
  dropped.
- `ca_led` is a resolved-registry test on the first authorship, while
  `ca_any_author` is true when any authorship has a resolved California
  institution. Affiliation text is useful for an unresolved-CA QC warning but
  is not sufficient evidence for either flag.
- `make qc` can use the committed four-work S2.2 fixture when the ignored live
  raw table is absent, keeping the acceptance path reproducible without API
  calls.

## 2026-11-06 - Resumable OpenAlex works ingestion
- OpenAlex publication-date windows are accepted for the works endpoint, while
  `from_updated_date` returned HTTP 429 Plan upgrade required on the available
  free access level. Use inclusive publication-date rereads by default and
  deduplicate by stable OpenAlex work ID.
- A cursor must be followed separately for every <=100-institution batch and
  year window. Write raw snapshots and the merged Parquet output before
  advancing the high-water mark so an interrupted run can safely repeat its
  boundary.

## 2026-11-06 - Versioned OpenAlex query audit
- OpenAlex accepts the candidate Boolean expression through a fully encoded
  `filter=title_and_abstract.search:` value; the 2026-11-06 run returned
  98,118 works with exclusions and 100,335 without them. Trust response cost
  metadata and headers: six bounded requests used 60 credits and USD 0.0060.
- A generic `microfiber` can still be a biomedical false positive when paired
  with a configured context such as `synthetic`; title/abstract screening is
  therefore useful before owner promotion, but it is not a replacement for a
  later gold set.
- OpenAlex's works identifier filter is `openalex_id`, not `id`; use the
  server's valid-field list when extending recall spot checks.

## 2026-11-05 - GeoNames normalization and local lookup
- GeoNames country dumps are UTF-8, tab-delimited 19-field records; for U.S.
  records the California administrative code is `CA`. Filter both
  `country_code=US` and `admin1_code=CA`, rather than using a loose bounding
  box that can include neighboring-state names.
- Different GeoNames alternate spellings can normalize to the same text. Keep
  one deterministic display spelling per `(geonames_id, normalized_name)` to
  preserve the unique SQLite index and make Windows rebuilds atomic only after
  explicitly closing the SQLite connection.
- Exact matching alone is not safe for common words. Keep the explicit,
  documented blacklist ahead of both source and curated-alias lookup; region
  centroids are gate candidates, not evidence that a study sampled there.

## 2026-11-05 - Land masks and CDFW polygon packaging
- A legal state-boundary polygon is not a land-only mask: the tested Census
  state feature included offshore jurisdiction and swallowed the intended
  `state_waters` result. Use a coastline-following land polygon and test the
  land/water/none precedence with known offshore points.
- CDFW ds3158's hosted ArcGIS feature layer is a line. The official ZIP ships
  `ds3158.gdb` (line) and `ds3158_alt.gdb` with the analysis-ready
  `ds3158_poly` multipolygon. Do not construct a replacement polygon from the
  line when the distributed polygon is available.
- Full-resolution polygon GeoJSON was unnecessarily large because of dense
  coordinates. GeoParquet preserves the geometry compactly; reserve simplified
  GeoJSON for the browser.

## 2026-11-05 - Broad plastic search is not a pollution corpus
- The top-100 institution mix included many hospitals, neuroscience and
  immunology institutes, physics and astronomy units, and technology companies.
  The owner's inference is that literal OpenAlex `search=plastic` is matching
  plasticity, plastic surgery, and plastic deformation; underlying works were
  not checked during this review.
- Keep those counts only as S1.2 review-priority metadata. Before any public
  leaderboard uses them, S1.5 must tighten the versioned query or restrict it
  with validated OpenAlex topics and measure the result.

## 2026-11-05 - Institution coverage and resumable review
- An exact OpenAlex `geo.region:California` seed is necessary but not a
  sufficient coverage assertion. Compare against explicit official UC/CSU
  lists and supplement missing required records by bounded institution search.
- The shared anonymous OpenAlex budget can be exhausted by other users on the
  network. Validate the local key before a production pull; the builder accepts
  both `OPENALEX_API_KEY` and the owner's local `OPEN_ALEX_API_KEY` alias.
- Use the checksum-verified ROR dump for bulk joining. Resume interrupted
  Zenodo downloads with HTTP ranges rather than restarting a large transfer.
- A generated human-review CSV is state, not disposable output. Preserve owner
  columns by stable OpenAlex ID on rebuild and keep S1.2 unchecked until all
  100 rows contain both an owner type and review date.

## 2026-11-05 — OpenAlex and ROR live contracts
- OpenAlex's exact institution-region value is `California`, not `CA`.
  `institutions.id` and `authorships.institutions.id` matched the same works,
  but the shorter documented spelling is canonical for new code.
- OpenAlex rejects a 101-value institution OR filter even when its URL is far
  below the separate 8,190-byte GET limit; keep ID batches at 100 or fewer.
- Anonymous OpenAlex calls can initialize a cursor but need an API key to
  follow it. Basic paging is sufficient only for bounded result sets under the
  10,000-result ceiling.
- ROR v2 schema 2.1 uses `country_code=US` and
  `country_subdivision_code=CA`; do not expect the combined code `US-CA`.
- ROR emits no billing credits. Log its request count with zero cost so a run's
  cross-source accounting remains complete.

## 2026-11-05 — GitHub Pages live acceptance
- Changing the repository to public removed the plan restriction, but Pages
  still had to be created explicitly with `build_type=workflow` before the
  deployment could pass `configure-pages`.
- The Pages API reports the account custom-domain URL
  `https://scottcoff.in/CA_Plastics_Research_Dash/`; verify that URL's status
  and expected page content, not only the Actions conclusion.
- Manual run `42092058401` built and deployed the site successfully.

## 2026-11-05 — GitHub Actions and Pages scaffold
- GitHub Pages creation returned HTTP 422 because the current plan does not
  support Pages for this private repository. Resolving that requires an owner
  decision under G-7: change visibility after the license decision, upgrade the
  plan, or choose alternate hosting.
- GitHub documents the 60-day scheduled-workflow inactivity disablement for
  public repositories. Scheduled workflows run only from the default branch and
  may be delayed or dropped, so S0.2 uses off-peak minutes plus a watchdog.
- The Job_Scraper reference is AGPL-3.0 while this repository's license remains
  pending. Reuse its documented concepts, not its workflow code.
- Validate workflow syntax locally with `actionlint`; live execution still
  requires the files to be present on the default branch.

## 2026-11-05 — Bootstrap environment
- GNU Make is not on PATH, but Rtools provides
  `C:\rtools45\usr\bin\make.exe`; direct Python equivalents also work.
- Do not rely on an ambient `PYTHONPATH` in acceptance checks. Pytest now gets
  `src` from `pyproject.toml`, so a clean `make test` imports the package.
- `gh` 2.89.0 is installed, so S0.2 can inspect and trigger GitHub Actions after
  repository authentication and permissions are confirmed.

## 2026-11-06 -- S3.3 browser acceptance
- The WSL Playwright wrapper is reliable with an explicit named session and
  `--json`; use Node 20.20.2 plus the installed Chromium browser. A local WSL
  HTTP server is required for fetch-based static payloads.
- Keep deliberate screenshots under ignored `output/playwright/`; do not add
  Playwright session captures or CLI logs to the repository.

## 2026-11-06 -- Continuous roadmap orchestration
- A fresh chat is not the safety boundary; the atomic checkpoint is. Keep each
  task's acceptance, documentation, commit, and push isolated even when one
  Goal-mode run continues across several tasks.
- `.agent/` is the task-level source of truth. Keep `agent_docs/` concise and
  synchronized so Medium or Heavy intake does not replay stale milestones.
