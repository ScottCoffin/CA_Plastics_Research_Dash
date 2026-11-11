# Governance checklist (S10.2)

Prepared 2026-11-10. The agent prepared this package; the owner signs it.
Acceptance for S10.2 is "Checklist signed off by the owner."

Linked documents: [privacy review](PRIVACY_REVIEW.md),
[corrections and takedown process](CORRECTIONS.md),
[data dictionary](DATA_DICTIONARY.md), [citation file](../CITATION.cff),
[third-party licence register](REUSE.md), [repository licence](../LICENSE),
[methods](METHODS.md), and the [About tab](../site/index.html).

## How to sign off

For each row, the owner writes initials in "owner sign-off" and the date in "date".
A row marked "Gap" or "Needs owner decision" can be signed only after the owner
accepts the stated action, or records a deferral in its place. Alternatively, the
owner may sign once on the line below the table, which covers every row.

The "status found by you" column is the agent's finding as of 2026-11-10. It is
not a sign-off.

| item | evidence link | status found by you | owner sign-off | date |
|---|---|---|---|---|
| Privacy review against F4 (all clauses) | [PRIVACY_REVIEW.md](PRIVACY_REVIEW.md) | Partial: scan clean, several clauses open | SC | 2026-11-10 |
| Privacy scan: no email-like or phone-like strings in 14 public files | [check_s10_2.py](../scripts/check_s10_2.py) | Found: 0 matches (email 0, phone 0, intl 0) | SC | 2026-11-10 |
| Social-account domains absent from public payloads | [PRIVACY_REVIEW.md](PRIVACY_REVIEW.md) | Found: 0 matches | SC | 2026-11-10 |
| Owner decision: principal-investigator names in grants.json (447 rows) | [PRIVACY_REVIEW.md](PRIVACY_REVIEW.md) | Needs owner decision | SC | 2026-11-10 |
| Owner decision: ORCID values in public payloads | [PRIVACY_REVIEW.md](PRIVACY_REVIEW.md) | Needs owner decision | SC | 2026-11-10 |
| Owner decision: Sea Grant HTML scraper acceptable under F4 | [ca_sea_grant.py](../src/atlas/ingest/grants/ca_sea_grant.py) | Needs owner decision | SC | 2026-11-10 |
| Correction request process documented on About tab | [CORRECTIONS.md](CORRECTIONS.md) | Found: About card and drawer link exist | SC | 2026-11-10 |
| Removal mechanism and policy | [curation.py](../src/atlas/build/curation.py) | Found: `curation/suppressions.csv` removes authors and works from every export payload; policy and About wording still need owner decision | SC| 2026-11-10|
| Institution overrides applied in the build | [institutions.py](../src/atlas/ingest/institutions.py) | Found: config/institution_overrides.csv consumed | SC | 2026-11-10 |
| Author merge and split overrides applied in the export | [curation.py](../src/atlas/build/curation.py) | Found: merges in `curation/author_merges.csv` re-point authorships at export; splits not applied (OpenAlex correction request) | SC | 2026-11-10 |
| Work overrides applied in the build | [curation.py](../src/atlas/build/curation.py) | Found: `curation/overrides_works.csv` applied at export for an allowlisted set of fields; unknown fields rejected | SC | 2026-11-10 |
| "Is this you? Report an issue" link | [index.html](../site/index.html) | Found: drawer header link added (prefilled "Profile issue: name (author_id)" title); pending owner review | SC | 2026-11-10 |
| Author prominence shown as tagged-work count, not a ranking | [index.html](../site/index.html) | Found: copy and fields; browser default order not tested | SC | 2026-11-10 |
| Independence disclaimer (A3.4 / G-12) | [index.html](../site/index.html) | Found: About tab disclaimer present | SC | 2026-11-10 |
| Owner affiliation disclosure (co-founder role) on About tab | [index.html](../site/index.html), [REUSE.md](REUSE.md) | Found: disclosure sentence added under the About disclaimer; pending owner review (EM-14) | SC | 2026-11-10 |
| Data dictionary covers every public file in site/data and site/feed.xml | [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | Found: check confirms each file named | SC | 2026-11-10 |
| Licence audit: repository code licence | [LICENSE](../LICENSE) | Found: MIT, confirmed by owner 2026-11-10 (QUESTIONS LICENSE-A) | SC | 2026-11-10 |
| Licence audit: derived-data licence (CC BY 4.0) | [LICENSE-DATA.md](../LICENSE-DATA.md) | Found: CC BY 4.0 confirmed by owner 2026-11-10; upstream terms per source in REUSE.md (some rows still incomplete, see next item) | SC | 2026-11-10 |
| Licence audit: third-party register complete for shipped sources | [REUSE.md](REUSE.md) | Found: rows added for NIH, NSF, USAspending, CA Sea Grant, OPC, Delta, FAAST, ROR, OpenAlex and CA Grants Portal; terms not recorded for seven federal and state sources, marked TERMS-UNVERIFIED | SC | 2026-11-10 |
| Monitoring rows limited to the rights-cleared dataset | [monitoring_publication.yml](../config/monitoring_publication.yml) | Found: 314 rows, one dataset (CC BY 4.0, owner determination) | SC | 2026-11-10 |
| Monitoring registry entries with unknown licences (metadata only) | [monitoring.json](../site/data/monitoring.json) | Needs owner decision: 24 entries, most licences unknown | SC | 2026-11-10 |
| CITATION.cff parses and has CFF 1.2.0 required keys | [CITATION.cff](../CITATION.cff) | Found: keys present; license field follows the code licence decision | SC | 2026-11-10 |

Owner sign-off for the whole package (optional, instead of per-row): ______________  Date: ____________
