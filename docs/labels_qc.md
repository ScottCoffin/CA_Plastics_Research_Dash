# Provisional work-label QC

Generated at (UTC): `runtime`
Source: `normalized=data/processed/normalized/works.parquet; raw=data/interim/works_raw.parquet`

This is an owner-supplied candidate rule layer, not a validated classifier. `label_source=rule`, `confidence` is nullable and uncalibrated, and the candidate remains unpromoted.

| Check | Count |
|---|---:|
| Normalized work rows | 2038 |
| Label rows | 2038 |
| Raw OpenAlex work rows | 2077 |
| Missing raw work rows | 0 |
| Normalized topic ID rows | 6111 |
| Matched raw topic-name rows | 6111 |
| Missing raw topic-name rows | 0 |
| Missing primary-topic names | 0 |
| Plastic-related rows | 1750 |
| Excluded rows | 0 |
| Rows with provisional domain tags | 1345 |
| Mis-attached (ignored) abstracts | 0 |
| Always-relevant rule rows | 2 |

Topic display names are joined from raw OpenAlex records by `work_id`; missing raw rows and missing topic entries are retained and counted.
