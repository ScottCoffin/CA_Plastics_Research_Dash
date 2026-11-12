# S5.1 plastic-relevance classifier: dev evaluation, gap and labelling plan

Date: 2026-11-12. Command: `PYTHONPATH=src py -3.14 scripts/eval_s5_1_dev.py` (writes
`scratch/s5_1_dev_eval.json`).

Acceptance (spec Part E): "Meets thresholds in G-9 on test set, or documents the gap and
proposes more labels." G-9 / Appendix F1 target: plastic-relevance F1 >= 0.90. This
document takes the second route. The frozen S4.2 test split (155 works) has no gold labels
yet, so no test-set number exists. Nothing below touches the test split.

## Labels used

535 owner labels outside the test split (`atlas.nlp.active_relevance.assemble_labels`):
476 AT-1 audit labels and 59 owner decisions from the works review app. These labels are
skewed: the AT-1 sample was drawn from query hits, so about 85% are relevant (391 relevant
vs 72 not relevant among those with text).

## Results (relevant class, development data)

| Predictor | n | Precision | Recall | F1 (95% bootstrap CI) |
|---|---:|---:|---:|---|
| Keyword rule (`plastic-v3.1` local rule) | 455 | 0.879 | 0.922 | 0.900 (0.878-0.922) |
| Claude Haiku assist (where a call exists) | 51 | 0.967 | 0.744 | 0.841 (0.742-0.923) |
| AL embedding model, bge-small + calibrated LR, 5-fold CV | 463 | 0.913* | 0.967* | 0.939* |

\* Derived from the CV confusion counts: ROC AUC 0.917, accuracy 0.894, not-relevant
precision 0.735, not-relevant recall 0.500. Haiku's 51 rows are works the owner judged
while seeing the Haiku call, so that row measures agreement more than independent accuracy.

## Gap

1. No test-set measurement: the S4.2 gold set is unlabelled.
2. The weak class is "not relevant". The model misses half of the off-topic works (recall
   0.50) because only 72 negatives exist. The keyword rule's lower bound (0.878) sits just
   under the target.
3. The labels come from query hits, so they under-represent the hard negatives
   ("plasticity", passing mentions, BPA/phthalate health studies with no plastic angle).

## Labelling plan

1. Owner labels the S4.2 sample in the gold-labelling app
   (`scripts/review_gold_labels_app.py`): dev and test first (230 works), then train.
   A Claude reviewer double-labels 20% for kappa (owner decision, ADR-GATES-2026-11-11).
2. Keep the works review app's Smart queue on uncertain works; it surfaces likely negatives.
   Target at least 150 not-relevant labels outside the test split before retraining.
3. Then evaluate once on the test split (F3 hygiene: no tuning on test). If F1 < 0.90,
   escalate per Appendix F1 (more labels, SciBERT/SetFit, local LLM) via DECISIONS.md.
