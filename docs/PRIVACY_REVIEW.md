# Privacy review (F4)

Prepared 2026-11-10 for owner sign-off through `docs/GOVERNANCE_CHECKLIST.md`.
Reviewer: prepared by the repository agent for Scott Coffin, Ph.D. The owner
decides each "needs owner decision" item.

## Requirement (spec F4, quoted)

> Public bibliographic metadata only; no scraping of personal emails, phone numbers or social accounts. Researchers can request correction or removal; process documented on the About page; overrides applied within the next build. Present author prominence as 'number of tagged works,' not performance rankings; avoid default citation-based rankings of individuals. OpenAlex disambiguation errors (C8) mean some profiles will be wrong; provide an 'Is this you? Report an issue' link. Respect the owner's affiliation context: include the independence disclaimer (A3.4/G-12).

## Method

- Offline scan, run 2026-11-10 by `scripts/check_s10_2.py`, over every public payload:
  `site/data/*.json`, `site/data/authors/*.json`, `site/data/*.geojson` and `site/feed.xml`.
- Patterns: email-like (`local@domain.tld`), US-style phone (`NNN-NNN-NNNN` with optional
  separators and `+1`), and international-style phone (`+` country code followed by groups).
- Strings were scanned as JSON keys and values, and as raw text for the feed. Matches are
  reported by file and field path only. No matched value was printed or copied here.
- Field inspection used key names, types and row counts only. No payload file was read in full.
- A separate count, run the same way, looked for social-account domains (Twitter/X, LinkedIn,
  Facebook, Instagram, Bluesky, Mastodon, ResearchGate, Google Scholar, Academia.edu, TikTok,
  YouTube) and found 0 in JSON and 0 in the feed.

## Scan results

| Scope | Files scanned | Email-like | Phone-like (US) | Phone-like (intl) | Social-account domains |
|---|---|---|---|---|---|
| `site/data/**/*.json` | 12 | 0 | 0 | 0 | 0 |
| `site/data/*.geojson` | 1 | 0 | 0 | 0 | included in JSON count above |
| `site/feed.xml` (raw text) | 1 | 0 | 0 | 0 | 0 |
| **Total** | **14** | **0** | **0** | **0** | **0** |

Counts are the output of `py -3.14 scripts/check_s10_2.py`. A non-zero count would
fail the check and stop the item, and the owner would decide on it. None was found.

## Clause-by-clause assessment

| F4 clause | Evidence | Status |
|---|---|---|
| Public bibliographic metadata only | Payload fields are OpenAlex-derived work and author metadata, funder award records, rights-cleared monitoring samples, pipeline status and the feed (`docs/DATA_DICTIONARY.md`). The scan found no email, phone or social-account strings. | Found, with owner decisions on personal names and ORCID (below). |
| No scraping of personal emails, phone numbers or social accounts | `src/atlas/ingest/grants/ca_sea_grant.py` fetches public project pages over HTML, honours `robots.txt` and does not extract contact fields. No `mailto`, email, phone or social-account extraction was found in `src/` or `scripts/`. Grant PI names are the only personal names taken from web pages or award records. | Found. The Sea Grant ingester is a scraper of public project pages; the owner should confirm that is acceptable under this clause. |
| Researchers can request correction or removal | "Corrections and source work" card on the About tab (`site/index.html`, about-corrections card, around lines 316-318) and the profile drawer link "Report an error about this profile" (around line 917). Process: `docs/CORRECTIONS.md`. | Found for correction. Removal mechanism is not built (see CORRECTIONS.md). |
| Process documented on the About page | About tab card links to a data-correction issue and to `docs/METHODS.md`, which carries a "Corrections and source work" section. | Found. |
| Overrides applied within the next build | Institution overrides (`config/institution_overrides.csv`) are applied in `src/atlas/ingest/institutions.py`. Author overrides (`config/author_overrides.csv`) are recorded as `override_flags` only, and merge or split is not applied. Work overrides (`curation/overrides_works.csv`) have header only and no code reads them. | Partial. Owner decision and build work needed. |
| Author prominence as "number of tagged works", not performance rankings | About tab and Experts copy: "Tagged-work volume ... is a descriptive count ... it is not a quality ranking" (`site/index.html`, around line 220). Drawer shows "N works" and "N CA-connected works". `cited_by_count` is in the data but is not referenced by `site/index.html`. The export orders records by stable IDs (`src/atlas/build/export_site.py`), not by citations. | Found. The Experts default sort was not tested in a browser. |
| Avoid default citation-based rankings of individuals | As above: no citation field is used in the UI, and the export order is by ID. | Found (code and copy review; no browser run). |
| "Is this you? Report an issue" link for disambiguation errors (C8) | The About tab names disambiguation limits ("author profiles can split one person's works or combine different people"). The drawer has "Report an error about this profile". No "Is this you?" wording exists in `site/index.html`. | Partial. Wording and link need a site change (out of scope for this task). |
| Independence disclaimer (A3.4 / G-12) | `site/index.html` About tab: "Disclaimer: Independent project; not an official OEHHA or State product." The spec G-12 text is "Independent project; not an official OEHHA/State product"; the wording matches in substance. | Found. |
| Owner affiliation context | `docs/REUSE.md` §0 rule 7 says the owner's roles (co-founder of Plastiverse) are disclosed on the About tab (A2-D8, EM-14). No such disclosure text was found in `site/index.html`. | Gap. Owner decision: the wording and whether to add it. |

## Personal data present in public payloads

These fields are personal or identifying. Each is public in its source. Each needs an owner decision.

| Payload | Field | Count | Note |
|---|---|---|---|
| `site/data/index.json` | `authors[].name` | 4 rows | Display names from OpenAlex. Disambiguation may be wrong (F4 C8). |
| `site/data/authors/*.json` | `author.name` | 4 files | Same names, in detail files. |
| `site/data/**/*.json` | `orcid` (ORCID URL) | 2 string values across the JSON payloads (locations not itemized here) | Public identifiers supplied by OpenAlex. The repository has no ORCID for the owner (none is shown here). Owner decision whether ORCID links stay. |
| `site/data/grants.json` | `rows[].pi_names` | 447 of 522 rows have at least one name | Principal-investigator names from public award records (NIH RePORTER, NSF, Sea Grant, OPC, USAspending). No contact details. Owner decision whether to keep names or show organization only. |
| `site/data/monitoring.json` | `samples[].contributor` | 314 rows, 1 distinct value | Value not reproduced here. Owner to confirm it names an organization and not a person. |
| `site/data/monitoring.json` | `samples[].lat`, `lon`, `date` | 314 rows | Sample-level coordinates and dates from the one cleared dataset. Public research data; no personal location. |
| Feed and index | `title`, `abstract`, `summary` | all works | Text supplied by OpenAlex and funders. Not checked line by line. |

## Monitoring rights (related to F4 "public bibliographic metadata only")

- `config/monitoring_publication.yml` lists one cleared dataset, `sf_bay_5gyres_microplastics`,
  licensed CC BY 4.0 by owner determination (QUESTIONS S7.3-A, 2026-11-10).
- `site/data/monitoring.json` carries 314 sample rows, all from that dataset (checked by
  `dataset_id` count only).
- The `datasets` array holds 24 source-registry entries. Most record their licence as unknown
  or provider-dependent and have no observations. The owner should confirm that a registry
  entry with an unknown licence is acceptable as metadata.

## Owner decisions

1. Keep or remove `grants.json` `pi_names` (447 rows), or show organization only.
2. Keep or remove the 2 ORCID values in the public payloads.
3. Confirm the Sea Grant HTML scraper is acceptable under "no scraping of personal contact data".
4. Confirm the monitoring `contributor` value names an organization.
5. Add the "Is this you? Report an issue" link (site change; out of scope here).
6. Decide the owner-affiliation disclosure wording for the About tab (REUSE §0 rule 7).
7. Decide the removal mechanism and policy, and build the work and author override consumers (see CORRECTIONS.md).
8. Confirm the registry entries with unknown licences may stay as metadata.

## Other observations

- `site/feed.xml` entry IDs use the `scottcoff.in` tag domain. The feed-level `link` uses
  `plastiverse.live`. The IDs are frozen on purpose (commit 569f4ea), so no change is proposed.
