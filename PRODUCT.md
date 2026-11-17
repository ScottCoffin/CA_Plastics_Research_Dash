# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Four audiences, confirmed by the owner on 2026-11-16, none ranked above the others:
- Researchers looking for collaborators, datasets, funding, or gaps.
- Agency staff (for example OEHHA, DTSC, Water Boards, OPC) who need a California plastics expert, monitoring data, or funding context quickly.
- Funders and policy staff sizing up California's research capacity.
- The public and press (journalists, NGOs, residents) curious about plastics research in California.

## Product Purpose
CA Plastics Research Atlas (plastiverse.live) is a static public dashboard and reproducible Python pipeline that maps plastic-related expertise, publications, monitoring data, and funding connected to California. Success: a first-time visitor picks the task they came for (find a researcher, see funding, check monitoring data, explore evidence) within seconds, and can trust where every number came from.

## Positioning
A transparent, reproducible starting point: every count is traceable to open sources (OpenAlex, ROR, CEDEN and other monitoring registries, public grant databases) through published methods, and the data rebuild automatically every day.

## Operating Context
- Daily GitHub Actions ingest from OpenAlex; daily build and deploy to GitHub Pages; weekly source watch; watchdog and keepalive jobs.
- Static site (Observable Framework); no server or database; data ship as JSON and Parquet.
- Pages: Overview, Experts, Collaboration network, Institutions, Monitoring, Funding, Evidence map, Policy, Related resources, About, Glossary, site-wide Search.

## Capabilities and Constraints
- No external CDNs at runtime; fonts are self-hosted.
- Colours live as tokens in `framework/src/design/tokens.css`; CI allows no hex literals elsewhere.
- WCAG AA; axe-clean routes are a CI expectation.
- Topic and matrix tags come from keyword rules and are provisional; monitoring observations do not establish statewide coverage.

## Brand Commitments
- Name: CA Plastics Research Atlas.
- Footer disclaimer: "Independent project; not an official OEHHA or State product." Never imply State endorsement.

## Evidence on Hand
Live counts in `site/data/build_metadata.json` (authors, works, institutions, California institutions, awards, monitoring samples and sources, network experts and links, plastic-related works). No testimonials, users, or press exist; do not invent any.

## Product Principles
- Tasks before tour: route each audience to its job immediately.
- Show provenance next to every number.
- Plain language over jargon; define terms in the Glossary.
- Honest scope: say what the data cannot show.

## Accessibility & Inclusion
WCAG 2.1 AA, keyboard-complete, reduced-motion respected, usable at 375 px.
