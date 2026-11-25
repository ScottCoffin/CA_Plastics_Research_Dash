# Global gold-sampling frame and frozen strata (BQ-G3)

Frame: `curation/gold_global_frame_v1.csv.gz` (gzip, mtime 0, deterministic; the plain CSV is not
committed). Manifest: `curation/gold_global_frame_v1.json`.
Builder: `scripts/build_gold_global_frame.py` (`--check` validates the committed frame; the rebuild
runs only when the ignored global inputs are present and unchanged). Rules and helpers:
`src/atlas/nlp/gold_frame.py`. Label-blind: the frame reads no gold labels, and no titles or
abstracts are committed.

## Rules

- **Universe.** Every work in `data/processed/global/works.parquet`, minus role=guide_example works
  (A3 section 4.3 item 8), matched by work_id or normalized DOI against `curation/a3_guide_examples.csv`.
  `scripts/check_s4_2.py` asserts the exclusion on the committed frame.
- **Block.** `registry_region` (the California registry region) when `work_regions.parquet` has a registry_region `california` row for the
  work; otherwise `global_english` if `language == "en"`; otherwise `global_non_english`. Missing
  language is counted in the manifest and falls to `global_non_english`.
- **Theme group (first match wins).**
  1. `lens-candidate`: any term of `themes.waste_colonialism_lens.terms` in `config/queries_v32_candidate.yml`
     in title or abstract (no anchor needed; A3 lens phrase).
  2. `lifecycle-and-society`: a plastic anchor (`anchor_phrases`, v3.2 candidate) AND either a
     `co_term` lifecycle row of `config/search_vocabulary_v1.yml` (title or abstract) or a
     `title_only` row (title only).
  3. `pollution-core`: any term of `config/pollution_core_v0.yml` `core_terms`.
  4. `other`: everything else (kept as its own group).
- **Rule score (proxy, `rules-v3.1-proxy`).** Points from `config/queries.yml`: 2 per core term hit in
  the title, 1 per core term hit in the abstract, 1 per qualified term with a context hit, and 1 per
  `tier_2_terms` hit. Any `exclusions` hit in title or abstract sets points to 0. Score =
  `min(1, points / 4)`, rounded to four decimals.
- **Bands.** `low` < 0.34, `medium` 0.34 to < 0.67, `high` >= 0.67.
- **Strata (16, ADR-GOLD-GLOBAL-SAMPLER-2026-11-25).** Ids are `block|theme|band`; `all` replaces the band
  where the band is not used.
  - `global_english`: theme (`pollution-core`, `lifecycle-and-society`, `other`) x band (`low`, `medium`,
    `high`) = 9, plus `global_english|lens-candidate|all` = 10.
  - `registry_region` and `global_non_english`: theme only (`pollution-core`, `lifecycle-and-society`,
    `other`), band `all`. Lens-candidate works here are merged into `lifecycle-and-society` in the
    frame's `theme_group` column, so there are 3 + 3 = 6 strata.
  - Zero-score works are in the `low` band and are drawable. N_h counts the full population.
  - Reason: A3 section 4.4 caps global labels at 200, and round 0 is 10 per stratum (160), which leaves
    40 for adaptive rounds. The earlier 36-cell scheme (32 non-empty strata) gave round 0 = 263.
- **Random keys.** One uniform key per work, drawn in sorted work_id order from
  `random.Random(42043)` (seed in the manifest), for later sampling.
- **Hashes.** `score_snapshot_sha256` is the sha256 of the sorted `work_id<TAB>score` lines over all
  works. `frame_sha256` is the sha256 of the committed `.csv.gz` bytes and `frame_uncompressed_sha256`
  is the sha256 of the uncompressed CSV. `--check` compares both and rebuilds byte for byte when the
  ignored inputs are present. The manifest also records the sha256 of each input (works, work regions,
  the page files combined, and every config file).
- **Frame rows.** Every work in the universe (minus guide examples) has a row, including zero-score works.
  The gzip file is about 3.5 MB; the uncompressed CSV is about 19 MB.
- **Evidence field.** The frame carries no labels, so no `ca_sampled` site text is recorded here.
  That rule applies to the labelling sheet, not to the frame.

## Strata table (N_h)

Generated from `curation/gold_global_frame_v1.json`.

| Stratum | N_h |
|---|---:|
| `global_english|pollution-core|low` | 10,945 |
| `global_english|pollution-core|medium` | 28,414 |
| `global_english|pollution-core|high` | 34,560 |
| `global_english|lifecycle-and-society|low` | 259 |
| `global_english|lifecycle-and-society|medium` | 139 |
| `global_english|lifecycle-and-society|high` | 229 |
| `global_english|other|low` | 41,179 |
| `global_english|other|medium` | 8,500 |
| `global_english|other|high` | 4,776 |
| `global_english|lens-candidate|all` | 28 |
| `registry_region|pollution-core|all` | 1,190 |
| `registry_region|lifecycle-and-society|all` | 11 |
| `registry_region|other|all` | 771 |
| `global_non_english|pollution-core|all` | 2,312 |
| `global_non_english|lifecycle-and-society|all` | 34 |
| `global_non_english|other|all` | 2,725 |
| **all** | **136,072** |

Population after guide-example exclusion: 136,072 works (136,074 in the universe, 2 guide examples excluded). Zero-score works (in the low band): {'registry_region': 305, 'global_english': 17639, 'global_non_english': 383}. Blocks: {'registry_region': 1972, 'global_english': 129029, 'global_non_english': 5071}. Gzip frame 3,469,705 bytes; uncompressed CSV 18,960,301 bytes.

## Proxy-score default and its limitation

No trained classifier exists, so the score is a transparent rule proxy, not a calibrated probability.
Its bands therefore describe rule evidence strength, not the probability that a work is plastic-related.
Any stratified design built on these bands must treat the score as a sampling covariate; it cannot be
used as a calibrated probability or as a substitute for labels. A future classifier replaces the score
only through a new frame version (`gold_global_frame_v2`) with a new model version and snapshot hash.

## Adaptive sampling (BQ-G4)

Code: `src/atlas/nlp/gold_sampler.py` (allocation, pure), `scripts/bq_gold_sampler.py` (CLI).
Ledger: `curation/gold_global_draws_v1.csv` (append-only). Labels: `curation/annotations/annotations_global_SC.csv`
(the CA sheet columns plus `round` and `stratum`; ids and labels only, no titles or abstracts).

### Procedure

1. `py -3.14 scripts/bq_gold_sampler.py round0`. Draws `min(10, N_h)` works from every non-empty stratum,
   in the frame's `rand_key` order, and creates the labelling sheet. Round 0 is label-blind.
2. Label the drawn works in the app (see "Labelling session" below).
3. `py -3.14 scripts/bq_gold_sampler.py next-round` once every drawn work is either `complete` or
   `adjudication_required`. Refused while any draw has no decision. Adds one round of 25 draws.
4. `py -3.14 scripts/bq_gold_sampler.py status`. Prints counts only: draws, complete labels, adjudication
   holds, checkpoint reached, active goal and draws per stratum. It prints no estimate and no interval.

The script checks the frame's sha256 against its manifest before every run and refuses to draw on a
mismatch. It never rewrites a ledger row, and it refuses a second `round0`.

### Allocation

For each stratum h with `N_h` drawable works (frame rows), `n_h` draws so far and `x_h` positive labels
among the completed labels:

- Jeffreys-smoothed prevalence `p_h = (x_h + 0.5) / (n_h + 1)`.
- Neyman weight `w_h = N_h * sqrt(p_h * (1 - p_h))`. Before any label, `p_h = 0.5`.
- Floor: every stratum with undrawn works gets one draw per round while the round has room. When there
  are more such strata than draws (32 strata against 25 draws), the floor goes first to the strata with
  the fewest draws so far, then to the heavier weight. Every stratum is therefore reached within two rounds.
  The strata left out are named in the CLI message.
- The rest of the round is shared in proportion to `w_h`, capped at `N_h - n_h` (a stratum that runs out
  passes its share on), and rounded by largest remainder so the round sums to exactly 25.
- The last round is smaller so that the total never passes 350 draws.

Each ledger row records the round, stratum, work id, rank in the stratum (1 = first in `rand_key` order),
`n_h` after the round, `N_h`, `N_h_full` (manifest count, including zero-score works), the within-stratum
inclusion probability `n_h / N_h` at that round, the seed, the model version and the frame hash. `status`
recomputes the final inclusion probability for each stratum. The ledger keeps the value at the time of
each draw, because it is append-only.

### Checkpoints and early stopping

Checkpoints are at 100, 200, 300 and 350 completed global labels. `status` reports whether one is reached
and whether stopping is allowed (only at a checkpoint). No interval is computed or published before the
final analysis (A3 section 4.3 item 4). The precision estimator is BQ-1.1. Its stratified form uses
weights `N_h / n_h` per drawn work, so the total is `sum_h N_h * mean_h(y)`.

### Spend-down

`DEFAULT_GOALS` in `atlas.nlp.gold_sampler` lists the goals in order: P1 (registry_region block), P3
(low band, reading "auto-excluded works" as the low band; the lead must confirm), P4 (lifecycle-and-society),
P5 (non-English block), P6 (lens-candidate), then the reserve (every stratum). The active goal is the first
one not met. While it is active, its strata receive each round's budget before any other stratum (the floor
still applies to all). "Met" is an owner flag: `curation/gold_sampler_goals_v1.json` (optional, owner-written)
with `{"met": ["P1"]}`. BQ-1.1 will replace this flag with the precision test of A3 section 4.2.

### Labelling session

1. From the repository root: `py -3.14 -m streamlit run scripts/review_gold_labels_app.py -- --global`
2. The app shows one drawn work per screen with its title and abstract (read from the local files). The
   admitting terms are highlighted. The score and score band are not shown; a stratum appears only as a
   short code.
3. Pick a round in "Show (round)", or "Unlabelled (all rounds)". Answer the questions and click "Save and
   next". Each click saves that one row at once. "Needs adjudication" holds a work for the owner.
4. Stop at any time. Unlabelled works stay in the ledger and block `next-round` until they are decided.
5. Run `status` to see the counts and the checkpoint.

### Known limits (owner or lead decisions)

- Zero-score works (305 registry, 17,639 global English, 383 non-English) are in the frame and in the low
  band, so they are drawable. P3 reads the low band as including them (ADR-GOLD-GLOBAL-SAMPLER-2026-11-25).
- Adaptive allocation is not label-free. Making allocation depend on labels means the inclusion probabilities
  are not fixed in advance, which strictly conflicts with A3 section 4.3 item 7. Simulated on a synthetic frame
  (`tests/test_gold_sampler.py`), the stratified estimator is biased by about -1% with the adaptive rule (500
  runs, -2.6 SE), and unbiased within noise when the allocation ignores labels. The test bounds the bias at 2%.
- Round 0 draws 263 works (registry 70, global English 112, non-English 81). A3 section 4.4 caps the global
  adaptive block at 200. Round 0 alone exceeds that cap. The spec and the cap conflict; the owner decides.
