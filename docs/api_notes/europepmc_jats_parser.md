# Europe PMC JATS parser

`atlas.fulltext.jats.parse_jats` parses caller-supplied JATS XML and extracts
short evidence text from Methods, Study Area, Sampling, and Data Availability
sections. Matching considers JATS `<title>` and `sec-type`, including nested
sections and namespace-qualified elements. Each result retains the section ID,
heading, section type, bounded evidence, and truncation indicator. Missing
matches yield empty lists and a `no_target_sections` fallback marker.

The parser does not fetch, persist, or license-check XML. Callers must first
apply the selected-copy license decision from the S6.1 locator.
`scripts/parse_jats.py` is a local-file CLI; it prints derived snippets to
stdout and creates no cache. Parsing uses `defusedxml` with entity expansion and
external entity access explicitly forbidden. A standalone external DOCTYPE is
preserved and never resolved; the parser rejects internal subsets before parse.
Known HTML5 names used by JATS are mapped to numeric references without
rewriting comments, CDATA, or the DOCTYPE. BOM/signature and XML-declared
encodings are honored before normalizing to UTF-8.

## License-gated retrieval cache

`atlas.fulltext.cache.fetch_jats_cached(locator, cache_dir=...)` is the
reusable fetch/cache interface. It accepts only an S6.1-style locator with
`source_type=xml`, the exact canonical Europe PMC URL for its PMCID,
`processing_allowed=true`, `license_status=permissive`, and
`storage_decision=cache_only`; it rechecks that the locator license is on the
project allowlist. The default cache is `data/raw/fulltext_cache`, which is
gitignored. Each XML file has a JSON sidecar binding work/PMCID, source URL,
license and license provenance, decision, JATS license-block text, byte count,
fetch time, and SHA-256. A cache
hit requires those current locator fields to match, integrity and article ID to
verify, a maximum age of 30 days, and a valid selected-copy CC BY/CC0 license
block. Nonpermissive, mismatched, corrupted, oversized, or invalid responses
are never written. Misses use one Europe PMC REST request, a 20-second timeout,
10 MiB limit, no retry, and a one-second process-local request interval.

This cache follows pyEuropePMC's documented cache-first reuse, 30-day age
bound, format validation, and one-second delay pattern (documentation inspected
2026-11-06). pyEuropePMC is MIT licensed
([repository LICENSE](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/LICENSE));
the behavior was inspected, but no source code was copied. The standalone
`scratch/s6_2_real` files used for fixture preparation are ignored verification
inputs; the reusable cache interface is the code above, not that scratch folder.

Verification includes ten synthetic edge fixtures and ten short JATS fragments
derived from real Europe PMC articles in
`tests/fixtures/s6_2_real_article_fragments.json`. Europe PMC metadata identifies
all ten copies as OA CC BY; each corresponding selected XML copy also contains
a CC BY license block. Authors, DOI, source URLs, exact license block text,
download hashes, and target headings are recorded in
`europepmc_s6_2_fixture_provenance.json`. Committed real-source fragments
contain at most two excerpts of 180 characters per work and retain attribution.
Full XML remains only in ignored local scratch. Rebuild the fixtures from that
local cache with `py -3.14 scripts/build_s6_2_real_fixtures.py`.

The focused checks cover heading/sec-type matching, nested sections, XML
namespaces, missing-section fallback, evidence bounds, malformed/nonarticle/
internal entity rejection, external DTD preservation without lookup, and real article
fragments. Parsing the ten complete local XML documents found target sections
in 9/10 articles. PMC13608240 had no target section headings and returned the
documented empty fallback. Across this selected set, Methods matched 8 articles,
Study Area 1, Sampling 4, and Data Availability 7. These counts describe only
the fixture set; they are not estimates of corpus-wide recall.

Europe PMC OA status alone is not permission to process or store article text.
The selected copies were processed only after checking explicit CC BY metadata
and the selected-copy JATS license block. Future fetches must follow the same
rule and the existing S6.1 decision.

Reference: [Europe PMC REST service](https://dev.europepmc.org/RestfulWebService),
including `getFullTextXML` and article metadata endpoints; pyEuropePMC
[FullTextClient cache behavior](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/api/fulltext-client.md).
