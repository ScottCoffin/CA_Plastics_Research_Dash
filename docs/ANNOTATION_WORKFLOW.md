# S4.3 annotation workflow

## S4.4 evaluation

`src/atlas/nlp/eval.py` evaluates one canonical, adjudicated gold row per work
against one prediction per work. It reports precision, recall, and F1 by class
for plastic relevance, plastic tier, California sampling, and study type; each
configured domain tag is scored as a binary label. Missing classes remain
`undefined` and zero-support tags are marked as lacking positive support.
When probabilities are present, it emits a reliability diagram and binned
observed rates. Optional boolean `gazetteer_gate` predictions produce gate
recall for gold `ca_sampled` values `yes` or `partial`.

Example after a validated, adjudicated gold JSON is prepared:

```powershell
py -3.14 scripts/evaluate.py --gold curation/gold_works.json --predictions model_predictions.json `
  --split dev --model-version rules-v1 --data-snapshot works-2026-11-06 `
  --output docs/EVAL_rules-v1.md --plot docs/EVAL_rules-v1_calibration.png
```

Development uses `--split dev`; it is the only appropriate split for threshold
selection and error analysis. Test access requires `--split test --final-test`;
this reports frozen final performance and must not influence development. The
harness refuses duplicate work IDs, unresolved or duplicate gold rows, split
misalignment, prediction ID mismatch, invalid classes, incomplete probabilities,
and missing model/data provenance. Use an adjudicated gold release: independent
annotator CSV imports are not evaluation truth until disagreements are resolved.
The synthetic acceptance output is in `docs/EVAL_synthetic_v1.md` and contains
no corpus labels or performance claims.

The workflow exports one CSV per annotator from `curation/splits_v1.csv`, validates returned CSVs against those frozen work IDs and split assignments, and computes pairwise Cohen's kappa summaries. It does not produce labels, suggestions, or adjudication decisions. The `guide_v1` approval/hash gate is checked by the command line before export, import, or report generation.

## Gate and held-out handling

`docs/LABELING_GUIDE.md` remains a draft pending S4.1-A. Until the owner approves and freezes the exact guide and `docs/LABELING_GUIDE_REVIEW.md` records its matching SHA-256, the command line refuses all annotation operations. Unit tests exercise the functions using synthetic rows; they do not represent human annotation or bypass the real-workflow gate.

Templates include title, abstract, and year from the normalized works snapshot as read-only context and omit model outputs. The importer checks that these source fields still match that snapshot. Test rows are omitted from export by default; exporting or importing test rows requires explicit `--include-test`. Agreement reports require an explicit `--split`; use `--split test` only for the test-set agreement report. The tool never provides suggestions. Per F3, do not use test items for threshold tuning or development error analysis. Leak-test rows remain in `test`.

## Export and import

After guide approval, export independent copies (replace annotator IDs with project-approved pseudonyms):

```powershell
py -3.14 scripts/annotation_workflow.py export --annotators A,B --output-dir curation/annotations_v1
py -3.14 scripts/annotation_workflow.py import --inputs curation/annotations_v1/annotations_A.csv curation/annotations_v1/annotations_B.csv --output curation/annotations_v1/validated.json
py -3.14 scripts/annotation_workflow.py agreement --annotations curation/annotations_v1/validated.json --output docs/annotation_agreement_v1.json --split train
```

Test rows are a separate explicit operation: include `--include-test` on both `export` and `import`, then request the report with `agreement --split test`. The tooling does not invent an evaluation-lock approval state; F3's no-development-use rule still applies.

The importer requires the exact ordered CSV header written by the exporter, a unique `(work_id, annotator)` pair, known IDs, unchanged source metadata, `split` and `sample_role`, matching guide version, allowed categorical values and taxonomy IDs, and coherent evidence/adjudication fields. It rejects test rows by default; add `--include-test` only for final evaluation preparation. Use `true`/`false` for `plastic_related`; a negative has no tier. `domain_tags` is a pipe-separated list of configured IDs. Use `decision_status=adjudication_required` for unresolved records; they must carry no labels and are excluded from kappa. A locator-only full-text decision uses `evidence_source=full_text_locator` and should identify the locator in the note/evidence field without copying restricted text. Adjudication fields preserve a later decision and rationale separately from independent annotator values.

Keep raw independently completed CSVs as provenance. Export writes `annotation_export_manifest.json`; import writes a sibling `.manifest.json`. These record the guide and split hashes, normalized-work snapshot hash, template/input CSV hashes, annotator IDs, and whether test rows were included. The validated JSON is a normalized working artifact, not a frozen gold release. No command writes to `curation/gold_works.csv`.

## Agreement report

The report gives pairwise Cohen's kappa for `plastic_related`, `plastic_tier`, `ca_sampled`, `study_type`, and each domain tag as a binary indicator, plus paired work count and observed agreement. Only complete annotations present from both annotators are paired. Kappa is `null` with a status when there are no pairs or expected agreement is one, so constant-label edge cases are visible rather than reported as a numeric pass. `disagreements` lists conflicting or unresolved work/fields with both annotators' values and evidence provenance; every item is `unresolved` and has empty adjudication fields. The report makes no adjudication or threshold claim. S4.3's ≥20% double-annotation rate is a later human annotation milestone and must be checked against the approved representative sample; synthetic acceptance tests cannot satisfy it.
