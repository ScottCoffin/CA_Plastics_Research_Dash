# Corpus-quality estimators (BQ-1.1)

Implementation: `src/atlas/nlp/quality.py` (pure, standard library only; per-class F1 reuses
`atlas.nlp.eval._class_metrics`), CLI `scripts/bq1_estimate.py`, tests `tests/test_bq1_estimate.py`.
Output schema `bq1-v1` is the input to BQ-1.4 (`quality.json`). Run:

    py -3.14 scripts/bq1_estimate.py --synthetic --out scratch/bq1/synth.json
    py -3.14 scripts/bq1_estimate.py [--predictions PATH] [--out scratch/bq1/quality.json]

## Estimands

| Id | Meaning | Domain (den) | Numerator | Design |
|---|---|---|---|---|
| E1 | CA precision of displayed plastic_related = true | predicted true | gold true and predicted true | CA two-stage HT ratio |
| E1g | Global precision, same definition | predicted true | gold true and predicted true | stratified ratio |
| E1s | Lifecycle-and-society precision (P4 centrality) | predicted tier = lifecycle_and_society | gold plastics_centrality in {primary, substantial} | CA two-stage HT ratio |
| E1l | Lens precision | predicted lens non-empty | gold lens = predicted lens | unweighted, exact; indicative |
| E2 / E2g | Recall within corpus (CA / global) | gold true | gold true and predicted true | as E1 / E1g |
| E3 | Current-model plastic_related P, R, F1 | held-out `test` rows | - | unweighted, Wilson on counts |
| E4 | Per-tag F1; per-study_type one-vs-rest F1 and kappa | gold true rows | - | unweighted |
| E7 | Low-band residual bound (P3) | predicted band = low | gold true | unweighted, zero-hit rule |

Breakdowns (descriptive): E1 and E2 within each block (CA, global) by theme group, label source,
year, language and abstract presence. Each level has n and an `insufficient_data` flag below
`--min-n` (default 30).

## Formulas

- **Wilson interval** for k of n: centre `(p + z^2/2n)/(1 + z^2/n)`, half-width
  `z sqrt(p(1-p)/n + z^2/4n^2) / (1 + z^2/n)`, z = 1.95996. Example: 5 of 10 gives (0.2366, 0.7634).
- **Zero-hit bound (P3)**: with no hits in n, the one-sided 95% bound is `1 - 0.05^(1/n)`;
  n = 100 gives 0.0295.
- **Clopper-Pearson** (k > 0): exact one-sided and two-sided bounds from the binomial CDF, solved by
  bisection. Used for unweighted counts (E1l, E4, E7). For k = 0 the upper bound equals the zero-hit rule.
- **Horvitz-Thompson (CA pool)**: strata are primary units; 500 of 873 strata are drawn and one work
  is taken per drawn stratum. Inclusion probability `pi = (500/873) / N_h`, weight `1/pi = 1.746 N_h`
  (ADR-GOLD-DESIGN-HT).
- **CA two-stage ratio** (`psu_ratio`): `p = sum(N_h num_h) / sum(N_h den_h)`. The linearised variance
  is `(1 - f) n s_t^2 / D^2`, where `f = n/M`, `t_h = N_h (num_h - p den_h)`, `D = sum(N_h den_h)`, and
  `s_t^2` is the sample variance of t over the n drawn strata. Hand check: M=4, n=2 gives 0.0703125.
  The reported interval is a cluster bootstrap percentile (see below); the linearised normal interval
  is also reported.
- **Stratified ratio** (`stratified_ratio`, global block): `p = sum(N_h mean num) / sum(N_h mean den)`,
  `Var = sum_h N_h^2 (1 - n_h/N_h) s_h^2 / n_h / D^2` over residuals `num - p den`. Hand check:
  strata (100, [1,1,0,1]) and (300, [0,0,1,0,0,0]) give p = 0.3125 and Var = 3050/160000.
  A stratum with one draw and a non-zero sampling fraction gives `unestimable_variance`.
- **Kish design effect**: `deff = n sum(w^2) / (sum w)^2`; effective n = n / deff.
  **Design effect against SRS**: `var_design / (p(1-p)/n)`.
- **Cluster bootstrap** over author groups: B = 1000 resamples of clusters with replacement, drawn by
  `random.Random(20261125)` with clusters ordered by key; percentile interval with linear
  interpolation at alpha/2 and 1 - alpha/2.
- **Cohen kappa** (binary): `(po - pe) / (1 - pe)`, where pe = pg pp + (1-pg)(1-pp).

## Flags

- `insufficient_data`: n below `--min-n` (30) for breakdowns and headline estimands; below 15
  positives for E4 per-tag and per-study_type results.
- `below_target_40`: E4 per-study_type value with fewer than 40 positives (A3 target).
- `experimental_kappa`: E4 per-study_type kappa < 0.70 (or undefined).
- `experimental_f1`: E4 per-tag or per-study_type F1 < 0.70.
- `unestimable_variance`: a global stratum has one draw, so the stratified variance is undefined.
- `zero_variance`: the global variance is zero, so the normal interval is degenerate.

## Status values

Real-path estimands carry one of: `ok`; `no_gold_yet` (no complete labels for the block that
estimand needs); `missing_predictions` (labels exist but no `--predictions` CSV, or some labelled
rows lack a prediction); `incomplete_gold` (CA labelled < 500 designed works, or global labelled <
drawn works, so a design estimate is premature). A run with no labels anywhere writes
`{"status": "no_gold_yet"}` for every estimand.

## Inputs and limits

- Gold labels: `curation/annotations/annotations_SC.csv` (CA) and `annotations_global_SC.csv`, rows
  with `decision_status = complete` only. The design comes from `curation/gold_design_v1.json`
  (weights and strata) and the global draws from `curation/gold_global_draws_v1.csv`.
- Predictions are not read from `data/`. They must be supplied as a CSV keyed by `work_id`
  (`pred_plastic_related`, `pred_plastic_tier`, `pred_analytic_lens`, `pred_domain_tags`,
  `pred_study_type`, `pred_band`, plus `label_source`, `theme_group`, `language`). No such export
  exists yet; the lead must decide how it is produced.
- Leak-test rows carry no design weight and are excluded from weighted estimands. They enter E3 only
  when they are in the `test` split.
- E3 accepts held-out `test` rows only and raises `ValueError` on train or dev rows.
- The global block uses adaptive Neyman allocation. A simulation on the earlier 32-stratum frame
  gave -1.18% relative bias (ADR-GOLD-GLOBAL-SAMPLER-2026-11-25). The 16-stratum redesign is not
  re-simulated here; the note is attached to every global estimate and breakdown.
- Breakdowns use Wilson intervals on Kish effective n. They are descriptive and not design-based.
- Synthetic output (`--synthetic`) is seeded test data and is never a corpus estimate.
