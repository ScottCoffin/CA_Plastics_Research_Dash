# Provisional work-label QC

Generated at (UTC): `runtime`
Source: `normalized=data/processed/normalized/works.parquet; raw=data/interim/works_raw.parquet`

This is an owner-supplied candidate rule layer, not a validated classifier. `label_source=rule`, `confidence` is nullable and uncalibrated, and the candidate remains unpromoted.

| Check | Count |
|---|---:|
| Normalized work rows | 194 |
| Label rows | 194 |
| Raw OpenAlex work rows | 194 |
| Missing raw work rows | 0 |
| Normalized topic ID rows | 582 |
| Matched raw topic-name rows | 582 |
| Missing raw topic-name rows | 0 |
| Missing primary-topic names | 0 |
| Plastic-related rows | 183 |
| Excluded rows | 0 |
| Rows with provisional domain tags | 128 |

Topic display names are joined from raw OpenAlex records by `work_id`; missing raw rows and missing topic entries are retained and counted.
