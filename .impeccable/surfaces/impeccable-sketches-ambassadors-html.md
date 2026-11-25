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
- No profile editing, no researcher profiles, no notifications centre, no map.
- No dark theme; the product is light, matching the global app.
- No live counts or claims about real people; sample activity is labelled as sample.

## Lead review notes (2026-11-25)

- Landing header shows both "Sign in" and "Sign out": prototype state only; the build shows one.
- The local-language case shows an abstract. Public case files (`ambassador_cases.json`) carry titles only, so
  abstracts must come from the backend to signed-in ambassadors (no abstracts in public files).
- The English "machine gloss" needs a translation step the Atlas does not have; drop it or decide a provider.
