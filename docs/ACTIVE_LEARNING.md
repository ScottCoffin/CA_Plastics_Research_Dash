# Active-learning labelling framework (spec, 2026-11-11)

Owner request: extend the work-relevance human-in-the-loop (ADR-AL-RELEVANCE-2026-11-11,
first implementation `atlas.nlp.active_relevance`, model card
`docs/MODEL_work_relevance_al.md`) to the other classification tasks, or spec it.

## Principle: two label streams, never mixed

| Stream | Selection | Used for | Must not be used for |
|---|---|---|---|
| Gold set (S4.2 `curation/splits_v2.csv`, guide_v2) | fixed stratified + leak-test sample, labelled as drawn | evaluation (frozen test), threshold choice (dev), kappa (Claude second rater on 20%) | active-learning selection |
| Active learning (AL) | model-chosen: uncertain, model-vs-assist disagreement, random audit | training data and accepting auto-labels | reporting model performance (biased sample) |

S4.2 test-split works are excluded from every AL queue and training set. Published model
metrics come only from the frozen test split (F3 / spec Part E S4.2 rule); AL audit
accuracy is reported separately, as "auto-label accuracy on confident predictions".

## Shared engine (`atlas.nlp.al`, generalising `active_relevance`)

- **Embeddings:** one cache per (unit, model) under `data/interim/embeddings/`; units are
  `work` (title+abstract), `sentence` (S5.3 evidence sentences) or `grant`
  (title+abstract). Default model BAAI/bge-small-en-v1.5 (local, optional `ml` extra).
- **Task config** (`config/al_tasks.yml`): task id, unit, label schema (binary,
  single-label with classes, or multi-label tag list), label sources (owner CSVs, AT-1,
  gold set excluded), assist source (Haiku/rules) for disagreement picks, output file,
  target accuracy (default 0.95), batch size, query mix.
- **Models:** binary and single-label use calibrated logistic regression (sigmoid, 5-fold);
  multi-label uses one-vs-rest calibrated logistic regression per tag, with per-tag
  thresholds chosen on cross-validation (never on the S4.2 test split). Classes or tags
  with < 15 positive labels are reported as "insufficient data" and never auto-accepted.
  SetFit stays the S5.1/S5.5 upgrade path when logistic regression plateaus.
- **Query strategy:** uncertainty (binary: |p-0.5|; single-label: margin between the top 2
  classes; multi-label: the most uncertain tag per item, rotated over tags with the
  fewest labels), assist disagreements, and about 15% random audits of confident labels.
- **Stopping and acceptance:** per class or tag, audit accuracy with a Wilson 95% interval;
  accept only classes/tags whose lower bound reaches the target with at least 30 audits.
  Others stay owner-reviewed or assist-labelled and are flagged "experimental" in the UI
  (S5.5 rule: weak tags merged or experimental).
- **State:** `curation/al_state/<task>.json` (labels counts, CV metrics, audit log with pick
  reasons, accuracy trend per retrain, model version); accepted labels in
  `curation/al_labels/<task>.csv`; export precedence: owner > curated overrides >
  accepted AL labels > assist (Haiku/rules).
- **App:** one Streamlit app with a task selector, reusing the accuracy panel (audit
  accuracy and CI against the target line, audits needed, CV fit, errors remaining,
  trend), Retrain, and Accept (enabled only when ready). Multi-label items show
  per-tag checkboxes and highlight the tag being queried.

## Per-task mapping

| Task | Unit | Labels | Assist for disagreement | Output feeds |
|---|---|---|---|---|
| S5.1 plastic relevance (built first) | work | binary | Haiku `work_relevance.csv` | export `plastic_related` |
| S5.3 sampling vs mention | sentence (gazetteer-hit sentences from abstracts/S6 full text) | binary sampled / mentioned | S5.2 rules | S5.4 `ca_sampled` aggregation |
| S5.5 domain tags | work | multi-label (8 topics + matrices) | S2.3 keyword rules | `domain_tags`, `facet_tags` (topics.js) |
| EM-4 A2 fields | work | study_type single-label; compartment, waterbody, pathway, source, product, size multi-label | A2 keyword rules (`config/a2_keyword_rules.yml`) | evidence map EM-8 |
| S8 grant topics | grant | multi-label topics | S2.3 rules on grant text | grants Sankey topics |
| S5.2 gazetteer gate | place match in context | binary keep/drop | gazetteer blacklist | S5.3 candidate sentences |

## Order of work

1. Ship and validate S5.1-AL (relevance) with the owner.
2. Refactor to the shared engine plus `config/al_tasks.yml`, with S5.1 re-expressed as
   the first config (regression: same queue and metrics).
3. S5.5 domain tags (largest visible gain: 38% of works are untagged), then S5.3 once
   evidence sentences exist, then EM-4 fields, then grant topics.
4. Gold-set app for the S4.2 sample (guide_v2 fields), sharing widgets but not selection.

Tracked as TODO S5.0.
