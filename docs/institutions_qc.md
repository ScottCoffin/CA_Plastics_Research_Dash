# California institution registry QC

Seeded from OpenAlex institutions filtered by exact `geo.region:California`,
supplemented by required-campus/name searches, then joined by known ROR ID
to the versioned ROR data dump.

## Build summary

- Institution rows: **4,677**
- OpenAlex rows with a ROR ID: **4,677**
- ROR IDs matched in the dump: **4,677**
- ROR release: **v2.15** (10.5281/zenodo.23500708)
- OpenAlex authenticated: **true**
- This build's API requests: **1**; OpenAlex credits: **1.0**; cost: **USD 0.0001**
- Plastic-work review ranking: broad OpenAlex `search=plastic` grouped count; this
  can include plasticity, plastic surgery, and plastic deformation. The owner inferred
  this risk from institution types rather than checking the underlying works.
  Treat it only as a review-priority heuristic; do not use it as a plastic-pollution
  leaderboard until the S1.5 versioned query or an OpenAlex topic restriction is applied.

## Counts per atlas type

| atlas_type | count |
|---|---:|
| CSU | 28 |
| JPA | 2 |
| UC | 77 |
| community-college | 52 |
| company | 2,235 |
| federal | 49 |
| intergovernmental-organization | 1 |
| local-agency | 70 |
| nonprofit/NGO | 1,767 |
| other-public | 1 |
| private | 344 |
| state-agency | 50 |
| utility | 1 |

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
| county-health-department-name | 10 |
| csu-lineage-or-name | 20 |
| education-default-private | 335 |
| federal-name | 25 |
| government-fallback-local | 17 |
| government-federal-name | 15 |
| government-local-name | 35 |
| government-state-name | 24 |
| local-agency-name | 6 |
| manual-override | 68 |
| organization-type-company | 2,012 |
| organization-type-nonprofit | 1,751 |
| public-education-name | 1 |
| state-agency-name | 18 |
| uc-lineage-or-name | 72 |
| untyped-fallback-company | 218 |

## Sources

- OpenAlex metadata: CC0; API behavior documented in `docs/api_notes/openalex.md`.
- ROR metadata: CC0; ROR location fields derive from GeoNames (CC BY 3.0);
  API and dump behavior documented in `docs/api_notes/ror.md`.
- UC campus list: <https://www.universityofcalifornia.edu/about-uc/campuses-locations>.
- CSU campus list and 22-university transition: <https://www.calstate.edu/attend/campuses/Pages/default.aspx>.

## California state agencies (2026-11-11)

Owner report: state institutions were not differentiated (CDPH, OEHHA, State Water Board, OPC...).
Cause and fix, in three parts.

1. **Registry gap.** OpenAlex now lists 148 `type:government,geo.region:California` institutions, but
   the cached seed had 108. `scripts/build_institutions.py --supplement-government --reuse-ror-dump`
   adds the missing 40 (CDPH, CARB, DTSC, OPC, Caltrans, Coastal Commission, DPR...) with one paged
   list call, reuses the ROR dump on disk (no download) and fetches plastic-work counts only for the
   new ids. A rebuild also re-applied the committed classifier, so ~25 CSU/UC/private campuses that
   the older registry file lacked (for example San Diego State, 115 works) are now CA-flagged.
2. **Classification.** The blanket `government-fallback-local` is now preceded by name rules:
   `government-state-name` (`California ...`, `State of California`, `... of California`, boards and
   commissions), `government-federal-name` (USGS, NOAA, USDA, Navy, national parks and labs) and
   `government-local-name` (county, city, district, municipal, police/fire). Names of county or city
   public-health, health-services and health departments are `local-agency` (rule
   `county-health-department-name`) whatever the ROR type. Owner overrides still win. Two name-only
   health records were set to `state-agency` in `config/institution_overrides.csv`, pending owner
   confirmation: I4210161945 (Department of Health Services) and I4405283712 (CDPH injury-control branch).
3. **Sub-agency resolver.** OEHHA, the State Water Board, the nine Regional Water Quality Control
   Boards, the State Lands Commission and the Delta Conservancy have no OpenAlex record; OpenAlex
   links them to CalEPA (I65137940) or State of California (I4389425283). `config/ca_state_agencies.yml`
   defines each with a synthetic id (`CAAG-*`), HQ coordinates, parent and strict regexes.
   `normalize` matches every raw-affiliation string, adds the agency id and removes the umbrella
   (so a work is counted once), and emits a synthetic row (`ca_flag` true, `parent_system` = parent
   OpenAlex id) only for agencies actually linked. `ca_basis` becomes `registry` for those
   authorships. To add an agency, append an entry to the YAML and rerun
   `scripts/normalize_openalex.py`, `scripts/build_export_site.py` and
   `scripts/build_institution_types.py` (which reads the same YAML).

State agencies on the site, works/authors before and after (CA-flagged, type `state-agency` after):

| Agency | id | Before: type, works/authors | After: works/authors |
|---|---|---|---|
| Office of Environmental Health Hazard Assessment | CAAG-OEHHA | absent | 37/3 |
| State Water Resources Control Board | CAAG-SWRCB | absent | 35/4 |
| California Department of Water Resources | I4405261152 | state-agency, 34/1 | 34/1 |
| California Department of Public Health | I1336788258 | other (not CA-flagged), 12/7 | 12/7 |
| California Department of Fish and Wildlife | I1333577951 | state-agency, 9/7 | 9/7 |
| California Environmental Protection Agency | I65137940 | other (not CA-flagged), 41/8 | 7/6 |
| State of California | I4389425283 | state-agency, 41/7 | 5/2 |
| California Air Resources Board | I1316958739 | other (not CA-flagged), 3/3 | 3/3 |
| California Coastal Commission | I1295874195 | local-agency, 2/1 | 2/1 |
| California Department of Transportation | I1328614147 | other (not CA-flagged), 2/1 | 2/1 |
| California Ocean Protection Council | I4387154128 | other (not CA-flagged), 2/1 | 2/1 |
| California State Lands Commission | CAAG-SLC | absent | 2/2 |
| California Department of Toxic Substances Control | I1290230355 | other (not CA-flagged), 1/1 | 1/1 |
| San Diego Regional Water Quality Control Board | CAAG-RWQCB9 | absent | 1/1 |
| San Joaquin Delta Conservancy | CAAG-SJDC | absent | 1/1 |

The regional boards other than San Diego do not appear in the current corpus (no raw affiliation
names them); their patterns are tested. Side effect: the top-100 review queue
(`institution_review_top100.csv`) was regenerated from the rebuilt registry, so its membership shifted.
