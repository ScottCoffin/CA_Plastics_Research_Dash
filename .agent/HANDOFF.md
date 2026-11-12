# Handoff - 2026-11-12 - UX spec integrated; UX-0..UX-3, UX-21 done

## Done this session
- Owner UX/UI spec `docs/EM_spec.md` integrated as TODO section "UX" (UX-0..UX-25, ADR-UX-SPEC-2026-11-12); decisions UXD-1..UXD-9 are QUESTIONS rows (owner task H17). Live browser audit (Playwright + axe + Lighthouse) is spec Section 1A.
- UX-1/UX-21 (`docs/UX_1_VERIFICATION.md`): Classic-site link, new-version banner, `lang`/zoom via `framework/scripts/postbuild.mjs`; live after deploy (CI green).
- UX-2/UX-3 (`docs/UX_2_3_VERIFICATION.md`): expert.html ID handling and messages; internal vocabulary removed; `scripts/check_public_text.py` in CI and deploy.
- Machine-wide audit tool `~/tools/ux-audit/` (owner's global CLAUDE.md and Codex AGENTS.md point to it).

## In progress (uncommitted, lead)
- UX-22: `framework/src/style.css` raises muted/faint text mixes to 75%/68% and underlines in-text links; light theme has 0 axe contrast/link nodes on all 9 routes. Dark theme still fails (51 nodes): page CSS hardcodes light-theme muted text `#536879` (panel-intro, data-note in institutions/monitoring/funding CSS) and the Experts h2 renders `#cbcbc3` on white. Fix those with theme variables, re-run `scratch`-free audit (`~/tools/ux-audit/ux_audit.py`), then seal.

## Next eligible
1. UX-22 finish, UX-23 (h1 on Experts/Funding, heading order), UX-24 (Monitoring CLS 0.50, nested-interactive), UX-4 (Evidence honest state).
2. After H16 ("switch"): Framework at the root. 2026-11-13: CORE audit (H1); eScholarship resume (72 pending).

## Owner actions (details in `.agent/HUMAN_TASKS.md`)
- H17 answer UXD-1..UXD-9. DTSC entries now labelled "source document, not online" (Background Document; 2024-2026 Priority Product Work Plan x2): send public URLs if they exist.
- H16 compare /app/ and answer EM5-STRIP; H1 CORE key; H2, H15, H8, H9.
