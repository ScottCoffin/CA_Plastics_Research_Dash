# DataCite outputs by expert ORCID (S2.5d)

Date: 2026-11-11. Code: `src/atlas/ingest/datacite_orcid.py`, `scripts/fetch_datacite_orcid.py`.
Output: `data/processed/expert_datacite_outputs.parquet` (17,199 rows). Raw pages are cached in
`data/raw/datacite_orcid/` (gitignored, 73 pages). Descriptions are read in memory to set
`plastic_related` and are never stored.

## Query

- Endpoint: `https://api.datacite.org/dois`, `page[size]=1000`, cursor paging via `links.next`
  (only URLs under the DataCite host are followed).
- Form: `(creators.nameIdentifiers.nameIdentifier:"https://orcid.org/<id>" OR ...)`, 25 ORCIDs per query.
- Experts: 1,598 unique ORCIDs from `orcid_profiles.parquet` (64 batches).
- User-Agent `CAPlasticsAtlas/0.1 (https://github.com/ScottCoffin/CA_Plastics_Research_Dash)`.
- Pacing: 0.25 s between requests. Retries on 429, 5xx and transport errors with backoff. Hard cap 400.

## Requests

| Run | Result | Live requests |
|---|---|---|
| `--limit 50` | 2 batches, complete | 2 |
| First full run | stopped on HTTP 502 after 4 attempts; nothing written; exact count not logged | at least 4 pages cached |
| Full run resumed from cache | complete | 71 |
| `--offline` | reproduces the same rows from cache | 0 |

Total cached pages: 73. The 502 cause is unknown; the resumed run succeeded without changes.

## Counts (unique DOIs, 14,684)

By `resourceTypeGeneral`: Dataset 12,852; Text 393; JournalArticle 523; Software 188;
Collection 244; Image 254; StudyRegistration 42; Audiovisual 29; Report 22; Other 84;
Dissertation 13; Poster 7 (as recorded in `resourceTypeGeneral`); Presentation 5;
Preprint 5; others below 5 each.

- DOIs that are versions (`IsVersionOf`): 415.
- Plastic-related DOIs (rule labeller, title + description): 98.
- Plastic-related and not in `works.parquet`: 84 DOIs.
- Plastic-related version families (`family_doi`): 93; families with no member or concept DOI in the corpus: 78.

Most of the 12,852 datasets are not plastic-related; the plastic flag is the candidate filter.

## Karapetrova probe

DOI `10.5281/zenodo.7217432` is **not found** by ORCID. This matches the S2.5 probe, which
reported an empty affiliation and no ORCID on that record. It can only be found by another route.

## Caveats

- Matching uses creator ORCIDs only. Contributors and name-only creators are not matched.
- Creator ORCIDs are self-declared metadata. A DOI is attached to every expert whose ORCID appears.
- `plastic_related` uses the active `plastic-v3.1` rules on title + description (not full text).
  Expect false negatives for outputs with thin metadata.
- `in_corpus` is an exact DOI match against `works.parquet`; a family is in corpus if any member
  or its concept DOI is there.
- 17,189 DataCite items were returned; 17,199 rows exist because one DOI can match several
  experts (rows are deduplicated per author_id and DOI). 0 items failed to parse.
- Coverage is DataCite's ORCID indexing only. It is not a complete census of expert outputs.
