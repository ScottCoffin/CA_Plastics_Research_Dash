# Handoff — 2026-11-16 — task VD-7a

## Done
- VD-7a Monitoring adoption is implemented at commit `6e89d172`, deployed, and accepted. Shared caution/disclosure/filter/map presentation is in place; the UX-19 320 px reflow row is closed.
- Live 1440 x 900, 390 x 844 and 320 x 568 audits: axe 0, no horizontal overflow or browser/request errors, and no sub-24 px actionable target except Framework's inert 1 x 1 checkbox.
- Direct and extended marker clicks, Enter/Space, drag preservation, submit-safe filter Enter, and keyboard-focusable horizontal details all pass. Evidence: `docs/VD_7A_VERIFICATION.md` and `scratch/ux_vd7a_live_acceptance/`.
- Three live Lighthouse runs: performance 97, accessibility/best-practices/SEO 100, CLS 0. This passes the Section 9 score gate exactly (live control 100); LCP increased from 1.7 s to 2.4-2.5 s and is not hidden.

## State of the repo
- VD-7c and VD-8 implementation files and verification drafts remain intentionally uncommitted for their own atomic checkpoints; independent Luna reviews requested bounded fixes before acceptance.
- The owner's unrelated formatting edits in `.agent/QUESTIONS.md` remain untouched and uncommitted.
- Pages is restored and deployment workflows pass. H27 now tracks only the remaining GitHub **Enforce HTTPS** switch; HTTP currently does not redirect.

## Next tasks (suggested)
- Finish, commit, deploy and live-audit VD-7c, then VD-8 as separate checkpoints.
- Re-read the roadmap and delegate the next independent available VD tasks (VD-9, VD-10 and VD-11) to Luna workers.

## Gotchas the next agent must know
- `serve_framework_preview.py` serves under `/CA_Plastics_Research_Dash/`; browser scripts must include the prefix.
- Compare Lighthouse only between equivalent live runs; the single-threaded local preview makes LCP numbers much slower.
- Preserve the owner's `.agent/QUESTIONS.md` edits and stage only the current checkpoint.

## Needs owner input
- H25 (VD-12 design review) and VD-5's absolute LCP target remain open.
- H27: enable GitHub Pages HTTPS enforcement after the renewed certificate becomes available.
