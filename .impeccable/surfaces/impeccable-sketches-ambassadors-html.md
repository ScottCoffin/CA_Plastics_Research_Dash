---
version: 1
slug: "impeccable-sketches-ambassadors-html"
primary_target: ".impeccable/sketches/ambassadors.html"
related_targets: ["docs/AMBASSADORS_SPEC.md"]
---

# Surface: Local ambassadors (AMB-1 design prototype `.impeccable/sketches/ambassadors.html`)

Mode: Operate for the workspace, reviewer, forms and moderation; Read-leaning for the landing and sign-in copy. Design only: the owner reviews before any build (AMB-1 step 2).

Audience: researchers and community leaders in California, Norway and Belgium who check or add regional knowledge; the owner and region leads who moderate. Plain language; no "expert" or "experts" in public text (researchers, local collaborators).

Job: get an eligible person from "can I join?" to a clear first task in minutes, then let them make many one-case-at-a-time decisions quickly, with every change visibly waiting for review.

Visual system: Plastiverse Live tokens as on the global app and region pages (ground, navy ink, slate data, coral for live marks only, sun highlight for matched terms). Schibsted Grotesk and Martian Mono, self-hosted. Flat, square, hairline rules; no cards inside cards; no eyebrows above headings.

## Key interaction decisions

- One case per screen for stream A, with the admitting terms highlighted and the machine decision shown beside the evidence. Agree, Disagree and Unsure are one-click; Disagree reveals the right-value choice; a saved line and a Next case link follow. Keys A, D, U, 1 to 3, N, B.
- Two case kinds (institution in region; local-language relevance) use the same frame, so the owner can compare them.
- Eligibility checker is a single field (email or institution name) plus region, with three outcomes: eligible (named institution and domain), not eligible yet (email route as text), and free-mail refused.
- Sign-in asks only for region and institution email, with a Turnstile placeholder; the "check your email" and expired-link states are separate screens.
- First visit separates the required terms consent (CC BY-NC 4.0) from the optional public credit, which shows a live preview.
- Stream C has two structured forms (group or organisation; local policy with dated fields). Unknown dates are shown as "date not known", never guessed.
- Moderation shows field-level before/after with text labels ("Changed", struck-through removals, highlighted additions), so the diff does not rely on colour alone. Approve, ask for changes and reject are separate; reject and changes need a note.
- The region lead badge and moderation link appear only in lead view (toggle in the owner switcher bar, which is prototype-only).

## Open questions for the owner

1. Do Norway and Belgium ambassadors see the Belgium and California institution names, or only their own region's allowlist?
2. Should a single-ambassador answer be visible to that same ambassador as "suggestion pending", or only after consensus?
3. Is "Show a public credit" default-off (as drafted) acceptable for the pilot?
4. Should the stream A save auto-advance to the next case, or stay on the saved line as drafted (safer for review, one more click)?
5. Final wording of the contribution terms and the link target (the full text does not exist yet).
6. Region lead promotion: who approves a lead, and can a lead see other regions' queues (drafted: no)?
7. Sample names and domains (NIVA, NTNU, SINTEF Ocean, VLIZ, UC Santa Barbara) are illustrative; confirm the eligibility rule shows real allowlist data before pilot.
8. "Handelens Miljøfond — to confirm" stays a placeholder; no URL is invented.

## Deliberately left out

- No real sign-in, timers, storage, email, or Turnstile; all state is in-page and resets on reload.
- No photos or images (none are approved for ambassadors yet), so the text-over-image rule is not exercised.
- No profile editing, no researcher profiles, no notifications centre. The round 2 world map is included.
- No dark theme; the product is light, matching the global app.
- No live counts or claims about real people; sample activity is labelled as sample.

## Lead review notes (2026-11-25)

- Landing header shows both "Sign in" and "Sign out": prototype state only; the build shows one.
- The local-language case shows an abstract. Public case files (`ambassador_cases.json`) carry titles only, so
  abstracts must come from the backend to signed-in ambassadors (no abstracts in public files).
- The English "machine gloss" needs a translation step the Atlas does not have; drop it or decide a provider.

## Round 2 (AMB-1 design, spec sections 8 and 9)

New screens and states:
- 1 Landing: the Regions list is replaced by a world map (Natural Earth projection, d3 `geoNaturalEarth1`, world-atlas 2.0.2 countries 1:50m, pinned jsdelivr). Colours: ambassadors active (coral), proposed (hatched, with a legend text label), open. Small countries have focusable dots; California is outlined on the US. Zoom buttons, keys (+, -, 0, arrows), drag. A side panel shows status, ambassadors, eligible institutions, works (sample) and the action (join, or propose with a prefilled unit). A table alternative is behind a toggle.
- Search above the map: one combobox over about 60 sample places (countries, subdivisions, cities), arrow keys, Enter and Escape. Results show name, kind and parent. Choosing a place zooms to its bounds or a 300 km minimum box.
- 9 Propose a region: pick units by search or on the map, city radius slider per city (default 25 km), running summary (units, eligible institutions inside, works as sample figures), name, proposer institution. Outcomes: inside, so live at once (active on the map); outside, so sent for review (proposed, waiting). The stored rule is shown in plain text, e.g. "countries: PW, FM, MH, ...".
- 10 Region tree and splitting (owner and region lead): group tree, Samoa split (own ambassador and 50 works), Oakland city split under California (own ambassador and 58 works), before and after preview, split or keep grouped.
- Dashboard: "Plan a session" (5, 15 or 30 minutes), a plan list, a task table with "fits this session", and the total "about 15 minutes for the next 30 cases". Durations appear on every stream and task.

Decisions taken in this round (recorded as defaults; owner can change):
- Zoom minimum box is 300 km (spec). Island states (Palau, Micronesia, Marshall Islands, Kiribati, Solomon Islands, Vanuatu, Nauru, Tonga, Samoa, Tuvalu, Fiji) zoom to a 300 km box around their main islands, not their full feature bounds, because the bounds include far atolls.
- Tuvalu has no polygon in Natural Earth 1:50m, so it is a dot only.
- Estimates: case 30 s, placeholder 2 min, group 5 min, policy 8 min, region 5 min; the stream A estimate note shows 14 of 20 answers.

Open questions for the owner:
1. City radius default: 25 km proposed. Should the radius be fixed by the region lead or chosen by the proposer?
2. Do "proposed" regions (including ones waiting for review) appear on the public map, or only once approved? Drafted: proposed shows publicly as a hatched area; pending review is visible only in the panel text.
3. Split threshold: own verified ambassador AND at least 50 plastics works (Tier B). Is that the final rule, and must the child also keep the parent's ambassador?
4. The 300 km minimum box leaves Palau's main islands at about a sixth of the map width. Should island states use a smaller minimum (about 120 km) so the islands fill more of the view?
5. Koror has about 11,000 people, below the 15,000 GeoNames rule for places. It is in the index because the owner named it. Keep it as a named exception?
6. Subdivisions: California is drawn from a simplified outline; Vestland, Flanders and Alameda County are approximate boxes. Real admin-1 geometry (Natural Earth admin-1 or GADM) is needed before the pilot.
7. Estimates for lead and owner tasks (moderation, region tree) are not set; the spec lists five kinds only.
8. Does the shared `/explore` map adopt the same search and minimum-box rule (spec section 8)? Not changed here; the prototype does not touch `/explore`.
9. The Pacific Island countries group, Samoa, the National University of Samoa and all works and ambassador counts are sample data.

Still not built: no real geocoder, no GeoNames data, no persistence, no real auth.

## Round 3 (AMB-1 design, spec section 10, 2026-11-25)

New and changed screens:
- Institution entry (landing eligibility checker and "Your institution" on screen 9): text field with an ARIA combobox (name, acronym, alternate names, email domain; type and city shown). Sample catalogue of 40 institutions: 12 Norway, 12 Belgium, 15 California, 1 Samoa (National University of Samoa, kept so the Samoa proposal example works). No drop-downs remain for institutions.
- Boundaries on every world map: Natural Earth disputed boundary lines (dashed) and Pacific groupings (dotted), loaded from jsDelivr v5.1.2 (`ne_50m_admin_0_boundary_lines_disputed_areas.geojson`, `ne_10m_admin_0_pacific_groupings.geojson`). Legend entries and a credit line state the default Natural Earth view on disputed areas. If either file fails, the map still works and the credit says so.
- Map controls: d3-zoom (wheel or trackpad, drag, pinch, double-click). Keyboard + - arrows 0 when the map has focus. The external buttons are gone; an overlaid control group sits in the map frame's top-right corner. Zoom is bounded (1x to 150x; 150x is needed for the 300 km island minimum box). Strokes are non-scaling.
- Screen 9 opens centred on the landing selection (hash parameter `propose?place=KEY`, else the landing selection, else Norway). Selected units use a mint fill with an ink outline drawn on top.
- Ambassador badge ("Ambassador · Norway") on the landing "Show your Ambassador badge" block (top researchers and search-result mocks), the workspace header, and the linked author profile on screen 11. One switch hides it on screens 11 and 14.
- Screen 11 Link your author record: name search, radio list of OpenAlex records with ORCID when known, linked when name and institution match exactly, otherwise pending moderator check.
- Screen 12 Emails: welcome, fortnightly reminder (with the pause rule), and the "nothing else is sent automatically" statement.
- Screen 13 Invite your co-authors: eligibility by region, mailto Draft invitation (empty recipient, subject and body), Copy invitation with the personal link. No co-author address is shown or stored.
- Screen 14 Notification settings: reminders switch, fixed two-week frequency, badge switch, unsubscribe.

Decisions taken in this round (defaults; owner can change):
- Selected-unit fill changed from slate to mint. Ink on slate is about 2.5:1, which fails the 3:1 rule; ink on mint is 11.7:1, and ink against the sea wash is 13.3:1.
- The eligibility combobox lists the institutions of the selected region only; the proposal's institution combobox lists all regions.
- Pacific groupings use slate dotted lines (not light slate) so they meet 3:1 on the paper and sea colours.
- Map wheel zoom captures page scroll while the pointer is over the map (touch-action none). Accepted for the prototype.
- Co-author invitations are sent from the ambassador's own program only; the Atlas stores none of them.

Open questions for the owner:
1. Should the badge text be "Ambassador · Norway" (as drafted) or add the institution as well?
2. Does a linked-but-pending author show on the public author page without the badge (drafted: yes, without badge)?
3. Sender address for the emails: `ambassadors@plastiverse.live` is a placeholder; confirm it.
4. Reminder time estimate: the reminder shows only the placeholder tasks (about 12 minutes) and lists stream A progress without a total; confirm whether stream A counts as a task.
5. Is the map wheel capture acceptable on phones, or should page scroll win until the map is focused?
6. Co-author eligibility uses the same allowlist as sign-in; confirm co-authors outside the list get the email route, not an error.
7. Sample names (co-authors, authors, Ole Vik, Marte Lie) are invented; replace with real corpus data before the pilot.
8. Natural Earth boundaries: confirm the default-view credit wording with the owner.

## Lead review notes (round 3, 2026-11-25)

- Screen 9 map shows a dashed box west of Bergen whose meaning is not labelled; identify it (city radius preview, grouping line or disputed line) or remove it.
- The prototype map still captures the mouse wheel. The build uses the cooperative rule now live on /explore (spec section 10): Ctrl/Cmd or a click to zoom, one finger scrolls the page.

## Round 4 (AMB-1 design, spec section 11, 2026-11-25)

New and changed screens:
- Badge: one SVG seal component (`badgeMarkup`), drawn into every `[data-amb]` element. Seal 18 px inline and 64 px on the landing explainer and the author profile header. Label ribbon: "Ambassador" and the region. Accessible name "Plastiverse Live ambassador for <Region>" (role img). Ink seal with the gold sun mark from the header, coral ring (decorative), butter ribbon with ink text (13.5:1). Gold sun on ink is 8.0:1.
- Eligibility row: place field (same combobox as the landing map, pre-filled from the landing selection, default Norway) and institution or email field on one row at 700 px and wider. Labels are one line, both fields 44 px, the button is bottom-aligned. Stacked below 700 px. No select.
- Sign-in: region radios removed. "Signing in for: <place> — change" with a small map preview; change reveals the same place search.
- Screen 11: "Connect your ORCID" first. ORCID iD icon, then states: "Connecting to ORCID...", "ORCID verified: 0000-0002-1825-0097", then either "Matched to your Plastiverse Live author record: A. Example, NIVA, 18 works — badge active" or "No match yet — search your name instead" (falls back to the name search). Proto bar switch "ORCID mock: no match" shows the second outcome.
- Workspace opens with the Norway region map: mainland outline, 13 sample institution points, numbered task markers (1 Oslo, 2 Bergen, 3 Trondheim), legend.
- Screen 9: the map is the main element. Content width (max 1360 px wrap), height clamp(420 px, 66vh, 760 px): 594 px at 1440x900. Units list and summary sit beside the map at 1600 px and wider, below it otherwise.
- Screen 15 "Share monitoring data": who (me, or an organisation with type-ahead or free text, role, permission checkbox), dataset name, sampling period, place (search and map), matrix chips, size chips, methods, QA notes, access (public link or DOI, or a file upload stub "stored privately until reviewed"), five licence cards with one-line explanations, publication choice (summaries only, or summaries and rows), rights confirmation. Submit shows "In review; nothing is published until its licence is cleared." Linked from workspace stream C and the landing "Add local knowledge" text.
- Cooperative gestures on every map (spec 10): wheel zooms with Ctrl/Cmd, or after the map is activated by click, tap or focus. Escape, focus leaving or the pointer leaving deactivates. A blocked wheel scrolls the page and shows a hint for 1.8 s. Touch: `touch-action: pan-y`; the zoom filter accepts only two-finger gestures.

Decisions taken (defaults; owner can change):
- Region for a place: Norway, Belgium, California or Samoa from the sample catalogue. Places with no institution list get the email route with a plain message.
- Workspace map centres on Norway's mainland. Svalbard, Jan Mayen and Bouvet are kept out of the framing (the country shape includes them).
- ORCID iD in the mock is ORCID's documented example iD (0000-0002-1825-0097, the one used in ORCID's own docs); it is not a real person's record.
- Share: no publication option or licence is pre-selected; the form requires both.

Credits and licences:
- Badge seal: outline adapted from Lucide's `badge` icon (ISC licence, https://lucide.dev). Credit comment is in the HTML. The path was written from the Lucide icon as recalled, not copied from a fetched file; check it against lucide.dev before build.
- ORCID iD icon: a simplified stand-in (green #A6CE39 circle with white "iD" text). Replace with the official iD file from ORCID's brand guidelines page before build. White on that green is 1.8:1, as in ORCID's own mark; the icon is aria-hidden and the button label carries the name.

Open questions for the owner:
1. Badge label: "Ambassador" and region only, or also the institution (round 3 question 1, still open)?
2. ORCID: owner registers the free public API client and the redirect URI on the Worker. Confirm the sample name "A. Example" for the mocked match.
3. Share: should "Summaries only" be pre-selected, or should the owner be forced to choose (drafted: forced)?
4. Share: place required at region granularity, or may it be any unit on the map?
5. Touch: two-finger pan and pinch need a visible hint on phones; is the hint text enough?
6. Ctrl/Cmd and activation: is the 1.8 s hint acceptable, or should the hint persist until the map is clicked?

Verification (round 4 self-check, 2026-11-25; scratch/amb_design4/):
- Eligibility row at 1440x900: place and email fields 44 px tall, same top (difference 0 px), button bottom-aligned (0 px). Stacked at 375 px.
- Propose map: 594 px tall at 1440x900 (0.66 of the viewport).
- Workspace map: Norway outline centred (0 px offset).
- Wheel over an inactive map scrolls the page with the map unchanged; Ctrl-wheel zooms; click activates; Escape deactivates.
- Badges: 6 Norway badges, each with the accessible name.
- No horizontal overflow at 375 px on any screen. No page or console errors.
- axe-core NOT run: it is not on disk and the sandbox rules block fetching it. Run it before the build.

## Lead review notes (round 4, 2026-11-25)

- axe-core run by the lead on all 19 screens at 1440x900 and 375x800: 0 violations.
- Before the build, replace the hand-drawn Lucide badge outline and the simplified ORCID iD icon with the official assets (Lucide ISC; ORCID brand guidelines).
