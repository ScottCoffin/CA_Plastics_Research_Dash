# Rising-share flag (BQ-4.2)

Flags a reported topic tag whose share of CA plastic-related works is rising. It reads the frozen
topic series (BQ-4.1, see `docs/TOPIC_SERIES.md`) and writes one gitignored file. Nothing is
published here: the topic evolution page (BQ-4.4) decides what the site shows.

    py -3.14 scripts/build_rising_share.py                    # write the output
    py -3.14 scripts/build_rising_share.py --check            # fail when missing or stale
    py -3.14 scripts/build_rising_share.py --as-of 2026-11-25 # pin the as-of date

Run `scripts/build_topic_series.py` first. This step reads only the frozen labels snapshot
(`data/processed/analytics/labels_snapshot_v1.parquet`), never the live labels. Code:
`src/atlas/analytics/rising_share.py`. Tests: `tests/test_rising_share.py` (synthetic inputs).
Output: `data/processed/analytics/rising_share.json`, schema `bq4-rising-v1`.

## Flag rule

A reported tag is flagged only when every check passes. Experimental tags are never flagged.

| Check | Pass condition |
|---|---|
| Trend | Two-sided p < 0.05 with a positive trend statistic, over all complete years |
| Volume | At least 10 works with the tag in the last 3 complete years (2023 to 2025 for as-of 2026) |
| Sensitivity | The trend test passes for every NON-EMPTY label-source variant |
| Leave-one-institution-out | The trend test passes after each single-institution drop |

Each failed check is listed in `reasons_failed` (`volume`, `trend`, `sensitivity:<variant>`,
`leave_one_institution_out`, `leave_one_institution_out_not_testable`).

### Trend test

Cochran-Armitage trend test on (count, denominator) by complete year, with scores equal to the
calendar year. Denominator is the plastic-related CA works that year, so the test asks whether the
share rises. `T = sum t_i (r_i - n_i p)`, `Var = p (1 - p) (sum n_i t_i^2 - (sum n_i t_i)^2 / N)`,
`p = R / N`, and `z = T / sqrt(Var)`. The two-sided p-value uses the normal approximation
`erfc(|z| / sqrt 2)`. scipy is not a dependency, so no other library is used. A test with no works,
no variation in the share, or equal scores is undefined and never passes.

Complete years run from the first plastic-related year in the corpus to the year before the as-of
date. Partial years are dropped from the trend and the window.

### Label-source sensitivity

Each variant from BQ-4.1 (`all_sources`, `owner_model_only`, `rule_only`) gets the same trend test
on its own counts. For a tag, a variant with no works in any complete year is reported as
`not_testable` and does not block the flag. A non-empty variant that fails blocks it.

Today `all_sources` and `rule_only` are identical and `owner_model_only` is empty (no owner tag
overrides, no model topic labels). So the robustness claim covers the rule source only. The
owner default in QUESTIONS (BQ42-SENSITIVITY) is followed: each non-empty variant is tested, and an
empty one is reported, never claimed as robust.

### Leave-one-institution-out

Institutions come from `data/processed/normalized/authorships.parquet` (`institution_ids`, one row
per authorship, compacted from OpenAlex URLs). For each institution with at least one tagged work in
the window, the works linked to that institution are dropped from both numerator and denominator,
and the all-sources trend test is rerun on the whole series. The record keeps the worst case: the
largest p-value over the reruns (a rerun with a non-positive trend counts as p = 1), with its
institution. The check passes only if every rerun passes. If no tagged window work has an
institution link, the check is `not_testable` and the tag is not flagged.

## Outputs

`rising_share.json` (`bq4-rising-v1`): `as_of`, `last_complete_year`, `window_years`, `alpha`,
`min_window_works`, `test`, `labels_snapshot` (with `content_sha256`), `inputs` (sha256 of
`config/taxonomy.yml` and the authorships file), `tags` (per tag: `flag`, `reasons_failed`,
`trend` {z, p, slope_sign}, `window_years`, `window_count`, `total_complete_years`, `sensitivity`,
`loio` {worst_p, worst_institution, pass, institutions_tested}), `flagged`, `tags_excluded`.

`--check` recomputes the payload from the current inputs and fails unless it matches the file, and
also fails when the last complete year has changed. It exits 0 with SKIP when an input is absent.

## Not done

- Kleinberg-style bursts are not implemented. They are optional in A3 and the trend test above
  already covers the rising-share question; add them only if CiteSpace continuity is required.
- No correction for multiple testing across tags. Treat `flagged` as a screen for review, not a
  confirmed finding.

## Limits

- Early years have small volume; the trend is dominated by the later years when they carry most
  works. Read flags for early-volume tags with care.
- Leave-one-institution-out drops works linked to any author from an institution, so a work with
  several institutions is dropped in each of those institutions' reruns. Works with no institution link cannot be
  dropped and stay in every rerun.
- Sensitivity variants are tested per tag. A variant that matches `all_sources` adds no independent
  evidence.
- The as-of date sets which years are complete; `--check` needs the same year as the output.
