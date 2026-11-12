# UX-2 and UX-3 verification (2026-11-12)

Contract: `docs/EM_spec.md` (Sections 1A and 4). Implementation: Haiku workers; the lead reviewed, gated and browser-checked the work.

## UX-2: expert profile entry
- Browser audit, 2026-11-12: "Full profile" links (`expert.html#author=<id>`) already open
  populated profiles for the first three cards (Geyer, Rochman, Cole), so the link-breakage claim
  in Section 1 was not reproduced.
- `site/assets/expert_page.js` adds the pure function `parseExpertId(search, hash)`, which returns
  `{id, status: ok|missing|malformed, raw}`. It reads the ID from `#author=`, then `?author=`, then
  `?id=`, and accepts a full OpenAlex URL. `site/expert.html` routes on it and rewrites query
  addresses to the canonical `#author=` form.
- Local preview (Playwright, light theme):
  - `expert.html`: "No expert selected. To open a profile, choose an expert in the Experts list.
    Profile addresses look like expert.html#author=A5046986222."
  - `expert.html?id=A5046986222`: redirected to `#author=A5046986222`; Roland Geyer's profile renders.
  - `#author=bogus!`: "Invalid expert id. "bogus!" is not a valid OpenAlex author ID. An author ID
    is the letter A followed by digits..."
  - `#author=A0000000000`: "No profile is available for "A0000000000" in this snapshot."
  - Each message is followed by "Back to the Experts list".
- Tests: `tests/test_expert_page_ids.py` (9 tests, run under Node).

## UX-3: internal vocabulary
- Rewrites:
  - Institutions intro: "S3.1 export" became "data snapshot".
  - Policy: the EM-17 sentence became "In preparation: how the Ocean Protection Council's 22 early
    actions map to global plastics-policy topics."
  - Evidence placeholders: "In development."
  - About: the candidate-query and fixture sentences are now in plain language.
  - Status string: "Example data loaded — sample data, not a current refresh." (classic site and
    Framework app).
  - DTSC `source_label`: "(source document, not online)". This applies to three entries: the
    Background Document and the 2024-2026 Priority Product Work Plan (twice). They are listed for
    the owner in HANDOFF.
- `scripts/check_public_text.py` checks text nodes (comments, scripts and styles stripped) of the
  Framework build and the classic pages, plus string values in `dtsc_timeline.json` and
  `linkouts.json`. It runs in `ci.yml` (static) and in `build_deploy.yml` after the Framework build.
- Tests: `tests/test_check_public_text.py` (13 tests). A seeded "Coming with EM-8" fails, the same
  string inside a comment or script passes, and the real sources pass.
- Not covered: attribute text (`title`, `aria-label`).

## Gate
- Links, A1 and A2 scaffolds; `make lint test build`: 1,369 passed, 9 skipped; `git diff --check`.
- `check_at5.py --dist dist` and `check_public_text.py` (14 files) passed. The headless smoke
  passed on 9 pages.
