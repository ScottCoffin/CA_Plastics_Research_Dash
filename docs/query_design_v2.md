# Plastics query v2 design input

Status: owner-supplied S1.5 input, recorded 2026-11-05. At the owner's request,
the findings and OpenAlex counts below were not independently reproduced in
this session. They are design evidence, not current production metrics.

## What the literature contributes

The external review found that the four papers support query vocabulary,
false-positive analysis, and domain-taxonomy seeds. They do not provide a
directly reusable OpenAlex query or a benchmark for California institutions.

| Paper | Reported search/screening contribution |
|---|---|
| Zhang et al. (2020) | Used microplastic term variants and reportedly removed 373 of 2,501 articles/reviews involving mechanical microplasticity. Contributes hyphenated/size variants, `resin pellet`, and mechanical exclusions. |
| Wong et al. (2020) | Used micro/nanoplastic wildcards with food/drink terms; reportedly screened 549 results to 330 because wildcard results included metal microplasticity. Contributes food-web, ingestion, inhalation, and dermal concepts. |
| Yang et al. (2023) | Used `microplastic* and soil*`; contributes identification, adsorption, porous-media, wastewater-treatment, soil, and agriculture concepts. No cleaning was reported in the supplied review. |
| Dullah et al. (2025) | Used a non-Boolean natural-language search across several services and had an unreconciled PRISMA count in the external review. Contributes human-exposure, estimated-intake, airborne, BPA, and phthalate concepts only. |

These searches came from Web of Science or non-Boolean services and therefore
must not be treated as OpenAlex syntax. Keyword screening remained necessary.
The external agent found no California-institution benchmark in these papers.

## Collision findings supplied by the external agent

- Bare `microfiber` returned 13,721 works; 4,588 also contained optical,
  photonic, waveguide, sensor, coupler, or similar terms. Use environmental or
  textile context instead of the bare term.
- Bare `tire wear` returned 2,436 works; 1,565 co-occurred with particle or
  environmental terms. Require particle/runoff/pollution/toxicity context.
- Mechanical terms overlapped 2,209 of 129,083 works in the earlier core query.
  Treat phrase exclusions as a precision aid, not a substitute for screening.

## Candidate `plastic-v2` behavior

The canonical term lists and candidate Boolean expression are in
`config/queries.yml`. Key changes from the broad S1.2 ranking heuristic are:

1. Search titles and abstracts for explicit microplastic/nanoplastic, plastic
   pollution/debris/litter, particle, ingestion, and pellet concepts.
2. Qualify generic `microfiber`, `tire wear`, and `plastic waste` terms with
   domain context.
3. Exclude explicit mechanical microplasticity phrases.
4. Keep chemicals-in-plastics in tier 2, consistent with G-1; retain qualified
   tire-wear and textile microfibers in core, consistent with G-2.

The external snapshot reported 98,118 global v2 works versus 129,083 for its
v1 core, and institution comparisons of UCSF 25 versus broad `search=plastic`
5,062; SLAC 2 versus 945; and UC Davis 129 versus 8,618. These values are
unverified snapshots and must not be shown in the public dashboard.

## Required S1.5 follow-through

- Render the query from configuration rather than duplicating terms in code.
- Store `query_version` and the rendered query with count caches; invalidate
  legacy flat caches and version mismatches.
- Smoke-test OpenAlex encoding, Boolean behavior, group-by behavior, and cost.
- Run the required count-only corpus estimate and record its timestamp.
- Perform a precision audit of sampled UCSF/SLAC/global matches and a recall
  audit against known relevant works before promoting the candidate to active.
- Use the tags in `config/taxonomy.yml` as seed concepts only; later classifier
  stages must validate and version actual tagging rules/models.
