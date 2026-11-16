# NET-1 verification: research networks (Land to Sea Microplastics Consortium)

Date: 2026-11-15. Owner request: link the UC Davis Land to Sea Microplastics Consortium,
with its logo on the UC Davis page.

## Sources
- Steward page (owner-supplied saved copy; the live page returns HTTP 403 to automated
  clients): title "Land to Sea Microplastics Consortium | Coastal and Marine Sciences Institute",
  canonical `https://marinescience.ucdavis.edu/microplastics-consortium-source-solution`,
  "Last update: October 29, 2026". The aim sentence and the four focus-area headings in
  `config/research_networks.yml` are verbatim from that page.
- Logo: the URL the owner gave (1000 x 250 PNG, HTTP 200), cropped to the droplet, outer white
  made transparent, 160 px palette PNG (4,812 bytes). Terms recorded in `docs/REUSE.md`.

## Contributors vs the Atlas
The page lists 14 contributors. 6 have Atlas expert profiles (name match against
`site/data/index.json`, lead-checked): Susanne Brander, Scott Coffin, Jenessa Gjeltema, Sanjai
Parikh, Karen Shapiro, Neil Tangri. 8 have none, which the owner attributes to no
plastic-related publications so far. The roster itself is not copied (link, don't mirror).

## Surfaces
| Surface | Result |
|---|---|
| `/institution#inst=I84218800` | Host card: logo, linked name, steward, quoted aim, 4 focus chips, 6 contributor links, "14 contributors ... 6 have Atlas expert profiles", policy-brief link, disclosure |
| OEHHA, CDPH, Oregon State, UC Berkeley, GAIA institution pages | One-line pointer to the consortium and the UC Davis page, plus disclosure |
| `expert.html#author=<id>` (6 experts) | Linked badge with an 18 px logo |
| `/resources`, Evidence Map strip | LO-13 (topics: human exposure and health, ecotoxicology, analytical methods); disclosures now published for LO-8 and LO-13 |
| Static `/institutions/I84218800/` | Link, disclosure, JSON-LD `subOrganization` with logo; 4 CA member pages carry the pointer (Oregon State has no static page: not California) |

## Checks
- Full gate: doc links, A1/A2 scaffolds, Ruff check/format, compileall,
  `build_research_networks_json.py --check`, `build_linkouts_json.py --check`,
  `check_public_text.py`; pytest 1,702 passed, 9 expected skips.
- Framework build (`ATLAS_FW_OUT=dist-net1`), SEO pages and assembled preview: headless Edge at
  1280 and 375 px on UC Davis, OEHHA, Oregon State, Resources and an expert page: sections
  found, logo loaded, no console errors, no horizontal overflow; axe clean except the existing
  expert.html metrics `definition-list` row (UX-32).

## Not verified
- Live-site rendering (after deploy) and the weekly link check for LO-13.
- Logo permission from the consortium (H26).
