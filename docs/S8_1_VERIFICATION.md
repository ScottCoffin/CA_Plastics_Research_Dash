# S8.1 verification: grant schema and normalization

Date: 2026-11-09. Acceptance: "C3 schema tests" (`.agent/TODO.md`).

- `atlas.ingest.grants.schema`: `GRANT_COLUMNS` in exact C3 order, a pyarrow
  schema, and frozen `grant_key` (the first 16 hex characters of SHA-256 over
  `source\x1fsource_award_id`; pinned golden value `80a2a46282e95427`).
- `atlas.ingest.grants.normalize`: field normalization (dates, amounts, ISO
  currency, 2-letter `org_state`, `ca_led` from `org_state`, nullable unknowns
  never coerced to False), validation (required fields, duplicate keys, types)
  and deterministic atomic Parquet writing.
- Plastic relevance and domain tags are provisional S2.3 rules
  (`classify_plastic_text`, `_taxonomy_tags`). Replace them with the shared S5.1
  classifier when it exists. `ca_sampling_flag` stays null until S5. Cross-source
  de-duplication is S8.6. See [GRANTS_SCHEMA.md](GRANTS_SCHEMA.md).
- Evidence: `py -3.14 scripts/check_s8_1.py`; `tests/test_grants_s8_1.py` (64 tests,
  8 synthetic records); full gate passed (471 passed, 9 skipped).
