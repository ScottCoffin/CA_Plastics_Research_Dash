# ORCID enrichment (S2.5c, feeding S9.5)

Generated 2026-11-11 by `scripts/fetch_orcid_profiles.py` from the ORCID public API (CC0, no key). Raw JSON is cached in `data/raw/orcid/` (gitignored); the `emails` section of `/person` is dropped before caching and nothing contact-related is stored. Requests this run: 0 (0 in `--offline` mode).

## a. Coverage

Experts: 2426; with an ORCID: 1605; profiles fetched and readable: 1604.

| Field | Experts with data (of profiles read) |
|---|---|
| biography | 100 (6.2%) |
| keywords | 217 (13.5%) |
| researcher URLs | 286 (17.8%) |
| employments | 1027 (64.0%) |
| any CA employment (dated) | 624 (38.9%) |
| any CA employment (incl. undated) | 807 (50.3%) |
| ORCID works with a DOI | 1333 (83.1%) |

Dated CA employment keeps employments that have a start or end year and that are in California (US region CA/California, or a ROR matching a California institution).

## b. Carry-forward check (CA-CARRY)

`author_carry_forward` authorships: 230. Work year within a dated California employment (+/-1 year; open end = present) is confirmed. Contradicted means the author has dated employments but none in California cover the year.

- confirmed: 90 (39.1%)
- contradicted: 19 (8.3%)
- no evidence: 121 (52.6%) (author has no ORCID: 35; ORCID without dated employments or work year: 86)

Contradicted examples (up to 15):

- Chelsea M. Rochman, work year 2014: University of Toronto (ON) 2016-present
- Ellen Willis‐Norton, work year 2015: Port of San Diego (California) 2025-present
- Chelsea M. Rochman, work year 2015: University of Toronto (ON) 2016-present
- Chelsea M. Rochman, work year 2016: University of Toronto (ON) 2016-present
- James J. Guilinger, work year 2019: University of California Irvine (CA) 2022-present
- Tarun Anumol, work year 2020: Agilent Technologies Inc Wilmington (DE) 2015-present
- Ke Wang, work year 2021: Cornell University (US) 2024-present
- Yike Chen, work year 2021: Second Affiliated Hospital of Zhejiang University (Zhejiang) 2024-present
- Ruihong Zhang, work year 2021: 扬州大学 (江苏省) 1990-present
- Scott Coffin, work year 2022: California Office of Environmental Health Hazard Assessment (California) 2024-present
- Scott Coffin, work year 2022: California Office of Environmental Health Hazard Assessment (California) 2024-present
- Mingliang Fang, work year 2022: Nanyang Technological University (Singapore) 2016-present; Scripps Research Institute (CA) 2015-2016; China National Offshore Oil Corp - Tianjin (Tianjin) 2006-2009
- Brandon Kuczenski, work year 2012: University of California, Santa Barbara (CA) 2016-present
- Matthias Schmidt, work year 2024: Helmholtz Centre for Environmental Research (DE) 2014-present; Max Planck Institute of Microstructure Physics (DE) 2013-2014; University of Pretoria (ZA) 2012-2013; Universität Leipzig (DE) 2007-2012
- Julie M. Schoenung, work year 2025: Texas A&M University (US) 2023-present; University of California Irvine (CA) 2018-2023; University of California Irvine (CA) 2018-2023; University of California Davis (CA) 2015-2018

This is evidence for a later rule decision; normalize is unchanged.

## c. ORCID works not in the corpus

DOIs on experts' ORCID records missing from works.parquet: 57934 (53828 distinct) across 1287 experts. These are mostly the experts' unrelated publications (the corpus is a plastics query), so the list needs an OpenAlex DOI+query match, which costs credits. Saved to `data/interim/orcid_missing_dois.csv`. Nothing was ingested.

## d. ROR discovery

Top 30 California institutions by works in the corpus, ORCID `expanded-search` by ROR, first 200 results each. Distinct ORCID researchers not on the expert list: 4752 (`data/interim/orcid_ror_candidates.csv`).

| Institution | ROR | Corpus works | Results (<=200) | Not on expert list |
|---|---|---|---|---|
| Stanford University | 00f54p054 | 190 | 200 | 200 |
| University of California, Davis | 05rrcem69 | 174 | 200 | 199 |
| University of California, Berkeley | 01an7q238 | 154 | 200 | 200 |
| University of California, Riverside | 03nawhv43 | 118 | 200 | 200 |
| University of California San Diego | 0168r3w48 | 107 | 200 | 200 |
| University of California, Los Angeles | 046rm7j60 | 92 | 200 | 200 |
| University of California, Santa Barbara | 02t274463 | 91 | 200 | 200 |
| Scripps Institution of Oceanography | 04v7hvq31 | 64 | 200 | 198 |
| University of Southern California | 03taz7m60 | 61 | 200 | 200 |
| University of California, Irvine | 04gyf1771 | 51 | 200 | 200 |
| San Diego State University | 0264fdx42 | 48 | 200 | 200 |
| Southern California Coastal Water Research Project | 00yzwgc71 | 44 | 29 | 22 |
| University of California, Santa Cruz | 03s65by71 | 44 | 200 | 199 |
| University of California System | 00pjdza24 | 40 | 43 | 42 |
| California Polytechnic State University | 001gpfp45 | 35 | 200 | 200 |
| University of California, San Francisco | 043mz5j54 | 35 | 200 | 200 |
| San Francisco Estuary Institute | 025et0929 | 24 | 16 | 13 |
| Hopkins Marine Station | 04c524341 | 24 | 3 | 3 |
| Joint BioEnergy Institute | 03ww55028 | 22 | 33 | 30 |
| California Institute of Technology | 05dxps055 | 21 | 200 | 200 |
| California State University, Northridge | 005f5hv41 | 21 | 200 | 200 |
| Stanford Medicine | 03mtd9a03 | 21 | 200 | 200 |
| California State University, Long Beach | 0080fxk18 | 19 | 200 | 200 |
| California State Polytechnic University | 05by5hm18 | 16 | 200 | 200 |
| San Francisco State University | 05ykr0121 | 15 | 200 | 199 |
| California State University, Channel Islands | 04v097707 | 14 | 183 | 180 |
| California State University, Chico | 027bzz146 | 14 | 200 | 200 |
| University of California, Merced | 00d9ah105 | 13 | 200 | 200 |
| IBM Research - Almaden | 005w8dd04 | 13 | 111 | 111 |
| J. Craig Venter Institute | 049r1ts75 | 12 | 48 | 48 |

## d2. ROR-discovered researchers: works ingest (2026-11-12)

`scripts/fetch_ror_researcher_dois.py` fetched the public `works` list of all 4,752 candidates
(4,752 requests, 0 errors; only the works endpoint, so no contact data) giving 18,221
distinct DOIs. `scripts/ingest_orcid_dois.py --dois-file data/interim/ror_researcher_dois.txt`
looked them up in OpenAlex with plain DOI filters (365 requests, 365 credits): 17,710 found,
11 pass the local plastics rule, 2 pass the California gate, 1 new work. Researchers at CA
institutions who are not experts yet have almost no plastics work missing from the corpus.
