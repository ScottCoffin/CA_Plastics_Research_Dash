# Model card: work-relevance active learning (S5.1-AL)

## Purpose

Over 1,000 works carry a Claude Haiku call in `curation/work_relevance.csv` ("is plastic a central subject?"). Reviewing every one is too much for the owner. This model ranks the works so the owner labels the few that matter, and measures how accurate the model's confident calls are, so the rest can be accepted with a stated error rate instead of read one by one.

## Data

- Texts: OpenAlex title plus abstract (abstract truncated to 2,000 characters) from `data/interim/works_raw.parquet`, 1,933 corpus works.
- Embeddings: `BAAI/bge-small-en-v1.5` (sentence-transformers, CPU, 384 dimensions, L2-normalized), cached in `data/interim/embeddings/<model_slug>.npz` keyed by `work_id` and the SHA-1 of the text. Only new or changed texts are recomputed. Fallback model: `sentence-transformers/all-MiniLM-L6-v2`.
- Human labels: owner AT-1 audit labels (`docs/QUERY_AUDIT_REVIEW.csv`, then `docs/QUERY_AUDIT_REVIEW_V3.csv`, which wins; `relevant` = 1, `not_relevant` = 0, `unsure` skipped) plus owner decisions in `work_relevance.csv` (`owner_review` confirmed or changed). An owner decision beats an AT-1 label for the same work.
- Excluded everywhere: works in the S4.2 frozen **test** split (`curation/splits_v2.csv`, `split=test`). They are never trained on, scored, queued or accepted.
- Unlabeled population: every non-test corpus work with no owner decision and no AT-1 label: works with a pending Haiku row, plus works with no Haiku row at all (no disagreement pick for those; uncertainty and audit picks apply). Owner-"unsure" rows and works skipped as unsure are left alone.
- Owner decisions on works with no Haiku row are appended to `work_relevance.csv` by `record_owner_decision`: `plastic_related` = owner choice, `assist_plastic_related` and `confidence` empty, reason `owner (no assist call)`, `owner_review` confirmed. The loader and export accept the empty assist value (tested). "Unsure" on such a work is stored as a skip in the state file, not in the CSV.

## Method

Logistic regression (`class_weight="balanced"`, C=4) on the embeddings, sigmoid-calibrated (`CalibratedClassifierCV`, cv=5) when both classes have at least 10 labels; otherwise uncalibrated with a warning. Fit metrics are 5-fold stratified cross-validation on the labelled set: ROC-AUC, accuracy, and precision and recall of the "not relevant" class at 0.5. These describe fit on labelled works. **They are not the accuracy of the auto-labels** on unreviewed works.

## Query strategy (batch of 20)

| Share | Pick | Why |
|---|---|---|
| 12 (60%) | Smallest abs(p - 0.5) | Most informative labels |
| 5 (25%) | Model and Haiku disagree, ranked by model confidence | Likely errors on either side |
| 3 (15%) | Uniform random from confident auto-labels (abs(p - 0.5) >= 0.4) | **Audit**: unbiased sample for the accuracy estimate |

The audit sample is drawn first from the full confident pool. Each audit pick is logged with its reason, the model's call at pick time and the owner's answer. **Audit round.** The app has a prominent "Start audit round" button: a batch of 20 random audits drawn from confident auto-labels, stratified across predicted classes in proportion. The panel recommends it when the last two retrains each changed CV accuracy by under 1 point. The mixed queue stays the default and returns after the batch.

The model retrains from cached embeddings (about 0.5 s) every 20 decisions or on demand.

## Stopping rule

Auto-label accuracy is estimated from audited items only (outcome correct or wrong; "unsure" is dropped), with a Wilson 95% interval. `ready_to_accept` needs a lower bound at or above the target (owner decision: **95%**) and at least 30 audited items. Estimated wrong auto-labels remaining = (1 - accuracy) x number of confident auto-labels, with an upper bound from the interval's lower end. Note the arithmetic: even with zero errors the Wilson lower bound reaches 95% only at about 73 audited items, and each error raises that figure substantially. State and the per-retrain trend live in `curation/work_relevance_al_state.json`.

Accepting (app button, only when ready and a confirmation box is ticked) writes `curation/work_relevance_model.csv` (`work_id, plastic_related, p_relevant, model_version, accepted_at`) for confident, unlabeled, non-test works only. Owner-decided rows are never written.

## How it feeds S5.1 and the export

Export precedence for `plastic_related`: owner decision (`owner_review` confirmed/changed) > owner AT-1 overrides (`curation/overrides_works.csv`) > accepted model labels > Haiku (`work_relevance.csv`) > rule label. `scripts/build_export_site.py --model-relevance` defaults to the model CSV and treats a missing file as no labels. Every owner decision also becomes training data for the next S5.1 steps.

## First run (2026-11-11)

- Labels: 404 (346 relevant, 58 not relevant), all AT-1; no owner decisions yet; test-split works excluded (72 AT-1 labelled works are not in the current corpus).
- 5-fold CV: ROC-AUC 0.921, accuracy 0.908, "not relevant" precision 0.756, recall 0.534 (calibrated).
- Queue-eligible works: 1,448 (1,027 with a Haiku row, 421 with none); confident auto-label candidates: 816; model-Haiku disagreements: 149.
- First queue: 12 uncertain, 5 disagreement, 3 audit.
- Timings (12 cores, CPU): embedding all 1,933 works about 112 s once; rerun from cache 0.06 s; train plus score 0.3 to 0.5 s.

## Limitations

- Only 58 negative labels, and they come from the AT-1 audit of query hits, not from Haiku's 310 "false" calls, so recall on "not relevant" is weak until the owner labels more. Expect early disagreements to be informative.
- Labels from AT-1 and from the review queue come from different distributions; the audit sample is the only unbiased check, and it covers only works the model is confident about.
- Wilson interval assumes independent audit draws; reshuffling after each retrain keeps this approximately true. The model changes between audits, so the pooled estimate is an average over model versions; the trend table shows whether later audits are better.
- Text only: no journal, topic or author features. Works without an abstract rely on the title.
- English-language embedding model; abstracts truncated at 2,000 characters.
- Needs the optional `ml` extra (`py -3.14 -m pip install -e .[ml]`); it is not part of CI or base dependencies.
