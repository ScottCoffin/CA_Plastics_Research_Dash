Add-on Spec A4 — Community Groups layer (Ambassador-tagged)
Project: CA Plastics Research Atlas (Plastiverse Live) · Task prefix: CG- · Depends on: base spec, A1–A3 · Audience: the owner's IDE agent, the Ambassador coordinatorStatus: v5. BFFP permission for retrieval obtained (owner); organisations only, single-person practices excluded, no public count of excluded entries; tagging by volunteer Ambassadors via existing infrastructure; roster extraction built by the IDE agent; no automated tagging; geography-first tree with two alternative hierarchies; full view set; Sankey package and map asset approved.

0. Rules (A4)
1.	No automated tagging. No script, crawler, scraper or language model may write a value into any published tag field. Every published tag is entered by an Ambassador (opaque internal ID) and reviewed per §7. Optional tooling (CG-X) may assist a human but never writes tags. Roster extraction (§4) writes identity fields only.
2.	Roster ≠ tags. The BFFP roster supplies identity fields (name, country/region, URL, provenance). Everything else comes from Ambassadors.
3.	Organisations only — hard exclusion of individuals and single-person practices. They are never admitted to the roster, the public dataset, derived files, logs or committed manifests (§4.4). Admission requires positive evidence of organisational status; heuristics can exclude but can never admit.
4.	Evidence or not_stated. Each evidenced facet carries an evidence URL, access date and a quote of ≤25 words, or an explicit not_stated / cannot_determine with a reason (§6).
5.	Provenance is not endorsement. BFFP membership is shown as a neutral provenance fact (§9.2). It is never a tag, score, rank or inclusion criterion for plastics focus.
6.	No rankings or scores of groups. Group lists are never sorted by a computed score. Aggregate charts (counts by country, sector, activity) may be sorted by count with an explicit note that counts reflect tagging coverage, not group importance.
7.	Static-site constraint (A3 rule 5). The published site is static and $0 to host. New dependencies, services or backends need owner approval (A4-D9), except the two approved under A4-D22.
8.	Honest coverage. Every chart and table shows its denominator (tagged groups ÷ admitted roster organisations, by region). Absence of a tag means "not yet tagged", never "no plastics work".
9.	Citation style in documentation: in-text (Authors Year); no numbered or superscript hyperlinks (A3 rule 13).
10.	Memory protocol: log every decision in .agent/DECISIONS.md under A4-D#; do not silently change taxonomy values.
11.	Ambassador infrastructure is the system of record for Ambassadors. This spec does not re-create it; it defines the contract (§5.5, §8.3) the Atlas needs from it.
12.	The repository is public. Anything committed is public. Names or counts of excluded entries, raw BFFP pages and Ambassador personal data must never be committed (§4.3, §10).

1. Scope
In scope: a groups layer covering organisations listed as members of the Break Free From Plastic (BFFP) movement, plus Ambassador-suggested organisations. It records what each organisation is, what it does, where it works, and how plastics-focused it is, and presents this in a geography-first collapsible tree (with two alternative hierarchies), a network view, and coverage, map, composition, flow, participation, co-occurrence and language views (§9).
Size context. BFFP states that more than 13,000 organizations and individual supporters from across the world have joined the #BreakFreeFromPlastic movement 1 (BFFP homepage). That figure includes individuals, which this layer excludes, so the organisation count will be lower and the 13,000 figure must not be used as a denominator. The admitted roster size is measured by the extractor (§4.3).
Planning arithmetic (inference, not a finding). If N organisations each took 3–5 minutes for Tier-1 tagging, effort is N × 3–5 ÷ 60 hours; for N = 13,000 (an upper bound) that is about 650–1,080 hours. Plan in regional batches; do not promise full coverage.
Out of scope: automated classification; scraping group websites for tags; contact with groups beyond the optional confirmation step (§5.8); inferred inter-group relationships; funding data; rankings; linking groups to Atlas papers (possible later extension).

2. Decisions

ID	Decision	Status
A4-D0	Groups layer is an add-on module; no change to A1–A3 paper-level schemas	Confirmed
A4-D1	Roster extraction is built by the IDE agent. BFFP has given the owner permission for retrieval from its site (owner statement 2026-11-26). The owner records the permission details (G0, §4.1) in DECISIONS; discovery precedes extraction	Resolved; record details pending
A4-D2	Individuals are excluded from all outputs	Confirmed; see A4-D20
A4-D3	Groups without a plastics focus are shown in a separate, clearly named adjacent layer; Ambassadors can fill in details	Resolved (owner)
A4-D4	Taxonomy facets F1–F14 as §3; Tier 1 required, Tier 2 optional	Proposed
A4-D5	Evidence rule: URL + date + ≤25-word quote, or not_stated / cannot_determine	Proposed
A4-D6	Group-level plastics_centrality reuses A3's graded values with group-specific rules (§6.2)	Proposed
A4-D7	BFFP membership is provenance only	Confirmed
A4-D8	Auto-prelabel + review design (v1)	Superseded by A4-D11
A4-D9	New dependencies, paid services or backends need owner approval (except A4-D22)	Confirmed
A4-D10	Other directories are link-only; no bulk reuse without a licence check	Confirmed
A4-D11	Tagging is performed by volunteer Ambassadors, assigned by region; no scraping/crawling-based tagging	Resolved (owner)
A4-D12	BFFP membership may be shown publicly, neutral wording "Listed as a BFFP member as of ⟨date⟩"	Resolved (owner)
A4-D13	Submission/queue platform = the existing Ambassador infrastructure; the IDE agent documents its interface (§5.5); the CSV contract (§8.3) is the fallback seam	Resolved; interface documentation pending
A4-D14	Ambassador attribution: aggregate by default; named only with explicit consent	Proposed
A4-D15	incidental and none → adjacent layer	Confirmed (owner)
A4-D16	Untagged roster entries appear in a searchable roster table with a "Help tag this group" call-to-action; not drawn as graph nodes by default	Confirmed (owner)
A4-D17	Contributor licence/agreement for Ambassador-entered data (e.g., CC BY 4.0 candidate)	Open — owner decision
A4-D18	Visualisation module (§9)	Resolved: scope as §9
A4-D19	Tree default hierarchy = geography-first; function-first and centrality-first alternatives ship (owner confirmed 2026-11-26). Each group appears once, under its principal activity in activity-based levels; an "all activities" toggle shows distinct counts	Resolved
A4-D20	Organisations-only rule (§4.4): positive admission test; individuals and single-person practices excluded by default; excluded entries not retained	Resolved (single-person exclusion confirmed by owner 2026-11-26)
A4-D21	All extra views are in scope: V-SANKEY, V-PART, V-COOC, V-LANG, plus V-TREE, V-NET, V-COV, V-MAP, V-HEAT, V-COMP, V-EVID	Resolved
A4-D22	Explicit owner approval (2026-11-26): the agent may add one small, permissively licensed Sankey layout package and one map geometry/centroid asset. Before use, log name, version, licence and source in DECISIONS. Any other new dependency needs approval under A4-D9	Approved
A4-D23	Raw-cache retention 30 days (or sooner once parsing is verified)	Resolved (owner: "30 days fine")
A4-D24	No public display or committed record of the count of entries excluded as individuals or single-person practices. The methods page may state the exclusion rule but not a number	Resolved (owner: "Don't publish aggregate count")


3. Taxonomy facets
Tier 1 (required for ambassador_tagged): F1, F2, F3, F4, F7, F8. Tier 2 (optional): F5, F6, F9–F14.

#	Facet	Values / form	Notes
F1	entity_type	organisation, network_coalition, programme_project, campaign, informal_group, chapter_branch, other	chapter_branch requires parent_group_id when the parent is on the roster. All values describe collective entities, never individuals
F2	sector	ngo_civil_society, community_informal, foundation, academia_research, private_sector, government, igo, other	Derived from the GPML stakeholder types: Governments, Scientific and Technological Community and Academia, Business, Industry and Private Sector, NGOs and Foundations, IGOs, and Private Citizens 2 (GPML Digital Platform Concept Document). The "Private Citizens" type is deliberately not carried over. community_informal is an extension for unincorporated collective groups
F3	plastics_centrality	primary, substantial, incidental, none, cannot_determine	Rules in §6.2; drives the adjacent layer
F4	primary_activities[] (1–3, ordered most central first)	working labels: advocacy_campaigning, policy_governance, research_monitoring, education_awareness, cleanup_removal, waste_management_recycling, reuse_refill_alternatives, business_innovation, community_organising_justice, coalition_building_capacity, funding_grantmaking, legal_action, other	Based on GPML initiative categories plus extensions (cleanup_removal, coalition_building_capacity, funding_grantmaking, legal_action). [VERIFY] exact GPML labels at CG-4. The first value is the "principal activity" used by tree, Sankey and heatmaps
F5	participation_in_science	contractual, contributory, collaborative, co_created, collegial, not_applicable	Only for groups that do or host monitoring/research. The CAISE report describes contributory projects (designed by scientists, with the public primarily contributing data), collaborative projects, and co-created projects (designed by scientists and members of the public working together) 3 (Bonney et al. 2009a); the 2012 Ecology & Society PPSR framework adds contractual and collegial contributions 4

F6	legal_form	registered_nonprofit, unincorporated, company, public_body, university, unknown	Optional free-text legal_form_note with evidence (e.g., 501(c)(3))
F7	geographic_scope + places[]	scope: local, subnational, national, regional_multi_country, global; places: ISO 3166-1/-2 codes (≤5)
F8	evidence[]	per-facet objects: facet, url, accessed_at, quote (≤25 words) or not_stated	§6.1
F9	themes[]	A3 §5.4 theme tags	Only when stated on the group's own pages
F10	analytic_lens[]	A3 §5.4 lens values	Rarely needed; default empty
F11	constituency[]	frontline_fenceline, indigenous, youth, waste_workers, coastal_fishing, faith, consumers, industry, other	Only when self-described
F12	external_codes	NTEE / ICNPO looked up by the build, never typed by Ambassadors	Optional; empty unless a lookup source is approved
F13	stated_affiliations[]	each: target_group_id (roster match) or target_name (external organisation), relation ∈ {member_of, partner_of, fiscal_sponsor, parent_of, funded_by}, plus evidence	Only relations the group itself states on its own pages; drives group–group edges in the network view (§9.4). Never inferred. Targets must be organisations
F14	website_languages[]	ISO 639-1 codes of the languages in which the group's own pages are published	Drives V-LANG; recorded by the Ambassador at tagging time

System-set provenance fields (not Ambassador-set): source, org_status, bffp_listed, bffp_listed_asof, roster_retrieved_at, status, tagged_by (opaque; never published), tagged_at, reviewed_by, reviewed_at.

4. Roster extraction (built by the IDE agent)
Purpose: obtain name, country/region and URL for each BFFP-listed organisation. Nothing else is extracted. Tags come only from Ambassadors (rule 1).
4.1 Permission record (G0) — owner action
The owner reports that BFFP has given permission for retrieval from its site. Record in .agent/DECISIONS.md (A4-D1):
•	date and form of the permission (written/verbal; who at BFFP, by role),
•	scope: which pages/data, any rate limit, frequency, retention or attribution conditions BFFP specified,
•	whether it covers public display of member names (A4-D12 already decides public display is acceptable to the owner; record BFFP's position if known).
Permission does not remove the technical safeguards below. If robots.txt, authentication or rate limiting blocks access in a way the permission did not anticipate, stop and ask the owner to clarify with BFFP; do not circumvent. My earlier fetch of BFFP's robots.txt failed (a tool error, not evidence), and the members widget on the pages I read earlier rendered only after client-side loading, so [VERIFY] both in a real browser at CG-1.
4.2 Phase 1 — Discovery (CG-1), no bulk retrieval
Produce docs/bffp_roster_discovery.md answering:
•	Which public BFFP page(s) list members (directory, map, per-country pages)? Server-rendered, or loaded by a data request from the page?
•	If loaded by a request the public page itself makes, record its URL pattern, parameters, pagination and response fields. Discover it by reading the page source and linked scripts or the browser network panel; do not guess undocumented endpoints.
•	What do robots.txt, the privacy policy and any terms say about automated access? Quote verbatim with URL and date. Note any conditions from the permission (§4.1).
•	Which fields exist per member, and is there a field that distinguishes organisations from individuals (e.g., a member type)? Record the exact field name and values. This determines the admission route in §4.4.
•	Approximate total and the organisation/individual split, if observable (record in the local notes only; see A4-D24).
•	Is there a sitemap path listing member pages?
Stop conditions (report to owner): login or CAPTCHA required; robots.txt disallows the path; terms or permission conditions prohibit the intended access; the list is not publicly reachable. Do not bypass authentication, CAPTCHAs, rate limits or technical blocks.
4.3 Phase 2 — Extractor (CG-2)
•	Seam: a RosterSource interface (fetch() -> Iterable[RawEntry]) with adapters (BffpPublicSource, CsvFileSource). A later BFFP-supplied export is another adapter.
•	Language/dependencies: Python ≥3.11; use libraries already in the repo, or the standard library. A headless browser is allowed only with approval (A4-D9) and only if no public data request exists and automated access is permitted.
•	Politeness: identifying User-Agent with a contact address; ≤1 request/second unless BFFP specified otherwise; cache responses; honour robots.txt; stop on 403/429; at most two retries with back-off; single pass; re-run no more than quarterly (or as BFFP agreed); checkpoint and resume.
•	Raw cache and retention (A4-D23): raw responses go under a gitignored data/raw/bffp/<date>/ with a sha256 manifest, are never committed or uploaded, and are purged after parsing is verified or 30 days, whichever is sooner. The raw cache may contain individuals' entries, which is why retention is short.
•	Two manifests (rule 12, A4-D24):
◦	roster_manifest.local.json — gitignored, never published: retrieved_at, source URLs, request count, status-code counts, parser version, entries fetched, admitted by org_status, excluded, ambiguous, sha256 of raw inputs.
◦	roster_manifest.json — committable and publishable: retrieved_at, parser version, admitted-by-org_status counts and source URLs only. It must not include the fetched total or any excluded/ambiguous count, because the excluded count is derivable as fetched − admitted.
◦	Neither manifest, nor any log, contains the name of an excluded entry.
•	Structural-change guard: fail loudly if the entry count drops by more than a threshold versus the previous run (proposal: 20%, evaluated against the local manifest) or expected fields vanish; require owner acknowledgement. Never publish a silently truncated roster.
•	Tests use saved fixture pages (synthetic or anonymised); CI makes no live calls.
4.4 Organisations-only admission rule (A4-D20) and normalisation
org_status values

Value	Meaning	Admitted to public build?
source_declared_org	The source's own member-type field (identified in discovery) says organisation/business/NGO or equivalent	Yes
heuristic_org	No usable source type field, but the entry has an organisational web domain and does not match person-name patterns	Yes, flagged for Ambassador confirmation
human_confirmed_org	A coordinator or the owner confirmed it from the entry's public identity	Yes
ambiguous	Cannot be decided automatically (e.g., personal name with a business-like suffix, no URL)	No until a human decides
excluded_individual	Source type says individual/supporter; or the entry is a personal name, personal-email domain or personal social-profile URL; or a single-person practice (sole trader, freelance consultant, artist trading under their own name)	No — dropped

Rules
1.	Positive admission only. Only the first three values are admitted. Heuristics may demote an entry to ambiguous or excluded_individual; they can never promote an ambiguous entry.
2.	Single-person practices are excluded by default (owner confirmed). A human may admit one only by confirming a collective organisational identity (e.g., an incorporated studio with a staff page); the reason is logged in DECISIONS or the audit log without naming the entry in a public file.
3.	Data minimisation: excluded_individual rows are dropped at parse time and never reach roster.json, derived files, logs or the committed manifest. Counts are kept only in the gitignored local manifest.
4.	Quarantine: ambiguous entries are held in a local, gitignored roster_quarantine.csv, decided by a human, then deleted. Entries not decided within the review window are discarded.
5.	Ambassador check: heuristic_org entries are confirmed at tagging. If an Ambassador selects not_an_organisation, the record is removed from all public outputs and its name purged from the working store.
6.	Suggest-a-group entries (§5.4) pass the same test.
7.	Denominators (rule 8) count admitted organisations only. No public page shows how many entries were excluded (A4-D24); the methods page may describe the rule in words.
Normalisation and dedupe
•	Allow-list: name, name_alt[], country, region_label, url, bffp_listed, org_status, roster_retrieved_at. Drop everything else at read time.
•	Unicode NFC; trim; collapse whitespace; keep original-script names verbatim.
•	group_id = stable hash of (casefolded name, ISO country, URL registrable domain).
•	Dedupe on group_id, then fuzzy-match within country (same domain, or token-set similarity ≥0.9); route near-matches to a human dupe_review list; never auto-merge near-matches.
•	Region mapping: country → Ambassador region scheme (§5.2); no country → region_unknown for the coordinator.
•	Reconciliation on re-import: diff against the stored roster. Added → unlabelled; removed → roster_removed (tags kept, BFFP wording suppressed); changed URL → url_changed task.
4.5 Optional link-rot check (CG-X1; needs approval)
One cached HTTP HEAD per URL, same politeness rules; records url_status only.

5. Ambassador programme and queue
5.1 Roles
Ambassador (volunteer tagger); regional lead (optional reviewer/adjudicator); coordinator (runs the existing Ambassador programme: assignment batches, agreements, correction channel); dataset owner (final taxonomy decisions).
5.2 Regions and assignment
•	Region scheme: country (ISO 3166-1) → UN M49 sub-region, with US-CA as a named subnational area; Norway a prepared region. If the existing infrastructure defines Ambassador regions, adopt and map its scheme (§5.5).
•	Assignment unit: a batch of 20–30 roster entries from one country/region (proposal).
•	Priority: (1) California; (2) regions with an active Ambassador; (3) regions in preparation; (4) unassigned pool.
•	Language fit: by the group's website language where known; otherwise by country; entries can be returned as needs_language_support.
•	Claim and lease: 30-day lease (proposal), renewable once; unfinished entries return to the pool; one holder per entry except the double-tag sample (§7.2).
•	Conflict of interest: an Ambassador must not tag an organisation they work for, formally lead or fund.
5.3 Task states
unlabelled → assigned → ambassador_tagged → reviewed → group_confirmed (optional)
Side states: cannot_determine (with reason), needs_language_support, dupe_review, quarantined, roster_removed, correction_requested.

State	Public display
unlabelled / assigned	roster table only (§9.3)
ambassador_tagged	shown, badge "Volunteer-tagged"
reviewed	badge "Reviewed"
group_confirmed	badge "Confirmed by group"
cannot_determine	roster table with reason

5.4 Tagging form (minimal path)
Pre-filled with roster fields; Ambassadors edit only tag fields.
1.	Open the group's website (or the best independent source).
2.	Confirm the entry is a collective organisation, not an individual or single-person practice (if not: not_an_organisation, §4.4 rule 5).
3.	Check in order: home page, About/Mission, Programmes/Campaigns, then a site search for "plastic" (time-box about 5 minutes).
4.	Fill Tier 1 (F1, F2, F3, F4, F7) with evidence per facet (F8). Record website_languages[] (F14) if known.
5.	Optionally fill Tier 2, including stated_affiliations[] (F13) when the group's own page lists partners or parent bodies.
6.	If no determination is possible: cannot_determine plus a reason (no_web_presence, dead_link, language_barrier, insufficient_information, not_an_organisation, conflict_of_interest).
Mandatory checks: F3 set (possibly cannot_determine); F4 has 1–3 values; evidence for F3 and F4; quote ≤25 words.Suggest-a-group: Ambassadors may add a missing organisation (source: ambassador_suggested, with URL), shown without BFFP wording.
5.5 Integration with the existing Ambassador infrastructure (A4-D13, CG-5)
I have not seen the infrastructure. Before building anything in §5.2–5.4, the IDE agent writes docs/ambassador_infrastructure.md answering:
1.	Where are Ambassador records kept (sign-up, region, languages, status), and who administers them?
2.	Does it already support assigning items to Ambassadors, and how do Ambassadors currently submit work (form, sheet, app, repository)?
3.	Can it export structured data (CSV/JSON) on a schedule or on demand, and can it enforce controlled vocabularies?
4.	What authentication and data-protection arrangements apply (personal data must stay outside the public repo)?
5.	What region scheme and language list does it use?
Adaptation rule: reuse what exists; build only what is missing. The Atlas needs: (a) roster entries delivered to Ambassadors as assignments; (b) submissions returned as rows meeting the CSV contract (§8.3); (c) an opaque ambassador_id per submission. Where the infrastructure cannot enforce vocabularies or evidence rules, ingest validation (§7.1) is the enforcement point. If it cannot hold assignments, build the assignment engine (CG-6) against the CSV seam; any new service needs approval (A4-D9).
5.6 Training and guide
An Ambassador guide (≤6 pages): facet definitions, §6.2 decision rules, the organisation check, worked examples, evidence rule, time box, COI rule. Every new Ambassador tags the five calibration cases (§6.4) before receiving a batch; disagreements are discussed, not penalised. Re-calibrate after any taxonomy change.
5.7 Attribution and privacy
Ambassadors have an opaque ambassador_id; names and contact details stay in the Ambassador infrastructure, outside the public repo. Public pages credit Ambassadors in aggregate by default; named credit needs explicit, withdrawable consent (A4-D14).
5.8 Group confirmation (optional)
The coordinator may invite a group to confirm or correct its record via the correction channel (§10.3). Confirmation is by a reply from an address at the group's own domain; record the date only, not the person.

6. Evidence rules and decision rules
6.1 Evidence
•	Sources: the group's own website or official channel; an official registry; a reliable independent source. Social-media pages count only when no own site exists.
•	Per facet: url, accessed_at (ISO date), quote (≤25 words, verbatim, in the source language) or not_stated.
•	A separate note (≤200 characters) may give an English gloss. An archived-copy URL is optional.
•	At review, the reviewer confirms the quote appears at the URL.
6.2 plastics_centrality (group level)

Value	Rule
primary	Plastics (pollution, waste, policy, production, health) is the stated core mission or flagship programme
substantial	Plastics is one of up to three named programme areas, or has a dedicated campaign/page/report
incidental	Mentioned only in passing, in a long list of topics, or only in a BFFP-membership statement
none	No plastics mention after the §5.4 checks
cannot_determine	Site unavailable or unreadable

BFFP membership alone never establishes plastics focus (rule 5). Rate on what the group states about its own work: a group with relevant work but no plastics wording (e.g., fenceline justice on petrochemical facilities) is substantial only if it links that work to plastics or plastic production in its own words; otherwise none, with a note. The reviewer arbitrates.
6.3 Other rules
•	F4: what the group says it does, not what it supports; order most central first.
•	F5: only when monitoring or research participation is described.
•	F7: the widest scope claimed for the group's own work, not its network's.
•	Chapters: tag on the chapter's own evidence; set parent_group_id if the parent is on the roster.
6.4 Calibration cases (proposed reference tags)
Provisional readings of group self-descriptions captured earlier in this project. [VERIFY] and re-capture evidence quotes at guide-writing time; the owner finalises.

Case	Provisional tags	Why included
Inland Ocean Coalition	programme_project/network_coalition; ngo; primary; research_monitoring + education_awareness	Programme hosted by a larger nonprofit (fiscal-sponsor pattern; tests F13)
PNW Consortium on Plastics	network_coalition; mixed academia/ngo; primary; research_monitoring	Multi-sector network; sector is a judgement call
Paddle Out Plastic	organisation; ngo; primary; cleanup_removal	Clean-cut volunteer cleanup group
The Ocean Cleanup	organisation; ngo; primary; cleanup_removal + business_innovation	Hybrid nonprofit/technology; multi-activity ordering
UNIDOS Network	network_coalition/community_informal; none (plastics not mentioned on the page reviewed); community_organising_justice	Tests the adjacent layer and "rate what is stated"

Add two synthetic training cases for the organisation check: a single-person consultancy (expected exclusion) and an entry whose URL is a personal social-media profile (expected exclusion).

7. Quality assurance
7.1 Automated validation (not tagging)
Schema validity; controlled vocabularies; evidence present; quote ≤25 words; ISO codes; duplicates; legal state transitions; org_status admissibility. This is the enforcement point whatever platform produced the submission.
7.2 Double-tag sample and agreement
•	A random 10% of each batch (proposal) is tagged blind by a second Ambassador.
•	Agreement per field: weighted κ for the ordinal plastics_centrality; PABAK or Gwet's AC1 for skewed or nominal fields (A3 BQ-G5). Report prevalence and intervals alongside each statistic.
•	Disagreements go to the regional lead or reviewer; both tags stay in the audit log.
7.3 Review
Reviewer checks ambassador_tagged records against evidence: 100% of primary ratings in each Ambassador's first batch, then sampling (e.g., 20%, proposal). Edits are logged with a reason code.
7.4 Precision card
Per field and region: audited n; reviewer-agreement proportion with a Wilson 95% interval; cannot_determine counts; coverage (tagged ÷ admitted roster). Published on the methods page. No target is claimed until the pilot; set targets by ADR afterwards.

8. Data contract
8.1 Files
•	data/groups/roster.json — identity fields (public subset; admitted organisations only).
•	Not committed/published: roster_manifest.local.json, roster_quarantine.csv, data/raw/, assignments.csv, submissions/*.csv, audit_log.csv.
•	Committable/published: roster_manifest.json (restricted fields, §4.3), data/groups/groups.json (schema cg-v2).
•	Derived by data loaders: groups_tree.json, groups_graph.json, coverage.json, flows.json, precision_card.json (§9.5).
8.2 groups.json record (cg-v2)
{
  "schema": "cg-v2",
  "group_id": "string (stable hash)",
  "name": "string",
  "name_alt": ["string"],
  "url": "string|null",
  "country": "ISO 3166-1 alpha-2|null",
  "region": "UN M49 sub-region label|region_unknown",
  "places": ["ISO code"],
  "source": "bffp_roster|ambassador_suggested|other",
  "org_status": "source_declared_org|heuristic_org|human_confirmed_org",
  "bffp_listed": true,
  "bffp_listed_asof": "YYYY-MM-DD|null",
  "status": "unlabelled|assigned|ambassador_tagged|reviewed|group_confirmed|cannot_determine",
  "cannot_determine_reason": "string|null",
  "layer": "core|adjacent|untagged",
  "entity_type": "enum|null",
  "sector": "enum|null",
  "plastics_centrality": "primary|substantial|incidental|none|cannot_determine|null",
  "primary_activities": ["enum (ordered)"],
  "geographic_scope": "enum|null",
  "legal_form": "enum|null",
  "legal_form_note": "string|null",
  "participation_in_science": "enum|null",
  "website_languages": ["ISO 639-1"],
  "themes": ["A3 theme tag"],
  "analytic_lens": ["A3 lens value"],
  "constituency": ["enum"],
  "parent_group_id": "string|null",
  "stated_affiliations": [
    {"target_group_id": "string|null", "target_name": "string|null",
     "relation": "member_of|partner_of|fiscal_sponsor|parent_of|funded_by",
     "evidence": {"url": "string", "accessed_at": "YYYY-MM-DD", "quote": "string (<=25 words)", "not_stated": false}}
  ],
  "evidence": [
    {"facet": "string", "url": "string", "accessed_at": "YYYY-MM-DD",
     "quote": "string (<=25 words)|null", "not_stated": false, "note": "string|null"}
  ],
  "tagged_at": "YYYY-MM-DD|null",
  "reviewed_at": "YYYY-MM-DD|null"
}
Validation rules
•	V1 layer is derived: core if centrality ∈ {primary, substantial}; adjacent if ∈ {incidental, none}; untagged otherwise.
•	V2 status ≥ ambassador_tagged requires F1, F2, F3, F4, F7 set (F3 = cannot_determine only with status cannot_determine).
•	V3 every quote ≤25 words; exactly one of quote or not_stated=true.
•	V4 evidence has entries for plastics_centrality and primary_activities.
•	V5 primary_activities length 1–3; places length ≤5.
•	V6 participation_in_science ≠ not_applicable only when research_monitoring ∈ activities.
•	V7 bffp_listed=true requires bffp_listed_asof.
•	V8 no personal-data fields; any email-pattern string fails the build.
•	V9 ambassador_id never appears in published files.
•	V10 parent_group_id and every non-null target_group_id must reference an existing group_id.
•	V11 every stated_affiliations[] entry carries a quote (not_stated is invalid for affiliations).
•	V12 org_status ∈ the three admitted values; any other value fails the build (A4-D20).
•	V13 website_languages values are valid ISO 639-1 codes.
•	V14 no published file contains a field or string reporting the number of excluded or ambiguous entries (A4-D24).
8.3 Submission CSV contract
One row per group per submission; columns = facet fields; array fields ;-separated; evidence_<facet>_url, _accessed_at, _quote, _not_stated per evidenced facet; affiliations in a companion affiliations.csv keyed by group_id. UTF-8, header row. The ingest is platform-agnostic.
8.4 Example (illustrative; not a real record)
{
  "schema": "cg-v2", "group_id": "cg_ex001", "name": "Example Coastal Cleanup Group",
  "url": "https://example.org", "country": "US", "region": "Northern America", "places": ["US-CA"],
  "source": "bffp_roster", "org_status": "source_declared_org",
  "bffp_listed": true, "bffp_listed_asof": "2026-11-26",
  "status": "ambassador_tagged", "layer": "core",
  "entity_type": "organisation", "sector": "ngo_civil_society",
  "plastics_centrality": "primary", "primary_activities": ["cleanup_removal","education_awareness"],
  "geographic_scope": "subnational", "legal_form": "registered_nonprofit", "website_languages": ["en"],
  "evidence": [
    {"facet":"plastics_centrality","url":"https://example.org/about","accessed_at":"2026-11-26",
     "quote":"We remove plastic litter from California beaches.","not_stated":false}
  ]
}

9. Visualisation module
9.0 Platform and principles
The site is built with Observable Framework, an open-source static site generator for data apps, dashboards, and reports 5 whose data snapshots are generated by data loaders in any programming language 5, so the derived files in §8.1 are built by Python loaders at build time. Framework includes libraries such as Observable Plot, D3 and Leaflet 5 (Observable Framework home page), and Observable Plot is available by default as Plot in Markdown 6 (Observable Framework, Plot page). The network view continues to use Sigma.js + graphology as in A3. Framework self-hosts npm imports and lets you pin a version with a semver range in the import specifier 7 (Observable Framework, converting notebooks page); use pinned, self-hosted imports for the two packages/assets approved under A4-D22.
Design principles
1.	Denominators everywhere. Each chart carries a caption "Based on N of M roster organisations tagged (x%)" and a per-region coverage indicator. Because assignment is by region priority and volunteers choose what they tag, tagged groups are not a random sample (inference from the design); captions must say so.
2.	Layers visible and separable. Core and adjacent groups are always distinguished (shape/hue + legend), each with its own toggle. Untagged groups are never drawn in graph views (A4-D16) and appear in tree views only as aggregated counts.
3.	No rankings of groups (rule 6).
4.	Evidence one click away. Any group node/leaf opens the group card (§9.2).
5.	Accessible: colour-blind-safe palette; no colour-only encoding; keyboard-operable tree; each chart has a "View data" table and CSV download; responsive layout.
6.	Shareable state: filters and expanded tree nodes encoded in the URL hash.
7.	Small-cell caution: cells/flows with n below a threshold (proposal: 5) are drawn muted with the count visible; none is suppressed or hidden.
8.	Performance budget (proposal): first meaningful paint of each view ≤2 s on a mid-range laptop with the full tagged set; lazy-render tree children on expand; the network view caps visible labels (A3 label budget).
9.1 Layers
•	Core: plastics_centrality ∈ {primary, substantial}.
•	Adjacent: incidental or none, named "Adjacent organisations (no stated plastics focus)", visible by default as a separate, distinct node group with its own toggle and the text: "These organisations are listed in the roster but do not state a plastics focus on their public pages. Volunteer Ambassadors can add details."
•	Untagged: roster table and coverage views only.
9.2 Group card
Name, URL, country/places, entity type, sector, centrality, ordered activities, languages, evidence quotes with links and access dates, status badge, affiliations (as stated, with evidence), and the provenance line "Listed as a BFFP member as of ⟨date⟩". Standing note: "Tags were entered by volunteers from public sources and have not been verified by the group unless marked Confirmed." Includes "Suggest a correction" (§10.3). No scores.
9.3 Roster table and coverage panel
A searchable, filterable table of all admitted roster organisations (status, region, country) with a "Help tag this group" call-to-action, plus a coverage panel (tagged ÷ roster by region; cannot_determine counts by reason). No count of excluded entries is shown anywhere (A4-D24).
9.4 Views
V-TREE — Collapsible tree (default: geography-first; alternatives ship, A4-D19). D3's hierarchy module provides tidy trees and notes that indented trees are useful for interactive browsing 8 (d3-hierarchy documentation); its tree layout produces tidy node-link diagrams 9 (D3 tree layout page). Use an indented (outline) tree as the default (scales to thousands of leaves; keyboard-friendly), with an optional tidy-tree rendering for the upper levels.
•	Default (geography-first): Region → Country → (US-CA as a subnational node) → Layer (core / adjacent) → Sector → Group.
•	Alternatives (switch above the tree): Function-first: Layer → Sector → principal activity → Group. Centrality-first: plastics_centrality → principal activity → Group.
•	Placement rule: each group appears once, under its principal activity in activity-based levels. An "All activities" toggle lists a group under each of its activities; branch badges always show distinct counts and the interface says so.
•	Branch badges: n tagged / M roster; untagged groups appear as one aggregated leaf per country "Not yet tagged (n)" linking to the roster table, never as individual leaves.
•	Behaviour: collapsed to depth 1 by default; expand/collapse all; type-ahead search that expands to matches; leaf click opens the group card; status badges on leaves; state in URL hash.
•	Accessibility: role="tree"/treeitem, aria-expanded, arrow-key and Home/End navigation.
V-NET — Network view (Sigma.js).
•	Default graph (bipartite, no inference): group nodes (core and adjacent) linked to facet nodes: activities, themes, countries/places. Edges are tag assignments, not relationships between groups.
•	Layer "Stated affiliations": group–group edges drawn only from stated_affiliations[] with a quote (F13), labelled by relation type and directed where directional. External (non-roster) organisation targets appear as hollow ghost nodes or are hidden by a toggle.
•	Projection "Tag co-occurrence": activity–activity (or theme–theme) edges weighted by the number of groups carrying both tags; labelled "co-occurrence of tags, not partnerships".
•	Encodings/controls: colour by sector (default) with selectors for layer, centrality, region, participation-in-science; size by degree (legend: not importance); filters for status, region, sector, layer, centrality; ego-network on click; search by name; label budget per A3; layout computed at build time and cached (A3 patterns) with a live-layout fallback; node and edge counts shown.
•	Caution text: the view reflects tagged groups only; absence of edges reflects missing data (rule 8).
V-COV — Coverage and progress. Stacked horizontal bars per region (unlabelled / assigned / tagged / reviewed / cannot_determine, with counts) and a weekly cumulative "groups tagged" line from the aggregated audit log. No individual attribution (§5.7).
V-MAP — Geographic distribution. Proportional-symbol map by country (roster size, with a second encoding for tagged fraction) plus a California panel (US-CA groups by activity). Use country centroids and a simplified, neutral base layer; avoid assertions about disputed boundaries. Map asset (A4-D22): Natural Earth is a candidate: its terms page states that all versions of Natural Earth raster and vector map data are in the public domain, with no permission needed and crediting the authors unnecessary 10 (Natural Earth Terms of Use). The same page has no specific disclaimer about political or disputed boundaries 10 and carries third-party disclaimers for certain themes (roads, time zones, European rivers and lakes); so choose a country-level theme, record the exact theme, version and scale in DECISIONS, and write a short boundary-neutrality note on the map page. The agent may use a different permissively licensed asset if it logs the same details.
V-HEAT — Composition heatmaps (Observable Plot). (1) plastics_centrality × sector; (2) principal activity × region, with counts and within-region share, using the small-cell rule.
V-COMP — Composition (treemap and/or sunburst). D3's hierarchy module offers adjacency diagrams such as the sunburst and enclosure diagrams such as the treemap, which can encode a quantitative dimension in area 8. Use a treemap (area = number of groups) over Layer → Sector → principal activity with breadcrumb zoom, complementing the tree.
V-SANKEY — Flow diagram (A4-D21/D22). Sector → plastics_centrality → principal activity, for tagged groups. Link width = number of groups. Node order is fixed by taxonomy order, not by size. Conservation rule: the flow totals at each level equal the number of tagged groups included. Package (A4-D22 approved): add one small, permissively licensed Sankey layout package, pinned and self-hosted; I could not confirm a Sankey layout in Framework's default libraries, so the agent must verify and log package name, version and licence before use. Fallback: a Plot-based stacked-bar alternative with the same data. Small-cell rule applies.
V-PART — Participation in science (A4-D21). Small multiples (faceted by sector) of F5 values for groups tagged research_monitoring, using the five-model scheme from the PPSR literature (§3 F5). Caption states how many groups carry an F5 value; most groups will have not_applicable.
V-COOC — Activity combinations (A4-D21). An UpSet-style view (ranked bars of the most frequent activity combinations with a dot-matrix key) built with Plot, no extra library. Combinations with fewer than 3 groups are collapsed into "other combinations". Ordering is by frequency of tag combinations; caption says so.
V-LANG — Website language coverage (A4-D21). Groups by website_languages[] × region, plus the count of needs_language_support entries; where the Ambassador infrastructure can export aggregated Ambassador language coverage (no personal data), show it alongside to expose gaps. Caption notes that language is recorded only for tagged groups.
V-EVID — Evidence and quality. From precision_card.json: share of tagged groups with evidence per Tier-1 facet; cannot_determine reasons; agreement statistics (κ/PABAK/AC1) with intervals per field and region; review coverage. Doubles as the methods transparency panel.
9.5 Derived data files (built by Python data loaders)
•	groups_tree.json — pre-aggregated hierarchies with per-node counts (tagged, roster, distinct) for each selectable hierarchy; leaves reference group_id.
•	groups_graph.json — nodes and edges for V-NET, with separate edge sets by edge_type (assignment, affiliation, co-occurrence).
•	coverage.json — region × status counts, weekly tagged totals, country counts, language counts.
•	flows.json — Sankey links, participation counts and activity-combination counts.
•	precision_card.json — §7.4 statistics.
•	All derived files are generated from groups.json + roster.json; none introduces data not present there, and none contains excluded-entry counts (V14).
9.6 Wording
Neutral descriptions; do not describe a group beyond its own evidence; avoid language implying that BFFP membership proves commitment.

10. Ethics, privacy, corrections
1.	No personal data in the public dataset; individuals and single-person practices are excluded at intake and not retained (§4.4). BFFP's own figure covers organizations and individual supporters 1, so exclusion is a real filtering step. Because the repository is public (rule 12), the excluded count is kept only in a local, gitignored manifest and is never published (A4-D24).
2.	Ambassador data stays in the Ambassador infrastructure outside the public repo (§5.7).
3.	Correction and removal channel on every group card and the methods page. Response target and removal policy are set by the owner (open). Requests from a group's own domain take precedence over Ambassador tags; removals are honoured.
4.	BFFP relationship: the methods page states the Atlas is independent of BFFP unless BFFP agrees otherwise; "BFFP member" wording is provenance only, and the permission obtained (§4.1) is acknowledged according to its conditions.
5.	Sensitive contexts: a group may be set hidden_pending_review at an Ambassador's or the group's request when public identification could create risk. [Owner policy needed.]
6.	Language: evidence quotes are kept in the source language. Non-English groups go to Ambassadors who declare that language; otherwise needs_language_support. Non-English coverage is currently unmeasured.

11. Other directories (link-only)
GPML is described as an open source, crowd-sourced, multi-stakeholder platform that compiles different resources, connects stakeholders, and integrates data 11 (GPML framework document). Its categories inform F2/F4. Do not bulk-reuse its member lists without a licence check (A4-D10); the same applies to other directories identified earlier (Nurdle Hunt Hub, GIZ/Nile Basin mapping). Ambassadors may cite any of them as evidence for a single group.

12. Tasks

ID	Task	Notes
CG-0	Repo + .agent/ entries for A4; log A4-D1..D24; add .gitignore entries for data/raw/, roster_manifest.local.json, roster_quarantine.csv, submissions, audit log
CG-1	Record permission details (owner) + BFFP discovery (§4.2) → docs/bffp_roster_discovery.md, including the organisation/individual field	Stop conditions apply
CG-2	Roster extractor (§4.3) with RosterSource seam, two manifests, 30-day raw-cache purge, structural-change guard, fixtures	After CG-1 clears
CG-3	Org-admission filter (incl. single-person exclusion), normalisation, dedupe, region mapping (§4.4)	Excluded entries never persisted outside the raw cache
CG-4	Schema cg-v2 + validation V1–V14; confirm GPML labels [VERIFY]
CG-5	Document existing Ambassador infrastructure (§5.5) → docs/ambassador_infrastructure.md; define adapter	Before CG-6
CG-6	Assignment engine and submission ingest — build only what CG-5 shows is missing
CG-7	Review queue, audit log, agreement statistics
CG-8	Ambassador guide, calibration set (incl. organisation-check cases), agreement text	Owner/coordinator content
CG-9	Build groups.json and derived files (§9.5)
CG-10	V-TREE (geography-first default + two alternatives)
CG-11	V-NET (bipartite, affiliations, co-occurrence)
CG-12	V-COV, V-MAP, V-HEAT, V-COMP, V-EVID	Log map asset per A4-D22
CG-12b	V-SANKEY, V-PART, V-COOC, V-LANG	Log Sankey package per A4-D22
CG-13	Roster table, coverage panel, call-to-action, group card
CG-14	Correction channel and methods page (describe the exclusion rule without any count)
CG-15	Pilot (California batch) and retrospective; set precision targets by ADR
CG-16	Docs, DECISIONS updates
CG-X1	Optional: link-rot check (HEAD only)	Needs approval
CG-X2	Optional, off by default: Ambassador-side assistive tooling	Needs an ADR; may never write tags

Removed from v1: bulk enrichment fetcher and automated LLM pre-labelling.

13. Tests

ID	Test
T-SCH	Valid/invalid records against cg-v2; each of V1–V14 has a failing fixture
T-EXT	Extractor on saved fixtures: parses allow-listed fields only; both manifests produced; structural-change guard trips on a truncated fixture; politeness settings enforced (rate, User-Agent, stop on 403/429)
T-ORG	Fixture mixing organisations, individuals, single-person practices and ambiguous entries: only admitted org_status values reach roster.json; heuristics never promote ambiguous; single-person practices excluded; no excluded entry's name appears in any output file, log, manifest or derived file (string search over all artefacts)
T-MAN	Committed roster_manifest.json contains no fetched total and no excluded/ambiguous counts; roster_manifest.local.json is gitignored; no published file reports an excluded count (V14, A4-D24)
T-RAW	Raw-cache purge runs after parse verification or at 30 days; raw cache is gitignored and absent from build outputs
T-NRM	Unicode forms, whitespace, original-script names preserved, stable group_id across re-imports
T-DUP	Exact and near-duplicate routing; no auto-merge of near-matches
T-RGN	Country → region mapping incl. US-CA, region_unknown routing
T-ASG	One holder per entry; lease expiry returns entries; COI return; priority order
T-ADP	Ambassador-infrastructure adapter: rows meeting the CSV contract ingest identically regardless of source
T-STA	Illegal state transitions rejected; side states reachable; not_an_organisation removes the record from public outputs
T-EVI	Quote ≤25 words; quote XOR not_stated; required facets present; affiliations require quotes
T-LAY	Every centrality value → expected layer (incidental → adjacent)
T-AGR	Agreement statistics on synthetic data with known κ; skewed-prevalence case
T-PRI	Published files contain no ambassador_id, email-like strings or personal fields
T-TREE	Geography-first is the default; all three hierarchies build; each group placed exactly once per hierarchy; distinct counts correct in all-activities mode; untagged only as aggregates; expanded state round-trips via URL hash
T-GRAPH	No untagged nodes; no group–group edges without a quoted affiliation; edge sets separated by edge_type; co-occurrence labelled as such
T-SANKEY	Flow totals at each level equal the tagged-group count; node order follows taxonomy order; package name/version/licence present in DECISIONS
T-COOC	Combination counts reconcile with primary_activities; combinations with n<3 collapsed into "other"
T-PART	F5 counts reconcile with tagged research/monitoring groups; not_applicable handled
T-LANG	Language counts reconcile with website_languages; invalid codes rejected
T-MAP	Country counts reconcile with roster.json; map asset theme/version/licence recorded in DECISIONS; boundary-neutrality note present
T-COV	Chart denominators match roster.json counts; caption text present on every distribution chart
T-DSP	Adjacent layer visible by default and separately toggleable; BFFP wording with date on group cards
T-A11Y	Tree keyboard navigation; each chart has data table and CSV; no colour-only encoding
T-PERF	Views meet the §9.0 budget on a fixture of ≥5,000 groups
T-NOA	No-automation guard: CI fails if any code path writes tag fields from a non-submission source
L-01..03	Manual: discovery findings and permission record in DECISIONS; Ambassador pilot dry run; correction channel test request


14. Open items (owner-gated)
1.	Permission record details (§4.1): form, scope, conditions, whether it covers public display.
2.	Ambassador infrastructure interface — documented by the IDE agent (CG-5); owner confirms any gaps (vocabulary enforcement, assignment).
3.	A4-D14 / D17: Ambassador attribution policy and contributor licence.
4.	Correction channel: response target, removal policy, sensitive-context handling.
5.	Language handling for non-English groups and Ambassador language coverage.
6.	Review capacity and precision targets (ADR after the pilot).
7.	Calibration tags (§6.4) to be finalised.
8.	Reuse terms for other directories (§11).
9.	Gaps: I found no peer-reviewed typology specific to plastics community groups; F1–F7 are assembled from PPSR literature, GPML categories and nonprofit classifications and are unvalidated for this population. Non-English coverage is unmeasured. Whether BFFP's source data distinguishes organisations from individuals is unknown until CG-1.
References
1.	Break Free From Plastic | The global movement envisioning a future free from plastic pollution. Retrieved 2026-11-26, from https://www.breakfreefromplastic.org/
2.	Concept Document. Retrieved 2026-11-26, from https://wedocs.unep.org/server/api/core/bitstreams/2cae6886-36f5-4a1e-bf06-a06203f9d2c5/content
3.	Public Participation in Scientific Research: Defining the Field and. Retrieved 2026-11-26, from https://www.astc.org/wp-content/uploads/2025/11/PublicParticipationinScientificResearch.pdf
4.	Public Participation in Scientific Research: A Framework for Deliberate Design - Community Science Initiative. Retrieved 2026-11-26, from https://communityscience.astc.org/resources/public-participation-in-scientific-research-a-framework-for-deliberate-design
5.	Observable Framework. Retrieved 2026-11-26, from https://observablehq.com/framework
6.	Observable Plot | Observable Framework. Retrieved 2026-11-26, from https://observablehq.com/framework/lib/plot
7.	Converting notebooks | Observable Framework. Retrieved 2026-11-26, from https://observablehq.com/framework/convert
8.	d3-hierarchy | D3 by Observable. Retrieved 2026-11-26, from https://d3js.org/d3-hierarchy
9.	Tree | D3 by Observable. Retrieved 2026-11-26, from https://d3js.org/d3-hierarchy/tree
10.	Natural Earth » Terms of Use - Free vector and raster map data at 1:10m, 1:50m, and 1:110m scales. Retrieved 2026-11-26, from https://www.naturalearthdata.com/about/terms-of-use/
11.	GLOBAL PARTNERSHIP ON MARINE LITTER AND (GPML). Retrieved 2026-11-26, from https://wedocs.unep.org/server/api/core/bitstreams/fb482978-91d2-481e-b970-c1107db4a45d/content
