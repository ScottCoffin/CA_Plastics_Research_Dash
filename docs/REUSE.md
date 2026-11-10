# Reuse Registry

No external code has been copied.

S1.1 uses Python standard-library HTTP and logging code implemented in this
repository; no OpenAlex or ROR client code was copied.

S1.2's institution builder, classification rules, owner-review workflow, and
acceptance check were implemented in this repository; no external code was copied.

S1.5's query renderer, cache validation, smoke runner, and acceptance check
were implemented in this repository. PyYAML is a declared runtime dependency
used only to parse the repository's local YAML configuration; no external code
was copied.

S2.1's OpenAlex works ingester, cursor/date filter handling, raw snapshot
writer, high-water state, smoke runner, fixture, and acceptance check were
implemented in this repository using Python standard-library HTTP plus the
already-declared PyArrow dependency; no external code was copied.

S2.2's OpenAlex normalization, C3 table schemas, California flag derivation,
QC report, fixture, and acceptance check were implemented in this repository
using the already-declared PyArrow dependency; no external code was copied.

S2.3's provisional labeler and facet rules were implemented independently from
the repository's `config/queries.yml` and `config/taxonomy.yml`.  The
Trendspotter entry below was inspected for the documented MIT license and
facet approach, but no Trendspotter source code or data was copied.

S3.2's app shell was implemented independently in one static HTML file. The
Job_Scraper triage structure named in the specification was not copied; its
license remains documented below as a pattern that was inspected only.

S6.2's JATS section matching and XML handling were implemented independently
with `defusedxml` plus a small local JATS entity mapper. The
`atlas.fulltext.cache` interface independently implements cache-first reuse,
age and format checks, and request throttling after reviewing pyEuropePMC's
FullTextClient documentation (checked 2026-11-06). Its [repository LICENSE](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/LICENSE)
is MIT; no source code was copied. The cache also requires a current S6.1
permission decision, exact source binding, SHA-256 integrity, matching PMCID,
and a selected-copy JATS license block. Ten short JATS evidence fragments are
derived from selected CC BY Europe PMC copies; their author, DOI, article URL,
exact selected-copy license text, and full-source hashes are recorded in
`docs/api_notes/europepmc_s6_2_fixture_provenance.json`.

S6.3's GROBID REST adapter, TEI section mapping, pdfminer.six fallback, and
derived-output cache were implemented independently; no GROBID source code or
model data was copied. GROBID itself is distributed under Apache-2.0, as stated
in its [official license documentation](https://grobid.readthedocs.io/en/latest/License/).
PDF processing remains gated by the selected PDF copy's S6.1 license decision.
The 30-PDF spot check used selected Frontiers publisher copies only after both
their Europe PMC XML license block and the PDF's own CC BY statement matched.
Two candidates lacking a CC BY statement were rejected before caching. Source
hashes, license evidence, extraction outcomes, and the text-level accuracy
check are recorded in `docs/api_notes/s6_3_pdf_spotcheck.json`; full PDFs remain
in ignored `data/raw` storage.

| Repository/source | URL | License | Reused material | Adaptation and attribution |
|---|---|---|---|---|
| Job_Scraper | https://github.com/ScottCoffin/Job_Scraper | AGPL-3.0 | Watchdog and opt-in commit-guard concepts | Inspected as the documented owner pattern; independently reimplemented for this repository without copying workflow code. |
| Natural Earth Admin 1 v5.1.1 | https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-1-states-provinces/ | Public domain | California land geometry | Selected the `US-CA` feature; retained unsimplified GeoParquet and generated a simplified browser copy. Source recorded despite attribution not being required. |
| CDFW ds3158 | https://data.ca.gov/@california-department-of-fish-and-wildlife/three-nautical-mile-state-maritime-limit-r7-cdfw-ds31581 | CC BY 4.0 | California three-nautical-mile state-waters geometry | Used the official `ds3158_poly` layer, retained unsimplified GeoParquet, and embedded source/license attribution in generated features. |
| GeoNames U.S. extract | https://download.geonames.org/export/dump/US.zip | CC BY 4.0 | California place-name subset and feature coordinates | Filtered official U.S. records to `country_code=US` and `admin1_code=CA` into a 127,963-feature SQLite database; retain GeoNames credit and link in downstream attribution. |
| SF Bay and Adjacent Sanctuaries Microplastic and Microparticle Project (SFEI and 5 Gyres; OPC on data.cnra.ca.gov) | https://data.cnra.ca.gov/dataset/78ac95ac-9665-4e53-aea6-ad0762055cce | CC BY 4.0 (owner determination 2026-11-10, QUESTIONS S7.3-A; package metadata says ODC BY, also attribution) | 314 normalized sample rows (display fields only) in `site/data/monitoring.json` | Normalized by `atlas.ingest.monitoring.sfbay`; raw workbook and particle rows stay local; attribution shown per row and in the source registry |
| Karapetrova et al. 2026, ES&T, Supporting Information Tables S1-S2 | https://doi.org/10.1021/acs.est.6c02757 | ACS article (not OA); SI freely available. Factual values reused with citation under fair use (owner determination 2026-11-10, QUESTIONS SIERRA-A) | 40 per-sample concentration and deposition values and 7 site coordinates (`curation/monitoring/karapetrova2026_sierra_snow.csv`) | Values only; no text, tables or figures reproduced; full citation on every row and in the registry |

## Add-on A1 licence ledger (sections 0 and 7)

This ledger lists the external tools and projects named in add-on A1 §§0 and 7. It records only licences stated there, except for the required bibliometrix treatment below. An unknown licence is not permission to reuse code.

| Name | Licence recorded | Add-on context |
|---|---|---|
| OpenAlex | UNKNOWN - needs SPK-7 | §0 untrusted-response example; SPK-7 cost and budget spike |
| GitHub Pages | UNKNOWN - needs SPK-1 | SPK-1 hosting comparison |
| Actions runners | UNKNOWN - needs SPK-1 | §7 public repository runner-budget note |
| Cloudflare R2 | UNKNOWN - needs SPK-1 | SPK-1 hosting comparison |
| Cloudflare Pages | UNKNOWN - needs SPK-1 | SPK-1 single-file hosting limit |
| curl | UNKNOWN - needs SPK-1 | SPK-1 range-request and header checks |
| head | UNKNOWN - needs SPK-1 | §0 compact local inspection command |
| Headless-browser measurement | UNKNOWN - needs SPK-3 | §0 tool request; SPK-3 interaction measurements |
| DuckDB (CLI, CI writer, and DuckDB-Wasm) | UNKNOWN - needs SPK-2 | §0 tool request; SPK-2 writer/browser compatibility |
| zstd | UNKNOWN - needs SPK-2 | SPK-2 Parquet compression option |
| Observable Framework | UNKNOWN - needs SPK-3 | SPK-3 shell bake-off |
| Node.js | UNKNOWN - needs SPK-3 | §0 tool request; SPK-3 Framework runtime |
| Python | UNKNOWN - needs SPK-5 | SPK-5 comparison implementation |
| R | UNKNOWN - needs SPK-5 | §0 tool request; SPK-5 bibliometrix adapter |
| Mosaic | UNKNOWN - needs SPK-4 | SPK-4 facet comparison |
| Arrow | UNKNOWN - needs SPK-4 | SPK-4 data transfer |
| DESTINY | UNKNOWN - needs SPK-4 | SPK-4 reference; concepts only, no code |
| bibliometrix | GPL-3 | SPK-5 adapter and parity check |
| SciPy | UNKNOWN - needs SPK-5 | SPK-5 comparison implementation |
| Biblioshiny | UNKNOWN - needs SPK-5 | SPK-5 out-of-scope tools |
| Biblio AI | UNKNOWN - needs SPK-5 | SPK-5 out-of-scope tools |
| TALL | UNKNOWN - needs SPK-5 | SPK-5 out-of-scope tools |
| contentanalysis | UNKNOWN - needs SPK-5 | SPK-5 out-of-scope tools |
| Gemini API | UNKNOWN - needs SPK-5 | SPK-5 out-of-scope tool reference |
| VOSviewer Online | UNKNOWN - needs SPK-6 | SPK-6 embed spike |
| npm | UNKNOWN - needs SPK-6 | SPK-6 build commands |
| Plot | UNKNOWN - needs SPK-6 | SPK-6 fallback network-chart option |
| D3 | UNKNOWN - needs SPK-6 | SPK-6 fallback network-chart option |

Rules from §0 and the L6 licence gate:

- Copy/vendor only MIT, BSD, ISC, or Apache-2.0 code, as allowed by §0.
- Do not copy GPL/AGPL code.
- Treat bibliometrix as GPL-3; it may run only as a separate process.
- No DESTINY code; concepts only.

## Add-on A2 source and licence ledger (sections 0, 4, 5, 7, 8, 12)

This ledger lists the external sources, tools and resources named in add-on A2 §§0, 4, 5, 7, 8 and 12. It records only terms stated in those sections. Anything not stated is written as `unknown`, and an unknown licence is not permission to reuse content or code. Link-only entries with no stated terms are written as `unknown (terms not recorded)`. Source documents are paraphrased or quoted briefly with a link; no PDFs or full-text extracts are committed (§0 rule 5).

| Name | Licence or terms recorded | Reuse mode | A2 context |
|---|---|---|---|
| 2022 Statewide Microplastics Strategy (OPC, February 2022) | unknown | paraphrase/short quote + link | §0 rule 6 source identity; §0 rule 5 attribution; §7 Part A 22 early-action codes; §12 confirmed |
| SFEI/OPC Statewide Plastics Monitoring Strategy and Planning Framework (August 2026, #1289) | image permission only (one-time use in this publication); no text licence found | paraphrase/short quote + link | §0 rule 6 canonical Monitoring Strategy (owner determination); suggested citation used verbatim; §12 quotes checked against page text; Public Review February 2026 version is not the reference |
| DTSC Three-Year Priority Product Work Plan (2024–2026) | unknown | paraphrase/short quote + link | §0 rule 6; §7 Part B timeline; §12 identity and microplastics section confirmed |
| DTSC Candidate Chemicals listing page (microplastics) | unknown | paraphrase/short quote + link | §0 rule 6; §0 rule 8 listing is not regulation; §7 Part B timeline dates |
| DTSC Microplastics in Consumer Products research page | unknown | paraphrase/short quote + link | §0 rule 6; §7 Part B timeline table (newest-first); §12 confirmed |
| DTSC Proposal to Add Microplastics to the Candidate Chemicals List (2023 workshop proposal) | unknown | paraphrase/short quote + link | §0 rule 6 (9 pages, no tables or appendices); §0 rule 8; §7 Part B 27 June 2023 workshop |
| DTSC Background Document on Microplastics in Consumer Products Research (November 2025) | unknown | paraphrase/short quote + link | §0 rule 6 (preliminary screening research results); §0 rule 8; §7 Part B November 2025 entry; §12 Table 1 and Table A1 |
| Regional Board Boundary Features service (California Water Boards, layer 1) | Custom License (text not retrievable); owner-determined open use [OWNER], mandatory accuracy disclaimer | commit polygons (may simplify) | §4 regional layer; V-2 and V-9a regional disclaimer with source links; offshore rule; EM-2 acceptance checks |
| PSSDplusplus / ToMEx 2.0 (tomex2 dataset, v0.4.1 package) | MIT + file LICENSE (package); dataset licence unknown | DOI list only, owner-run R; R not in CI | §0 rule 1 complementarity; §4 ToMEx package (aquatic-organisms database only); DOI column [OWNER] |
| ROSES flow-diagram templates | CC BY 4.0 | template with attribution | §5 V-3 pipeline flow diagram; use current published template (update started July 2026); "not performed" stages shown |
| DuckDB (CLI, Python and Wasm builds) | unknown | dependency/API | §0 rule 4 counts from DuckDB tables only; §4 tooling facts (list_has_any, list_contains, len); version pin [VERIFY] in EM-11 |
| OpenAlex | unknown | dependency/API | §4 type field and is_retracted flag; type = 'review' used as a prior only, never as the label |
| Global Plastic Laws (Plastic Pollution Coalition) | All rights reserved | link_only | §7 Part A topic and California search links; site disclaimer quoted; no integration and no outreach [OWNER] |
| LO-1 Global Plastic Laws | All rights reserved (same site as the row above) | link_only | §8 registry entry; /search, /map, /topic/{slug}, /law?lawId= link patterns; terms recorded per entry |
| LO-2 ToMEx (Aquatic Organisms; Human Health), SCCWRP | unknown (terms not recorded) | link_only | §8 registry; living resource; §0 rule 1 calls ToMEx an open access database, which is not a licence statement |
| LO-3 NOAA NCEI Marine Microplastics | unknown (terms not recorded) | link_only | §8 registry; quarterly data update frequency as stated |
| LO-4 Atlas of Ocean Microplastics (AOMI), Japan Ministry of the Environment | unknown (terms not recorded) | link_only | §8 registry; root link only |
| LO-5 Global Plastics Hub (GPML) | unknown (terms not recorded) | link_only | §8 registry; root link only |
| LO-6 Global Plastics Data Tracker (UNSW CSDR via Global Ocean Accounts Partnership) | unknown (terms not recorded) | link_only | §8 registry; root link only |
| LO-7 Global Plastics Policy Tool (Berkeley) | unknown (terms not recorded) | link_only | §8 registry; root link only |
| LO-8 Plastiverse tools directory | unknown (terms not recorded) | link_only | §8 registry; owner is a co-founder of Plastiverse (§0 rule 7 disclosure) |
| LO-9 Moore Institute: One4All and Microplastics Open Data Portal | unknown (terms not recorded) | link_only | §8 registry; root URL confirmed at EM-16; Monitoring Strategy names the California Open Data Portal as the upload destination |
| LO-10 DTSC: Microplastics in Consumer Products (research page) | unknown (terms not recorded) | link_only | §8 registry; page URL; invites exposure data, adverse impact data and mitigation strategies |
| LO-11 DTSC: Addition to the Candidate Chemicals List: Microplastics (listing page) | unknown (terms not recorded) | link_only | §8 registry; page URL |
| LO-12 DTSC: Priority Product Work Plan (three-year plan page) | unknown (terms not recorded) | link_only | §8 registry; page URL |

Rules from §0 and §8 for this ledger:

- The Minderoo Plastic Health Map is excluded from the tool entirely (owner determination; EAT-8). It has no row and no link.
- The atlas is not an official OPC, SFEI, DTSC, OEHHA, Water Board or partner product (§0 rule 5).
- Disclosure of the owner's roles is handled in the About tab (A2-D8, EM-14), not in this ledger (§0 rule 7).
- Do not add a row, link or code from a source that is not named in the A2 sections above without a new ledger entry.

## A1 spike libraries (SPK-1..SPK-4, 2026-11-10)

Used only in `spikes/` (not shipped in `site/`). Licences are as each project
states them; re-verify at adoption (AT-4/AT-5).

| Name | Version used | Licence (project-stated) | Use |
|---|---|---|---|
| @observablehq/framework | 1.13.4 | ISC | SPK-3 shell bake-off; G-SHELL choice |
| @duckdb/duckdb-wasm | 1.29.0, 1.32.0 | MIT | SPK-1/2/3 browser Parquet reads |
| @uwdata/mosaic-core / vgplot | 0.34.1 | BSD-3-Clause | SPK-4 comparison only (not adopted) |
| DuckDB (Python) | 1.1.1, 2.0.0 via `uv run --with` | MIT | SPK-2 writer; G-PARQ pins 1.1.1 + zstd |
