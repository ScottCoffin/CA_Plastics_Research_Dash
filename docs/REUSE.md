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

| Repository/source | URL | License | Reused material | Adaptation and attribution |
|---|---|---|---|---|
| Job_Scraper | https://github.com/ScottCoffin/Job_Scraper | AGPL-3.0 | Watchdog and opt-in commit-guard concepts | Inspected as the documented owner pattern; independently reimplemented for this repository without copying workflow code. |
| Natural Earth Admin 1 v5.1.1 | https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-1-states-provinces/ | Public domain | California land geometry | Selected the `US-CA` feature; retained unsimplified GeoParquet and generated a simplified browser copy. Source recorded despite attribution not being required. |
| CDFW ds3158 | https://data.ca.gov/@california-department-of-fish-and-wildlife/three-nautical-mile-state-maritime-limit-r7-cdfw-ds31581 | CC BY 4.0 | California three-nautical-mile state-waters geometry | Used the official `ds3158_poly` layer, retained unsimplified GeoParquet, and embedded source/license attribution in generated features. |
| GeoNames U.S. extract | https://download.geonames.org/export/dump/US.zip | CC BY 4.0 | California place-name subset and feature coordinates | Filtered official U.S. records to `country_code=US` and `admin1_code=CA` into a 127,963-feature SQLite database; retain GeoNames credit and link in downstream attribution. |
