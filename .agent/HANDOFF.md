# Handoff — 2026-11-27 — GP-SHELL

## Done

- Norway and Belgium feature pages use the Plastiverse Live shell and typography, local menu and search, and global footer styling. The site wordmark links home and the scope menu links to the regional pages. California route and data files matched the preceding checkpoint byte-for-byte. The global landing, Explore, groups, ambassadors and quality HTML matched as well.
- The evidence heatmap selection keeps the count ramp and selected ring. Unselected counts and zero-count filter labels use opaque, contrasting ink. Chromium measured a minimum of 5.02:1 for enabled cells after selection and zero axe violations across both modes at 1440 and 390 px in California, Norway and Belgium. Keyboard selection and clear passed. California evidence styling changed with owner approval and its data files matched byte-for-byte.
- `/norway/topics`, `/belgium/topics`, and regional search reuse the California renderer and builders. The topic denominator is unscreened query hits. The rising-share screen uses rule labels and institution checks. Search resolves to regional pages, author profiles, institutions and tag-filtered author lists.
- `scripts/build_topics_json.py --region <slug> [--check]` and `scripts/build_search_index.py --region <slug> [--check]` emit the payloads from the committed region export. Both checks passed for both regions. See [region export design](../docs/GLOBAL_PARITY.md#3b-port-design-region-exports-in-the-california-schema-lead-2026-11-26).
- GP-1 passed for all 17 California routes with 257,265 checked links and zero broken. All 4,993 assembled files in `california/` and `data/california/` matched the pre-change build byte-for-byte.
- Chromium verified both regional topics and search routes at 1440 and 390 px with zero axe violations, JavaScript errors, HTTP errors or document overflow. Search loaded its own region's index.
- Earlier port checkpoints cover institutions, author lists and profiles, networks, topic tags, works and evidence maps (GP-5/2/3/4/8/8b).

## State

- Region export building reads the local global partition and raw cache. The GP-10a builders only require the committed region exports.
- The committed California search index already reported stale at baseline. Fresh California outputs from the old and new index builders matched byte-for-byte. The published California index was preserved as required by GP-10a.
- On this Windows checkout, the sandbox can report the ten Norway and Belgium bundle files as deleted and deny esbuild directory traversal. An approved local check confirmed the files are present and unchanged. Use the direct Python executable from [LESSONS.md](LESSONS.md) if the WindowsApps launcher is inaccessible.
- Observable reports 16 pre-existing unresolved links in the unassembled build (feed paths and Norway/Belgium institutions references). GP-10a introduced zero additional warnings.

## Next checkpoints

1. GP-GROUPS puts the scoped interactive map first and applies the `/explore` shell to the groups views.
2. VD-SM transitions the California Atlas to the main site's design. The owner lifted the design freeze and confirmed the global typography and colors as the source. Apply Impeccable and the platform-wide app design in [DESIGN.md](../DESIGN.md).

## Verification

Build with `npm run build` in `framework`, then assemble with `scripts/assemble_site.py --site site --dist framework/dist --out scratch/<task>_site`. Run `scripts/check_gp1_contract.py --site scratch/<task>_site` and Chromium at 1440 and 390 px on the affected region routes. Inspect axe, page errors, HTTP errors, region data paths and overflow. Before pushing, run links, scaffolds, Ruff, `git diff --check`, and the full test suite with an external pytest `--basetemp` in a clean worktree.

## Needs owner input

See [HUMAN_TASKS.md](HUMAN_TASKS.md) for H39, H9, H2, H42 and H28. Every-country scale still depends on GX-1 and R2 (GX-3). H64 remains deferred until a budget exists.
