# Europe PMC full-text XML locator

Verified 2026-11-06 against the official Europe PMC REST documentation and a
single bounded live smoke. The locator endpoint is:

```text
GET https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML
```

The official service reference describes `getFullTextXML` as returning article
XML for the full-text OA subset. The live request for `PMC9417507` returned
HTTP 200, `application/xml`, and a JATS article prefix. A separate one-request
search query located OA PMCID records. No article body was saved. One earlier
read attempt timed out, so callers must use bounded timeouts and should not
retry aggressively.

The API documentation checked does not specify a request-rate ceiling. Keep
requests sequential, add at least a one-second delay between future article
fetches, use a descriptive User-Agent, and stop on HTTP errors/timeouts. This
S6.1 locator makes no network requests. For a future fetcher, inspect the
article's license before processing or caching: Europe PMC OA status does not
mean all articles share a reusable license. An OpenAlex license is accepted for
Europe PMC XML only when it comes from a validated HTTPS PMC/Europe PMC
repository URL with a canonical article/fulltext path naming the exact selected
PMCID. Bare IDs, publisher hosts, query-only mentions, and substring matches do
not count as copy evidence. The best publisher copy's license is not evidence for the PMC XML. For
PDF, the license must come from the same `best_oa_location` record as the
selected `pdf_url`. Missing same-copy evidence is `unknown`, retains the
provenance reason, and sets `processing_allowed=false`. Only CC0 and explicit
CC BY license codes are automatically eligible here; other labels remain
review-only. Under G-8, any permitted cache is local and gitignored.

Official references:

- Europe PMC REST service: <https://dev.europepmc.org/RestfulWebService>
- Europe PMC SOAP/REST reference, `getFullTextXML`: <https://dev.europepmc.org/docs/EBI_Europe_PMC_Web_Service_Reference.pdf>
- OpenAlex work attributes (`ids.pmcid`): <https://help.openalex.org/data/works/attributes/>
- OpenAlex locations (`pdf_url`, `license`, OA location semantics): <https://help.openalex.org/data/locations/>
- OpenAlex OA location fields and their copy-specific licenses: <https://help.openalex.org/data/works/open-access/>

Live check: `py -3.14 scripts/smoke/europepmc_fulltext.py` (one GET, 20-second
timeout, 2,048-byte response prefix only, no retries or local cache).
