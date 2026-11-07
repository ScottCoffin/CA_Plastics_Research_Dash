# Open Questions

Defaults below come from `spec.md` Part G and remain in use until the owner
answers. Add an answer and date without deleting the original question.

| ID | Owner question | Default in use | Owner answer | Status |
|---|---|---|---|---|
| G-1 | Include chemicals-in-plastics and tire chemicals? | Core particles/debris/litter; flagged chemicals tier 2 | Yes | Answered 2026-11-05 |
| G-2 | Include tire-wear particles and textile microfibers in core? | Yes | Yes | Answered 2026-11-05 |
| G-3 | Include CA-led human-health work with no CA sampling? | Yes, via `ca_led` | Yes | Answered 2026-11-05 |
| G-4 | How should sampling beyond California's 3-nm waters be classified? | Partial/not CA-sampled; filterable | Partial/not CA-sampled; filterable | Answered 2026-11-05 |
| G-5 | What time horizons should works and grants use? | All works, last 10 emphasized; grants last 15 FY | All works, last 10 emphasized; grants last 15 FY | Answered 2026-11-05 |
| G-6 | Where are State Water Board research awards published? | Investigate; defer without machine-readable source |  See docs\AWARDS_DATA.md for details   | Open |
| G-7 | Confirm repo name, hosting, code license, and data license. | Separate repo; MIT code; CC BY derived data pending review | `CA_Plastics_Research_Dash`, public GitHub Pages; MIT code; CC BY derived data pending upstream review | Answered 2026-11-05; source reviews remain |
| G-8 | May OA full text be cached and snippets published? | Gitignored cache only; short snippets | Gitignored cache only; short snippets | Answered 2026-11-05 |
| G-9 | Confirm F1 acceptance thresholds. | Use proposed thresholds | Use proposed thresholds | Answered 2026-11-05 |
| G-10 | Who labels/adjudicates the gold set and how much time is available? | Owner plus 1–2 colleagues; owner adjudicates | Owner plus 1–2 colleagues; owner adjudicates | Answered 2026-11-05 |
| G-11 | Include literature-derived monitoring datasets? | Yes, flagged secondary | Yes, flagged secondary | Answered 2026-11-05 |
| G-12 | Confirm disclaimer wording and affiliation statement. | Independent; not official OEHHA/State product | Independent; not official OEHHA/State product | Answered 2026-11-05 |
| G-13 | Include out-of-state federal recipients sampling in California? | Yes; `ca_led=false` | Yes; `ca_led=false` | Answered 2026-11-05 |
| G-14 | Confirm repository size and data-branch strategy. | Slim main-branch data; large intermediates outside Git | Slim main-branch data; large intermediates outside Git | Answered 2026-11-05 |
| S0.2-A | How should the private repository be hosted when its current plan does not support GitHub Pages? | Keep it private and leave Pages blocked until G-7 is resolved; do not change visibility automatically | Made public; keep it public | Answered and verified 2026-11-05 |
| S0.2-B | When should automated repository commits be enabled? | Leave `ENABLE_DATA_COMMITS` unset until the owner approves keepalive and future data commits | Immediately; variable added | Answered and normalized to exact `true` 2026-11-05 |
| S0.2-C | When will the OpenAlex credential be added? | Leave `OPENALEX_API_KEY` unset and never commit it | Added as a repository Actions secret | Answered and secret name verified 2026-11-05 |
| S1.2-A | Confirm the default major-private coverage set and review the generated top-100 plastic-work institution queue. | Use the 11 institutions listed in `atlas.ingest.institutions.MAJOR_PRIVATE_UNIVERSITIES`; keep S1.2 open until all review rows have an owner type and date. | Reviewed all 100 rows; retain the default set and apply the 22 type corrections. | Answered 2026-11-05 |
| S2.3-A | Is owner input required to implement the local provisional rules? | No; keep the candidate unpromoted pending later validation/promotion review. | No input required for S2.3 implementation. | Recorded 2026-11-06 |
| S1.5-A | Review and approve promotion of `plastic-v2-candidate` for a bounded production export used to measure full-data S3.6 performance? | Keep candidate inactive; do not incur ingestion cost or treat the count estimate as data. | Pending | Recorded 2026-11-07 |
