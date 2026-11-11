# Corrections and takedown process

Prepared 2026-11-10 for owner sign-off through `docs/GOVERNANCE_CHECKLIST.md`.
This is the process behind the "Corrections and source work" card on the About
tab of the site (`site/index.html`) and the "Report an error about this profile"
link in the Experts drawer. The wording here must match the About tab. If the two
disagree, the owner decides which one changes.

## Who can ask

Any person may ask for a correction, for a profile to be reviewed, or for a
profile to be removed. Requesters do not need to be the person named in the record.

## How to ask

1. Open a data-correction issue at
   <https://github.com/ScottCoffin/CA_Plastics_Research_Dash/issues/new?title=Atlas%20data%20correction>.
   Use the profile link in the Experts drawer to pre-fill the author name.
2. Include, where you have them:
   - the OpenAlex work or author ID, the DOI, or the source URL;
   - the field that looks wrong (for example title, year, affiliation, author split or merge, or topic label);
   - the proposed correction and any evidence (for example a publisher page).
3. For a privacy or removal request, say so in the issue title or first line.
   Do not post personal contact details, health information, or other sensitive
   material in the issue. The owner decides whether a request moves to a private channel.

Note: the About tab and drawer do not yet carry an "Is this you? Report an issue"
link for disambiguation errors (spec F4). See the open items below.

## What the owner does

1. Triage the issue and label it as a correction, a profile review, or a removal request.
2. Check the claim against the source record. The project does not alter the
   upstream OpenAlex record, a publisher record, or a funder record.
3. Record an accepted action as one row in the matching curation file. Every row
   needs `reason`, `reviewed_by` and a review date. The build refuses a row without
   `reviewed_by`, so an unreviewed correction cannot reach the site.
4. Run the export (`py -3.14 scripts/build_export_site.py`). The build reads the
   curation files on every run, so the action is applied in that build and
   `site/data/build_metadata.json` records the counts under `curation`.
5. Close the issue with a link to the commit or the snapshot that carries the change.

| Action | File (header) | What the export does |
|---|---|---|
| Remove an author profile | `curation/suppressions.csv` (`kind,id,reason,requested_at,reviewed_by`), `kind` = `author` | The author is dropped from `index.json`, `authors/<id>.json` is not written, and the author's ID is removed from every work's `author_ids`. Works with no remaining linked author are dropped. Institution and aggregate counts are recomputed. |
| Remove a work | `curation/suppressions.csv`, `kind` = `work` | The work is dropped from every payload, and its authorships are removed. |
| Correct a work field | `curation/overrides_works.csv` (`work_id,field,value,reason,reviewed_by,reviewed_at`) | Replaces the value before aggregation. Allowed fields: `title`, `publication_year`, `ca_led`, `ca_any_author`, `plastic_related`, `study_type`, `domain_tags` and `facet_tags` (pipe-separated). Any other field is an error. Two rows for the same work and field are an error. |
| Merge two author profiles | `curation/author_merges.csv` (`from_author_id,to_author_id,reason,reviewed_by,reviewed_at`) | Re-points the `from` author's authorships to the `to` author. The `from` profile is dropped. Chains are resolved; cycles are an error. |
| Institution fields | `config/institution_overrides.csv` | Applied by `src/atlas/ingest/institutions.py` during ingest. |

Split of an author profile is **not** handled by the atlas. Ask OpenAlex to split the
profile, and record the request in the issue.

`config/author_overrides.csv` is still read only by `src/atlas/ingest/normalize.py`
and written as `override_flags`. It does not change the export. Use
`curation/author_merges.csv` for merges.

Identifiers may be given as bare IDs (`A9000000102`, `W9000000101`) or as full
OpenAlex URLs. The export removes or changes only the listed IDs. It does not
read or change the upstream OpenAlex record.

Known limits: a suppressed author's name can still appear in a work's title or
abstract, and the work-level `ca_led` and `ca_any_author` flags are not recomputed
after an author is removed. Check both by hand when you suppress a profile.

## Timing

Spec F4 requires that accepted overrides are applied within the next build. The
curation files above are read by every export run, so an accepted row is applied
in the next build after it is committed. Institution overrides are applied at ingest
(`src/atlas/ingest/institutions.py`), not at export. The owner still needs to set the
response-time commitment (none is stated in the repository yet).

## Removal

Removal is handled by a `kind=author` or `kind=work` row in
`curation/suppressions.csv`. The export drops the listed profile or work from every
public payload. Records are dropped from the site, not deleted from the source
database or from the Parquet tables. The owner still needs to decide the removal
policy (for example whether the record is also excluded from the next ingest, and
how long a removed profile stays suppressed), and to confirm the About tab wording.

## Source-level problems

Some errors come from the source, not the atlas:

- OpenAlex disambiguation (authors split or merged, wrong affiliations): report to
  OpenAlex, and also use the atlas author-level override once implemented.
- Monitoring observations: the source dataset owner governs the record. The atlas
  publishes only the cleared dataset listed in `config/monitoring_publication.yml`.
- Grant records: the funder's public record governs. Amounts follow each source's
  own basis (see `docs/DATA_DICTIONARY.md`).

## Open items for owner decision

- Decide whether suppressed records must also be excluded at ingest, not only at export.
- Set a response-time commitment for issues.
- Add the "Is this you? Report an issue" link to the About tab and profile drawer.
- Decide whether the About tab should also name the owner's roles (see `docs/PRIVACY_REVIEW.md`).
- Align the About tab card with the removal and correction steps above.
