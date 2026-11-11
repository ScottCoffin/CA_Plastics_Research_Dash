# Provisional work-label QC

Generated at (UTC): `runtime`
Source: `normalized=data/processed/normalized/works.parquet; raw=data/interim/works_raw.parquet`

This is an owner-supplied candidate rule layer, not a validated classifier. `label_source=rule`, `confidence` is nullable and uncalibrated, and the candidate remains unpromoted.

| Check | Count |
|---|---:|
| Normalized work rows | 1486 |
| Label rows | 1486 |
| Raw OpenAlex work rows | 1506 |
| Missing raw work rows | 0 |
| Normalized topic ID rows | 4458 |
| Matched raw topic-name rows | 4458 |
| Missing raw topic-name rows | 0 |
| Missing primary-topic names | 0 |
| Plastic-related rows | 1244 |
| Excluded rows | 0 |
| Rows with provisional domain tags | 928 |

Topic display names are joined from raw OpenAlex records by `work_id`; missing raw rows and missing topic entries are retained and counted.
