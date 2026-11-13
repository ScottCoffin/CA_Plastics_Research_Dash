# Lessons (newest first; append-only)

## 2026-11-12 -- Framework header links and template
- Observable Framework 1.13.4 rewrites header/footer hrefs that leave the app root (`../`) to `./`, silently pointing at the current page; it also hardcodes `<html>` without lang and `maximum-scale=1`. Check rendered hrefs in `dist/`, not the config, and fix in `framework/scripts/postbuild.mjs`.
- Text-extraction walkthroughs of a site misread hrefs (`expert.html#author=` came out as `expert.html=`) and loading states; confirm such findings in a real browser before changing code.

## 2026-11-12 -- Emails in committed tables; eScholarship rate limit
- The site export redacted emails, but the committed normalized tables (authorships raw_affiliation, works abstract) carried 808 + 4 OpenAlex strings with emails. Redact at the point where any committed table is written, not only at the public export; grep committed Parquet for `@domain.tld` after schema changes.
- eScholarship blocks the HTML site and OAI (bot screen) and blocked the GraphQL API too after ~120 requests at 2 s spacing; use OpenAlex (which indexes eScholarship) to find items, and fetch single items slowly from cache-first scripts. A worker kept paging after a stop message: kill background processes yourself rather than relying on a message.

## 2026-11-11 -- Mis-attached OpenAlex abstracts and stale site files
- OpenAlex served one teaser-style micro-nano plastics abstract (two snippets joined by "...") as the abstract of 10 unrelated PNAS papers (1962-2023, no real abstract; Europe PMC has none either). Verbatim-shared abstracts are also legitimate (preprint versions and `/supp-N` files, book chapters, report series), so flag only when >= 3 works share it with >= 3 distinct DOI roots and >= 3 distinct title families (`atlas.ingest.abstract_qc`); normalization blanks them.
- `export_site` never deleted author files of authors who left the export: 171 stale `site/data/authors/*.json` stayed reachable. Any per-entity output folder must prune files it did not write.

## 2026-11-11 -- AT-3 analytics
- DuckDB parallel float SUM varies in the last bit between runs; set `SET threads = 1` (or round before ranking) wherever reproducible ranks or seeded bootstrap outputs are tested. DuckDB 1.1.1 has no Python 3.14 wheel, so the pipeline uses 2.0.0. When regenerating `requirements/lock.txt`, `uv pip compile --extra ml` drags in torch/CUDA; the existing lock pins the ml extra by hand, so insert single pins instead of recompiling.

## 2026-11-09 -- S7.5 monitoring publication and runtime
- Keep registry catalogue output separate from observations: unknown contributors remain unknown, and an empty public sample view is not a data-gap claim. Private previews must resolve outside the public site tree, including aliases. The focused browser-logic regression runs through pytest and requires Node.js 20+ on PATH; install/version pinning belongs with S10 environment hardening.

## 2026-11-09 -- S7.3 monitoring source rights and QC
- Keep current package-level license metadata, resource-level license fields,
  historical source notes, and fetch outcomes distinct. A public listing or
  successful local read does not resolve reuse rights. Until clarified, keep
  raw/normalized data local and ignored; commit aggregate QC and conflict
  categories only, while retaining row-level diagnostics solely in ignored QC.

## 2026-11-07 -- S6.3 PDF extraction evidence
- Report GROBID transport/technical failures separately from successful processing that found no target sections. In the 30-PDF convenience sample, GROBID had zero technical failures but 21 no-target results; pdfminer recovered six and 15 remained empty, mostly reviews/editorials. Heading and excerpt text checks do not establish visual PDF accuracy or candidate-corpus performance.

## 2026-11-07 -- S6.2 JATS entity handling
- Reject internal DTD subsets with XML-aware parsing; token scanning can be fooled by comment text resembling CDATA delimiters. Preserve external DOCTYPE declarations without resolving them, and test both the parser and cache persistence boundary.

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

## Parallel workers must not run full pytest sessions at the same time
Concurrent pytest processes share the `pytest-of-<user>` basetemp root; one
session's old-directory cleanup can remove another's live `tmp_path`, producing
a one-off failure (seen in `tests/test_fulltext_cache.py` during EM-1, not
reproducible in 5 solo runs). Let workers run focused tests; the lead runs the
full gate once after they finish.

## Do not pipe gate commands through `tail` when chaining with `&&`
`cmd | tail -1 && git commit` takes the exit status of `tail`, so a failing
check still commits (it happened with check_doc_links during SPK-1). Redirect
to a file and test the command's own status, or use `set -o pipefail`.

## Local gates miss CI-only failures; check CI after pushing
CI ran red from e410e03 onward (a link to an ignored screenshot, and a fixture
`.gitkeep` hidden by the `release/` ignore rule) while every local gate passed,
because the ignored files exist locally. Before sealing, run the checks in a
clean `git worktree add --detach <tmp> HEAD`, and confirm the CI run after pushing.

## `build/` in .gitignore hid src/atlas/build from git add and from ruff
An unanchored `build/` matched `src/atlas/build/`, so new modules there were
silently untracked and ruff skipped the directory (11 hidden E501s). Fixed by
anchoring to `/build/`. Never run `scripts/build_export_site.py` as a check:
it rewrites public `site/data/` from the current processed data. Use
`scripts/check_s3_1.py`.

## Wall-clock dates in tests and watch scripts
`test_open_calls_s8_9` broke on 2026-11-10 because the script used the real date
and a fixture deadline passed; scripts that filter by date take `--today`, and
tests pin it. `scripts/check_source_watch_s7_6.py` is the live watch, not an
offline check: it rewrites `docs/SOURCES.md` and the watch JSON. Run only the
pytest file offline. A watch digest must exclude headers servers generate per
request (opc.ca.gov sends `Last-Modified` equal to `Date`).

## Playwright route globs do not cross `/` in query strings
`ctx.route("https://x/page.html*")` missed `page.html?base=https://...`, so the
real (522) origin was fetched and the probe hung for 10 minutes. Match with a
predicate (`lambda url: url.split("?")[0] == prefix`) and use short timeouts
while debugging.

## OpenAlex search stemming breaks exclusions
Adding `microplasticity` to the query's NOT list cut Win Cowger's matched works from
60 to 11, because OpenAlex stems it onto `microplastic`. The `plastic` stem also hits
`plasticity`, which is why "litter AND plastic" pulled in leaf-litter phenotypic
plasticity papers. Measure each exclusion and context pair alone (labelled set plus
a stand-alone global count) before adding it.

## Scratch scripts must not shadow stdlib modules
`scratch/at1/bisect.py` and `types.py` broke `random` and `enum` imports
(circular-import errors). Name scratch scripts after their purpose, never after a
stdlib module.

## Clean-worktree pytest can be very slow on this machine
On 2026-11-11 the clean `git worktree` test run took 1 h 35 min (779 passed), against
about 90 s in the main checkout. The suspect is real-time antivirus scanning freshly
written files. Run that step in the background with a long timeout, and do not push
until it reports.

## Scratch API scripts bypass the budget guard
- 2026-11-11: audit attribution scripts called `_request_json` directly (~700 calls at 10
  credits) and pushed the UTC day to $0.69, past the owner's $0.25 local stop; the guarded
  backfill then refused to run. Estimate credits first (boolean searches cost 10), and
  route exploratory calls through `ingest_live`-style budget checks or a `--max-credits`
  counter.

## Tracked CI state lives under ignored-looking paths
- `data/interim/works_raw.parquet` and the high-water JSON are force-added by CI. Never
  move them locally; copy instead (`git status` shows them as deleted).


## 2026-11-11: verify a live pipeline by its output, not its exit code
- The S2.1 "backfill from 1950" passed tests and CI but would have fetched only 1950 and replaced the table with it (end year defaulted to the start year), and per-year windows multiplied 10-credit calls 77-fold. Before relying on a range pull, count it cheaply (`per_page=1` per batch) and assert the requested window in a test.
- Three overnight sessions reported "all ungated work done" while the Experts tab still served the 4-work fixture. Every downstream stage (S3.6 measurement, S4.2 representative sample, S5 classifiers trained on that gold set) was blocked on that one fault. When several stages are blocked on the same missing input, fix that input first and say so in the handoff; do not treat the stages as separately gated.
- Owner labels in a review CSV are inert until a build step reads them. After any owner labelling round, wire the labels into curation and check the public payload.

## 2026-11-11: shell heredocs corrupt regex escapes here
- Python patches sent through Git Bash heredocs turned `\b` into a backspace (0x08) twice, silently breaking regexes. Write patch scripts with the Write tool, or use lookarounds; scan with `grep -rlP "\x08" --include=*.py`.
- A share metric must use the same population in numerator and denominator: corpus-only plastics citations over career citations put Rochman at 42% (true 98.7%).

## 2026-11-11: frozen artifacts must tolerate corpus growth; refresh only stale enrichments
- A frozen split's check asserted the live corpus hash, so growing the corpus "failed" S4.2. Check frozen files against their manifest; rebuild only when inputs are unchanged.
- An enrichment pass that refreshes every author costs ~1,200 credits/run; gate refreshes by age/version (30 days) so a routine run costs ~40.
- Derived committed files (AT-2 institution types) must be regenerated wherever the corpus is regenerated (ingest workflow), or the next push fails their freshness test.

## 2026-11-11: owner-reviewed files must be write-protected from rebuilds
- A registry rebuild re-ranked the top 100 and rewrote `institution_review_top100.csv`, silently dropping 100 owner reviews on 2026-11-06; checks then passed against the blank file for days. Any generator that writes a file carrying owner annotations must refuse to overwrite reviewed rows; checks should assert the reviewed count (S1.2 now reports 100/100).

## 2026-11-12 AT-5 Framework ports
- Haiku workers porting a whole classic tab (300-600 lines) hit the 30-turn limit every time; one "continue, be economical" message finished each. Budget a resume per large port, or split by file.
- Observable Framework: a top-level `const view` in a page shadows the builtin `view()` and breaks interpolation (`Cannot read properties of undefined`). Framework's default head links Google Fonts; set `globalStylesheets: []`.
- The Bash safety parser rejects heredocs containing `${...}` in some shells ("could not be checked for dangerous rm"); write such files with the Write tool or a Python generator.
- Headless Edge `--dump-dom --virtual-time-budget` is a reliable Windows browser smoke when the WSL Playwright browser is missing; one render in ~6 can stop early, so rerun before calling a page broken.
- Never chain `git push` after the clean-worktree pytest with `;`: a failing worktree run (EM-6 tests needing gitignored `release/`) still pushed. Gate the push on the pytest exit code. Tests must not depend on gitignored folders (`release/`, `data/`); skip when absent.

## 2026-11-12 UX remediation batch
- Python `Path.write_text` on Windows turns every `\n` into `\r\n`; text read with `read_text`
  already carries `\r\n` from the autocrlf checkout, so a round trip writes `\r\r\n` and git stores
  CRs in LF files. Edit repo files as bytes (strip `\r`, write `\n`) or with `newline=""`; check
  `git show HEAD:<file> | grep -c $'\r'` after scripted edits.
- `cmd && tail -1 log && git commit` commits even when the command failed, because `tail` exits 0.
  Capture the exit code (`cmd > log; rc=$?`) and gate the commit on it.
- Haiku workers sometimes park on a background preview server ("waiting on background work") and
  never report; one short "stop waiting and report" message ends it. Killing processes can be
  denied to a worker: do not relay that kill; leave it for the owner.
- Worker-written public copy tends to cite repo paths ("docs/...", "src/...") and "TODO-OWNER" on the
  page; `check_public_text.py` now rejects TODO-OWNER and "pending owner review", but read new
  public pages before sealing.
