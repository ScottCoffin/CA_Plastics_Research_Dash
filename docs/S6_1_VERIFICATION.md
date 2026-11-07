# S6.1 full-text locator verification

`src/atlas/fulltext/__init__.py` implements deterministic, metadata-only
selection. Europe PMC XML wins for an OA work with a valid PMCID; otherwise the
direct PDF URL from the best OA location is used. The normalized C3 work fields
remain unchanged. The CLI joins normalized candidate IDs with `raw_json` from
the ignored OpenAlex interim table, where `ids.pmcid`, `best_oa_location.pdf_url`,
and location licenses are available. An XML license is accepted only from a
`locations[]` entry whose validated HTTPS landing-page or PDF URL uses a trusted
PMC/Europe PMC repository host and canonical article/fulltext path containing
the exact PMCID. Bare IDs, longer ID substrings, publisher hosts, and query-only
mentions are rejected. A publisher/best-location license is never transferred
to Europe PMC XML. When no PMCID-specific license can be established, the XML locator remains available
as metadata with `license_status=unknown`, a provenance reason, and
`processing_allowed=false`. For a PDF, its license must come from the same
`best_oa_location` record as its selected `pdf_url`; the normalized work-level
license is not used as fallback.

The locator never downloads article text. HTTPS URLs with credentials, unusual
ports, localhost/private literal IPs, invalid lengths, or invalid PMCID values
are rejected. For later network code this validation is only an input check;
that downloader must also validate redirects and resolved IP addresses at
connection time.

License decisions are deliberately conservative. Explicit CC0 and CC BY
license codes are eligible for processing and a gitignored cache only.
Explicit closed/all-rights-reserved labels are blocked. Missing, unfamiliar,
and non-whitelisted licenses require review and cannot be processed or cached
automatically. Every locator carries its license and attribution URL when
known.

Acceptance fixture: 8 synthetic candidates yield 2 XML, 4 PDF, and 2 none
(25%, 50%, 25%). Rows without selected-copy license evidence remain blocked
for review; a selected PDF with an explicit restricted license is also blocked
from processing and caching. License counts are 2 permissive, 1 restricted,
and 5 unknown. These are fixture-only counts, not production-corpus coverage.
No downloaded production candidate corpus is available; the prior OpenAlex
count estimate is not a corpus. Coverage report generation is in
`scripts/locate_fulltext.py`; it records candidate rows, XML/PDF/none shares,
and license-decision counts.

Verification commands:

```powershell
py -3.14 scripts/check_s6_1.py
py -3.14 -m pytest tests/test_fulltext_locator.py
py -3.14 scripts/smoke/europepmc_fulltext.py
```
