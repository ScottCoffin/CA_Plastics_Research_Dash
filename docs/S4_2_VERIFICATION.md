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
is `curation/splits_v1.csv` plus a deterministic source-hash manifest.

## Current evidence and limits

The committed `splits_v1` artifacts were generated from the existing normalized
four-work `s2_2_openalex_works.json` fixture. Only two fixture works have a
resolved CA-affiliated author and enter the pool; the other two are not leak
test cases because no versioned gazetteer-hit list exists. The manifest
identifies this as `fixture_only`; it records two pool IDs, zero leak-test IDs,
and the exact input hashes. With only two author groups, the fixture is split
between train and test; it cannot support a dev set. This checks reproducibility
and holdout plumbing only. It is not a
representative gold-set sample and does not meet the planned ~400–600 works or
provide the required leak-test sample. No real-corpus split is frozen.

The production pool is unavailable because the local normalized Parquet files
derive from the fixture. The owner-supplied `plastic-v2-candidate` query is
still inactive pending S1.5-A, and the 98,118 S1.5 count is an estimate rather
than downloaded works. Do not promote the query, fetch a paid export, or claim
corpus representativeness as part of S4.2 without the existing owner authority
and budget. Also, `guide_v1` remains pending approval: this preparation is
label-independent and does not authorize annotation or guide freeze.

## Verification

- `py -3.14 scripts/check_s4_2.py`: deterministic rebuild, strata, split and
  author-group non-overlap, leak sample isolation, fixture provenance/status.
- `py -3.14 -m pytest tests/test_sampling.py`: focused deterministic sampler
  tests; together with `tests/test_build_gold_sample.py`, all 7 focused tests
  pass, including rejection of a gazetteer-hit CSV without a `work_id` header.
- The persisted manifest records pool=2, leak-test=0, train=1, dev=0, test=1,
  author-group isolation, the three normalized source SHA-256 values, and the
  split CSV SHA-256. The zero leak count reflects a missing versioned hit list,
  not an observed absence of leak candidates.
- `py -3.14 -m ruff check` and `py -3.14 -m ruff format --check` pass for the
  sampler, CLI, acceptance check, and both focused test files.
- `C:\rtools45\usr\bin\make.exe PYTHON="py -3.14" test`: full suite, 56 passed.
- `git diff --check` passes.

S4.2 remains partial until an authorized representative export is available,
the specified pool and leak-test counts are sampled, and the resulting
production split IDs are frozen and isolated.
