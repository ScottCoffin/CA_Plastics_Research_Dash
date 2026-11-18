# PLAT-1 verification: California moved to /california/ (clean break)

Date: 2026-11-17. Decision: ADR-PLAT1-LAYOUT-2026-11-17 in `.agent/DECISIONS.md`.
Plan: `docs/PLATFORM_ARCHITECTURE.md` section 8 (phase P1).

## What moved

| Before | After |
|---|---|
| `framework/src/<page>.md` (14 pages) | `framework/src/california/<page>.md`; `framework/src/index.md` is the global page (placeholder until PLAT-2) |
| `/<page>` on plastiverse.live | `/california/<page>`; `/` is the global page |
| `site/expert.html` | `site/california/expert.html` (reads `../data/`, links `experts`, `institution#inst=`) |
| SEO pages `site/experts/<id>/`, `site/institutions/<id>/` | `site/california/experts/<id>/`, `site/california/institutions/<id>/` |
| Redirect stubs (`/app/*`, `grants.html`, `sem.html`, classic `index.html#tab`) | none (clean break; `assemble.py` removes leftovers) |

Unchanged at the root: `data/`, `assets/`, `feed.xml` (frozen ids, links now `/california/`), `status.html`,
`robots.txt`, `llms.txt` (links updated), `sitemap.xml` (lists `/` and `/california/...`).
Retargeted: search-index hrefs (`california/` prefix), ntfy click URL, digest `site_url`.

## Evidence (local, assembled deploy in `scratch/deploy_plat1`)

Built with `npm run build`, `scripts/build_seo_pages.py`, `scripts/check_s3_8.py` (ok: 2,649 expert
and 207 institution pages) and `scripts/assemble_site.py`, served by
`scripts/serve_framework_preview.py --assembled`.

- Routes: `/`, `/california/`, `/california/experts`, `/california/expert.html`,
  `/california/experts/<id>/`, `/data/index.json`, `/sitemap.xml` and the Archivo font return 200;
  `/experts`, `/app/experts` and `/grants.html` return 404.
- `scripts/check_at5.py --dist dist`: static and build checks pass (12 pages incl. the global page).
- `scripts/ux_tasks.py`: 6/6 tasks pass. Task 6 now checks that the global page leads to the
  California overview (the old "/app/ link redirects" task no longer applies). Tasks 1 and 6 use the
  current Overview copy (the VD-25 h1 and "Find a researcher"); the old strings had gone stale.
- `~/tools/ux-audit/ux_audit.py` on 14 routes (global page, every California page, the expert
  profile, search): axe 0 violations and 0 console errors on every route.
- `scripts/check_doc_links.py`: links OK.

## Owner action

After the deploy, resubmit `https://plastiverse.live/sitemap.xml` in Google Search Console (H32).
