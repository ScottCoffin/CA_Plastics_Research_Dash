# S4.1 guide preparation checks

This note records bounded source and edge-case consistency checks for `guide_v1`. Owner approval was recorded 2026-11-07 in `docs/LABELING_GUIDE_REVIEW.md`; together with the checks below, this completes S4.1 only. It does not establish representative data, annotation, gold labels, or corpus performance.

## Contract sources checked

- `spec.md` A2 (lines 11–21): plastic scope and tier, CA-led, CA-sampled, CA-plastic-centric derivation, California land/state waters, and candidate-pool caveat.
- `spec.md` C3–C4 (lines 202–228): existing work-label fields; candidate relevance rules; sampling-versus-mention; polygon boundary and partial cases; multi-label domain tagging.
- `spec.md` S4.1 and S4.2 (lines 408–417): required edge cases, owner approval and freeze before labeling, stratified sampling and held-out test hygiene.
- `spec.md` F1 and F3 (lines 501–517): proposed G-9 targets are targets rather than current performance claims; test-set isolation.
- `.agent/QUESTIONS.md` G-1–G-5 and G-9–G-10: tier and core inclusions, CA-led scope, beyond-3-nm handling, all-years/last-10 emphasis, proposed thresholds, and owner-led adjudication.
- `config/queries.yml` and `config/taxonomy.yml`: candidate terms, collision-prone qualified terms, configured domain IDs, and candidate provenance.
- `curation/gold_works.csv` header only and `docs/api_notes/labels.md`: existing annotation columns and provisional rule status.

## Bounded consistency examples

| Case traced through guide | Expected result | Check |
|---|---|---|
| California-affiliated first author, no California field work | `ca_led` can be true; `ca_sampled` remains `no` or `unclear` based on evidence | Separate fields; affiliation is not a sample site. |
| Field study in California coastal waters plus sites beyond 3 nm | `ca_sampled=partial` | Matches G-4 and the guide’s explicit mixed-footprint rule. |
| California lab analyzes organisms collected at a named non-CA site | `ca_sampled=no` | Lab location does not replace sample provenance. |
| Review of Bay Area monitoring literature | Plastic label depends on review subject; `ca_sampled=no` | Work itself did not sample; background mention is not sampling. |
| Abstract says only “Bay Area” and gives no collection detail | `unclear` only if sampling is asserted but the site is unresolved; otherwise `no` | No site is invented from an ambiguous mention. |
| Abstract studies tire-wear particles in runoff | `plastic_related=true`, `core`; supported occurrence/environment tags may be multiple | G-2 and qualified query term agree. |
| Abstract studies only 6PPD-quinone exposure as its primary subject | Passes the initial relevance gate; `plastic_related=true`, `chemicals-in-plastics`; not core from a chemical mention alone | The first gate explicitly includes tier-2 subjects; G-1 tier separation and candidate tier terms agree. |
| Work is about environmental synthetic textile microfibers | `plastic_related=true`, `core` | G-2 plus query qualification; generic/optical microfiber remains negative. |

These are policy examples, not labels assigned to corpus records. No gold records were opened beyond the CSV header, and no annotation or adjudication occurred. The guide edge-case DoD and explicit owner approval are complete; representative-data and annotation gates remain open.
