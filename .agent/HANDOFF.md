# Handoff — 2026-11-28 — VD-SM

## Done

- The owner lifted California's design freeze and made the global `--pv-*` colors, Schibsted Grotesk and Martian Mono canonical (ADR-ATLAS-PLATFORM-DESIGN-2026-11-27). The shared regional shell now covers California's research routes and styleguide, keeps its local route menu and region-aware search, and uses the black global-logo footer. Classic and SEO profile surfaces adopt the approved shared appearance.
- California route, data, feature, link and interaction contracts remain intact. The adopted regional pages retain metadata and favicon; postbuild uses one idempotent Schibsted preload and copies the canonical regional CSS and its self-hosted fonts into `framework/dist/assets/` for AT-5 package validation. Site assembly overlays the same canonical `site/assets/` sources.
- Funding Sankey names include the visible SVG label first and full title details; heatmap names include visible counts; `#grants-basis` is a named keyboard-focusable scroll region. The runtime fixture checks that each displayed Sankey label begins its accessible name.
- Integrated GP-1 passed all 17 routes and checked 257,655 links with zero broken. AT-5 package/build checks passed; production-style SEO generation and checks passed for 2,688 author pages and 209 institutions. Selected global pages and 7,934 California/Norway/Belgium data files matched baseline. Whole-repository Ruff and Markdown link checks passed. VD-SM is complete.

## State of the repo

- Build and assemble with `cd framework && npm run build && cd ..` and `py -3.14 scripts/assemble_site.py --site site --dist framework/dist --out scratch/vd_sm_site`.
- Check the Observable package with `py -3.14 scripts/check_at5.py --dist dist`.
- Run `py -3.14 scripts/check_gp1_contract.py --site scratch/vd_sm_site`; it passed for 17 routes and 257,655 links with zero broken. Keep California route, content, link, data-path, interaction, runtime and overflow checks active. The appearance exception is specific to VD-SM; later GP slices retain the historical California-preservation requirement. `--screenshots <dir>` is optional for side-by-side review; no GP-1 re-record is needed.
- Chromium review covered California research routes, both evidence selection modes, classic/SEO profiles, and representative global pages at 1440 px and 390 px. AT-5 and SEO page generation/checks passed as above.
- Focused Node checks and runtime fixture passed. Focused shell/Funding pytest passed with the built-page check enabled; Ruff lint/format and documentation links passed. Before pushing, run the strict clean-worktree full-suite gate and confirm the worktree is clean. After pushing, check hosted CI and the Pages deployment, then confirm the deployed site.
- On this Windows checkout, if `py` is inaccessible, use `C:/Users/scoff/AppData/Local/Python/pythoncore-3.14-64/python.exe`; set pytest `--basetemp` outside the workspace. A local Observable build may fail when esbuild cannot traverse `../..` under the sandbox; the lead's assembled build is the integrated verification path.

## Next task (suggested)

- Re-read TODO, owner direction and dependencies to choose the next checkpoint. Do not restart GP-10a or choose an arbitrary task.

## Gotchas the next agent must know

- GP-1's appearance exception is deliberate and applies only to VD-SM. Preserve the functional/data contract; keep historical California preservation for all other GP slices.
- Preserve the global token values and self-hosted font files. California header search relies on `data-atlas-site-search` and its route pathname to select the California search index.

## Needs owner input

- Optional visual review H25 remains in the existing VD-12 workflow; it does not gate VD-SM. Other owner items remain in [HUMAN_TASKS.md](HUMAN_TASKS.md), including H39. H64 remains deferred until a budget exists.

## Files that are large or unsafe to read whole

- `site/data/` — use the specific region payload or builder/check command; do not bulk-read.
