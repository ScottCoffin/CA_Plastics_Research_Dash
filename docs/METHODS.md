# Methods

This document describes the implemented versioned queries, data normalization,
classification, geographic logic, evaluation, and refresh process. The
definitions in `spec.md` A2 are authoritative during bootstrap.

## Candidate plastics query

The owner-supplied `plastic-v2-candidate` vocabulary and Boolean design are in
`config/queries.yml`; supporting collision findings and literature-derived
taxonomy seeds are documented in `docs/query_design_v2.md`. The S1.2
`search=plastic` counts remain review-priority metadata and are not a
publication corpus or leaderboard.

Any term, Boolean, exclusion, or field-scope change increments the query
version. Count caches must store both the version and rendered query and must be
discarded when either differs. The candidate is not production-active until
S1.5 reproduces a timestamped count estimate and completes precision/recall
checks.

S1.5 implementation is in `src/atlas/query.py`. It renders the core Boolean
expression from the structured term lists, builds a fully encoded
`title_and_abstract.search` filter, and rejects count caches unless both
`query_version` and `rendered_query` match. The ignored local cache is
`data/interim/openalex_query_counts.json`; the live smoke/audit runner is:

```powershell
py -3.14 scripts/smoke/query_s1_5.py
py -3.14 scripts/check_s1_5.py
```

The count is metadata-only (`per_page=1`, grouped by publication year); the
smoke also compares the exclusion-bearing query with its positive control,
checks URL encoding and group-by response shape, and records OpenAlex response
credits/costs through the shared logger. Precision is a bounded manual
title/abstract review of UCSF, SLAC, and global samples, while recall uses the
four literature-informed anchors in
`tests/fixtures/s1_5_known_relevant.json`. These are screening checks, not a
replacement for the later owner promotion review or the gold-set evaluation.

## Public snapshot, definitions, and limits

The site is a static export of OpenAlex work, author, and institution metadata
joined to the project's California institution registry. The browser reads the
exported JSON and does not query OpenAlex. `site/data/build_metadata.json`
records the export's `generated_at` timestamp and the counts reported on the
About tab. The timestamp is the time this static snapshot was built; it is not
the last-modified time for every underlying OpenAlex record. The value
`"fixture"` is a deliberate sentinel for the committed demonstration data and
must be presented as fixture data, not as a current refresh.

The displayed counts mean:

- **Authors:** author records in the exported index.
- **Works:** work records in the exported index.
- **Institutions:** institution records in the export.
- **California institutions:** exported institution records marked as located
  in California by the project registry.
- **Labeled works:** work-label records included in the export. A label record
  does not mean the label has been validated.

Project definitions follow `spec.md` A2. A **plastic-related work** is about
plastic debris or particles, plastic litter, microfibers, tire-wear particles,
or plastic-pollution policy; chemicals in plastics are a separately flagged
Tier 2 scope. **CA-led** means the first author's affiliation resolves to a
California institution. **CA-sampled** means field sampling, sample collection,
or deployed monitoring took place in California land or state waters. A
California affiliation alone does not show that sampling occurred in
California. A **California institution** is one whose registry location is in
California.

The state-waters definition uses California's three-nautical-mile maritime
zone. Its polygon derives from NOAA's offshore maritime-limit line, clipped to
California state waters through the CDFW dataset; the boundary is not a legal
depiction of maritime limits. See the project scope and source notes in
[`spec.md`](../spec.md).

## Current source and classification caveats

OpenAlex supplies the bibliographic and affiliation metadata represented in
this snapshot. Its coverage and affiliation records can be incomplete or
incorrect, and author disambiguation can split one person's work across
profiles or combine different people. Institution records are resolved
through the project's registry; an institution's California location describes
the registry entry, not where a study collected samples.

The current `plastic_related` and topic labels are provisional, rule-based
screening metadata. The held-out gold set and evaluation are later roadmap
work, so this snapshot makes no validated precision or recall claim. The
owner-supplied `plastic-v2-candidate` query remains inactive. The broad S1.2
OpenAlex `search=plastic` counts are review-priority metadata, not the published
corpus or an institution leaderboard. Counts and tags therefore describe this
snapshot's records; they are not pollution measurements or research-quality
rankings.

## Corrections and source work

To report a correction or request review of a profile, [open a data-correction
issue](https://github.com/ScottCoffin/CA_Plastics_Research_Dash/issues/new?title=Atlas%20data%20correction).
Include the OpenAlex work or author ID (and DOI or source URL when available),
the field that appears wrong, and the proposed correction. For a privacy or
removal request, say so in the issue without posting sensitive information.
Changes are reviewed for a later snapshot; this project does not alter the
upstream OpenAlex record.

The site data shape and exporter counts are described in
[`docs/SITE_DATA.md`](SITE_DATA.md). OpenAlex is the source for the indexed
works and affiliation metadata; see [OpenAlex](https://openalex.org/) for the
upstream catalogue.
