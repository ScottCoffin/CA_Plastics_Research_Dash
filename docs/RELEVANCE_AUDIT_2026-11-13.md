# Relevance audit, 2026-11-13 (REL-1)

Owner report: "Investigating early brewing and filtering technology in late Neolithic: pottery
residue analysis of the Wayaoli site in Southern China" (W7225234225, 4 Nov 2026,
*Archaeological and Anthropological Sciences*) appeared on the Evidence map.

## Why it appeared

1. **Ingest.** The OpenAlex query (`plastic-v3.1`, `title_and_abstract.search`) matched it, but
   OpenAlex does not return the abstract (the publisher withholds it; `abstract_inverted_index` is
   null). The record's OpenAlex keywords include "microfibers" (plant fibres in pottery residue), so
   the hidden abstract almost certainly hit the qualified term `microfiber` together with a context
   word such as "washing". The search still covers abstracts that the API no longer serves.
2. **Labels were correct.** With no abstract, the local rule labeller found no hits
   (`plastic_related=false`), and the Haiku screen agreed ("Neolithic pottery residue analysis",
   high confidence).
3. **Display bug.** The export keeps every California work (experts' profiles need them), and
   `works_detail.json` carries `plastic_related`. The Evidence map rendered all 1,909 works and
   ignored that field. 432 works labelled not plastic-related were on the page, this one among them.

## Similar mis-tagged works

All 432 export rows with `plastic_related=false` were exposed the same way. Examples included
landslide soil plasticity, Younger Dryas chronology, serotonin pharmacology, and plastic surgery and
"plastic responses" in ecology. The fix (Evidence map shows `plastic_related === true` only) removes
them as a class. Among the works labelled true, the only doubtful rows lack a Haiku or owner
decision (e.g. W2053506921 atmospheric organic aerosol, W2165962279 oil-spill remote sensing,
W4396837860, W4405269670). They stay in the owner's review queue (H2) and are not changed here.

## Relevant works we were losing

Cross-tab of export decision × rule label × Haiku call × owner review (1,909 works):

| Group | Works | Action |
|---|---:|---|
| Rule false, never screened (ingested after the Haiku pass: ORCID, eScholarship, Moore Institute) | 35 | 8 rescued by the title patterns below; the other 28 screened by Haiku on 2026-11-13 (10 true, 18 false), appended to `curation/work_relevance.csv` as pending rows |
| Rule chemicals-in-plastics hit, Haiku false with **low** confidence, owner pending | 78 | Kept as plastic-related by `relevance_policy.tier2_survives_low_confidence_false` (REL-TIER2) |
| Rule core hit, Haiku false, low confidence, owner pending | 79 | Unchanged; mixed (trash/litter surveys vs. particle physics). Owner review H2 |
| Rule core hit, Haiku false, high confidence | 121 | Unchanged; spot check found these correct (litter beetles, "microplastic" deformation of metals, quantum chemistry "upcycling") |

Rescued by the 2026-11-13 changes include the plastisphere paper (W1967071586), the Raman
identification of polymers in fish stomachs (W2761119328), microplastics in rainfall (W4408982698),
polystyrene and polyolefin conversion papers, the Plastics Treaty commentary and the ALDFG special
issue.

## Protocol changes

1. **Display:** the Evidence map (counts, trends, heatmap, table, "new" callout) uses only works
   whose resolved `plastic_related` is true. The precedence is unchanged: owner decision > AT-1
   override > accepted model > always-relevant patterns > Haiku > rule.
2. **Title-only patterns** (`title_relevant_patterns` in `config/queries.yml`): eight
   high-precision phrases at the same precedence as `always_relevant_patterns`. Each had 100% precision
   on the export titles (36 already-true matches, 8 rescues, 0 false hits). The same phrases in
   abstracts were noisy (e.g. "plastic film" in greenhouse papers), so abstracts are not searched.
   They do not change the OpenAlex query, so `query_version` stays `plastic-v3.1`.
3. **Chemicals-in-plastics tier:** a pending low-confidence Haiku "false" no longer drops a rule
   tier-2 hit (BPA, phthalates, 6PPD). The labelling guide treats that tier as plastic-related.
   High-confidence Haiku calls and owner decisions still win.
4. **Unscreened works:** each new batch of rule-false works needs a Haiku screen before export. The
   audit query is the cross-tab above (works in `works_detail.json` with no row in
   `curation/work_relevance.csv`). Run it after any non-query ingest (ORCID DOIs, eScholarship,
   always-include filters).

## Resulting counts

Export after the changes: 1,909 works, of which 1,573 are plastic-related (1,477 before REL-1;
1,563 after the patterns and tier-2 policy, then +10 from the 28 new Haiku rows). The Evidence map
shows those 1,573 works.
