# Supplementary bibliographic sources for coverage gaps (assessed 2026-11-11)

Question (owner): which sources could fill gaps that OpenAlex misses (case: Aleksandra
Karapetrova, UC Riverside, whose 2022 Zenodo poster carries no affiliation)?

## Live probes (2026-11-11, free endpoints, no keys)

| Source | Probe | Result | Verdict |
|---|---|---|---|
| OpenAlex `raw_affiliation_strings` | DOI lookups of 40 Europe PMC CA records missing from the corpus | 35/40 are in OpenAlex with a California raw affiliation but no linked institution, so the `institutions.id` filter never fetched them; 3 errata (correctly excluded); 2 non-CA | Largest fix, inside OpenAlex: add a `raw_affiliation_strings.search:California` scope with a strict local matcher (S2-COVERAGE) |
| Europe PMC REST | `AFF:"California" AND (microplastic* OR nanoplastic*)` | 639 records (635 MEDLINE), 323 not in the corpus; MEDLINE affiliation strings are full and reliable | Use as an audit/recall benchmark for biomedical and environmental-health papers; no key |
| ORCID public API (`pub.orcid.org/v3.0`) | `/employments`, `/works`, `expanded-search` by `ror-org-id` | Employment history lists UC Riverside and OEHHA for Karapetrova (dated affiliations); works list has 6 items (no poster); ROR search returns researchers | Best for author-level evidence: dated CA employment supports the carry-forward rule; ROR search can discover CA researchers to anchor. Public API, no key; rate-limited (about 24 req/s) |
| DataCite REST | `/dois/10.5281/zenodo.7217432` | Creator present, affiliation empty, no ORCID | Already used for datasets (S7.4); can query by creator ORCID for posters/datasets of known experts |
| Crossref REST | her 2024 SSRN record; `query.affiliation=California` + microplastic | Affiliations empty (ORCIDs present); only 45 affiliation hits | Poor for affiliation discovery; useful for ORCID-to-DOI linkage and funder metadata |
| Semantic Scholar Graph API | author search | 6 papers, no affiliations, no poster | Not a coverage source; useful later for SPECTER2 embeddings (AT-9) and TL;DRs; key recommended |
| CORE API v3 (owner key, 2026-11-11) | `authors:Karapetrova`; `microplastic AND "San Francisco Bay"`; bare `"California"`; DOI lookup | Bearer auth; token bucket `x-ratelimit-limit: 150` per window (simple query 1 token, complex 3-5, scroll more); max 10,000 results per search, scroll beyond. No record of Karapetrova (hits are other Karapetrovas); exact place-name phrases work (13 SF Bay records, mostly repository theses/full text, e.g. University of San Francisco, TSpace); bare `California` is far too loose (7,683); some compound field queries return HTTP 500 | Not an affiliation/discovery source. Use for (1) full text by DOI for S6 CA-sampling evidence and (2) a repository/theses audit with CA place-name phrases. Key in `.env` (renew daily per owner; CI secret only if a CI job needs it) |

Not probed but relevant: UC eScholarship (OAI-PMH; UC Open Access Policy deposits, theses,
grey literature), Lens.org scholarly API (free non-commercial token; institution filters),
NSF Public Access Repository (grant-linked papers, S9.1), and agency report libraries
(SFEI, SCCWRP, OEHHA, State Water Board). Dimensions is paid; Google Scholar has no API
and scraping it is prohibited.

## Recommendation (in order)

1. OpenAlex raw-affiliation scope plus raw-affiliation and carry-forward CA inference
   (in progress, S2-COVERAGE). Cheapest and largest gain; no new source.
2. Europe PMC recall audit: a scheduled check that lists CA-affiliated Europe PMC records
   missing from the corpus, and ingests their OpenAlex records by DOI when they match the
   active query (singleton DOI lookups cost 0 credits).
3. ORCID enrichment for the expert list: dated employments (strengthens carry-forward and
   "currently in California"), ORCID-listed works by DOI, and ROR-based discovery of CA
   researchers missing from the expert list.
4. DataCite by ORCID for posters/datasets; CORE (key available) for full text by DOI (S6)
   and a CA place-name theses/grey-literature audit; eScholarship OAI-PMH for UC deposits.

Tracked as TODO S2.5 (supplementary coverage sources).
