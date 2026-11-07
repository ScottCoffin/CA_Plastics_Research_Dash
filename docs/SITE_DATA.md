# Static site data contract (S3.1)

`scripts/build_export_site.py` converts the normalized C3 Parquet tables into
small, deterministic JSON payloads under `site/data/`.  The exporter is a
build step; the browser never needs PyArrow or Parquet support.

All payloads use `schema_version: "s3.1"`, compact UTF-8/ASCII JSON, stable ID
ordering, and UTC `generated_at` metadata.  The default build inputs are the
S2.2 normalized tables and the optional S2.3 `work_labels.parquet` output.
Missing labels are retained as `null` and are never inferred by the exporter.

## Files

| File | Contract |
|---|---|
| `index.json` | `counts`, slim `works`, and slim `authors` arrays. Work rows contain IDs, title/year/type, CA flags, citation count, author/institution IDs, and provisional label fields. Author rows contain IDs, display fields, year range, work IDs, and institution IDs. |
| `authors/<author_id>.json` | One detail document per author with the indexed author row and full work rows (abstract, DOI, journal, OA fields, topics, and label fields). |
| `institutions.json` | Institution rows with reviewed type/CA flag, coordinates, work and author counts, year coverage, and tags. |
| `institutions.geojson` | GeoJSON `FeatureCollection` of California institutions with non-null coordinates. Properties mirror the institution summary. |
| `aggregates.json` | `by_year`, `by_type`, and `by_tag` arrays. Each row has `count` and `plastic_related_count`; tag rows combine taxonomy domain and matrix facet IDs. |
| `build_metadata.json` | Build timestamp, row counts, per-file raw and gzip byte sizes, and total payload sizes. This is the S3.1 size log. |

The initial C5 target is an initial payload below 3 MB gzip.  A build that
exceeds the target must retain the recorded sizes here and document the reason
before introducing DuckDB-Wasm or another client-side query engine.

## Rebuild and check

```powershell
py -3.14 scripts/build_export_site.py
py -3.14 scripts/check_s3_1.py
```

The acceptance script uses the committed S2.2 fixture and checks deterministic
ordering, complete author-detail joins, aggregate counts, California map
features, and the payload budget without contacting OpenAlex.
