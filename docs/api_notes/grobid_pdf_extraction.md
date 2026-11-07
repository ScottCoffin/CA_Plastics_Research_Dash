# S6.3 GROBID PDF extraction

`atlas.fulltext.grobid.extract_pdf` posts a selected PDF to the local GROBID
`/api/processFulltextDocument` service, parses TEI into the S6.2 section shape,
and falls back to local `pdfminer.six` text extraction when GROBID times out,
is unavailable, returns invalid TEI, or yields no target sections. Results
include `extractor` and `failure_category` so failures remain visible. GROBID
requests are bounded by a timeout and response-size cap; the adapter accepts
only a local HTTP endpoint, so PDF content is not uploaded to a remote service.

`extract_pdf_cached` accepts only a selected S6.1 PDF locator with a confirmed
allowlisted CC BY/CC0 license and `cache_only` decision. It downloads one PDF,
keeps its bytes in memory, and stores only bounded section output and a SHA-256
of the source in ignored `data/raw/fulltext_cache/pdf/`. Cache identity binds
the work ID, selected URL, and license; cached derived output has its own
integrity hash. Requests are sequentially throttled by at least one second.

The local fallback requires `pdfminer.six` (declared project dependency). It
uses selectable PDF text and heading labels, so image-only scans can return
`no_target_sections`. `py -3.14 scripts/check_s6_3.py` checks TEI conversion,
malformed-PDF reporting, and timeout fallback without contacting a service.
`py -3.14 -m pytest tests/test_s6_3_grobid.py` covers cache gating, cache reuse,
invalid TEI, and section extraction.

## Local GROBID setup

The first implementation environment had no reachable Docker Desktop Linux
daemon and Java on PATH was 8. For the completed spot check, the owner supplied
a local GROBID 0.9.1 CRF container with 4 GB memory; it passed `/api/isalive`
with HTTP 200 and `true`. The reproducible lightweight setup is:

```powershell
docker pull grobid/grobid:0.9.1-crf
docker run --rm --init --ulimit core=0 -p 8070:8070 grobid/grobid:0.9.1-crf
```

The official GROBID Docker instructions document the `grobid/grobid` image,
port 8070, and the CRF-only image for lighter CPU use:
<https://grobid.readthedocs.io/en/latest/Grobid-docker/>. Its service API
documents `/api/processFulltextDocument`:
<https://grobid.readthedocs.io/en/latest/Grobid-service/>.

## Thirty-PDF spot check

`docs/api_notes/s6_3_pdf_spotcheck.json` records the completed run. It contains
30 directly acquired Frontiers PDFs selected from two disjoint Europe PMC
`cursorMark` result pages (59 distinct metadata records). Each selected PDF
passed both the Europe PMC full-text XML CC BY license-block check and a CC BY
license-statement check against text extracted from that exact publisher PDF.
Two other candidates were rejected because their selected PDFs did not contain
the required CC BY statement; they were not cached or submitted to GROBID.
Publisher requests required an exact HTTPS URL, public DNS resolution, and no
HTTP redirects. The prior PMC anti-automation challenge was not bypassed.

GROBID had no technical request failures. It returned no target sections for
21/30 PDFs (70%); `pdfminer.six` handled those fallback cases. Six fallback
documents yielded target sections, while 15/30 documents (50%) had no target
output after both routes. Those 15 were 13 review articles and two editorials.
GROBID found target sections directly in nine PDFs. Across 15 PDFs with section
output, all 16 reported section headings and their short evidence prefixes
matched text from the hash-matched selected PDF. This is a convenience sample
of Europe PMC-indexed Frontiers papers returned in relevance order; it is not a
random or representative sample of the project corpus. The comparison checked
PDF text content, not visual page layout.

The run keeps full PDFs only under ignored `data/raw/fulltext_cache/`; committed
evidence contains per-document DOI, license block, selected PDF license text,
SHA-256, outcome, and bounded excerpts. `py -3.14 scripts/spotcheck_s6_3.py`
repeats the bounded acquisition using cursor pagination and local GROBID.
