# Community group enrichment: options for Plastiverse Live

Research spike, 2026-11-26. Scope: where facts for the 2,673 Break Free From Plastic roster groups could come from, without scraping or crawling (decision A4-D11). Every option below is either an ambassador-confirmed suggestion or a verified identity or registry fact.

## Status

- 2026-11-26: owner approved suggestion-only use (H61, ADR-GRP-ENRICH-2026-11-26). Slice 1 built: `scripts/build_group_suggestions.py` writes `site/data/global/groups/suggestions.json` with Wikidata suggestions for 319 roster groups (274 by website, 45 by English name with a country check and organisation type labels; AF never name-matched; ambiguous and shared items dropped). Slices 2 (form and register links) and 3 (IRS NTEE) are next.

## Bottom line

- A Wikidata lookup can pre-fill an identity suggestion (Wikidata item, official website, founding year) for about **17 to 19% of groups**, and about 80% of those suggestions were correct on hand review. Wikidata is CC0, so it is safe to reuse with attribution.
- Official registers give strong facts for a few countries. The US IRS file is public domain and carries NTEE sector codes. The UK, Canada and Australia registers are open-licensed but cover only their own countries.
- Recommendation: build the ambassador-side pre-fill from Wikidata and registers as **suggestions the ambassador confirms with evidence**. Do not write any tag without a human confirmation. This needs one owner ruling (see Decisions).
- Avoid OpenCorporates (ODbL share-alike) and Wikipedia text (CC BY-SA share-alike). Both conflict with a CC BY-NC 4.0 dataset.

## Source survey

| Source | Fields that map to facets | Coverage | Access | Licence (reuse in CC BY-NC) | Verdict |
|---|---|---|---|---|---|
| [Wikidata](https://www.wikidata.org/wiki/Wikidata:Licensing) | P31 type → entity_type; P856 website; P571 inception; P1454 legal form; P452 industry; P463 member of; P749 parent | Measured below: ~17-19% of roster | SPARQL (query.wikidata.org) and wbsearchentities API; ~1 req/s, UA required | Structured data CC0; text CC BY-SA 4.0 (use facts, not copied text) | **Use**, as a pre-fill suggestion |
| [Wikipedia text](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use) | Summaries for activities, sector | Not measured | API or dumps | CC BY-SA 4.0: share-alike conflicts with NC | Use only as a link for the ambassador; no bulk text |
| [IRS EO BMF](https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf) | NTEE_CD → sector and activities; STATUS; ruling year | US only; ~1.98M records nationally | Per-state CSV, e.g. [eo_ca.csv](https://www.irs.gov/pub/irs-soi/eo_ca.csv) | US federal data, public domain (page carries no licence statement) | **Use** for US groups as a suggestion |
| [UK Charity Commission register](https://register-of-charities.charitycommission.gov.uk/en/register/full-register-download) | Charity number, classification, governing document, activities | England and Wales only | Daily extract, JSON or TSV | Open Government Licence v3 ([NCVO guide](https://github.com/ncvo/charity-commission-extract/blob/master/beginners-guide.md)) | **Use** for GB groups |
| [CRA list of charities (Canada)](https://open.canada.ca/data/en/dataset/05b3abd0-e70f-4b3b-a9c5-acc436bd15b6) | Registration number, activities, directors | Canada only | Annual CSV | Open Government Licence Canada (per search; not re-fetched) | Use for CA groups, verify licence |
| [ACNC register (Australia)](https://data.gov.au/data/dataset/acnc-register) | Charity size, purposes, ABN | Australia only | CSV, weekly | Main register is CC BY 3.0 AU (not 4.0); attribution only, compatible | Use for AU groups |
| [Belgium KBO/BCE](https://kbopub.economie.fgov.be) | Legal form, NACE activity, start date | Belgium only | ZIP of CSV (open data, active companies) | Open data licence with a direct-marketing restriction; wording varies by source | Use after licence check |
| [Norway Enhetsregisteret](https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/index.html) | Legal form, NACE, founding date | Norway only | Keyless REST API | NLOD 2.0 (compatibility with CC BY-NC not confirmed) | Use after licence check |
| [India NGO Darpan](https://dataful.in/collections/637/) | Registration, field of work | India | Portal; Dataful mirrors | Official terms **not found**; mirror pages state no licence | Hold until terms confirmed |
| [OpenCorporates](https://opencorporates.com/terms-of-use-2/) | Company identity, legal form | Global companies, few NGOs | API keys; free key only for open-licensed projects | ODbL; share-alike applies to derived data ([ODbL](https://opendatacommons.org/licenses/odbl/1-0/)) | **Reject** for bulk use; link only |
| [GlobalGiving API](https://www.globalgiving.org/api/methods/get-all-organizations-download/) | Organisation list, themes, country | Partner orgs only | API key; two doc versions conflict on key placement | Terms not confirmed | Low value; skip for now |
| [Candid / GuideStar](https://guidestar.candid.org/guidestar-pro-pricing/) | Full nonprofit profile, NTEE | Global, US-strong | Paid API (quotes conflict); exports capped by plan | Licence for NC reuse not confirmed | Paid; needs owner approval (A4-D9) |
| Groups' own websites | About text, languages | Not measured | Crawling | Not fetched | **Out of scope**: A4-D11 forbids crawling-based tagging |
| Common Crawl | Anything | Not measured | Bulk dump | Terms not checked | Reject: it is a crawl |

Not surveyed: Philippines SEC (a company lookup, not a charity register) and Common Crawl licence terms.

## Measured: Wikidata coverage (300-record stratified sample)

Sample: seed 20261126, stratified by country group (US 73, IN 16, PH 16, GB 12, NG 12, other 171). Script: `scratch/group_enrichment/wikidata_spike.py` (cached, rerunnable offline).

- **Overall:** 64 of 300 matched (21.3%, 95% CI 16.7-26.0%). After hand review: 51 correct, 6 ambiguous, 7 wrong. Correct matches are about 17% of the roster.
- **By method:** website domain 47 (exact host on P856); English label or alias 30; any-language search 4 (only 1 correct). Drop the any-language step.
- **Domain precision:** 42 of 47 correct, 5 ambiguous, 0 wrong.
- **English label precision:** 8 of 13 correct. Name collisions are common: a Brazilian municipality, a disambiguation page, a song, a painting.
- **By country group:** US 18/73 (25%), GB 3/12, IN 4/16, PH 3/16, NG 0/12 (only 4 of its records have an eligible URL), other 36/171 (21%).
- **Properties on matched items:** P856 website 56/64; P31 type 62/64 (mostly nonprofit organisation Q163740); P571 inception 37/64; P463 member of 18; P1454 legal form 10; P749 parent 7; P452 industry 5. Inception and website are the useful pre-fill fields.
- **Country check:** rejected 6 matches. Two of the six were plausibly right, but the roster country was an artefact (AF, which has 193 records and is usually a form default). Country cleanup comes before any country-based filter.
- **Errors to design around:** duplicate roster rows (Korea Federation twice); a person's name used as a group (matched to the organisation's domain); a social-media URL in the roster used as a website.
- **Rate limit:** the first run stopped on HTTP 429 at its first large query and was not retried in the same session. A second run completed with no further 429s. Production jobs should keep to 1 req/s and back off.

## IRS spot test (California file only)

- All 652 US roster groups checked against `eo_ca.csv` (CA only): 46 exact-normalised name hits. The national file would be needed for a real rate.
- Within the 300 sample: 6 hits of 73 US records. One was false: an alternate name matched an unrelated Sonoma entity, so alternate-name matching needs a location check.
- NTEE major groups among the 46: Environment (C) 25, Education (B) 3, Health (E) 2, Human services (P) 2, and others. NTEE gives a sector suggestion, not a verified activity list.

## Recommendation (ranked by value per effort, A4-D11-compliant)

1. **Ambassador pre-fill from Wikidata (website, inception, type).** Shown as a suggestion with its source link. Ambassador confirms or rejects, then adds a quote as evidence. Low effort, CC0. Use domain and label matches only, with a country check and a human confirmation.
2. **Register links for each group.** Show the ambassador search links for the group's country register (IRS, Charity Commission, ACNC, CRA). The ambassador copies the registration number and quote. This is not automated tagging and needs no new data rights.
3. **IRS NTEE suggestion for US groups.** Download all state files once (public domain). Suggest sector from NTEE, confirmed by the ambassador.
4. **UK and other open registers** after a licence check and a country-by-country rollout, starting with GB.
5. **Not recommended:** OpenCorporates bulk use, Wikipedia text, Candid (paid, unclear licence), GlobalGiving, and any crawl of group websites.

## Decisions for the owner

1. **A4-D11 interpretation.** Does a Wikidata or registry lookup shown as a suggestion, and confirmed by the ambassador, count as "scraping- or crawling-based tagging"? Recommended answer: no. If yes, amend A4-D11 to name these lookups explicitly.
no.
2. **Attribution text.** Approve an attribution line in the dataset licence for CC0 (Wikidata), public domain (IRS), OGL (UK, Canada) and CC BY 3.0 AU (ACNC).
yes.
3. **Share-alike exclusions.** Confirm no OpenCorporates bulk data and no Wikipedia text in the dataset.
confirmed
4. **Candid.** Approve or decline a paid subscription (A4-D9). Recommendation: decline for now.
declide paid.
5. **Roster cleanup first.** Fix country artefacts (AF), duplicates and person-name groups before the country filter runs.
yes.
6. **Licence verification.** Confirm the Belgium, Norway and India terms and the Charity Commission download licence on the live pages; several could not be fetched in this session.


## Register licences (verified 2026-11-26)

Checked from publisher pages on 2026-11-26. "Fetched" means the page was read directly. "Search excerpt" means the wording came only from a search result for the official page, because the fetch was refused (HTTP 403/406) or the page had no licence text. Quotes come from automated page summaries and are not yet checked word for word, so each licence needs one manual copy-paste check before the methods page ships. No bulk data was downloaded.

| # | Register | Licence (name, version) | Where read (status) | Attribution required | (a) Non-commercial research publication | (b) Mixing into a CC BY-NC 4.0 dataset | (c) Bulk download / API limits | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | UK Charity Commission (England and Wales), full register download | Open Government Licence v3.0 | [full-register-download](https://register-of-charities.charitycommission.gov.uk/en/register/full-register-download): **UNVERIFIED** direct read (HTTP 403). OGL v3.0 from search excerpt of the same site: "all content is available under the Open Government Licence v3.0, except where otherwise stated" | Attribution to the Charity Commission and the OGL; copy the full wording from the download page | Permitted | Permitted with attribution; OGL does not restrict non-commercial use | Daily extract in JSON and tab-delimited; no rate limit in the excerpt. Search exports capped at 5,000 rows; use the full download | **Use with conditions** (attribution; confirm wording on the live page) |
| 2 | Belgium KBO/BCE Open Data (kbopub.economie.fgov.be) | KBO Open Data licence: **name and text UNVERIFIED**. Users must accept a licence to get files | [kbopub login page](https://kbopub.economie.fgov.be/kbo-open-data/login) fetched: no licence text, only "Access to these files is free." Cookbook (Dutch) per search: files for those who accept the KBO Open Data licence. Open Data information page: fetch blocked (bot check) | **UNVERIFIED** | **UNVERIFIED** | **UNVERIFIED.** Public Search (economie.fgov.be) is **not usable**: its terms prohibit reuse and systematic downloading (search excerpt; fines up to EUR 50,000 or 6% of turnover under Code of Economic Law XV.79). Direct-marketing restriction not confirmed | Daily files, kept 31 days. Registration required; SFTP or web download | **UNVERIFIED. Do not use** until the KBO Open Data licence text is read and any direct-marketing clause is confirmed |
| 3 | Norway Enhetsregisteret (data.brreg.no) | NLOD 2.0 (Norwegian Licence for Open Government Data) | [data.brreg.no API docs](https://data.brreg.no/enhetsregisteret/api/dokumentasjon/en/index.html) fetched: names NLOD 2.0. Licence text at [data.norge.no/nlod/en/2.0](https://data.norge.no/nlod/en/2.0) (HTTP 406 on direct fetch; section 5 and section 9 from search excerpt) | Credit the licensor as specified and include a reference to the licence (section 5); link to licence and source where practical. No share-alike clause found in excerpts | Permitted | **Do not mix.** Section 9 lists CC BY 4.0 and older CC BY versions as compatible, but not CC BY-NC. Commentary says NLOD is not compatible with CC for databases; database parts map to ODC-BY 1.0. Mixing into a CC BY-NC dataset is therefore not clearly permitted | No rate limit in the fetched API docs (first 100,000 characters read) | **Do not mix into the CC BY-NC dataset.** Keep as a separate source, or get a Digdir answer first |
| 4 | India NGO Darpan (ngodarpan.gov.in); GODL-India if published on data.gov.in | No open licence found for Darpan. GODL-India (Government Open Data Licence, India, gazetted 2017) applies only to data published on data.gov.in | Darpan home and terms pages fetched: no licence named. Search excerpt: the portal reserves the right to use submitted information. data.gov.in terms and GODL pages: HTTP 403 / 404 (**UNVERIFIED** direct read) | GODL-India attribution template (search excerpt): provider, year, dataset, repository, version, identifier, licence name and URL | Darpan: no grant found, so **UNVERIFIED**, treated as all rights reserved. GODL-India: permitted per excerpts | Darpan: **do not mix** without written permission. GODL-India: attribution-only per excerpts; no share-alike found, **UNVERIFIED** | Not stated for Darpan. GODL-India: none in the excerpts | **Darpan: do not use.** GODL-India data from data.gov.in: **use with conditions** once the licence text is fetched (**UNVERIFIED**) |
| 5 | Canada CRA List of Charities (open.canada.ca) | Open Government Licence – Canada, version 2.0 | [OGL-Canada 2.0](https://open.canada.ca/en/open-government-licence-canada) fetched. Dataset record: [2025 List of charities](https://open.canada.ca/data/en/dataset/4b60228a-2b78-45d3-8e05-f7150b8fe8d8) (search) | "Contains information licensed under the Open Government Licence – Canada." Acknowledge the source and link to the licence where possible. Do not imply endorsement | Permitted; commercial use included | Permitted with attribution. OGL-Canada permits any lawful use, so CC BY-NC output is fine if attribution is kept | None stated in the licence. Bulk CSV per year | **Use with conditions** (attribution and no-endorsement) |
| 6 | Australia ACNC Register (data.gov.au) | CC BY 3.0 AU (dataset metadata). **Conflict:** page footer says CC BY 4.0. Coat of Arms excluded | [acnc-register](https://www.data.gov.au/data/dataset/acnc-register): HTTP 403 on direct fetch; metadata/footer conflict from search excerpt. **Version UNVERIFIED** | Attribution under CC BY 3.0 AU or CC BY 4.0 (author, title, source, licence link). Use the wording the ACNC states on the dataset page | Permitted | Permitted with attribution. CC BY (either version) allows NC outputs. Use CC BY 3.0 AU wording until the ACNC resolves the conflict | Weekly updates; no rate limit in excerpts | **Use with conditions** (attribution; resolve metadata/footer conflict) |
| 7 | US IRS EO BMF (irs.gov) | No licence statement on the IRS page. US federal government work (general law, 17 U.S.C. section 105; **not stated on the page**) | [EO BMF page](https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf) fetched: only an endorsement disclaimer ("does not constitute or imply its endorsement"). No copyright or reuse statement | No legal attribution requirement found; source line and no-endorsement statement as courtesy | Permitted | Permitted. Mixing is fine; keep the no-endorsement line | No restriction stated on the page | **Use** (no restriction stated; keep source line and no-endorsement statement) |

### Attribution lines for the methods page (draft; check each against the live licence text)

- UK: "Contains public sector information licensed under the Open Government Licence v3.0. Source: Charity Commission for England and Wales, Register of Charities."
- Canada: "Contains information licensed under the Open Government Licence – Canada. Source: Canada Revenue Agency, List of charities."
- Australia: "Source: Australian Charities and Not-for-profits Commission (ACNC) Register, licensed under Creative Commons Attribution 3.0 Australia (https://creativecommons.org/licenses/by/3.0/au/)." Change the licence version if the ACNC resolves the footer conflict in favour of CC BY 4.0.
- US: "Source: Internal Revenue Service, Exempt Organizations Business Master File Extract (EO BMF). This is not an endorsement by the IRS."
- Not used yet (Norway, Belgium, India): no attribution line. Add one only if the verdicts above change.

### Open items for the owner

1. Read the live UK download page and the ACNC dataset footer, then copy the exact licence wording.
2. Read the KBO Open Data licence text (after registering on kbopub) and confirm whether it has a direct-marketing clause. Belgium stays unusable until then.
3. Ask Digdir whether NLOD 2.0 data can be combined with CC BY-NC 4.0 content, or keep Norway out of the mixed dataset.
4. Confirm whether NGO Darpan data is published on data.gov.in. If not, Darpan stays excluded.
