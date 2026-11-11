# AT-1 query audit status

## Offline implementation

`src/atlas/ingest/institutions.py::plastic_work_counts` keeps the production
default on the existing broad `search=plastic` ranking and legacy cache. The
Appendix A query is available only through explicit `query_mode="audit"`, with
caller-supplied version and query path plus a separate audit cache path. Its
filter is fully percent-encoded. An audit cache is reused only when its version,
complete query text, integer counts, and requested institution IDs match.
Legacy, malformed, partial, and mismatched audit caches are refetched. The v2
path does not import the untracked `atlas.query_v2` scaffold module and cannot be
activated by the normal registry build.

Institution registry rows, owner-reviewed classification fields, and the
existing review queue are outside the ranking cache and are not modified by this
partial checkpoint. This does not promote the query to an owner-approved
production candidate. No production cache is read or written by audit mode.

## Precision audit

Status: **filter accepted; all 20 strata collected with 405/500 target rows**.
The complete available sample and baseline counts are in
`docs/QUERY_AUDIT_REVIEW.csv` and `docs/QUERY_AUDIT_COUNTS.json`. Human-labelled
evidence remains **0/500 works**.

The required audit is 25 works from each of the top 20 institutions, labelled
relevant/not relevant by the owner or colleagues. No labels, precision estimate,
noise-term findings, or query revision are available yet. The 2026-11-07
regression baselines in `docs/add_on_spec.md` are documented expectations only;
the runner records actual counts and drift without changing those expectations
or forcing a pass.

### 2026-11-09 run evidence

The single preflight attempt returned HTTP 200 from `/rate-limit`, but omitted a
valid `X-RateLimit-Credits-Used` header. The sanitized usage record marks both
credits and cost as unknown; no amount is claimed as spent or free. The runner
stopped immediately and made no query or sample requests. It wrote no review
CSV or count summary. Do not retry by guessing endpoint accounting behavior;
resume only after the provider returns valid request accounting metadata or the
owner provides an accepted status preflight method.

### 2026-11-09 snapshot-adapter attempt

After approval of the separate status-snapshot adapter, one additional
`/rate-limit` request returned HTTP 200. The response lacked the required
`resets_in_seconds_at_capture` field, so the sanitized balance snapshot is
empty and the runner stopped before any metered query. The separate usage row
records the HTTP status and unknown cost/credits; it does not overwrite the
earlier failed request record. No balance amount, baseline, filter acceptance,
or sample is claimed from this attempt. No further request was made.

### 2026-11-09 reviewed-adapter run

The fresh authenticated status snapshot returned HTTP 200 at 17:54 UTC:
daily budget USD 1.00, USD 0.972 remaining and USD 0.028 used; 10,000-credit
limit, 9,720 remaining and 280 used; prepaid and one-time balances were zero;
reset time was 2026-11-10 00:00 UTC. The snapshot was logged as a separate
balance observation, not as metered request cost.

The encoded global filter and three named institution count calls (UCSF, SLAC,
UC Davis) succeeded, but the runner did not checkpoint their returned count
values. Six top-20 strata returned 25 works each. At rank 7, Lawrence Livermore
National Laboratory (`I1282311441`), the request returned 4/25 works and the
runner stopped without retrying or changing the query. In total, 11 metered
requests used 110 credits and USD 0.011 accounted cost. The 154 returned sample
rows were transient in memory; no partial CSV or count summary was written.
That run's returned rows and baseline values were not persisted. No labels were
created and no production ranking was changed.

### 2026-11-09 durable resumed collection

The progress cache was absent, so missing counts and strata were recollected
under a fresh status snapshot at **18:04:43 UTC**: USD 0.961 remaining and 9,610
credits remaining, with zero prepaid/one-time balance. The prior run's transient
response rows were not fabricated or reused. The global filter and all three
named baseline requests returned valid counts; each is within 10% of its
expected v2 baseline.

| Scope | Expected v2 | Current | Drift |
| --- | ---: | ---: | ---: |
| Global | 98,118 | 98,328 | +0.21% |
| UCSF | 25 | 25 | 0.00% |
| SLAC | 2 | 2 | 0.00% |
| UC Davis | 129 | 130 | +0.78% |

All 20 selected strata were collected. The CSV has 405 rows and 354 unique work
IDs; 51 rows are repeated work IDs across institution strata, explicitly
flagged in the CSV. Eight strata had fewer than 25 matching works, leaving a
95-row shortfall:

| Institution | Available rows | Shortfall |
| --- | ---: | ---: |
| California Institute of Technology | 21 | 4 |
| California Polytechnic State University | 22 | 3 |
| Cedars-Sinai Medical Center | 5 | 20 |
| Jet Propulsion Laboratory | 10 | 15 |
| Lawrence Livermore National Laboratory | 4 | 21 |
| SLAC National Accelerator Laboratory | 2 | 23 |
| Stanford Medicine | 19 | 6 |
| University of California System | 22 | 3 |

The run did not refill from other institutions or duplicate rows to reach 500.
All 405 review labels remain blank.

The run made 25 requests including its fresh status snapshot. The 24 metered
requests used 240 credits and USD 0.024 accounted cost. No post-run balance was
queried. No candidate activation or registry build occurred.

### Owner decision — 2026-11-09

Scott Coffin decided to **keep the top-20 sample at 405 rows and 354 unique
works**, leave the 500-work acceptance gate open, and make no supplements, new
institution selections, or query changes. Human labels remain **0**. The eight
short strata and the 95-row gap are recorded above; the owner decision does not
promote the query or close the precision audit.

## Bounded collection runner

`scripts/run_at1_audit.py --offline-plan` shows the plan without network access.
Live use requires `--live --confirm-free-only`, an API key from the process
environment or `.env` aliases, the owner confirmation artifact, a successful
authenticated `/rate-limit` preflight showing zero prepaid and one-time balance,
and valid request-credit headers. Each request reserves against the configured
daily guard plus a USD 0.10 / 1,000-credit run cap; the runner makes no retries
and stops on unknown accounting, HTTP errors, or inadequate free headroom. The
maximum is 80 requests; the planned run is 25 (status, four baselines, twenty
sample pages). Raw API response bodies are not saved.

The top 20 strata come from the existing institution review-queue rank and are
verified against only the selected OpenAlex ID/name columns in the registry.
The CSV output contains stable OpenAlex work IDs, DOI URLs, titles, publication
dates, concise reconstructed abstract excerpts, query text/version, stratum,
duplicate-across-strata flags, and blank review fields. OpenAlex scholarly
metadata is CC0. The sample is for manual owner/colleague review; it does not
label or promote any work automatically. On every response, an ignored
`data/interim/at1_query_v2_audit_progress.json` cache and the commit-ready CSV
and JSON summaries under `docs/` are atomically updated. Valid cached baseline
calls and completed strata are skipped when resuming.

## Remaining AT-1 acceptance inputs

- Owner/colleague labels for the 405 available rows; no labels or precision
  estimate have been made.
- Owner decision on how to address the 95-row shortfall across eight strata
  before claiming the 500-work audit acceptance target.
- One documented noise-term revision and a repeated labelled audit after the
  owner has reviewed the sample.
- Owner review of audit findings and query promotion decision before the S2.1
  backfill.

## AT-1 partial audit checkpoint

AT-1 remains unchecked. Query-v2 is isolated behind explicit audit mode with version/query/cache identity checks and path-alias rejection; legacy production ranking/cache remain default. The audit runner is bounded, resumes only matching progress, persists partial outputs, validates its free-only status preflight before metered calls, and records the 2026-11-09 review sample in `docs/QUERY_AUDIT.md`, `docs/QUERY_AUDIT_COUNTS.json`, and `docs/QUERY_AUDIT_REVIEW.csv`.

All 20 top-20 strata are present: 405 rows, 354 unique works, 51 cross-stratum duplicate rows, eight short strata and 95 rows below the 500 target. Baselines 98,328 / 25 / 2 / 130 are within 10% of 98,118 / 25 / 2 / 129. The run used 24 metered requests, 240 credits and USD 0.024 accounted cost, plus one status snapshot. Labels remain blank; candidate promotion remains pending.

Scott Coffin decided on 2026-11-09 to keep the 405-row sample, leave the 500-work gate open, and make no supplements, new institution selections, or query changes. AT-1's human labeling, precision/noise-term review, repeat audit, and promotion decision remain outstanding.

Offline verification with network sockets blocked and both API-key environment aliases unset: full suite 222 passed; scoped Ruff and format checks passed. No API or live check was run during verification.

### Next
- Continue at S7.1, the next independent unchecked roadmap task. AT-2 and AT-11 remain dependency-blocked by AT-1; do not promote `plastic-v2-candidate`.

## Labelling the sample (owner)

Run the local review app from the repository root:

```bash
py -3.14 -m streamlit run scripts/review_query_audit_app.py
```

It opens in the browser at http://localhost:8501. Enter your initials in the sidebar,
then label each work Relevant, Not relevant or Unsure; optional noise terms record the
word that pulled in an off-topic work. Each click saves to `docs/QUERY_AUDIT_REVIEW.csv`.
One label covers all rows of the same `work_id` (354 works across 405 rows). The
default "Unlabeled" view moves to the next unlabelled work; "Show: All" revisits
earlier labels. Label helpers: `atlas.query_audit_review`.

## Results of the owner audit (2026-11-10)

Scott Coffin labelled all 354 works (405 rows) on 2026-11-10: 293 relevant and 61 not
relevant. The owner had approved this 354-work sample as the audit set, so the AT-1
"≥ 500 labelled works" target is closed at 354 by owner decision.

- Precision of `plastic-v2-candidate`: 293/354 = **82.8%** (Wilson 95% CI 78.5-86.3%).
- By stratum, precision is 100% at Stanford, UC San Diego, UC Riverside, UC Santa Cruz
  and Scripps, and 96% at UC Davis. It is low at Caltech (6/21), Lawrence Livermore
  (0/4) and JPL (7/10).
- Noise groups: materials-science "plasticity" (microplasticity, strain-gradient
  plasticity, ductile fracture, elastic-plastic contacts); "microfiber" in engineering
  and medicine (gecko adhesives, vascular grafts, scaffolds); microfabrication ("micro
  plastic embossing", "microplastic lens"); and passing mentions in air-pollution,
  exposome and policy abstracts. Recorded noise terms: microfiber (3), microplasticity,
  plasticity, elastic-plastic.
- Duplicates and non-research items: 5 near-duplicate pairs (preprint/article, chapter/
  "other", one book in two years) and 21 items typed editorial (8), dataset (4), other
  (3), erratum (3), peer-review (2) and letter (1).

## Query v3 candidate (`config/queries_v3.yml`, not yet active)

OpenAlex stems search terms. `microplasticity` therefore matches `microplastic`: as an
exclusion it removed 49 of Win Cowger's 60 matched works. `plastic` also matches
`plasticity`, so neither term may be used as an exclusion or as a context word.
Exclusions were tested one at a time on the labelled set and kept only if they removed
no relevant work.

| Change | Detail |
|---|---|
| Core terms added | macroplastic, mesoplastic, "plastics pollution", "plastic pollutants", "plastic trash", "plastic contamination", "anthropogenic litter", "anthropogenic debris", "anthropogenic microparticle(s)", "ingested plastic(s)", "eat plastic", "consuming plastic" |
| Qualified terms | microfiber only with textile, laundry, washing, shedding, wastewater or microplastic context; new litter (trash, cleanup, roadside, beach, stormwater) and trash (litter, stormwater, beach, creek, ocean, debris) |
| Exclusions added | crystal plasticity, strain gradient plasticity, ductile fracture, elastic-plastic, plastic embossing, gecko, dislocation, nanopillar, plastic deformation (each removed only not-relevant works; polycrystalline, "particulate matter" and PM2.5 were rejected because each removed relevant works) |
| Types excluded | erratum, peer-review, retraction, paratext (`type:!<slug>` filters; editorials and datasets are kept because the owner labelled them relevant) |
| Always included | works whose raw affiliation names the Moore Institute for Plastic Pollution Research or Algalita (owner: all Moore Institute publications). OpenAlex has no institution record for the Institute and leaves 43 of its authorships without any institution, so these works bypass both the terms and the California institution filter. |

Pairs dropped after measuring their stand-alone contribution (works matched beyond v2,
globally): litter + anthropogenic (2,372), litter + plastic (2,027), trash + plastic
(1,838), trash + river (1,195, mostly trash racks), microfiber + environment (722),
trash + capture (720), and a `plastics` qualifier that stemmed to "plastic".

Evaluation (2026-11-10; free-plan, cost-logged calls):

| Measure | v2 | v3 |
|---|---:|---:|
| Labelled works matched | 354 | 329 |
| Precision on the labelled set | 82.8% | 89.1% (0 relevant works lost) |
| Win Cowger works matched | 60 | 67 |
| Scott Coffin | 33 | 35 |
| Andrew B. Gray (two author records) | 33 | 37 |
| Matthew S. Savoca | 22 | 27 |
| Moore Institute affiliation works (49) | 40 | 44 by terms; 49 with the always-include rule |
| Global matching works | 98,424 | 145,818 (102,333 before the LCA/recycling scope addition) |

The named authors' remaining misses fall outside the audit's scope (toxicology and
water reuse, wildfire sediment, whale ecology) or are records without abstracts
(software versions, datasets). Works with no California-registry institution still
fall outside the institution filter. For the Moore Institute the always-include rule
covers this; other cases need registry additions.

### Scope addition: plastics LCA, recycling and alternatives (owner, 2026-11-11)

The owner confirmed that plastics-focused LCA papers are in scope. v3 now also matches
plastic(s) recycling, recycled plastic(s), single-use plastic(s), bioplastic(s),
biodegradable plastic(s), "circular economy of plastics"; "plastic packaging" with waste,
food, recycling or sustainability context (to skip electronics packaging); and life cycle
assessment, chemical recycling, mechanical recycling and upcycling, each only with a
plastic or polymer name. Stand-alone contributions beyond v3 were bioplastic(s) 11,272,
LCA 7,659, plastic packaging (unqualified) 5,444, upcycling 4,133, chemical recycling
3,355 and biodegradable plastics 3,505. "Plastic products" (4,512) and "plastic
production" (1,242) were measured, found to be mostly manufacturing and unrelated
noise, and left out. The labelled-set precision and the named-author recall are
unchanged by this addition.

## Repeat audit (owner action)

`py -3.14 scripts/run_at1_repeat_sample.py` drew 143 works that v3 adds over v2
(10 per stratum, seed 20261110, type exclusions applied) into
`docs/QUERY_AUDIT_REVIEW_V3.csv`. Label them with:

```powershell
py -3.14 -m streamlit run scripts/review_query_audit_app.py -- --csv docs/QUERY_AUDIT_REVIEW_V3.csv
```

The precision of these additions decides whether v3 replaces v2 (QUESTIONS S1.5-A).
Near-duplicate collapsing (preprint versus article, repeated chapters) belongs in S2.2
normalization and is tracked in TODO under AT-1.
