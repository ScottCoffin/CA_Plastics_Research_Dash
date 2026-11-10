# S9.1 work-grant link precision spot-check

Scope: all 17 links in `data/processed/work_grant_links.parquet` (fewer than the
50-link target, so every link was checked). Sampling used
`atlas.link.work_grants.sample_links(links, 50, seed=91)`, which returned all 17.

Method: each link was checked against independent evidence from the grant's own
record in `data/interim/grants/grants_merged.parquet` (PI name, lead institution,
title) and the work's `raw_json` (authorship names, institution names, title).
Automated flags were computed for PI surname in the full author list, lead
institution words in the work's institutions, and title overlap. Verdicts are the
author's judgment from those flags. Abstracts were not used.

Verdict scale: **correct** = the grant's PI or lead institution appears in the work
and the topic agrees; **incorrect** = the independent evidence contradicts the link;
**unclear** = the independent evidence is partial, such as a centre-level award
whose PI is not an author.

Columns: `#` is the sample index. `work` is the last 8 characters of the OpenAlex
work id. `grant` is the first 6 hex characters of `grant_key`. `award` is the
OpenAlex `funder_award_id` (normalized) and the RePORTER `appl_id` or NSF award id.

| # | work | grant | award | verdict | reason |
|---|---|---|---|---|---|
| 1 | 51321069 | 3c6f64 | R01ES032037 / appl 10876343 | correct | PI Castillo is an author; UNM affiliation; microplastic GI topic matches |
| 2 | 51321069 | 516496 | R01ES032037 / appl 11022777 | correct | Same project number; diversity supplement under PI Castillo, who is an author |
| 3 | 51321069 | 61d221 | P20GM130422 / appl 11506799 | unclear | UNM affiliation matches; PI El Hayek not an author; CSF topic loosely related |
| 4 | 51321069 | 63c049 | P30CA118100 / appl 11423301 | unclear | UNM Cancer Center affiliation; PI not an author; program title unrelated to the work |
| 5 | 51321069 | 641f4e | R01ES032037 / appl 11383764 | correct | PI Castillo is an author; same project number; topic matches |
| 6 | 51321069 | 7a9814 | P20GM130422 / appl 11505275 | unclear | Same centre award as #3; PI not an author |
| 7 | 51321069 | a9d23f | P20GM130422 / appl 11378077 | correct | PI Campen is an author; UNM; centre-level project (topic weak) |
| 8 | 51321069 | ee500f | P30CA118100 / appl 11078137 | unclear | Topic matches (microplastic exposure, colon); PI Sanchez not an author; centre core |
| 9 | 60290292 | 3c6f64 | R01ES032037 / appl 10876343 | correct | PI Castillo is an author; UNM; microplastic toxicity topic |
| 10 | 60290292 | 516496 | R01ES032037 / appl 11022777 | correct | Same as #2; PI Castillo is an author |
| 11 | 60290292 | 641f4e | R01ES032037 / appl 11383764 | correct | Same as #5; PI Castillo is an author |
| 12 | 61836069 | 1290af | NSF 2340588 | correct | PI Jazaei is an author; University of Memphis; soil microplastic transport topic matches |
| 13 | 62468494 | 33367a | P30ES005022 / appl 11370862 | unclear | EOHSI affiliation matches; PI not an author; generic title "Human/Animal Exposure" |
| 14 | 62468494 | 401033 | P30ES005022 / appl 10830089 | unclear | Same centre award as #13 |
| 15 | 62468494 | ec6a6e | R01ES036575 / appl 11131889 | unclear | Co-PI Stapleton is an author (EOHSI); topic matches; lead org NYU not among the work's institutions |
| 16 | 63038666 | 11cbc9 | NSF 1935028 | correct | PI Harper is an author; Oregon State affiliation; micro/nanoplastic topic overlaps |
| 17 | 21776748 | ec6a6e | R01ES036575 / appl 11131889 | unclear | Same grant as #15; Stapleton is an author, but the topic link is weak and NYU is not listed |

Counts: correct 9, incorrect 0, unclear 8 (n = 17).

Precision = correct / (correct + incorrect) = 9 / (9 + 0) = 100.0% (n = 17 decided
links; 8 links are unclear and excluded from the denominator).

Caveats:
- Sample size is 17, so the 95% lower bound on precision is well below 100%.
- Verdicts are one reviewer's judgment, not an independent second reviewer.
- A single OpenAlex award fans out to every RePORTER `appl_id` for that project
  number, so one award can produce several links (for example #1, #2, #5 for
  R01ES032037). Owner decision needed: keep project-level fan-out or restrict to
  one appl per fiscal year.
- Eight unclear links (about half) are centre-level or co-PI matches. The owner should
  decide whether these stay in the atlas before the S9.1 DoD is closed.
