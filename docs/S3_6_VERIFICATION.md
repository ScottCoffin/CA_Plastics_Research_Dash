# S3.6 deployment and performance verification — 2026-11-07

## Deployment

- GitHub Actions run [42334138365](https://github.com/ScottCoffin/CA_Plastics_Research_Dash/actions/runs/42334138365) built and deployed commit `226df545da8b4e26442db830f342a0f41a6a3674`; both the Build Pages artifact and Deploy Pages artifact jobs succeeded.
- `curl.exe --silent --show-error --location --fail --write-out "HTTP=%{http_code} TOTAL=%{time_total}s SIZE=%{size_download}" https://scottcoff.in/CA_Plastics_Research_Dash/` returned HTTP 200, 52,038 bytes, and 0.237 seconds in this verification.
- The live HTML includes the S3.5 disclaimer. The live `data/build_metadata.json` reports the same fixture sentinel and counts as the committed snapshot: 4 authors, 4 works, 3 institutions, 1 CA institution, and 4 labeled works.

## C5 measurements and scope

The only normalized work export available in this checkout is the committed four-work fixture. `data/processed/normalized/` contains `works.parquet` (6,001 bytes), `authors.parquet` (2,857 bytes), `authorships.parquet` (2,519 bytes), and `institutions.parquet` (3,366 bytes). There are no OpenAlex work snapshots under `data/raw/`. The 98,118 figure in the S1.5 audit is a remote count estimate, not downloaded records. These inputs cannot support a full-corpus or representative-scale performance claim.

| C5 budget | Result | Scope |
|---|---:|---|
| Initial payload <3 MB gzip | 3,403 bytes (0.0033 MiB) | Committed fixture metadata; includes all top-level payloads and author details. |
| First Contentful Paint | median 44 ms; max 80 ms | 5 cold page contexts in headless Chromium 145.0.7632.6, WSL localhost fixture. Captured with the browser `PerformancePaintTiming` entry. |
| Meaningful render <2 s | median 75.1 ms; max 124.1 ms | Same 5 contexts; measured from navigation time origin until `#load-status` says `Data loaded` and at least one `.virtual-row` exists. All showed 4 rows. |
| Filter response <150 ms | median 14.2 ms; max 15.9 ms | 20 fixture searches over Alice, Bob, Carol, and Dana; measured from input event dispatch to the next animation frame, when updated row DOM/count were checked. All 20 produced exactly the expected author. |

The C5 time budgets pass on the fixture. The payload target passes for the fixture only. Do not report these values as full-data performance. No performance-driven optimization or DuckDB-Wasm escalation is justified from this fixture; C5's ordered ladder already has pre-aggregation, split index/detail payloads, and row virtualization in place. Filter-in-worker and a build-time text index remain later ladder options if representative measurements show they are needed.

## Production-data availability and decision

No safe representative export is available locally. The daily works workflow uses the configured candidate query and is budget-guarded, but the S1.5 candidate remains deliberately inactive pending owner promotion review. Do not activate it just to manufacture a performance fixture. The 98,118 metadata count is not a license to synthesize rows or a substitute for an export. Once an approved production query is active and an authorized bounded run is made under the existing OpenAlex credit guard, export that corpus and rerun C5. Until then, the full-data performance DoD is unmet.

## Real-data pass (S2.1-B, 2026-11-11)

- Ingest run [43043699471](https://github.com/ScottCoffin/CA_Plastics_Research_Dash/actions/runs/43043699471)
  (manual dispatch, commit `3f173d4`) detected the query-version change (`None -> plastic-v3.1`),
  backfilled 1950-01-01..2027-12-31 in one cursor-paged window per institution batch, fetched
  1,916 works (1,506 unique), normalized, labelled, exported `site/data`, committed it as
  `e954181` and dispatched deploy run 43044301692 (success). Cost: 53 boolean-search pages,
  about 0.05 USD (pre-run count of the same scope: 49 calls, 490 credits).
- Live check: `https://plastiverse.live/data/index.json` returned HTTP 200 (1,400,461 bytes) with
  the CI counts. Named CA researchers present: Win Cowger 37 CA works, Andrew B. Gray 29,
  Scott Coffin 25, Matthew S. Savoca 23, Stephen B. Weisberg 16, Leah M. Thornton Hampton 13,
  Rebecca Sutton 9.
- Curation applied afterwards (this checkpoint): AT-1 owner audit labels (497 rows; 128
  `exclude`, 62 of them in the corpus) and Claude Haiku relevance calls for the 1,081 works the
  owner had not labelled (`curation/work_relevance.csv`, owner_review pending). Export after
  curation: 1,424 works (1,115 plastic-related), 1,982 CA-affiliated experts, 2,141 institutions.

| C5 budget | Result (real data, after curation) |
|---|---:|
| Initial payload <3 MB gzip | 442,037 bytes (all top-level payloads; author detail files load lazily, 4.27 MB total gzip) |
| First Contentful Paint | median 204 ms; max 1,244 ms |
| Meaningful render <2 s | median 807 ms; max 1,765 ms |
| Filter response <150 ms | median 5.5 ms; max 15 ms (10 named-author searches) |

Method: headless Edge (Playwright, `channel=msedge`) against `python -m http.server` on
localhost, five cold contexts; render = navigation start to `Data loaded` plus a virtual row;
filter = input event to the next animation frame. Before this checkpoint, filtering took a
median of 519 ms because every keystroke rebuilt each author's summary by scanning all works
(O(authors x works)). Summaries and id lookups are now built once per payload. No DuckDB-Wasm
escalation is needed. `scripts/check_s3_2.py` now budgets the initial payload only, matching C5.

## Reproduction commands

```powershell
gh run view 42334138365 --json name,headSha,status,conclusion,event,createdAt,updatedAt,url,jobs
curl.exe --silent --show-error --location --fail --write-out "`nHTTP=%{http_code} TOTAL=%{time_total}s SIZE=%{size_download}`n" https://scottcoff.in/CA_Plastics_Research_Dash/ -o $env:TEMP\s36-live.html
curl.exe --silent --show-error --location --fail https://scottcoff.in/CA_Plastics_Research_Dash/data/build_metadata.json
Get-ChildItem data/processed/normalized -File | Select-Object Name,Length
Get-ChildItem data/raw -Recurse -File | Select-Object FullName,Length
py -3.14 scripts/measure_s3_6.py
```

The browser harness starts a temporary localhost server, uses headless
Playwright Chromium, and prints its measurements as JSON. The recorded figures
are from the latest harness run. It measures FCP from
the paint timing entry; meaningful-render time from navigation until fixture
data and an expert row are present; and filter response from synthetic input
event dispatch until the next animation frame and the resulting row/count
check. No external API is contacted.
