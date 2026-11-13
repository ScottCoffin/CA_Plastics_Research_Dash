# Handoff - 2026-11-12 (late) - UX-26 owner batch

## Done this session (checks: full gate 1,469 passed, AT-5 check, clean-worktree pytest before push)
- Framework: light theme only; Experts drawer lifted above the fixed header (it slid under it).
- Export (`atlas.build.export_site`): ordered `authors` + `author_count` on author-detail works;
  new `site/data/works_detail.json` and `site/data/work_text/abstracts.json` (lazy; subfolder so the
  abstract-free release snapshot stays clean). `site/data` regenerated locally (also applies the
  eScholarship evidence; counts unchanged at 1,909 works / 2,614 experts).
- Experts: proportional topic chips on expert.html; bylines on publication cards (page + drawer);
  co-authors outside the expert list now named (placeholder gone). Margaret Spring photo added
  (owner-supplied; credit to confirm, H19).
- Evidence map: related resources removed; trends and CA share follow the filters; interim
  provisional heatmap (topic x matrix / topic x time; S11.2 note); full-width publication table
  (sort/search/filters/CSV/lazy abstracts, newest first); "New in the last 2 weeks" callout and
  row badges; pipeline flow compact and collapsed.

## Not verified / left
- The Spring photo uses an absolute plastiverse.live URL, so it only renders after deploy.
- expert.html now fetches `data/index.json` (~2.5 MB) in the background to link expert names in
  bylines; consider a slim name map later.
- Pre-existing axe item on expert.html: `<small>` inside the metrics `<dl>` (definition-list).
- The CA share chart compares filtered California works with the unfiltered global query count
  (stated in the note under the chart).

## Next eligible (each needs an owner answer first)
1. UX-5 after UXD-3; UX-17 after UXD-9; UX-13 after H16; then the Framework-at-root switch.
2. S2.5 CORE audit after H1. S5 chain after H9 gold labels.

## Owner actions (details in `.agent/HUMAN_TASKS.md`)
- H19: photo credit line for Margaret Spring (or "remove the photo").
- H17 UX answers; H16 Framework comparison ("switch" or not); H1 CORE key.
