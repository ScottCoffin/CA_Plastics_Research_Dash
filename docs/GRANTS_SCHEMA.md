# Grant table schema (S8.1)

`src/atlas/ingest/grants/` defines the `grants` table from spec C3: one row per
funded award, with source-agnostic fields. The schema lives in
`schema.py` (`GRANT_COLUMNS`, `GRANT_SCHEMA`, `grant_key`). `normalize.py`
maps raw records onto it (`normalize_grant`), checks rows
(`validate_grants`), and writes Parquet (`write_grants_parquet`).

The column order is the C3 field order. Parquet output always uses
`GRANT_SCHEMA` in that order, and rows are written sorted by `grant_key`.

## Fields

Nullable columns use `null` for unknown. Lists use `[]` when the source does
not report a value. Unknown is never coerced to `false`.

| Column | Type | Null | Meaning and source notes |
|---|---|---|---|
| `grant_key` | string | no | Stable key, see the grant key rule below. |
| `source` | string | no | Name of the source feed that reported the award (for example, a funder or aggregator). |
| `source_award_id` | string | no | The source's own award identifier, stripped of surrounding whitespace. |
| `title` | string | no | Award title, stripped. |
| `abstract` | string | yes | Award abstract when the source provides one. Used for classification. |
| `pi_names` | list of string | yes (`[]`) | Principal investigator names, in source order, blanks dropped. |
| `org` | string | yes | Recipient organisation as reported by the source. |
| `org_ror` | string | yes | ROR identifier, without the `https://ror.org/` prefix. |
| `org_state` | string | yes | Two-letter US state code, upper case. Input is validated, so a full state name is rejected. |
| `start` | date32 | yes | Award start date. Accepts `yyyy-mm-dd`, `yyyy-mm` (first day of month), or `yyyy` (January 1). |
| `end` | date32 | yes | Award end date, same accepted forms as `start`. |
| `amount` | float64 | yes | Award amount in `currency`. Strips `$` and `,`. Negative, non-finite, or non-numeric values are rejected. |
| `currency` | string | yes | ISO-4217 code, upper case. Not defaulted; a missing currency stays null even when `amount` is set. |
| `funder` | string | yes | Funder named by the record. |
| `program` | string | yes | Program or mechanism name. |
| `funder_chain` | list of string | yes (`[]`) | Ordered funder path from the original funder to the reporting source, for example `["Synthetic Pass-Through Agency", "Synthetic State Sea Grant"]`. Required for pass-through awards. |
| `url` | string | yes | Source landing page for the award. |
| `plastic_related` | bool | yes | Provisional plastic relevance: title rule, abstract-only mentions default to `false`, reviewed overrides win (see the relevance rule below). |
| `domain_tags` | list of string | yes (`[]`) | Provisional taxonomy domain tags over title and abstract, from `config/taxonomy.yml`. |
| `ca_led` | bool | yes | `true` when `org_state` is `CA`, `false` when it is another known state, and `null` when `org_state` is unknown. |
| `ca_sampling_flag` | bool | yes | Reserved for the S5 sampling-location check. Always `null` from this module. |

## grant_key rule

`grant_key` is the first 16 lowercase hex characters of the SHA-256 digest of
`f"{source}\x1f{source_award_id}"`, after stripping both parts. `\x1f` is the
ASCII unit separator. Matching is case-sensitive.

Both parts are required. A blank part raises `ValueError`.

**This rule is frozen.** Do not change the separator, the hash, the
truncation, or the stripping. Changing it would change the key of every existing
grant and orphan exported rows. If the rule must change, create a new key
version and record it in an ADR. A golden value is pinned in
`tests/test_grants_s8_1.py`: `grant_key("SYNTH_FUNDER_A", "SYNTH-0001")` is
`80a2a46282e95427`.

The key identifies one award as reported by one source. It does not merge the
same award reported by several sources. Cross-source de-duplication of
pass-through awards is S8.6 and is not part of this schema.

## Validation

`validate_grants` reports every problem in one error. It checks:

- all 21 columns are present and no extra columns exist;
- `source`, `source_award_id`, `title`, and `grant_key` are non-blank;
- `grant_key` equals the derived key for `source` and `source_award_id`;
- `grant_key` values are unique;
- each column has the declared type, and `currency` and `org_state` match their code formats;
- the rows convert to `GRANT_SCHEMA` in pyarrow.

## Caveats

**Plastic relevance rule.** `grant_plastic_decision` in `normalize.py` returns
`(plastic_related, basis)`. A reviewed decision in `curation/grant_relevance.csv`
(keyed by `grant_key`, columns `plastic_related,assist_plastic_related,confidence,
reason,reviewer,reviewed_at,owner_review`) wins (basis `reviewed`).
`assist_plastic_related` keeps the Claude Haiku call permanently; the owner reviews
with `py -3.14 -m streamlit run scripts/review_grant_relevance_app.py`, which sets
`owner_review` to `confirmed`, `changed` or `unsure` (unsure keeps the Haiku call). Otherwise a core term in the
title (at most 250 characters) gives `true` (basis `title`). A core term that
appears only in the abstract gives `false` (basis `abstract_mention_only`), and
no match gives `false` (basis `none`). The export
(`atlas.build.grants_export`, run by `scripts/build_grants_export.py`) recomputes
`plastic_related` from `config/queries.yml` and the curation file, so the public
flag changes without re-ingest. The curation loader is `load_grant_relevance` in
`atlas.build.curation`; a missing file means no reviewed decisions.

**Provisional labels.** `plastic_related` and `domain_tags` apply the S2.3
rule-based labels to the grant title and abstract. They are provisional until
the shared S5.1 classifier exists. The candidate query in `config/queries.yml`
is still unpromoted and is not treated as approved by this module. Expect
labels to change when S5.1 lands.

**Amounts.** `amount` is the value the source reports, and its meaning differs
by source. Some sources report total award value, some report the current
fiscal-year or obligated amount, and some report a commitment across years.
Do not sum amounts across sources without checking the source notes. Per-source
amount caveats are planned for S8.10; until then, treat them as unverified.

**Pass-through awards.** A federal or state award may appear in more than one
source feed with different `source` values. Each appearance gets its own row
until the S8.6 de-duplication pass runs. Use `funder_chain` to see the path.

**Unknown geography.** `ca_led` depends on `org_state`. Records without a
state are unknown, not non-California.
