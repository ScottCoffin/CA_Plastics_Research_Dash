# S4.2 sampling and split preparation

## Implemented contract

`atlas.nlp.sampling.build_split_rows` makes a reproducible pool sample using a
fixed seed and the S4.2 dimensions: five-year publication band, OpenAlex work
type (the available journal/publication-type field), matrix, OA status, and
institution type. It takes a deterministic round-robin across observed joint
strata. Missing dimensions remain `unknown`; matrix is assigned only from
explicit metadata or transparent title/abstract terms. No rule/model labels,
topic predictions, or annotation fields are read.

Within the selected pool, works connected by any shared OpenAlex author ID are
kept in the same train/dev/test split (70/15/15 target). Leak-test candidates
are drawn separately from rows with no CA-affiliated author and a
`gazetteer_hit` supplied by a separately versioned hit pass. Those records are
marked `sample_role=leak_test` and `split=test`; they are never selected into
the development pool. If a leak-test candidate shares an author with a pool
work, the connected pool work is also forced into test to prevent author-group
overlap with development. The builder does not produce predictions, labels, or
annotation suggestions. F3 continues to prohibit test-set threshold tuning
and development error analysis.

`scripts/build_gold_sample.py` reads the normalized C3 works, authorships, and
institutions Parquet tables. Supply `--gazetteer-hits <csv>` to include the
leak-test stratum; the CSV must contain a `work_id` column and its provenance
must be recorded separately before interpreting a zero leak count. The output
is a split CSV plus a deterministic source-hash manifest (`splits_v1` by default;
`splits_v2` for the real corpus, see below). `--leak-candidates <parquet>` adds minimal
leak-test records (`ca_any_author=false`, `gazetteer_hit=true`) for works named in the hit CSV.

## Real-corpus sample (splits_v2, snapshot_status `v3.1_corpus`)

Generated 2026-11-11 from the v3.1 corpus (`plastic-v3.1`, 1,486 normalized works, 1,456 with a
CA-affiliated author) and the leak hit list below. Label-independent: no rule or model labels
were read, nothing was annotated.

### Leak candidates (`scripts/fetch_leak_candidates.py`)

One budget-guarded, cursor-paged OpenAlex pull: `openalex_filter(plastic-v3.1)` AND
`title_and_abstract.search:(California OR "San Francisco Bay" OR "Monterey Bay" OR "Santa
Monica Bay" OR "Southern California Bight" OR "Sacramento River" OR "San Joaquin" OR "Lake
Tahoe" OR "Los Angeles" OR "San Diego" OR "Channel Islands" OR "Salton Sea")` AND the
`exclude_types` filters. A `per-page=1` probe logged `meta.count = 790` (limit 6,000), then 8
pages of 100 (90 credits per run; two runs on 2026-11-11, the first superseded after the hit
rules below were tightened, 180 credits in total). Cursor paging returned 791 rows for 789
unique works.

| Stage | Works |
|---|---|
| OpenAlex `meta.count` | 790 |
| Unique works fetched | 789 |
| After dropping works with any authorship institution in the CA registry (4,614 institutions) | 602 |
| After the S1.4 gazetteer pass on title + abstract (>=1 hit) | 259 |
| Sampled as leak_test | 80 |

Gazetteer pass: capitalised 1-4 word windows of title + abstract are looked up with
`atlas.geo.gazetteer.lookup`, so the ambiguity blacklist applies. Hits are filtered for
information: state/country features (`A.ADM1`, `A.PCLI`) are ignored because the search terms
imply them; spot/building, vegetation and road classes (S, V, R) are ignored as mostly
ordinary words; a single-word match counts only for a populated place of at least 50,000
people (Berkeley, Davis, Oakland); a window inside a longer matched window is dropped. The
first, looser pass hit 543 of 602 works almost entirely on "California" (a mine feature),
"University" and "Pacific", which is why it was tightened. Matched names are recorded per work
in `curation/leak_gazetteer_hits_v1.csv` (`work_id, matched_names, query_version,
fetched_at_utc`). Most common matches: Los Angeles 47, San Diego 34, Southern California 26,
San Francisco Bay 24, Berkeley 17. Residual noise exists (for example "Reading", "Mason",
"Harper", "Ontario", "Rhode Island" resolve to small CA places or are names); these remain
leak candidates by the S4.2 definition (a gazetteer hit is the test condition), and the
reviewer judges them at annotation time. The raw pull is the ignored
`data/interim/leak_candidates.parquet` (all 602 non-CA works with text, author IDs and hit
names). `--rescan-raw` re-runs only the gazetteer pass without an API call.

### Sample and splits

`python scripts/build_gold_sample.py --gazetteer-hits curation/leak_gazetteer_hits_v1.csv
--leak-candidates data/interim/leak_candidates.parquet --sample-size 500 --leak-test-size 80
--snapshot-status v3.1_corpus --out curation/splits_v2.csv` (seed 42042) writes
`curation/splits_v2.csv` (580 rows) and `curation/splits_v2_manifest.json`.

| Role | train | dev | test | total |
|---|---|---|---|---|
| pool | 350 | 75 | 75 | 500 |
| leak_test | 0 | 0 | 80 | 80 |
| all | 350 | 75 | 155 | 580 |

The pool shares 267 author groups; no author group spans splits (overlap 0), and no leak work
shares a group with a pool work. Pool strata (round-robin across observed joint strata, so
small strata are over-represented relative to the corpus by design):

| Dimension | Pool counts |
|---|---|
| Year band | 2025-29: 143, 2020-24: 217, 2015-19: 74, 2010-14: 26, 2005-09: 11, 2000-04: 7, 1995-99: 9, 1990-94: 5, earlier: 8 |
| Type | article 322, review 44, preprint 25, conference-paper 23, book-chapter 22, editorial 17, conference-abstract 14, dataset 7, other 26 |
| OA status | closed 158, green 103, hybrid 86, gold 85, bronze 40, diamond 28 |
| Matrix (title/abstract terms) | unknown 202, marine 92, food 38, soil 32, freshwater 19, air 18, wastewater 10, mixed 89 |
| Institution type | combined values (48 distinct); `uc+other` 123, `uc` 76, `other+private` 50, `nonprofit/ngo+other` 39, `private` 29, remainder smaller |

Full counts per dimension are in the manifest (`stratum_counts`). Leak sample: 80 works,
2020-24: 25, 2015-19: 15, 2025-29: 14, 2010-14: 10, older: 15, unknown year: 1; articles 51,
dissertations 7, other types 22; closed 41, green 14, gold 8.

### Method changes to `atlas.nlp.sampling` (needed for the real corpus)

- Splits are assigned by a size-aware greedy over author components (largest first, each to
  the split furthest below its target share). The earlier count-of-groups rule put one
  163-work author component into test (test = 42% of the pool). Two-group inputs (the v1
  fixture) are unchanged.
- Leak candidates that share an author with a selected pool work are ranked last, because a
  shared author forces the whole connected pool component into test. They are still used if
  too few other candidates exist (existing behaviour and test preserved).

### Limits

- The pool is a stratified sample of the CA-affiliated corpus, not a random sample; it is
  weighted toward rare strata and is not a prevalence estimate.
- Matrix is inferred from transparent title/abstract keywords; 202 of 500 pool works are
  `unknown`. The institution stratum uses the combined atlas types of every affiliation.
- The leak pool is limited to works matching the plastic-v3.1 query and 12 place terms
  (790 works). Leak works whose text names a CA place only in the full text, or via a place
  outside the 12 terms, are not sampled.
- The leak parquet is ignored; a clean checkout verifies `splits_v2` against manifest hashes
  and the committed hit CSV, not by rebuild. The test set (75 pool + 80 leak) is frozen once
  committed; use dev for tuning and error analysis. `guide_v1` approval and annotation remain
  separate owner steps.

## Fixture evidence (splits_v1, superseded for representativeness)

`splits_v1` was generated from the four-work `s2_2_openalex_works.json` fixture (two pool
works, no hit list, manifest `fixture_only`). It checks reproducibility and holdout plumbing
only and is kept unchanged. The normalized Parquet files now hold the v3.1 corpus, so the v1
fixture rebuild cannot run locally; `check_s4_2.py` then verifies v1 against its manifest
hashes and structure instead.

## Verification

- `py -3.14 scripts/check_s4_2.py`: v1 manifest/structure (rebuild when the fixture inputs are
  local); v2 structure (pool 400-600, every leak row in test, no author group across splits,
  stratum and split counts equal the manifest, CSV and hit-CSV hashes), plus a full
  deterministic rebuild of `splits_v2.csv` when the ignored inputs are present and hash-match.
- `py -3.14 -m pytest -q tests/test_s4_2_v2.py tests/test_sampling.py
  tests/test_build_gold_sample.py`: 14 passed.
- `py -3.14 -m ruff check` and `ruff format --check` pass for `scripts src tests`.
