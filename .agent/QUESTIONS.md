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
| G-COST | What OpenAlex budget may the pipeline use? | Free allowance only; no paid fallback or billing changes | Measured 2026-11-09: free-only account confirmed; 10,000 daily credits / USD 1.00 limit and USD 0.25 local abort; 100-call benchmark completed. USD 0.026 response metadata vs. USD 0.028 conservative balance decrement remains explicitly reconciled conservatively. | Resolved for SPK-7; see `docs/api_notes/openalex_costs.md`. |
| S0.2-A | How should the private repository be hosted when its current plan does not support GitHub Pages? | Keep it private and leave Pages blocked until G-7 is resolved; do not change visibility automatically | Made public; keep it public | Answered and verified 2026-11-05 |
| S0.2-B | When should automated repository commits be enabled? | Leave `ENABLE_DATA_COMMITS` unset until the owner approves keepalive and future data commits | Immediately; variable added | Answered and normalized to exact `true` 2026-11-05 |
| S0.2-C | When will the OpenAlex credential be added? | Leave `OPENALEX_API_KEY` unset and never commit it | Added as a repository Actions secret | Answered and secret name verified 2026-11-05 |
| S1.2-A | Confirm the default major-private coverage set and review the generated top-100 plastic-work institution queue. | Use the 11 institutions listed in `atlas.ingest.institutions.MAJOR_PRIVATE_UNIVERSITIES`; keep S1.2 open until all review rows have an owner type and date. | Reviewed all 100 rows; retain the default set and apply the 22 type corrections. | Answered 2026-11-05 |
| S2.3-A | Is owner input required to implement the local provisional rules? | No; keep the candidate unpromoted pending later validation/promotion review. | No input required for S2.3 implementation. | Recorded 2026-11-06 |
| S1.5-A | Review and approve promotion of `plastic-v2-candidate` for a bounded production export used to measure full-data S3.6 performance? | Keep candidate inactive; do not incur ingestion cost or treat the count estimate as data. | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| S4.1-A | Approve the pending `guide_v1` labeling policy so it can be frozen before annotation? Review `docs/LABELING_GUIDE.md` and its checklist/hash in `docs/LABELING_GUIDE_REVIEW.md`; reply "Approve `guide_v1` as written" with the approval date, or name the exact section and requested revision. | Guide remains draft; no annotation or gold adjudication. | Approved as written by Scott Coffin; frozen guide hash recorded in `docs/LABELING_GUIDE_REVIEW.md`. | Answered 2026-11-07 |
| A1-D1 | Adopt which adoption levels (L0–L3)? | L0 + L1 now; L2 after spikes; L3 optional | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A1-D2 | Shell: Framework or single-file? | Framework, pending SPK-3 | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A1-D3 | Keep R if it passes the gate? | Yes, monthly job only | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A1-D4 | Use Cloudflare R2 when Parquet exceeds 25 MB? | Yes, via the owner's Cloudflare domain; otherwise stay on Pages | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A1-D5 | Default leaderboard measure: full or fractional counts? | Show both; default sort by fractional with stability intervals | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A1-D6 | Who labels the AT-1 audit sample (≥ 500 works)? | Owner plus one or two colleagues | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A1-D7 | Public Parquet without abstracts acceptable? | Yes | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| AT-1-A | How should the 2026-11-09 top-20 sample shortfall be handled? | Keep available rows; do not supplement or change institution selections/query; leave the 500-work gate open. | Keep 405 rows (354 unique), make no supplements, new selections, or query changes; labels remain blank. | Answered 2026-11-09; AT-1 remains partial |
| S7.3-A | Which reuse terms govern the SF Bay / 5 Gyres XLSX for normalization and publication, given current package metadata says ODC BY, the resource license is empty, the official resource fetch returned HTTP 403, and S7.2 recorded CC BY 4.0? | Do not publish raw or normalized data and do not infer legal clearance; retain only local processing/QC until clarified. | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-D1 | Secondary study_type labels? | Single primary; secondary hidden | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-D2 | Include Block M (macroplastics)? | Yes, collapsed | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-D3 | Include Block X rows? | Yes, labelled | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-D4 | V-5 parameters? | N = 5 years; threshold from build-time distribution | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-D5 | V-9a region unit? | Nine Regional Boards plus the two offshore values | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-D6 | Who validates need→rule mappings? | Owner first, then an OPC, SCCWRP, SFEI or DTSC colleague | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-D7 | Funding layer at launch? | No; after S8 | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-D8 | Disclosure text? | Include in About | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-D9 | Use size_subclass (DTSC 2023 bins)? | Optional; empty unless a work reports its size range | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-D10 | Show non-California regulations from DTSC Table 1? | Show as DTSC-stated context only, with caveat | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-D11 | State-waters polygon source for the offshore rule? | Pick in EM-2; owner confirms | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-INT-1 | A2 §6.3 specifies the ledger as UTF-8 CSV (`\|` list separator), but the companion file is `docs/opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx`. Which is canonical? | The XLSX is the owner-maintained source; EM-1 exports it deterministically to `config/need_ledger.csv` and EAT-10 validates both (70 rows, 20 columns). | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-INT-2 | EM-2 depends on "S5 geo". Must the regional-layer fetch wait for S5.4? | Interpret "S5 geo" as S5.4. The layer fetch, EAT-12 checks and offshore rule may proceed as partial work now (S1.3 is complete); `rwqcb_region` derivation on works waits for S5.4 geo_mentions, and EM-2 stays unchecked until then. | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
| A2-INT-3 | A2 has adoption levels E0–E3 but states no owner gate. Which levels are adopted? | All four (E0–E3); the owner determinations include EM-15..EM-18. Tasks are still blocked by their dependencies, including gated A1 tasks (AT-4, AT-10). | Default accepted (owner, 2026-11-09) | Answered 2026-11-09 (default) |
