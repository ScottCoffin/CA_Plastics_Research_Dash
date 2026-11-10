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
3. Record an accepted correction in the matching override file, with `reason`,
   `reviewed_by` and `reviewed_at`:

| Scope | File | What the build does today |
|---|---|---|
| Institution fields (for example `atlas_type`, `display_name`) | `config/institution_overrides.csv` | Applied by `src/atlas/ingest/institutions.py`. Verified in code. |
| Author-level action (merge or split) | `config/author_overrides.csv` | Read by `src/atlas/ingest/normalize.py` and written as `override_flags` only. The merge or split is **not yet applied** to the site export. |
| Work-level field | `curation/overrides_works.csv` | Header only. **No code reads this file yet.** A work correction will not reach the site until a consumer is built. |

4. Close the issue with a link to the commit or the snapshot that carries the change.

## Timing

Spec F4 requires that accepted overrides are applied within the next build. This is
true today only for institution overrides. The author and work overrides above are
open items in `docs/GOVERNANCE_CHECKLIST.md`. The owner also needs to set the
response-time commitment (none is stated in the repository yet).

## Removal

The repository has no removal mechanism that suppresses a profile or work from the
export. A removal request can be handled today only by a manual change to the
export input, after owner review, and that change is not yet recorded in an
override file. The owner needs to decide the removal policy and mechanism (for
example an author-level "exclude" action applied by the normalizer) before this
process can be completed. Until then the request is logged in the issue and the
owner decides the response case by case.

## Source-level problems

Some errors come from the source, not the atlas:

- OpenAlex disambiguation (authors split or merged, wrong affiliations): report to
  OpenAlex, and also use the atlas author-level override once implemented.
- Monitoring observations: the source dataset owner governs the record. The atlas
  publishes only the cleared dataset listed in `config/monitoring_publication.yml`.
- Grant records: the funder's public record governs. Amounts follow each source's
  own basis (see `docs/DATA_DICTIONARY.md`).

## Open items for owner decision

- Build the work-override consumer, or record that work corrections are manual until it exists.
- Apply author merge and split actions in the export, or record them as manual until then.
- Define the removal mechanism and policy.
- Set a response-time commitment for issues.
- Add the "Is this you? Report an issue" link to the About tab and profile drawer.
- Decide whether the About tab should also name the owner's roles (see `docs/PRIVACY_REVIEW.md`).
