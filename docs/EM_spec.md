CA Plastics Research Atlas — UX/UI Remediation Spec (for IDE agent)
Target: the deployed Atlas at plastiverse.live/app/ and the legacy pages index.html, expert.html, grants.html.Repository (from the site's own correction link): ScottCoffin/CA_Plastics_Research_Dash 1.Basis: an external, text-extraction walkthrough of the live site on 2026-11-12. Visual design, contrast, focus behaviour, responsive layout, and markup attributes were NOT observed. Items marked [VERIFY] must be confirmed in a real browser or in the source before any change.

Status 2026-11-12: integrated into .agent/TODO.md as tasks UX-0..UX-25 (section "UX remediation"). Section 1A records a browser audit that confirms or corrects Section 1; where they disagree, Section 1A wins.

0. Operating rules for the agent
Repository protocol overrides (ADR-UX-SPEC-2026-11-12): rule 2 (branch and PR per task) and rule 7 (append to .agent/handoff.md) are replaced by the repository's checkpoint protocol in CLAUDE.md: one task per checkpoint, committed on main as "UX-<n>: <summary>", and .agent/HANDOFF.md overwritten at each seal. The remaining rules apply as written.
1.	Read before writing. Task UX-0 is mandatory. Do not assume a framework, build tool, router, or file layout. The only repo paths known from the site are docs/METHODS.md and docs/SITE_DATA.md (the S3.1 site data contract) 2.
2.	One task = one branch = one small PR. Branch name ux/<task-id>-<slug>. Commit message starts with the task ID.
3.	Never modify data, schema, or the data-generation pipeline in a UX task. Presentation, copy, links, markup, and CI only. If a fix needs a data change, write a note in the handoff and stop.
4.	Do not invent facts. Where a definition is needed (tier, bootstrap interval, m-quotient, rising percentile, CA-led), take the wording from docs/METHODS.md or the code that computes it, and quote the file and line in the PR. If the repo does not define it, write "TODO-OWNER" and list it in the handoff. Do not guess.
5.	Preserve the "do not regress" list (Section 2).
6.	Verification is required. Each task has acceptance criteria. Provide evidence in the PR (command output, screenshot, or test name). Do not mark a task done on "looks right".
7.	Memory/handoff. After each task, append to .agent/handoff.md: task ID, files changed, what was verified, open questions. Keep it under 15 lines.
8.	Ask the owner, don't decide, for any item in Section 3 (Decisions) that has no default you can apply.

1. Observed state (evidence base)
1.1 Site shell and navigation
•	The Overview has eight navigation cards (Experts, Institutions, Monitoring, Funding, Evidence map, Policy, Related resources, About) 3. The refresh time is shown as a raw ISO string, "2026-11-12T17:09:05+00:00" 3. The tiles show Works 1,909 and Labeled works 1,909 3.
•	Every /app/ page has a "Classic site" link. Its href is https://plastiverse.live/app/ 1, the page the user is already on.
•	The root index.html is the older Experts browser. It contains no link to /app/ and no notice that a new version exists 4. The legacy profile page links back to https://plastiverse.live/index.html 5.
•	The funding visualisations link goes to https://plastiverse.live/grants.html 6, outside /app/.
1.2 Experts
•	Filters: search, institution type, institution, sort, career stage, domain/matrix tag, year range, CA basis (Any default listed first), OA availability, Reset filters, Export filtered CSV 1.
•	The count reads "2614 experts shown" 1. Cards include Rochman, Chelsea M., University of Toronto, tagged "ca-led" 1.
•	"Rising" and "m-quotient" are not explained beyond their sort labels, the percentile population is not stated, and the "ca-led" tag has no explanation 1. Cards show "rising: 0th percentile" for Geyer, Rochman and Cole 1.
•	No pagination or "load more" control was seen 1.
•	The "Full profile" href is https://plastiverse.live/expert.html=A5031423229, with = directly after expert.html and no ? or # 1. With ?id=A5046986222 the page showed "No expert selected", status "Not available", with no explanation of why the ID failed 5. Bare expert.html shows the same empty state and the page does not say how IDs are passed 5.
1.3 Institutions
•	The intro cites an internal artifact: "the same S3.1 export used by the Experts view" 7.
•	Header count: 161 California institutions in 5 tiers 7. Overview says 211 California institutions 3.
•	The bootstrap interval and rank range are not defined on the page, which defers to docs/METHODS.md 7.
1.4 Monitoring
•	"Access tier" (A, B, C, D) has no definition on the page 8.
•	The observation table has ISO-style timestamps (2015-07-28T00:00:00), units inline in values, and no visible download control 8.
•	Licence vocabulary includes "fair-use-factual-values" 8.
1.5 Funding
•	Headline: "492 report an amount, summing to $471,139,990 across mixed amount bases" 6, next to a warning that amounts "are not comparable or additive across sources or fiscal years" 6.
•	Only 9% of awards are California-led 9, and the page default is "Led from California: Any" 6.
•	The rows-per-page selector offers 25, 50 or 100 but the default is not stated 6.
1.6 Evidence map
•	"Loading the evidence bundle…" is shown and the page does not show whether loading finished 10.
•	The intro lists topic, sector, work type, OA, California leadership and relevance filters, but only "Search titles", "Year from", "Year to", "Reset filters" and "Show works" appear 10.
•	Placeholders: "Coming with EM-8", "Coming with EM-9", "Coming with EM-10", plus headings with no content (Pipeline flow, Trend panel) 10.
1.7 Policy
•	Entries 8 and 9 cite "uploaded document; no URL"; the OPC section reads "Coming with EM-17 (the mapping of the 22 early actions awaits owner review)"; date formats are mixed; the Nov 2025 entry links to the research page rather than the Background Document; acronyms are unexpanded 11.
1.8 Related resources
•	Most entries show "Updates: not stated" and "Terms: not recorded". Stewards are "not stated" for NOAA NCEI Marine Microplastics and the Plastiverse tools directory 12.
1.9 About
•	No licence statement, no citation format (only the release DOI), and no contact route other than the GitHub issue link 2. It contains developer vocabulary: "Fixture snapshot loaded" and the inactive plastic-v2-candidate query 2.

1A. Browser audit 2026-11-12 (verified)
Method: Playwright 1.x (Chromium) on the live site at 1366x900 and 375x812, axe-core 4.10.3 on desktop, a 12-step Tab walk per page, and Lighthouse 12.8.2 (mobile preset, Edge) on /app/, /app/experts, /app/evidence, /app/monitoring and /index.html. Reusable tool: ~/tools/ux-audit/ux_audit.py. Visual design was checked only through axe contrast rules and screenshots; no screen reader was used.
Corrections to Section 1:
•	1.1 "Classic site": the rendered href is "./" (Framework 1.13.4 rewrites the configured "../"), so it reloads the current page. Confirmed bug; root cause is in the build, not the copy.
•	1.2 "Full profile": hrefs are expert.html#author=<OpenAlex id> on both /app/experts and index.html, and the first three cards (Geyer, Rochman, Cole) open populated profiles. The "expert.html=A..." form was a text-extraction artifact. A bad ID already shows 'No profile is available for "<id>" in this snapshot' with a link back. Remaining UX-2 work: bare expert.html should say how to choose an expert, and ?id=<id> should be accepted as an alias.
•	1.6 Evidence map: no "Loading the evidence bundle…" text remains visible after load; the loaded state is not the problem. The intro/filters mismatch, the EM-n placeholders and the empty headings are confirmed.
•	1.1 root index.html: confirmed, no link to /app/.
•	Internal vocabulary confirmed in rendered text: "S3.1 export" (Institutions), "EM-8/9/10" and "Coming with" (Evidence), "EM-17", "uploaded document; no URL", "awaits owner review" (Policy), "Fixture snapshot" and "plastic-v2-candidate" (About).
New findings (not in Section 1):
•	Every /app/ page: <html> has no lang attribute (axe html-has-lang, serious) and the viewport meta sets maximum-scale=1, which blocks pinch zoom (axe meta-viewport, critical). Both come from the Framework 1.13.4 page template.
•	Every /app/ page: color-contrast failures (serious; 9-66 nodes per page, for example #7a7a76 muted text at 3.86:1), link-in-text-block (serious; links distinguished by colour only, 1.2:1 against body text, including the header and footer links), label-title-only (the sidebar search control), and list (malformed sidebar list).
•	/app/experts and /app/funding have no h1. heading-order skips on Institutions (h1 -> "California institution map"), Monitoring (h1 -> "Filters"), Evidence, Resources and About.
•	/app/monitoring: cumulative layout shift 0.50 (Lighthouse performance 79), caused by #monitoring-quality-note filling in after load; nested-interactive (5 nodes). grants.html: nested-interactive, aria-prohibited-attr, definition-list, empty-table-header.
•	/app/evidence overflows horizontally at 375 px. Touch targets under 24 px are common (Monitoring 107, grants.html 115, Evidence 58).
•	Lighthouse: performance 98-100 except Monitoring (79); accessibility 67-81 on /app/ pages against 99 on the classic index.html; SEO 90 (no meta description on /app/ pages); one console error per page (a network 404).
•	Not reproduced as problems: keyboard focus was visible on every element reached in the Tab walk; no unlabeled form inputs were found; no JavaScript errors.

2. Do-not-regress list
Preserve these existing strengths:
•	Independence disclaimer in every footer: "Independent project; not an official OEHHA or State product." 11
•	Institutions volume caveat: "It is not a quality ranking" 7, and the tier-overlap explanation ("cannot be reliably ordered, because their bootstrap rank ranges overlap") 7.
•	Map keyboard operation: arrow keys to pan, +/- to zoom, and Zoom in / Zoom out / Reset view controls 7.
•	Monitoring caveats: not statewide coverage, methods not comparable, blank cells are not evidence of a data gap 8.
•	Funding amount-basis section and empty state: "Amount basis by source" and "No open plastic-related calls right now" 6.
•	grants.html features: filter state saved in the page address, and a "View the Sankey as a table" alternative 9.
•	Policy caveat: "Listing does not by itself create requirements; Priority Product designation is a separate rulemaking." 11
•	About limitations and corrections process: limitations are explicit, with a 5–10 business-day acknowledgement target and a release DOI 2.

3. Decisions (apply the default unless the owner overrides)

ID	Decision	Default
UXD-1	Where "Classic site" should point	/index.html. Inference from the legacy page links above; [VERIFY] it is the legacy entry point.
UXD-2	Classic-site retirement	Add a "new version" banner now. Do not redirect until the owner sets a date.
UXD-3	Default scope on Experts and Funding	"California-connected" default, with a visible toggle to "All in corpus". The exact filter mapping is TODO-OWNER (see UX-5).
UXD-4	Rename "Experts"	"Authors" in headings and cards; keep the route /app/experts and keep the nav label "Experts" only if the owner chooses.
UXD-5	Evidence map visibility	Hide the nav card and route link until at least one panel is functional. Keep the route live with an "In development" notice.
UXD-6	Funding headline sum	Remove from the first screen. Show per-source subtotals instead.
UXD-7	Date format	ISO 8601 date (YYYY-MM-DD) in tables; "12 Nov 2026" in prose.
UXD-8	Licence for Atlas code and site content	TODO-OWNER. Do not choose one. Add a placeholder section and list it in the handoff.


4. Tasks
Priority: P0 = trust or broken path; P1 = comprehension or misuse risk; P2 = polish. Effort: S ≤ 2 h, M ≤ 1 day, L > 1 day.
UX-0 — Recon (mandatory first)  [S]
1.	Identify the stack (static generator, bundler, framework), the routes under /app/, the shared layout/header/footer component, the CSS approach, and the build and deploy commands.
2.	Locate: the "Classic site" link, the Experts card template, expert.html and its ID-reading code, the Evidence-map page, the Policy timeline data, the Resources data, and the About page text.
3.	Run the existing tests and build. Record the baseline in .agent/handoff.md.
4.	List which Section 1 observations can be reproduced from source and which cannot.Done when: the handoff lists file paths for every item above and the baseline build passes.
P0
UX-1 — Fix the "Classic site" link and cross-link versions  [S]
•	Change the shared header link target per UXD-1 and [VERIFY] the destination renders the legacy Experts browser.
•	Add a banner to index.html linking to /app/ (UXD-2). Wording: "A newer version of this atlas is available."
•	Acceptance: from /app/* the link navigates to a different page than the current one; from index.html the banner link reaches /app/; a test asserts both hrefs.
UX-2 — Fix expert profile links and failure state  [S/M]
•	[VERIFY] in a browser whether the "Full profile" link actually breaks. Then read how expert.html parses the ID (query string, hash, or other) and make the card href match it.
•	On unresolved ID, expert.html must say which ID it tried and why it failed (not found vs. malformed), and link back to the list.
•	Acceptance: clicking the first three cards in Experts opens a populated profile; a Playwright test covers it; a bad ID shows the new message.
UX-3 — Remove internal vocabulary from public text  [S]
•	Remove or rewrite: EM-\d+, "S3.1 export", "uploaded document; no URL", "awaits owner review", "Fixture snapshot loaded".
•	For Policy entries with no public URL, label the source as "Source document (not online)" or remove the source link, and list them in the handoff for the owner.
•	Add a build-time check that fails if these strings appear in the rendered HTML of /app/** (test file or script; allow-list for docs).
•	Acceptance: the check fails on a seeded sample and passes on the build.
UX-4 — Evidence map: honest state  [S/M]
•	Apply UXD-5. When the page is reachable, show one "In development" notice and remove empty headings (Pipeline flow, Trend panel) and "Coming with EM-n" text.
•	The intro must list only filters that are actually rendered. Show a visible loaded/failed state in place of a permanent "Loading the evidence bundle…", with a retry link on failure.
•	Acceptance: no empty headings; intro text matches controls; simulate a failed fetch and capture the error state.
P1
UX-5 — Scope toggle and labels  [M]
•	Experts and Funding: add a segmented control per UXD-3. The mapping of "California-connected" to the existing filters is TODO-OWNER. Propose a mapping from docs/METHODS.md definitions in the PR and wait for owner confirmation.
•	Show active filter chips and a "N of M" count (e.g., "N of 2,614 authors"). Apply UXD-4.
•	Acceptance: default view and toggle both work; filter state is reflected in the URL.
UX-6 — Reconcile institution counts  [S]
•	Find why Overview shows 211 and Institutions shows 161. Add the definition next to each number (e.g., "211 institutions with any California-resolved author; 161 shown here because…"). If the code cannot explain it, report it as a possible data bug and stop.
•	Acceptance: both pages state their definitions; the numbers are not changed unless the owner approves.
UX-7 — Inline definitions and glossary  [M]
•	Add accessible definitions (<details>, <abbr title>, or an info button that is keyboard-operable) for: access tier A–D, tier, fractional works, bootstrap interval, rank range, rising percentile and its population, m-quotient, CA-led, CA-sampled, matrix, plastic-related. Add /app/glossary and link it from every page footer. Definitions come from docs/METHODS.md and the About definitions (plastic-related, CA-led, CA-sampled, state waters 2); unknown ones are TODO-OWNER.
•	Acceptance: every listed term has a definition reachable by keyboard; unknown terms are listed in the handoff.
UX-8 — Funding: remove the headline sum  [S]
•	Apply UXD-6 on /app/funding and align grants.html (which shows "$471.1 M" with a basis warning 9). A figure must never appear without the "not a total" caveat in the same sentence.
•	State the selected rows-per-page default.
•	Acceptance: no dollar total outside the amount-basis section or without caveat text; the selector shows its current value.
UX-9 — Monitoring usability  [M]
•	Add a "Download observations (CSV)" control with citation and licence text bundled in the file or an accompanying README.
•	Show dates as YYYY-MM-DD; move units into column headers where the data allow; keep units inline where they vary per row.
•	Define access tiers (UX-7) and add a plain-language gloss for each licence label, including "fair-use-factual-values" 8, plus what reuse it permits (TODO-OWNER if unknown).
•	Acceptance: CSV downloads and matches the displayed filter; headers show units; the glossary links are present.
UX-10 — About: licence, citation, contact  [S]
•	Add "How to cite" using the release DOI already shown (10.5281/zenodo.24124017 2; confirm the current release before publishing), a licence placeholder per UXD-8, and a non-GitHub contact route (TODO-OWNER for the address).
•	Rewrite developer vocabulary (the fixture and inactive-query sentences) in plain language.
•	Link term definitions from other pages to the About definitions.
UX-11 — Related resources cleanup  [S]
•	Replace repeated "Terms: not recorded" and "Updates: not stated" with a single "Reuse terms not recorded" badge, shown only when true.
•	Fill stewards that are knowable from the source pages (NOAA NCEI and the Plastiverse tools directory) from the stewards' own pages, with a source link.
P2
UX-12 — Policy timeline polish  [S]
•	Apply UXD-7. Expand acronyms on first use: DTSC, OEHHA, OPC, Candidate Chemicals list, Priority Product, Work Plan. Point the Nov 2025 entry at the Background Document itself if a stable URL exists, otherwise leave it and note it in the handoff.
UX-13 — One shell  [M]
•	Make grants.html use the same header, nav, footer, and disclaimer as /app/. Keep its URL-saved filter state, and extend that behaviour to the /app/ pages with filters.
•	Acceptance: navigation between /app/funding and grants.html keeps the same chrome; state round-trips via URL.
UX-14 — Overview  [S]
•	Remove the duplicate "Labeled works" tile unless it differs from Works under a documented definition. Format the refresh time as "12 Nov 2026, 17:09 UTC" and keep the ISO value in a <time datetime> attribute.
•	Add a "Start here" row with three task links (e.g., find an author; see who is funded; check monitoring data). Copy is TODO-OWNER.
UX-15 — Experts list scalability  [M]
•	Add pagination or a virtualised list. Add a visible loading state and a no-results state with a "Reset filters" button.
UX-16 — "Volume, not strength" caption  [S]
•	Add a short caption to every count-based view that lacks one (Experts, Funding, future Evidence matrix), modelled on the Institutions wording.
Tasks from the Section 1A audit
UX-21 — Framework template accessibility  [S] (P0)
•	Post-process the build (framework/scripts/postbuild.mjs, run by npm's postbuild hook) so every /app/ page has <html lang="en"> and a viewport meta without maximum-scale. Ship with UX-1, which uses the same step for the Classic-site link.
•	Acceptance: axe reports no html-has-lang or meta-viewport violation on any /app/ route; a test covers the rewrite.
UX-22 — Contrast and link styling  [S] (P1)
•	In framework/src/style.css, raise muted text to at least 4.5:1 in both themes and underline links inside text blocks (header, footer, prose), so links are not distinguished by colour alone. Fix the sidebar search label (label-title-only) and the list markup if they are reachable from config; otherwise record them as Framework template limits.
•	Acceptance: axe color-contrast and link-in-text-block report 0 nodes on every /app/ route in the light theme; dark theme checked by screenshot.
UX-23 — Heading structure  [S] (P1)
•	Give /app/experts and /app/funding one visible h1; remove heading-level skips on Institutions, Monitoring, Evidence, Resources and About.
•	Acceptance: axe page-has-heading-one and heading-order pass on every /app/ route.
UX-24 — Monitoring layout shift and nested controls  [S] (P1)
•	Reserve space for, or render synchronously, #monitoring-quality-note so the cumulative layout shift is below 0.1; remove nested interactive controls on /app/monitoring and grants.html; fix grants.html aria-prohibited-attr, definition-list and empty-table-header.
•	Acceptance: Lighthouse CLS < 0.1 on /app/monitoring; axe reports none of those rules on the two pages.
UX-25 — Mobile and metadata  [S/M] (P2)
•	Remove the 375 px horizontal overflow on /app/evidence, bring touch targets on filter chips and table controls to at least 24x24 px (WCAG 2.2 target size), add a meta description per /app/ page, and fix the per-page 404 seen in the console.
•	Acceptance: no horizontal overflow at 375 px on any route; Lighthouse SEO 100 and no console errors on /app/ routes.

Quality gates
UX-17 — CI audits  [M]
•	Add Lighthouse and axe-core runs for each /app/ route and grants.html/expert.html. If using an agent-in-the-loop workflow, the Chrome DevTools MCP server can run Lighthouse audits, including accessibility, and is now stable 13,14.
•	Fail the build on new accessibility errors. Do not block on score thresholds until a baseline exists.
•	Add the string check from UX-3 to the same job.
•	Note: automated accessibility testing finds only 30–50% of problems 15, so UX-19 is required in addition.
UX-18 — Naive-user task scripts  [M]
•	Write Playwright scripts for the tasks below. Playwright MCP lets an LLM interact with pages through structured accessibility snapshots 16, and these also expose missing labels.
1.	From the Overview, find a California-led author and open the profile.
2.	Filter Experts to a topic and year range, export the CSV, confirm the row count matches the shown count.
3.	On Institutions, explain (read from the page) why two institutions share a tier.
4.	On Monitoring, filter to one matrix and download the CSV.
5.	On Funding, filter to California-led awards and find the amount basis for NIH awards.
6.	From index.html, reach /app/.
•	Each script records pass/fail, steps taken, and the last element touched on failure.
UX-19 — Manual accessibility pass (human or human-assisted)  [M]
•	Use a guided tool: Accessibility Insights FastPass runs automated checks and a manual assisted Tab Stops test for keyboard access 17.
•	Checklist (WCAG 2.2 AA; general knowledge, not from the site): keyboard-only operation of every control, including sortable headers and map clusters; visible focus; no traps; screen-reader labels on filters; live-region announcement for result counts and loading; non-colour encodings for tiers/funders/topics; text contrast 4.5:1 and non-text contrast 3:1; reflow at 320 px and 400% zoom; target size; page <title>, lang, heading order, viewport meta.
•	Output: a table of failures with route, element, criterion, and proposed fix. Do not fix in this task.
UX-20 — Moderated sessions (human only; agent prepares materials)  [L]
•	Prepare a 5-participant plan with the six tasks from UX-18 and a consent-free think-aloud script. Recruit from the Atlas's actual audiences (agency staff, researchers, students, journalists). The agent does not run or simulate sessions.

5. Agent screenshot critique (optional, triage only)
If a multimodal model is used to critique screenshots (desktop and 375 px), treat the output as candidate issues only. Evidence on reliability is mixed: one study reported Cohen's Kappa of 0.68–0.74 between LLM agents and human evaluators 18, another found prompt variation changed results 19, and a 2026 benchmark found exact diagnosis-chain success peaked at 24.7% 20. Rules:
•	Use at least two prompt variants and keep only issues both produce.
•	Every kept issue must be reproduced in the browser and logged with route, viewport, and a screenshot.
•	Do not use model-assigned severity as data.

6. Handoff template (append to .agent/handoff.md)
## <task-id> — <date>
Files: <paths>
Verified: <command/test/screenshot>
Not verified: <items>
TODO-OWNER: <items>
Next: <task-id>
7. Suggested order
UX-0 → UX-1 with UX-21, UX-2, UX-3 (parallel) → UX-4 → UX-17 (so regressions are caught) → UX-22, UX-23, UX-24 → UX-6, UX-7 → UX-5, UX-8, UX-9, UX-10, UX-11 → UX-12 to UX-16, UX-25 → UX-18 → UX-19 → UX-20.
8. Limits of this spec
Evidence came from text extractions of the live pages. Some pages were returned truncated, and the extraction may not reflect rendered behaviour. Anything about layout, performance, accessibility attributes, and mobile behaviour is untested. Items marked [VERIFY] and TODO-OWNER need confirmation before shipping.
References
1.	Experts | CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/app/experts
2.	About | CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/app/about
3.	Overview | CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/app/
4.	CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/index.html
5.	No expert selected · Expert profile · CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/expert.html
6.	Funding | CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/app/funding
7.	Institutions | CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/app/institutions
8.	Monitoring | CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/app/monitoring
9.	Plastics research funding · CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/grants.html
10.	Evidence map | CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/app/evidence
11.	Policy | CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/app/policy
12.	Related resources | CA Plastics Research Atlas. Retrieved 2026-11-12, from https://plastiverse.live/app/resources
13.	DevTools MCP server updates. Retrieved 2026-11-12, from https://developer.chrome.com/blog/new-in-devtools-146
14.	Connect your agent to the browser. Retrieved 2026-11-12, from https://developer.chrome.com/blog/devtools-for-agents-v1?hl=pl
15.	UK Government. Automated accessibility testing - Intelligence Community Design System. Retrieved 2026-11-12, from https://design.sis.gov.uk/accessibility/testing/automated-testing
16.	Playwright MCP | Playwright. Retrieved 2026-11-12, from https://playwright.dev/docs/getting-started-mcp
17.	Accessibility Insights for Web - Engineering@Microsoft. Retrieved 2026-11-12, from https://devblogs.microsoft.com/engineering-at-microsoft/accessibility-insights-for-web
18.	Mondragón HC, Luna-García H, Sarmiento WJ, Celaya Padilla JM, Despradel CA, Villalba Condor KO. AI Agents for Heuristic Usability Evaluation: A Comparative Study with Human Experts. Communications in Computer and Information Science. 2026;:1-15. doi:10.1007/978-3-032-31223-5_1.
19.	Hsueh NL, Lin HJ, Lai LC. Applying Large Language Model to User Experience Testing. Electronics. 2024;13(23):4633. doi:10.3390/electronics13234633.
20.	[2609.34854] AUV-Bench: Aesthetic Understanding and Generation Evaluation for User Interfaces. Retrieved 2026-11-12, from https://arxiv.org/abs/2609.34854
