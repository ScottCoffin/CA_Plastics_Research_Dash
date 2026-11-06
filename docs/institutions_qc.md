# California institution registry QC

Generated from OpenAlex institutions filtered by exact `geo.region:California`,
then joined by known ROR ID to the versioned ROR data dump.

## Build summary

- Institution rows: **4,614**
- OpenAlex rows with a ROR ID: **4,614**
- ROR IDs matched in the dump: **4,614**
- ROR release: **v2.15** (10.5281/zenodo.23500708)
- OpenAlex authenticated: **false**
- API requests: **96**; OpenAlex credits: **930.0**; cost: **USD 0.0930**
- Plastic-work review ranking: broad OpenAlex `search=plastic` grouped count; this is
  a review-priority heuristic, not the later versioned corpus query or classifier.

## Counts per atlas type

| atlas_type | count |
|---|---:|
| CSU | 8 |
| UC | 77 |
| community-college | 50 |
| company | 2,237 |
| federal | 24 |
| local-agency | 81 |
| nonprofit/NGO | 1,789 |
| other-public | 2 |
| private | 339 |
| state-agency | 7 |

## Coverage checks

- UC: 10 official campuses are present and typed `UC`.
- CSU: all 23 campus records are present and typed `CSU`; these represent
  22 universities after the fall-2026 Cal Poly/Cal Maritime integration.
- Major private-university default set: 11 present and typed `private`.
- Top-100 review queue: `data/processed/institution_review_top100.csv`.
  Fill `owner_atlas_type`, `owner_reviewed_at`, and optional `owner_notes`.

## Institutions with missing region

None. The exact OpenAlex region seed populated all output rows.

## Classification rule counts

| rule | count |
|---|---:|
| community-college-name | 50 |
| csu-lineage-or-name | 7 |
| education-default-private | 335 |
| federal-name | 16 |
| government-fallback-local | 72 |
| local-agency-name | 7 |
| manual-override | 22 |
| organization-type-company | 2,016 |
| organization-type-nonprofit | 1,787 |
| public-education-name | 2 |
| state-agency-name | 7 |
| uc-lineage-or-name | 73 |
| untyped-fallback-company | 220 |

## Sources

- OpenAlex metadata: CC0; API behavior documented in `docs/api_notes/openalex.md`.
- ROR metadata: CC0; ROR location fields derive from GeoNames (CC BY 3.0);
  API and dump behavior documented in `docs/api_notes/ror.md`.
- UC campus list: <https://www.universityofcalifornia.edu/about-uc/campuses-locations>.
- CSU campus list and 22-university transition: <https://www.calstate.edu/attend/campuses/Pages/default.aspx>.
