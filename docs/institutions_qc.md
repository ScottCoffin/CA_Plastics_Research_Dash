# California institution registry QC

Seeded from OpenAlex institutions filtered by exact `geo.region:California`,
supplemented by required-campus/name searches, then joined by known ROR ID
to the versioned ROR data dump.

## Build summary

- Institution rows: **4,637**
- OpenAlex rows with a ROR ID: **4,637**
- ROR IDs matched in the dump: **4,637**
- ROR release: **v2.15** (10.5281/zenodo.23500708)
- OpenAlex authenticated: **true**
- This build's API requests: **2**; OpenAlex credits: **1.0**; cost: **USD 0.0001**
- Plastic-work review ranking: broad OpenAlex `search=plastic` grouped count; this
  can include plasticity, plastic surgery, and plastic deformation. The owner inferred
  this risk from institution types rather than checking the underlying works.
  Treat it only as a review-priority heuristic; do not use it as a plastic-pollution
  leaderboard until the S1.5 versioned query or an OpenAlex topic restriction is applied.

## Counts per atlas type

| atlas_type | count |
|---|---:|
| CSU | 30 |
| UC | 78 |
| community-college | 50 |
| company | 2,235 |
| federal | 24 |
| local-agency | 81 |
| nonprofit/NGO | 1,788 |
| other-public | 1 |
| private | 343 |
| state-agency | 7 |

## Coverage checks

- UC: 10 official campuses are present and typed `UC`.
- CSU: all 23 campus records are present and typed `CSU`; these represent
  22 universities after the fall-2026 Cal Poly/Cal Maritime integration.
- Major private-university default set: 11 present and typed `private`.
- Top-100 review queue: `data/processed/institution_review_top100.csv`; owner review complete for **100/100** rows.

## Rebuild and acceptance

```powershell
py -3.14 scripts/build_institutions.py
py -3.14 scripts/check_s1_2.py
py -3.14 scripts/check_s1_2.py --require-owner-review
```

The final command requires all 100 owner-review rows to contain both
`owner_atlas_type` and `owner_reviewed_at`; the current count is shown above.

## Institutions with missing region

None. The exact OpenAlex region seed populated all output rows.

## Classification rule counts

| rule | count |
|---|---:|
| community-college-name | 50 |
| csu-lineage-or-name | 29 |
| education-default-private | 339 |
| federal-name | 16 |
| government-fallback-local | 72 |
| local-agency-name | 7 |
| manual-override | 22 |
| organization-type-company | 2,015 |
| organization-type-nonprofit | 1,786 |
| public-education-name | 1 |
| state-agency-name | 7 |
| uc-lineage-or-name | 74 |
| untyped-fallback-company | 219 |

## Sources

- OpenAlex metadata: CC0; API behavior documented in `docs/api_notes/openalex.md`.
- ROR metadata: CC0; ROR location fields derive from GeoNames (CC BY 3.0);
  API and dump behavior documented in `docs/api_notes/ror.md`.
- UC campus list: <https://www.universityofcalifornia.edu/about-uc/campuses-locations>.
- CSU campus list and 22-university transition: <https://www.calstate.edu/attend/campuses/Pages/default.aspx>.
