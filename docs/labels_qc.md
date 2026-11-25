# Provisional work-label QC

Generated at (UTC): `runtime`
Source: `normalized=data/processed/normalized/works.parquet; raw=data/interim/works_raw.parquet`

This is an owner-supplied candidate rule layer, not a validated classifier. `label_source=rule`, `confidence` is nullable and uncalibrated, and the candidate remains unpromoted.

| Check | Count |
|---|---:|
| Normalized work rows | 2067 |
| Label rows | 2067 |
| Raw OpenAlex work rows | 2106 |
| Missing raw work rows | 0 |
| Normalized topic ID rows | 6198 |
| Matched raw topic-name rows | 6198 |
| Missing raw topic-name rows | 0 |
| Missing primary-topic names | 0 |
| Plastic-related rows | 1778 |
| Excluded rows | 0 |
| Rows with provisional domain tags | 1366 |
| Mis-attached (ignored) abstracts | 0 |
| Always-relevant rule rows | 2 |

Topic display names are joined from raw OpenAlex records by `work_id`; missing raw rows and missing topic entries are retained and counted.
