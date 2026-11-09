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
