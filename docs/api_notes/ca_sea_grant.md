# California Sea Grant research projects (S8.5)

Source: `https://caseagrant.ucsd.edu` (Drupal site). Scraper:
`src/atlas/ingest/grants/ca_sea_grant.py`, CLI `scripts/ingest_ca_sea_grant.py`.
Verified live on 2026-11-09/10 with the User-Agent `ca-plastics-atlas/0.1 (research dashboard)`.

## robots.txt (verified)

- `https://caseagrant.ucsd.edu/robots.txt`, `User-agent: *`. Disallows include `/core/`,
  `/profiles/`, `/admin/`, `/search/`, `/search?`, `/user/login`, `/node/add/`,
  `/comment/reply/`. No rule covers `/our-work/research-projects` or project pages.
  No `Crawl-delay`.
- The crawl therefore never uses `/search/`. It uses the listing's `?keywords=` filter.
- `https://opc.ca.gov/robots.txt`: empty `Disallow:`, sitemap at `/sitemap_index.xml`.
  Only read for the cross-check.

## Listing (verified)

- `/our-work/research-projects`: about 44 pages of 11 rows (`?page=0` to `?page=43`).
  Full crawl would cost about 480 project fetches, so it is not used.
- Exposed filters: `keywords`, `field_status_value`, PI, co-PI, focus area, project type.
- Rows: `table.views-field-*`. Cells are `td.views-field-field-project-number`,
  `td.views-field-title` (anchor `href` under `/our-work/research-projects/<slug>`),
  `td.views-field-field-focus-area`, `td.views-field-field-project-date-range`
  (`<time datetime="YYYY-MM-DD">`). Header cells are `th` and are skipped.
- Paging: `li.pager__item--next` is present when a further page exists.
- `/projects` is an intro page with no list. `/research` returns 404.
- Keyword results (title hits seen): "microplastic" 6 rows, "plastic" about 10,
  "debris" about 7. Keywords match body text as well as titles and are loose
  ("plasticity" matches "plastic"), so the relevance filter runs on project pages.

## Project page (verified)

- Title: `h1.page-header`.
- `field--name-field-project-number` (`div.field--item`), e.g. `R/RCCE-12A`.
- `field--name-field-project-date-range`: `<time datetime>` start and end.
- `field--name-field-funding-agency`: one `span.field--item` per agency. Some values
  end with a comma, which is stripped.
- `field--name-field-focus-area`: `span.field--item` per area.
- `field--name-field-principal-investigators` and `...-co-principal-investigators`:
  one card per person. The name is the card's first `<a>`. The card nests
  `field--name-field-university-gov-affi`, so the institution is a second
  `field--item` and must not be read as a person.
- `field--name-body`: summary. Funding sentence: "funded by the California Ocean
  Protection Council (OPC) under Agreement No. ..., and is administered by California
  Sea Grant" (checked on R/RCCE-12A).
- Some pages carry Windows-1252 apostrophes. The decoder falls back to cp1252.

## Live request count

- Exploration (robots, home and listing pages, keyword listings, project pages, OPC
  pages): 17 requests.
- Scraper live run: 43 fetches (`requests=43`, 7 listing pages, 35 project pages,
  14 relevant, 0 invalid). Rerun from cache: 0 requests, 43 cache hits.
- Total: 60 of the 150-request cap. Cache: `data/raw/ca_sea_grant/` (ignored by git).

## Rows captured (14 relevant of 35 project pages fetched)

R/HCE-40A, R/HCE-40B, R/HCE-40C, R/RCCE-12A, R/RCCE-12B (the five OPC microplastics
projects), plus R/SFA-04, R/RCCE-16, A/EA-AR-64-18, R/CONT-220, A/EA-39M, R/RCCE-11,
R/RCCE-10, R/HCEOPC-50, A/EA-39F.

## Cross-check: OPC microplastics projects (DoD)

Evidence: OPC announcement "Microplastics Research Public Webinar and Panel - Recording
Available" (published 2025-11-07), `https://opc.ca.gov/2025/11/microplastics-research-public-webinar-and-panel-november-25-2025/`.
It says OPC and California Sea Grant provided $1.9 million "to fund five research
projects addressing microplastics in California", selected through two calls. It names
the speakers: Ludt (Natural History Museum of Los Angeles), Savoca (California Marine
Sanctuary Foundation), Lin (San Francisco Estuary Institute), Mohanty (UCLA), and
Fassman-Beck (SCCWRP).

The announcement does not list project numbers. The mapping below is by PI name on the
scraped project pages.

| Project | Title (as captured) | PI (page) | Captured |
|---|---|---|---|
| R/RCCE-12A | Design factors affecting microplastic retention, removal, and generation in structural best management practices | Sanjay Mohanty (UCLA) | yes |
| R/RCCE-12B | Field monitoring of microplastics loading and accumulation in low impact development-best management practices | Elizabeth Fassman-Beck (SCCWRP) | yes |
| R/HCE-40A | Investigation to assess clothes dryers as a source of microplastic pollution and inform solutions | Diana Lin (SFEI) | yes |
| R/HCE-40B | Plastics Past and Present: Understanding historical trends of microplastic consumption in California marine food webs to better inform future marine management | William Ludt (NHM LA) | yes |
| R/HCE-40C | From watershed to whales: Tracking the source and transport of microplastics in the greater Monterey Bay region to inform risk assessments | Matthew Savoca (CMSF) | yes |

All five are captured with OPC as the first funder and California Sea Grant as the last
`funder_chain` entry. The "administered by California Sea Grant" sentence was checked on
R/RCCE-12A only. The other four rely on the funder field and the project's Sea Grant
listing. No other OPC-funded microplastics project was found in the two calls.

## Mapping

- `source_award_id`: project number. `title`: h1. `pi_names`: principal and co-PI names.
- `org`: first institution. `org_state`: `CA` when the institution name matches a
  Californian marker (California, UC names, Cal Poly, CSU, Los Angeles, San Diego, and
  similar). Otherwise null. Never `false`.
- `start`/`end`: project date-range `datetime`. `amount`/`currency`: null (no amount
  on pages).
- `funder`: agencies joined with `; `. `funder_chain`: the agencies, then
  "California Sea Grant". For multi-agency projects the chain is a list of parallel
  funders, not a path.
- `program`: focus areas joined with `; `. `url`: project page.

## Limitations

- Relevance uses keyword listings plus the plastic-term rule. A project whose page
  names the term only in an unlinked attachment is not reached.
- `plastic_related` (provisional S2.3 rule) disagrees with the scraper's relevance in
  some rows, e.g. R/CONT-220 (4-nonylphenol). The scraper captured it on a summary term.
- The rule-based `org_state` depends on institution wording.
