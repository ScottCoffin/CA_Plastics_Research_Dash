# S3.3 verification

The Experts view uses a fixed-height scroll viewport and renders only the
visible author rows plus a four-row overscan window.  The row index is mapped
to a fixed 174px slot, so the committed fixture and larger exports use bounded
DOM work while preserving native scrolling.

The view supports URL-hash filters for name/ID, institution type, institution,
domain or matrix tag, year range, CA basis, and open-access availability.  A
researcher drawer loads the per-author S3.1 detail document on demand and
shows works, affiliation history, co-author IDs, links, and a GitHub correction
link.

Acceptance checks:

```powershell
py -3.14 scripts/check_s3_3.py
py -3.14 -m pytest -q
```

The browser smoke uses the repository Playwright CLI workflow.  It opens the
fixture through a local HTTP server, applies an Experts filter, opens Alice
California's drawer, verifies the work title and correction link, and captures
`output/playwright/s3_3-experts.png`.  The screenshot is a deliberate local
QA artifact and is not part of the committed site payload.

On the 2026-11-06 fixture run, the unfiltered viewport showed all four fixture
authors and the CA-led filter reduced the result to one author.  The list
viewport stayed fixed while rows were positioned into a 174px slot; the drawer
loaded its detail document on demand.  The only browser console messages were
the expected missing `/favicon.ico` requests from the dependency-free static
server.
