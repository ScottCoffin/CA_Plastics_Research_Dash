# Handoff - 2026-11-12 - UX spec integrated; UX-0, UX-1, UX-21 done

## Done this session
- Owner UX/UI spec `docs/EM_spec.md` integrated as TODO section "UX" (UX-0..UX-25, ADR-UX-SPEC-2026-11-12); decisions UXD-1..UXD-9 are QUESTIONS rows with defaults in use (owner task H17).
- Live browser audit (Playwright + axe-core 4.10.3 + Lighthouse 12.8.2, 12 routes, desktop + 375 px) recorded as spec Section 1A: Classic-site link and internal vocabulary confirmed; expert-profile links and stuck loading text NOT reproduced; new UX-21..UX-25 (lang/viewport, contrast, headings, Monitoring CLS 0.50, mobile overflow).
- UX-1/UX-21 (`docs/UX_1_VERIFICATION.md`): `framework/scripts/postbuild.mjs` fixes the Classic-site href (`../index.html`), `<html lang="en">` and viewport zoom; classic `site/index.html` banner links to `app/`.
- Machine-wide audit tool `~/tools/ux-audit/` (README; listed in the owner's global CLAUDE.md and Codex AGENTS.md).

## Verified / not verified
- Verified: full gate (1,353 passed), check_at5 --dist, smoke on 9 pages, Playwright click-through of both links and axe on the local preview.
- Not verified: live deploy of this commit (check CI run); remaining axe findings (UX-22..UX-25).

## Next eligible (dependency order)
1. UX-2 (expert.html empty state + `?id=` alias), UX-3 (internal vocabulary + rendered-HTML string check), then UX-4, UX-22, UX-23, UX-24.
2. After H16 ("switch"): Framework at the root. 2026-11-13: CORE audit (H1); eScholarship resume (72 pending).

## Owner actions (details in `.agent/HUMAN_TASKS.md`)
- H17 answer UXD-1..UXD-9; H16 compare /app/ and answer EM5-STRIP; H1 CORE key; H2, H15, H8, H9.
