# BQ-1.5: anchor overlap of the v3.1 query with independent routes

Live run 2026-11-23 (UTC). Output: `docs/api_notes/bq1_5_anchor_overlap.json`. Script:
`scripts/bq1_5_anchor_overlap.py`. Tests: `tests/test_bq1_5_anchor_overlap.py`.

## What was measured

For each anchor set, OpenAlex was asked which anchors the active query (plastic-v3.1, title and
abstract search, the v3.1 type exclusions, no California scope) returns when the request is
filtered to those anchors by OpenAlex ID or DOI. The share of anchors returned is an **anchor
overlap**, with a Wilson 95% interval.

This is a probe. It does not estimate how many relevant works the query finds. The anchor sets are
not random samples of any population, so the sets are reported separately and never pooled.

## Which sets were used, and why each is or is not independent of the query

| # | Set | Route into the Atlas | Independent of the v3.1 search? | Outcome |
|---|---|---|---|---|
| 1 | ORCID and ROR DOI routes | DOI-only fetch, search switched off (`scripts/ingest_orcid_dois.py`, `with_query=False`) | **Route: yes.** Selection: no. Each record had to pass a local rule built from the same v3.1 terms (`passes_query`, `classify_plastic_text`) before merge, so every anchor matches that vocabulary. | Probed, consistency check rather than independent coverage |
| 2 | eScholarship (`escholarship-ingest`) | OpenAlex snapshots filtered by location AND the v3.1 search AND type exclusions (`scripts/audit_escholarship_openalex.py`) | **No.** The route applied the query. | Skipped (19 records; 12 published and plastic-related, not probed) |
| 3 | Europe PMC (`europepmc-audit`) | DOI lookups with the v3.1 search on (`build_doi_url` defaults to `with_query=True`, `src/atlas/ingest/europepmc_audit.py`) | **No.** The route applied the query. | Skipped (10 records; 4 published and plastic-related, not probed) |
| 4 | DataCite positives (S7.4) | DataCite metadata search, then agent review | **Route: yes.** But the five positives are DataCite *Dataset* records, not articles, and none has an Atlas work ID. | Probed, reported beside the article sets |
| 5 | PubMed R1 in the Atlas (BQ-S9) | PubMed MeSH set `"Microplastics"[MeSH Terms] AND California[ad]`, restricted to published Atlas works | **Relevance: yes** (MeSH indexing). **Membership: no.** 160 of 163 entered the Atlas through the v3.1 query route. | Probed, consistency check only |
| 6 | `tests/fixtures/s1_5_known_relevant.json` | Four works chosen from the literature | **Yes.** Outside list, not an Atlas route. | Probed, n = 4 |
| 7 | plastiverse.live overview page | The Atlas's own published output | **No.** It is built from the corpus the query populates. | Skipped |

Route classes come from `source_run_id` families through `atlas.analytics.denominators`
(`route_family`, `QUERY_ROUTES`). The Moore always-include unit inside the `openalex-works` route also
skipped the search, but stored fields cannot separate it from query matches
(`docs/DENOMINATOR_SERIES.md`). So that whole route is treated as applying the query.

### Relevance behind set 1

Every ORCID and ROR record had to pass a local term gate before it was merged, and that gate uses the
v3.1 core, qualified and exclusion terms plus the tier-2 chemical terms. Relevance then follows the
export precedence: an owner decision, else an assisted label in `curation/work_relevance.csv`, else
the rule label. Of the 144 anchors:

- 49 were judged plastic-related by the assisted model, and 1 by the owner. Of the 128 rows that
  carry an assisted label, 126 were written by the Haiku assist and 127 still await owner review;
- 78 were judged not plastic-related by the assisted model at low confidence, but are kept because
  the chemical-term rule matched (the tier-2 policy in the relevance rules);
- 16 rest on the rule alone.

Because every anchor passed the same term gate, set 1 tests scope and consistency more than
independent coverage. See the caveats.

## Results

Credits: 11 calls, 92 credits in total (9 search probes at 10 credits, 2 lookups at 1 credit).
The cap was 150.

| Set | Anchors (n) | Returned by v3.1 | Share | Wilson 95% | Credits |
|---|---:|---:|---:|---|---:|
| 1. ORCID and ROR DOI routes (published, plastic-related) | 144 | 51 | 35.4% | 28.1% to 43.5% | 30 |
| 4. DataCite positives (resolved in OpenAlex; 5 DOIs given) | 2 | 1 | 50.0% | 9.5% to 90.6% | 11 |
| 5. PubMed R1 in the Atlas (published) | 163 | 163 | 100.0% | 97.7% to 100.0% | 40 |
| 6. Fixture s1_5 | 4 | 4 | 100.0% | 51.0% to 100.0% | 11 |

Subsets (descriptive only; the same probe, split by a label):

| Set 1 split | n | Returned | Share | Wilson 95% |
|---|---:|---:|---:|---|
| Tier `core` | 51 | 51 | 100.0% | 93.0% to 100.0% |
| Tier `chemicals-in-plastics` | 93 | 0 | 0.0% | 0.0% to 4.0% |
| Judged true by assisted model or owner | 50 | 35 | 70.0% | 56.3% to 80.9% |
| Kept by chemical rule after low-confidence model false | 78 | 0 | 0.0% | 0.0% to 4.7% |
| Rule only | 16 | 16 | 100.0% | 80.6% to 100.0% |

| Set 5 split | n | Returned | Share | Wilson 95% |
|---|---:|---:|---:|---|
| Entered the Atlas via the v3.1 query route | 160 | 160 | 100.0% | 97.7% to 100.0% |
| Not via the query route | 3 | 3 | 100.0% | 43.9% to 100.0% |

Notes on individual sets:

- **Set 4.** Only 2 of the 5 DOIs resolve in OpenAlex: `10.5281/zenodo.18038856` and
  `10.5281/zenodo.18500697`. The other three (`10.17882/72119`, `10.5281/zenodo.18038857`,
  `10.5281/zenodo.18500698`) are not in OpenAlex, so they are listed as unresolved and not counted.
  The one miss is `W7128525232`, "Fields of plastic: Tracking the growing footprint of agricultural
  plastics using remote sensing in California" (dataset).
- **Set 6.** All four works are returned. The titles all contain "microplastic(s)" and were
  picked from the literature, so this set says little about coverage.

## Misses and reasons

Set 1 has 93 misses. All 93 carry the rule label `chemicals-in-plastics`, meaning the local rule
matched a tier-2 chemical term and no v3.1 core term in title or abstract. v3.1 does not search
those chemical terms, so these are scope misses, not retrieval failures.

- 53 of the 93 titles name the chemical in the title. Examples: `W1602352289` "Vaginal douching and
  racial/ethnic disparities in phthalates exposures among reproductive-aged women …"; `W1927679233`
  "Phthalate concentrations in house dust in relation to autism spectrum disorder …".
- The other 40 titles name no tier-2 chemical. The reason comes from the abstract that the rule
  saw, which the title-level check cannot show. Example: `W1635896198` "Identification of California
  Condor Estrogen Receptors 1 and 2 and Their Activation by Endocrine Disrupting Chemicals".
- The per-miss reason for every miss is in the JSON (`sets[0].misses`).

Set 4 has one miss: `W7128525232`, whose title has "plastics" but no v3.1 phrase. The abstract was
not checked.

Sets 5 and 6 have no misses.

## Caveats

1. The anchor sets are not random samples. They are the works that each route happened to reach,
   or an outside list someone chose.
2. An overlap says whether the v3.1 search returns each anchor when filtered to that anchor. It does
   not say whether the search would find every relevant work in OpenAlex.
3. Set 1 was selected with the same term list that the query uses. Its 51 of 51 core-tier
   retrievals are therefore mostly agreement between the OpenAlex search and the local rule on
   those works, not an independent check of coverage. The 0 of 93 chemical-tier result reflects a
   scope choice in v3.1, not a retrieval gap.
4. Set 5 is conditioned on Atlas membership, and 160 of its 163 members came through the query.
   Its 100% is therefore close to a consistency check.
5. Set 4 records are datasets, and only 2 of 5 resolve in OpenAlex. Set 6 has four works. Their
   intervals are very wide, and they cannot support a rate.
6. Titles were used for the miss reasons. Those reasons are hints; the abstract and the index were
   not checked for each miss.

## Not probed, and why

- eScholarship candidates and Europe PMC candidates: their routes applied the query (rows 2 and 3
  above).
- plastiverse.live overview: the Atlas's own output (row 7).
- PubMed R1 records not in the Atlas (15 misses in BQ-S9): the brief restricts set 5 to Atlas works,
  and their OpenAlex IDs were not mapped. Mapping them needs an extra lookup.
- The Europe PMC benchmark cache (`data/raw/europepmc`) is an outside list. It was not probed here,
  because the brief defines the Europe PMC route by the Atlas route, which applied the query.

A more independent probe would use outside lists that were not filtered by the query: the R1 PubMed
records outside the Atlas, or the Europe PMC benchmark probed by DOI with no search. Either needs a
decision on extra credits and on the scope of a follow-up.

## Reproduce

    py -3.14 scripts/bq1_5_anchor_overlap.py            # live: reuses cached calls, fetches the rest
    py -3.14 scripts/bq1_5_anchor_overlap.py --offline  # rebuilds the JSON from data/interim/bq1_5_anchor_overlap/
    py -3.14 -m pytest -q tests/test_bq1_5_anchor_overlap.py

The query fingerprint in the JSON is the SHA-256 of the rendered v3.1 filter and its type filters.
Cached responses are in `data/interim/bq1_5_anchor_overlap/` (gitignored).
