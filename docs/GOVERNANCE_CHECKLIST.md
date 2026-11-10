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
| Privacy review against F4 (all clauses) | [PRIVACY_REVIEW.md](PRIVACY_REVIEW.md) | Partial: scan clean, several clauses open | | |
| Privacy scan: no email-like or phone-like strings in 14 public files | [check_s10_2.py](../scripts/check_s10_2.py) | Found: 0 matches (email 0, phone 0, intl 0) | | |
| Social-account domains absent from public payloads | [PRIVACY_REVIEW.md](PRIVACY_REVIEW.md) | Found: 0 matches | | |
| Owner decision: principal-investigator names in grants.json (447 rows) | [PRIVACY_REVIEW.md](PRIVACY_REVIEW.md) | Needs owner decision | | |
| Owner decision: ORCID values in public payloads | [PRIVACY_REVIEW.md](PRIVACY_REVIEW.md) | Needs owner decision | | |
| Owner decision: Sea Grant HTML scraper acceptable under F4 | [ca_sea_grant.py](../src/atlas/ingest/grants/ca_sea_grant.py) | Needs owner decision | | |
| Correction request process documented on About tab | [CORRECTIONS.md](CORRECTIONS.md) | Found: About card and drawer link exist | | |
| Removal mechanism and policy | [CORRECTIONS.md](CORRECTIONS.md) | Gap: no suppression mechanism in code | | |
| Institution overrides applied in the build | [institutions.py](../src/atlas/ingest/institutions.py) | Found: config/institution_overrides.csv consumed | | |
| Author merge and split overrides applied in the export | [normalize.py](../src/atlas/ingest/normalize.py) | Gap: recorded as override_flags only | | |
| Work overrides applied in the build | [overrides_works.csv](../curation/overrides_works.csv) | Gap: header only, no code reads it | | |
| "Is this you? Report an issue" link | [index.html](../site/index.html) | Gap: not present; a profile-drawer error link exists | | |
| Author prominence shown as tagged-work count, not a ranking | [index.html](../site/index.html) | Found: copy and fields; browser default order not tested | | |
| Independence disclaimer (A3.4 / G-12) | [index.html](../site/index.html) | Found: About tab disclaimer present | | |
| Owner affiliation disclosure (co-founder role) on About tab | [REUSE.md](REUSE.md) | Gap: REUSE rule 7 expects it; not on About tab | | |
| Data dictionary covers every public file in site/data and site/feed.xml | [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | Found: check confirms each file named | | |
| Licence audit: repository code licence | [LICENSE](../LICENSE) | Needs owner decision: file says "License pending owner confirmation" | | |
| Licence audit: derived-data licence (CC BY per ADR-002) | [DECISIONS.md](../.agent/DECISIONS.md) | Needs owner decision: upstream licences unrecorded for several sources | | |
| Licence audit: third-party register complete for shipped sources | [REUSE.md](REUSE.md) | Gap: no rows for NIH RePORTER, NSF, USAspending, CA Sea Grant, OPC grants, or ROR | | |
| Monitoring rows limited to the rights-cleared dataset | [monitoring_publication.yml](../config/monitoring_publication.yml) | Found: 314 rows, one dataset (CC BY 4.0, owner determination) | | |
| Monitoring registry entries with unknown licences (metadata only) | [monitoring.json](../site/data/monitoring.json) | Needs owner decision: 24 entries, most licences unknown | | |
| CITATION.cff parses and has CFF 1.2.0 required keys | [CITATION.cff](../CITATION.cff) | Found: keys present; license field follows the code licence decision | | |

Owner sign-off for the whole package (optional, instead of per-row): ______________  Date: ____________
