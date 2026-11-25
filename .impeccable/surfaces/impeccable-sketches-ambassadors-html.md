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
