# Provisional work-label QC

Generated at (UTC): `runtime`
Source: `normalized=data/processed/normalized/works.parquet; raw=data/interim/works_raw.parquet`

This is an owner-supplied candidate rule layer, not a validated classifier. `label_source=rule`, `confidence` is nullable and uncalibrated, and the candidate remains unpromoted.

| Check | Count |
|---|---:|
| Normalized work rows | 2071 |
| Label rows | 2071 |
| Raw OpenAlex work rows | 2110 |
| Missing raw work rows | 0 |
| Normalized topic ID rows | 6210 |
| Matched raw topic-name rows | 6210 |
| Missing raw topic-name rows | 0 |
| Missing primary-topic names | 0 |
| Plastic-related rows | 1782 |
| Excluded rows | 0 |
| Rows with provisional domain tags | 1370 |
| Mis-attached (ignored) abstracts | 0 |
| Always-relevant rule rows | 2 |

Topic display names are joined from raw OpenAlex records by `work_id`; missing raw rows and missing topic entries are retained and counted.
