MEMO / TASK SPEC — California Plastics Award Ledger and Solicitations Feed
Module 1: OPC Staff Recommendation Award ParserModule 2: Cal eProcure "Open and Recent Solicitations" Feed with Award Linking

To	Scott Coffin; the implementing IDE agent(s)
From	Hugh, Human Chemical Company
Date	2026-11-05
Status	Ready to implement. Standalone: no other repository is required.
Size	6 handoff-able sessions: A–C (Module 1), D–F (Module 2)

Epistemic labels. [V] = verified in research (cited). [INF] = my inference or design choice. [VERIFY] = the agent must test against the real page or document before relying on it. Document and page structures described below come from analyst-style readings of the sources, not raw bytes. Treat them as hypotheses that the first session of each module must confirm against the real files.

0. Purpose and shared design
Build two small pipelines that feed one ledger of California plastics-related public funding activity, for use in a dashboard tab ("What research is being funded in California?"):
1.	Module 1 (awards): parse OPC Council staff recommendations into itemized, validated award lines.
2.	Module 2 (solicitations): track plastics-related California state solicitations (IFB/RFP/RFQ) from Cal eProcure event pages through notice of intent to award, then link closed solicitations to their award record.
Shared conventions
•	Every row carries provenance: source_url, source_sha256, retrieved_at, acquisition_method (fetched / manual).
•	Dollar amounts are always typed (amount_type) because "authorized up to", "contract cap", "project award", "administration share", "cost share" and "augmentation" are different things and must never be summed together.
•	Pass-through chains are explicit (funder_chain, parent_ledger_id) so totals don't double count.
•	Public outputs must not contain personal contact names or emails. Procurement pages list a named contact; store only a boolean such as contact_listed.
•	No LLM calls. Rule-based parsing and deterministic matching only. Humans resolve what the rules can't.
•	Public aggregators (GovTribe, Cleatus, GovDash) are used only for discovery, never as the cited record (see §11).
Agent protocol (applies to all sessions)
•	One session = one task (A–F). Finish it to its Definition of Done, then stop.
•	Maintain .agent/TODO.md, MEMORY.md, DECISIONS.md, LESSONS.md, HANDOFF.md (overwritten each session), QUESTIONS.md, TOOL_REQUESTS.md.
•	Never cat large files; inspect with head, row counts or schema printouts. Put verbose logs in a gitignored scratch/.
•	If a capability would materially help (browser-automation tool, DuckDB CLI, PDF library, scheduler), record it in TOOL_REQUESTS.md with the benefit and fallback, and tell the user.

MODULE 1 — OPC STAFF RECOMMENDATION AWARD PARSER
1. Why this source
OPC Council staff recommendations are the richest public record I found of state-funded plastics research awards:
•	Each item itemizes recipient, amount, scope and timeline. For example, the June 2020 item lists SFEI up to $120,233 and SCCWRP up to $225,236, each with scope, deliverables and timeline 1, and the August 2023 item lists five named projects with institutions and amounts (e.g., UCLA, Dr. Sanjay Mohanty, $406,647; CSU Long Beach, Dr. Rebeka Sultana, $506,250 2).
•	OPC project directory pages carry the grantee and category but, on the page I read, no grant amount, program, project dates, funding source, status or grant number 3, so the PDFs are the source of amounts.
•	Money flows on through pass-throughs. SCCWRP minutes list "Ocean Protection Council (through California State University, Long Beach) ($460,000), Field Monitoring of Microplastics Loading and Accumulation in LID BMPs" 4, which looks like a subaward inside CSU Long Beach's $506,250 [INF]. The ledger must model this or totals will double count.
2. Scope
In scope: OPC Council staff recommendations, 2018–present, whose title or text concerns plastics, microplastics, tire wear, textile fibers, marine debris, or the Ocean Litter and Statewide Microplastics strategies. Include monitoring authorizations.
Out of scope: non-plastics items (count them for QC, extract no rows); grants approved only under delegated Executive Director authority (log as a known gap); other agencies' award sources (separate tasks); any total not stated in a document. Never infer an award amount.
3. Inputs and discovery
3.1 Where documents live [V]

Era	Pattern (examples)
Legacy	https://opc.ca.gov/webmaster/ftp/pdf/agenda_items/YYYYMMDD/<ItemName>.pdf (e.g., .../20200619/Item9_MicroplasticsProjects_FINAL.pdf 1)

Current	https://opc.ca.gov/wp-content/uploads/YYYY/MM/Item-<n><letter>-<Title>-508.pdf (e.g., /2023/07/Item-7a-CASG-Microplastic-Research-508.pdf 2)


•	The upload month need not equal the meeting month.
•	The same item can appear under two upload paths. The June 16, 2026 item appears at both /wp-content/uploads/2026/06/Item-6c-Plastics-Monitoring-508.pdf 5 and /wp-content/uploads/2026/08/Item-6c-Plastics-Monitoring-508.pdf 5. Deduplicate by content hash, not URL. If the hashes differ, treat the later upload as a revision and keep both.
•	Do not guess URLs from meeting dates. Discover them.
3.2 Discovery routes (use all; reconcile)
1.	Meetings index. https://opc.ca.gov/meetings lists meetings and says to scroll down for past meeting agendas, meeting documents, summaries and recordings 6. Crawl each meeting page and collect Item-*.pdf links. Meeting-page slugs vary (/2024/05/council-meeting-june-4-2024 7, /2026/01/ocean-protection-council-meeting-march-23-2026 8), so crawl the index rather than constructing slugs.
2.	Council meeting summary pages. They list approved funding as bullets in which each dollar amount is bold and hyperlinked to an agenda item PDF 9, introduced by "approved funding in amounts up to 9". Parse them as a cheap index (amount → PDF URL → recipient text) and as an independent cross-check of what the Council approved.
3.	OPC project directory (recall check only). The "Plastic Pollution" tag links to /single-category/plastic-pollution/?directory_type=projects, likely the filtered listing 3. I could not load that listing during research [VERIFY]. If it works, every plastics project there must map to a ledger row or a documented exception.
4.	Companion call pages (sidecars). OPC and California Sea Grant RFP pages (see §9, Fixture B) carry the call-level budget split.
3.3 Access constraints [V/INF]
•	At least one OPC PDF returned a block page to automated fetching: "Request Rejected: The requested URL was rejected," with a support ID 10. Other OPC PDFs fetched normally.
•	Requirements: descriptive User-Agent with a contact email; throttle (≥2 s between requests); cache; re-download only if ETag/Last-Modified/hash changes; support a manual drop folder data/raw/opc/manual/ processed identically (acquisition_method = "manual"); do not attempt to evade blocking.
•	Revised documents exist: the August 2023 item reads "Revised August 11, 2023" 2. Record the hash of every fetched file and keep superseded versions.
4. Document anatomy (observed; confirm in Session A)
Common skeleton [V, reader description]: header block ("Staff Recommendation ", "Action Item", staff name, optional "Revised"); Recommended Action; Location; Strategic Plan Goals and Objectives; Exhibits; Findings and Resolution; Executive Summary; Background; Project Summary/Summaries; About the Grantee; Project Timeline; Project Financing; Consistency with the California Ocean Protection Act; CEQA. (Heading order listed for Item 6c 5; header and project-summary layout for Item 7a 2.)

Variant	Example	Handling
Multi-project item with numbered sub-items	Aug 2023 Item 7a: numbered lines "7a.1 $363,814 to Natural History Museum of Los Angeles (NHMLA) for ..." through 7a.5 2, repeated as approval bullets and per-project Financing	Split on ^\d+[a-z]\.\d+; amounts appear in three places and must agree
Two-project item	Jun 2020 Item 9 (9a, 9b); the financing section is plain lines, not a true table, and labels like "9a." run into surrounding text 1
Tolerant label regex
Umbrella authorization to an administrator	Jan 2023: up to $1,328,710 to California Sea Grant, with up to $253,710 for Sea Grant's administration and a $375,000 Sea Grant contribution 11
authorization_umbrella; projects return later (individual projects were to come to the August 2023 meeting 11)

Budget augmentation	Aug 2023 Item 7b: up to $180,000 to SCCWRP for Bight 2023 microplastic sample processing, a budget augmentation to an existing grant 12
augmentation; parent not named (parent link is a review-flagged heuristic)
Grantee to be determined	Jun 2026 Item 6c: "External grantee(s) will be identified in coordination with the State Water Resources Control Board" 5
recipient null, recipient_status = TBD; never invent one
Varying funding source	2020: California Environmental License Plate Funds (ELPF) 1; 2023: Budget Act of 2022, $50 million General Fund appropriation to OPC 11; 2026: Budget Act of 2024, Greenhouse Gas Reduction Fund appropriation, FY 2024/2025 5
verbatim phrase + normalized fund_code

Rough edges. Ellipses in my excerpts are reading artifacts. Strip repeating header and footer lines (e.g., "Staff Recommendation – Item 7a ..." and "California Ocean Protection Council Meeting | August 15, 2023" 2) before parsing. Exhibits may be bundled: segment at "Exhibit" headings and don't parse exhibit text as award text.
5. Output: opc_award_ledger (Parquet + CSV)

Field	Description
ledger_id	hash of (meeting_date, item_id, subitem_id, recipient_norm, amount_usd, amount_type)
source_url, source_sha256, acquisition_method, retrieved_at	provenance
doc_revision_date, superseded_by	version handling
meeting_date, item_id, subitem_id, action_title	location in the meeting record
action_type	authorization_umbrella, project_award, augmentation, administration, concurrence, other
project_title, recipient_name_raw, recipient_name_norm, recipient_ror, administrator_raw, pi_name	entity fields (pi_name only when explicitly stated)
amount_usd (int), amount_qualifier (up_to/exact/unspecified)	amount
amount_type	authorization_total, project_award, admin_share, augmentation, cost_share_other_party, total_check
funding_source_raw, fund_code	ELPF/GF/GGRF/NOAA_SEA_GRANT/other/unknown
start_date, end_date, duration_text	timing
location_text, strategic_goal/objective/target	context
scope_snippet	≤300 characters; attribute via source_url
plastics_flag, plastics_terms	relevance
parent_ledger_id, funder_chain	pass-through modeling
validation_flags, parse_confidence, needs_review	quality

Rule for authorization vs. awards [INF]: an authorization_total is not a sum of researcher awards. In August 2023 the authorization (up to $1,905,672 to California Sea Grant 2) exceeds the five project awards ($363,814, $175,819, $199,432, $406,647, $506,250 2), which sum to $1,651,962 (computed). The $253,710 residual equals the Sea Grant administration figure in the January 2023 item. Only label it admin_share if the August document states it; otherwise record a non-blocking RESIDUAL_UNEXPLAINED flag.
6. Parsing approach (rule-based)
1.	Extract text with a layout-aware PDF library (agent's choice; request tools if needed), keeping bold and font cues. Strip repeating headers and footers. If text is nearly empty (scanned), flag ocr_needed and queue for manual handling.
2.	Segment by anchored labels (Recommended Action, Location, Strategic Plan..., Exhibits, Findings and Resolution, Executive Summary, Background, Project Summary/Summaries, About the Grantee, Project Timeline, Project Financing, ...). Record page ranges. Log unknown headings.
3.	Extract entities.
◦	Amounts: \$\s?\d{1,3}(,\d{3})*(\.\d{2})? with look-behind for "up to". Accept only inside Recommended Action, approval bullets, per-project Financing and Financing tables. Reject contextual figures (for example the $27 million GGRF appropriation 5).
◦	Recipients: \$[\d,]+ to (?P<recipient>…) for … and bullets.
◦	Sub-items: 7a.1-style and 9a/9b labels.
◦	Dates and durations: month–year ranges, "two years"; keep verbatim plus parsed.
◦	Funding source, location, strategic goal/objective/target, explicit PI names.
4.	Reconcile each sub-item across all places it appears. If values agree, confidence is high. If not, record all values, choose the Recommended Action value as primary, and flag V2_AMOUNT_CONFLICT.
5.	Normalize recipients with config/opc_aliases.csv (raw_pattern → canonical → ROR → org_type), seeded with entities seen in verified items: SCCWRP; SFEI; California Sea Grant (administered by Scripps Institution of Oceanography at UC San Diego 11); Natural History Museum of Los Angeles County; California Marine Sanctuary Foundation; UCLA; CSU Long Beach. No automatic fuzzy matching without a threshold and a review flag.
6.	Plastics flag. True when the action title or Recommended Action matches microplastic*, nanoplastic*, plastic pollution/debris/litter, marine debris, ocean litter, tire wear, textile/microfiber, "plastics monitoring". Background-only matches → maybe (review). Cross-check with the directory tag when available.
7.	Confidence. Start at 1.0; subtract 0.2 for each of: missing recipient (not TBD), amount in only one place, amount conflict, ambiguous date, ambiguous action type, extraction irregularity. needs_review if < 0.7 or any blocking flag.
7. Validation rules

Code	Rule	Severity
V1_SUM_PROJECTS_VS_AUTH	Σ(project awards) + stated admin = authorization total (±$1)	Blocking if all components are stated and fail; otherwise RESIDUAL_UNEXPLAINED
V2_AMOUNT_CONFLICT	Same sub-item amount differs between sections	Blocking
V3_TOTAL_LINE	"TOTAL" equals sum of line items	Blocking on mismatch
V4_DATE_SANE	Start ≤ end; within ±10 years of meeting date	Warning
V5_RECIPIENT_MISSING	Recipient empty and no TBD language	Blocking
V6_REVISED_VERSION	Multiple files for the same meeting and item	Keep the latest as primary; mark older rows superseded_by
V7_NON_PLASTICS	plastics_flag = false	Info (excluded)
V9_RFP_VS_AWARDS_GAP	Awards sum exceeds the call's advertised budget (see Fixture B)	Info; document, don't explain

Known conflict to reproduce [V]: the June 2020 financing text says "up to $120,182" for SFEI 1 while the table and recommended action say $120,233. Output $120,233 as primary with V2_AMOUNT_CONFLICT, recording both.
8. Gold fixtures (verify against the actual PDFs in Session A)
Fixture A — 2020-06-19, Item 9. 9a: SFEI, up to $120,233, ELPF, Sept 2020–Dec 2021. 9b: SCCWRP, up to $225,236, ELPF, Sept 2020–Sept 2022 (per the 2020 staff recommendation 1). Expect V2_AMOUNT_CONFLICT on 9a. Document total $345,469 (computed from the two stated figures).
Fixture B — 2023-01-24, Item 7a, plus the RFP sidecar.
•	Item: authorization_umbrella up to $1,328,710 to California Sea Grant; cost_share_other_party $375,000; combined $1,703,710; admin_share up to $253,710; source Budget Act of 2022, $50 million General Fund appropriation to OPC 11. A pending federal request ($1,500,000 IIJA Marine Debris Challenge 11) is explicitly not part of these figures. Do not ingest it as an award.
•	RFP sidecar (new): the OPC/Sea Grant call states a total of $1,450,000, with California Sea Grant contributing $375,000 of NOAA Sea Grant funds and OPC contributing $1,075,000 13, and Call 1 capped at $375,000 per project 13. This matches the January remainder (1,328,710 − 253,710 = 1,075,000, computed). Record the $375,000 with fund_code = NOAA_SEA_GRANT and a federal-origin note in funder_chain.
•	Reconciliation to flag: the five funded projects sum to $1,651,962 (computed), more than the advertised $1,450,000. Emit V9_RFP_VS_AWARDS_GAP. Don't speculate on the cause in the ledger.
Fixture C — 2023-08-15, Item 7a (revised Aug 11, 2023). Umbrella up to $1,905,672 to California Sea Grant. Project awards (all via Sea Grant), per the document read: 7a.1 NHMLA $363,814; 7a.2 SFEI $175,819; 7a.3 California Marine Sanctuary Foundation $199,432; 7a.4 UCLA (PI Mohanty) $406,647; 7a.5 CSU Long Beach (PI Sultana) $506,250 (project table 2). Location line: "Statewide, San Francisco Bay region, Monterey Bay region, Los Angeles County" 2.
Fixture D — 2023-08-15, Item 7b. augmentation up to $180,000 to SCCWRP (Item 7b recommended action 12).
Fixture E — 2026-06-16, Item 6c. authorization_umbrella up to $2,500,000; recipient TBD, identified in coordination with the State Water Resources Control Board 5; source Budget Act of 2024 GGRF appropriation, FY 2024/2025 5. Test the two-path duplicate (§3.1): both paths must collapse to one logical document or be recorded as a revision pair. Do not extract the $27 million appropriation as an award.
Negative fixture: one non-plastics OPC item. The parser must discover it, set plastics_flag = false, and emit no ledger rows.
9. Recall cross-checks (inference; verify each)

SCCWRP minutes line	Expected OPC trace
Dec 2022: OPC $750,000 and State Water Board $250,000, "Microplastic Sample Collection Method Standardization"; OPC approval not until early 2023 14
An OPC item in early 2023 (not yet identified)
Mar 2022: "Ocean Protection Council ($499,945)" 4 (title not visible in the excerpt)
A 2021–2022 OPC item (not yet identified)
Dec 2023: OPC through CSU Long Beach ($460,000) 4
Not a direct OPC item. Expect a parent link to 7a.5 and funder_chain = ["OPC","California Sea Grant","CSU Long Beach","SCCWRP"] as inference, flagged for review

10. Module 1 session plan
Session A — Acquire and fixture.
•	Build the discovery crawlers (meetings index, summary pages), polite fetcher with cache, hashing and manual drop folder.
•	Download the five fixture PDFs plus the RFP sidecar pages; dedupe by hash; commit extracted text and hashes (check redistribution before committing raw PDFs).
•	Write docs/OPC_ANATOMY.md confirming or correcting §4.
•	DoD: every fixture fetched or manually supplied; discovery_report.csv lists all discovered items with plastics prefilter; no row extraction yet.
Session B — Parse and validate.
•	Implement §6 steps 1–4 and §7 rules.
•	DoD: Fixtures A–E parse to exactly the expected rows (amount, recipient, sub-item, amount type); expected flags emitted; negative fixture yields no rows; unit tests pass; idempotent on re-run.
Session C — Normalize, export, watch.
•	Alias table, ROR resolution [VERIFY], plastics flag, confidence, review CSV, Parquet/CSV export, pass-through linking, and a scheduled watch job that checks the meetings index weekly and alerts on new plastics-flagged items.
•	DoD: full discovery run produces the ledger with a human-review queue; recall checks in §9 reported; README with run instructions; handoff written.

MODULE 2 — CAL EPROCURE "OPEN AND RECENT SOLICITATIONS" FEED
11. Rationale and decision
Decision: use Cal eProcure event pages as the primary source for state solicitations and notices of intent to award, and link closed solicitations to awards later through the Cal eProcure award notice or SCPRS. Aggregators are discovery-only.
Why:
•	The solicitation itself says the process runs through Cal eProcure: "questions, answers, and the notice of proposed award will be posted on the DGS Cal eProcure IFB Event Page" 15.
•	Aggregators republish with problems for a public dashboard: summaries are machine-generated ("AI Summary" and "AI Contract Breakdown" 16; "Written by GovTribe AI" 17), source links go to sign-up pages (Cleatus "View Original Source" links to a sign-up page 16), and file pages are metered (GovTribe marks the IFB file page not free 15). Neither showed an awardee for the California IFBs I examined (Cleatus 16; GovTribe 15).
•	They are still useful to find events. GovTribe's page slug ends in the Cal eProcure event ID (.../ifb-25-e0035-laboratory-analytical-services-0000039391 18), which gives a free join key.
12. What a Cal eProcure event page exposes [V]
Verified on two OEHHA events:

Field	IFB 25-E0035 (Event 0000039391)	IFB 25-E0032 (Event 0000039285)
URL	https://caleprocure.ca.gov/event/3980/0000039391	https://caleprocure.ca.gov/event/3980/0000039285
Type	"Sell Event / RFx" 19
"Sell Event / RFx" (IFB) 19

Department	Env'l Health Hazard Assessment 19
Env'l Health Hazard Assessment 19

Published / end	27/05/2026 2:00PM PDT; 10/06/2026 5:00PM PDT 19
05/14/2026 3:00 PM PDT; 05/29/2026 3:00 PM PDT 19

Codes	UNSPSC 41113300, 41104007, 70171501, 70171602 19
UNSPSC 77101900, 81102600, 77101701, 77101805 19

Award	"View Award Details" button; no award content on the page 19
"View Award Details" button; no award, notice of intent or awardee shown 19

Status	No explicit status field 19
Not stated explicitly 19


Observations the parser must respect:
•	Date format ambiguity. The two pages' readings show 27/05/2026 (day first) and 05/14/2026 (month first). One of the readings may have normalized, so the agent must determine the true page format from raw HTML and cross-check against the dates in the solicitation document (e.g., IFB available May 27, 2026, questions due June 3, bids due June 10, public bid opening June 11 15). Never parse ambiguous dates with a locale default.
•	UNSPSC, not NIGP. The event page uses UNSPSC codes (stated as UNSPSC, not NIGP 19), while GovTribe's opportunity page shows a field labeled NIGP codes. Store both with their code system.
•	No explicit status. Derive status (§14) and label it as derived.
•	Attachments. A "View Event Package" button 19 exists, but whether attachments are downloadable without login is unstated, and the "Event Search" page was not readable (it showed only site notices and a "Searching..." label 20). Don't depend on attachments; the event page text and aggregator mirrors are the data.
•	Aggregator ID vs. solicitation number. GovTribe shows the Event ID (0000039391) as the "solicitation number" while the IFB itself is numbered 25-E0035 15. Store both separately (event_id, solicitation_number).
•	URL segment 3980 appeared in both events. It may be the issuing department's code, but this is only inferred from two examples [VERIFY]. Don't assume you can build a URL from another department's code.
15 (moved up) Discovery without brute force
The event search form was not readable from my tooling, so discovery needs a verified route. In order of preference:
1.	User-supplied saved search or alert exported from a Cal eProcure account (if available), listing Event IDs. [VERIFY what Cal eProcure offers]
2.	Aggregator keyword alerts (GovTribe, Cleatus or GovDash free pages) as an Event-ID finder, using terms such as microplastic, plastic, polymer, tire wear, 6PPD, marine debris. For example, GovDash mirrors both OEHHA IFBs (25-E0032 21, 25-E0035 22). Extract the Event ID, then fetch the Cal eProcure page directly and cite that.
3.	Browser-automation fetch of the event search (a request to the user for tooling), only at low frequency, and only after checking Cal eProcure's terms of use and robots rules [VERIFY]. I did not find a Cal eProcure scraping policy.
4.	Manual drop-in list of Event IDs (config/eprocure_event_ids.txt).
Prohibited: sequential Event-ID enumeration or any high-rate crawling. Fetch only IDs that discovery has flagged, at most once per day per event.
16. Output: solicitations table (Parquet + CSV)

Field	Description
event_id, solicitation_number, bu_segment_in_url	identifiers
event_url	Cal eProcure URL (the cited record)
aggregator_urls	discovery mirrors (not cited as the source)
dept, event_type, event_version	page fields
published_at, end_at	UTC and local; parsing method recorded; date_format_verified bool
title, description_snippet (≤300 chars)	text
unspsc, nigp	code lists with system labels
value_cap_usd	only if stated (e.g., $250,000 maximum budget 15), from the page or a mirror; flag cap_source
contact_listed	boolean only; no personal data
pre_bid_conf_text	verbatim
deliverable_dates	key dates parsed from the description when present (e.g., Analytical Project Plan due September 30, 2026 15)

status_derived	see §14
noia_date, award_detail_checked_at	from the event page when visible
plastics_flag, plastics_terms, relevance_notes	relevance
scprs_link_id, scprs_supplier, scprs_grand_total, link_confidence, link_evidence	award linkage (§17)
source_sha256, retrieved_at, acquisition_method	provenance

Relevance. Keyword matching on title and description: microplastic*, nanoplastic*, plastic*, polymer, tire wear/tire-wear, 6PPD, marine debris, "SB 1147", etc. UNSPSC codes alone don't discriminate (water-quality codes cover many non-plastics events), so use them only as a secondary hint and a recall sweep. Items matching only generic water-lab terms → plastics_flag = "maybe".
14. Lifecycle (derived status)

State	Rule
open	now < end_at
closed_pending	now ≥ end_at, no notice of intent or award found
intent_to_award	a notice of intent to award is visible on the event page
awarded	a SCPRS or event award record is matched (§17) with sufficient confidence
cancelled_or_revised	event version changes or the page disappears (record the old version)
unknown	page unreachable

Show the derived status on the dashboard with the note "Derived from public pages; confirm on Cal eProcure."
17. Linking a closed solicitation to its award
Route 1 — Cal eProcure award details. The event page has a "View Award Details" button 19. Test whether it exposes the notice of intent to award, awardee and amount when logged out [VERIFY]. If it does, parse it and record noia_date, awardee name and amount with amount_type = award_value.
Route 2 — SCPRS (primary fallback). The SCPRS search offers fields Department, Purchase Document #, Supplier ID, Supplier Name, Description, Acquisition Type, Acquisition Method, Transaction Start Date, Certification Types and UNSPSC 23, with result columns including Supplier Name, Status, Purchase Document #, Start Date, End Date and Grand Total 23. It offers two Excel downloads: the results grid (up to 65,000 rows) and detailed line items (up to 45,000 rows) 23. A parameter is required: "System will NOT complete download action without the selection of a single search parameter" 23. Data is refreshed every 24 hours (Monday through Friday) 23.
Matching procedure (deterministic, review-flagged):
1.	Query SCPRS by department, a start-date window beginning at the event's end_at, and a description keyword or UNSPSC; export the results grid.
2.	Score candidates: same department (required); start date within a configurable window after end_at or the notice date; Grand Total ≤ value_cap_usd (when known); UNSPSC overlap; description token overlap with the solicitation title; supplier name consistent with any awardee found in Route 1.
3.	Confidence tiers: high (≥3 independent signals including an exact solicitation-number or event-ID match in the description or purchase-document fields), medium, low. Anything below high sets needs_review.
4.	Store the SCPRS Purchase Document # and keep the link evidence.
Cautions.
•	Whether SCPRS rows carry the Cal eProcure event ID or the solicitation number is unknown [VERIFY]. If they do, that is the strongest key.
•	SCPRS completeness: SCPRS is a centralized database of acquisitions of goods and services, and since July 1, 2016 agencies must report all acquisitions regardless of dollar amount 24. A State Auditor review of 2011–2015 data nonetheless concluded SCPRS "misrepresented or did not include many of the State's contracts and their associated amendments" 25. That is old data, but it argues for treating an unmatched solicitation as "no award found yet", never as "not awarded".
•	Contracts can post weeks after the notice of intent; re-check closed events on a schedule (for example weekly for 90 days).
•	A SCPRS Grand Total can combine amendments. Never present it as the original bid value.
18. Fixtures and acceptance tests (Module 2)
Fixture F — IFB 25-E0035 (Event 0000039391). Expected: Dept OEHHA; event type "Sell Event / RFx"; published and end dates matching the solicitation text (published May 27, 2026; bids due June 10, 2026, 5:00 p.m. PST; $250,000 maximum budget 15); UNSPSC list as in §12; scope microplastics and associated chemicals in drinking and bottled water (particles greater than 200±100 nanometers to 500 micrometers 19); derived status after June 11, 2026 = closed_pending unless an award is found; plastics_flag = true; contact stored only as a boolean.
Fixture G — IFB 25-E0032 (Event 0000039285). Expected: published May 14, 2026; end May 29, 2026; water sampling to support microplastics research (SB 1147 (Portantino 2024); notice of intent to award expected June 3, 2026; proposed start June 15, 2026 26); UNSPSC list as in §12; plastics_flag = true.
Date test. The parser must produce unambiguous UTC datetimes for both fixtures despite the format difference noted in §12, or flag date_format_unverified and not publish.
Aggregator cross-check. For each fixture, the GovTribe slug's trailing ID equals the Cal eProcure Event ID (GovTribe page for 25-E0035 ends in 0000039391 18).
Negative fixture. One non-plastics California event (e.g., generic IT services) must be discovered or supplied and not flagged.
Linking test (once awards exist). For each fixture, run the SCPRS procedure and record the result (high/medium/low/none) and the evidence. A none result is a valid, documented outcome.
19. Dashboard panel specification ("Open and recent solicitations")
•	List of events sorted by end_at (open first, then recently closed), with department, title, due date, derived-status badge, value_cap_usd if stated, and a link to the Cal eProcure page (not the aggregator).
•	Filters: department, status, date range, relevance (true / maybe).
•	Linked-award sub-row when link_confidence is high or medium, with SCPRS supplier and Grand Total, clearly labeled "from SCPRS; may include amendments".
•	Footnote: dates and status are derived from public pages and may lag; confirm on Cal eProcure.
•	Policy item (owner decision G-4): whether to display solicitations issued by the owner's own agency (OEHHA). They are public, but the dashboard carries an independence disclaimer. Default: include, labeled as public Cal eProcure listings, no commentary.
20. Module 2 session plan
Session D — Fetch and parse event pages.
•	Build a polite fetcher for flagged event IDs, an HTML parser for §12 fields, date-format determination, UNSPSC/NIGP handling, hashing, caching and a manual drop-in.
•	Fixtures F and G committed (text only unless redistribution is confirmed).
•	DoD: both fixtures parse to expected values; date test passes; no personal contact data in outputs; docs/EPROCURE_ANATOMY.md records what the pages really expose, including whether "View Award Details" and attachments need login.
Session E — Discovery, relevance and lifecycle.
•	Implement the discovery routes (§15) that are verified, the relevance rules, lifecycle states and a daily watch workflow; add the aggregator-ID cross-check.
•	DoD: given a list of discovered Event IDs, the pipeline produces solicitations with derived status; re-runs are idempotent; version changes recorded; weekly re-check of closed events scheduled.
Session F — Award linking and panel data.
•	Test Route 1 (award details) and implement Route 2 (SCPRS matching with Excel import), confidence tiers and a review CSV; export panel JSON; implement the dashboard panel if the front end exists.
•	DoD: linking runs on Fixtures F and G; results and evidence recorded; panel data validates against the schema; handoff written.

21. Open decisions for the owner

ID	Question	Default
G-1	Include OPC grants approved only by delegated Executive Director authority?	Out of scope; log the gap
G-2	Scope of "plastics-related" for solicitations (include generic microplastics-adjacent lab and sampling services)?	Include maybe items for review
G-3	How to supply discovery: Cal eProcure saved-search export, aggregator alerts, or browser automation?	Aggregator alerts as Event-ID finder, then fetch from Cal eProcure
G-4	Show OEHHA's own solicitations on the public dashboard?	Include, labeled as public Cal eProcure listings
G-5	Redistribution: commit source PDFs/pages or only extracted fields and hashes?	Extracted fields and hashes only
G-6	Window for re-checking closed events for award postings	Weekly for 90 days

22. Tool requests the agent should consider
•	Browser-automation tool (for JavaScript-rendered Cal eProcure pages), subject to terms-of-use review.
•	DuckDB CLI (to inspect Parquet and SCPRS Excel exports without loading them into context).
•	An Excel reader (SCPRS downloads are Excel, not CSV).
•	A PDF text-extraction library with layout and font information (OPC PDFs).
•	A scheduler or GitHub Actions access for the daily and weekly watch jobs.
References
1.	Consideration of Authorization to Disburse Funds to Address Microplastics in Coastal and Marine Ecosystems. Retrieved 2026-11-05, from https://opc.ca.gov/webmaster/ftp/pdf/agenda_items/20200619/Item9_MicroplasticsProjects_FINAL.pdf
2.	OPC Meeting August 15 2023 Agenda Item 7a. Retrieved 2026-11-05, from https://opc.ca.gov/wp-content/uploads/2023/07/Item-7a-CASG-Microplastic-Research-508.pdf
3.	Study assessing the efficacy of microplastic removal with various wastewater treatment methods - California Ocean Protection Council. Retrieved 2026-11-05, from https://opc.ca.gov/directory/projects/study-assessing-the-efficacy-of-microplastic-removal-with-various-wastewater-treatment-methods
4.	ftp.sccwrp.org. Retrieved 2026-11-05, from https://ftp.sccwrp.org/pub/download/DOCUMENTS/Minutes/Commission/2023/2312CommMin.pdf
5.	OPC Meeting June 16 2026 Item 6c: Plastics Monitoring Pilot. Retrieved 2026-11-05, from https://opc.ca.gov/wp-content/uploads/2026/06/Item-6c-Plastics-Monitoring-508.pdf
6.	Ocean Protection Council Meetings - California Ocean Protection Council. Retrieved 2026-11-05, from https://opc.ca.gov/meetings
7.	Ocean Protection Council Meeting - June 4, 2024 - Teleconference and Public Forum - California Ocean Protection Council. Retrieved 2026-11-05, from https://opc.ca.gov/2024/05/council-meeting-june-4-2024
8.	Ocean Protection Council Meeting - March 23, 2026 - Teleconference and Public Forum - California Ocean Protection Council. Retrieved 2026-11-05, from https://opc.ca.gov/2026/01/ocean-protection-council-meeting-march-23-2026
9.	Updates from the August 15, 2023 Council Meeting - California Ocean Protection Council. Retrieved 2026-11-05, from https://opc.ca.gov/2023/08/august-15-2023-council-meeting-summary
10.	Request Rejected. Retrieved 2026-11-05, from https://opc.ca.gov/wp-content/uploads/2026/05/OLS-Accomplishments-Report-2026-508.pdf
11.	Item 7A Competitive Call Microplastics Research 508. Retrieved 2026-11-05, from https://opc.ca.gov/webmaster/ftp/pdf/agenda_items/20230124/Item-7a-Competitive-Call-Microplastics-Research-508.pdf
12.	OPC Meeting August 15 2023 Agenda Item 7b. Retrieved 2026-11-05, from https://opc.ca.gov/wp-content/uploads/2023/07/Item-7b-Southern-California-Bight-Microplastics-Analysis-508.pdf
13.	2023 Microplastic Research Program: Request for Proposals | California Sea Grant. Retrieved 2026-11-05, from https://caseagrant.ucsd.edu/funding/2023-microplastic-research-program-request-proposals
14.	MINUTES OF THE REGULAR MEETING. Retrieved 2026-11-05, from https://ftp.sccwrp.org/pub/download/DOCUMENTS/Minutes/Commission/2022/2212CommMin.pdf
15.	IFB 25-E0035 Laboratory Analytical Services (0000039391): IFB_25-E0035_Laboratory_Analytical_Services.pdf – California, due Jun 11, 2026 | GovTribe. Retrieved 2026-11-05, from https://govtribe.com/file/government-file/ifb-25-e0035-laboratory-analytical-services-dot-pdf
16.	IFB 25-E0035 Laboratory Analytical Services | CLEATUS. Retrieved 2026-11-05, from https://www.cleat.ai/government/contracts/ifb-25-e0035-laboratory-analytical-services-joaf
17.	IFB 25-E0032 Water Sampling Services (0000039285) – California Contract Opportunity | GovTribe. Retrieved 2026-11-05, from https://govtribe.com/opportunity/state-local-contract-opportunity/ifb-25-e0032-water-sampling-services-0000039285
18.	IFB 25-E0035 Laboratory Analytical Services (0000039391) – California Contract Opportunity | GovTribe. Retrieved 2026-11-05, from https://govtribe.com/opportunity/state-local-contract-opportunity/ifb-25-e0035-laboratory-analytical-services-0000039391
19.	Event Details. Retrieved 2026-11-05, from https://caleprocure.ca.gov/event/3980/0000039391
20.	Event Search. Retrieved 2026-11-05, from https://caleprocure.ca.gov/pages/Events-BS3/event-search.aspx
21.	Ifb 25-E0032 Water Sampling Services. Retrieved 2026-11-05, from https://discover.govdash.com/solicitations/019e2fd8-8e51-74b1-932c-3311fea96af5--ifb-25-e0032-water-sampling-services
22.	Ifb 25-E0035 Laboratory Analytical Services. Retrieved 2026-11-05, from https://discover.govdash.com/solicitations/019e72ee-6682-7732-9f47-9fe92bbd9f46--ifb-25-e0035-laboratory-analytical-services
23.	FI$Cal SCPRS Search. Retrieved 2026-11-05, from https://caleprocure.ca.gov/pages/SCPRSSearch/scprs-search.aspx
24.	Microsoft Word - SCM Vol 1 rev 06212023 final .docx. Retrieved 2026-11-05, from https://www.dgs.ca.gov/-/media/Divisions/OLS/Resources/SCM-V1---06-2024-Update/SCM-V1-Ch4-June-2024-Edition.pdf
25.	Department of General Services and California Department of Technology: Neither Entity Has Provided the Oversight Necessary to Ensure That State Agencies Consistently Use the Competitive Bidding Process. Retrieved 2026-11-05, from https://information.auditor.ca.gov/pdfs/reports/2016-124.pdf
26.	IFB 25-E0032 Water Sampling Services (0000039285): Packet – California, due May 29, 2026 | GovTribe. Retrieved 2026-11-05, from https://govtribe.com/file/government-file/ifb-25-e0032-water-sampling-services-packet-dot-pdf
