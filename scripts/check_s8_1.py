"""Machine acceptance checks for S8.1 grant schema and normalization."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pyarrow.parquet as pq
import yaml

from atlas.ingest.grants import (
    GRANT_COLUMNS,
    GRANT_SCHEMA,
    normalize_grant,
    validate_grants,
    write_grants_parquet,
)

FIXTURE = Path("tests/fixtures/s8_1_grants.json")
QUERIES = Path("config/queries.yml")
TAXONOMY = Path("config/taxonomy.yml")


def main() -> None:
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(records, list) and 0 < len(records) <= 20
    assert all(str(item["raw"]["source_award_id"]).startswith("SYNTH-") for item in records)
    query_config = yaml.safe_load(QUERIES.read_text(encoding="utf-8"))
    taxonomy = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    rows = [
        normalize_grant(
            item["raw"], source=item["source"], query_config=query_config, taxonomy=taxonomy
        )
        for item in records
    ]
    validate_grants(rows)
    with tempfile.TemporaryDirectory(prefix="s8-1-acceptance-") as directory:
        target = Path(directory) / "grants.parquet"
        write_grants_parquet(rows, target)
        table = pq.read_table(target)
        assert table.schema.equals(GRANT_SCHEMA)
        assert table.column_names == list(GRANT_COLUMNS)
        assert table.num_rows == len(rows)
    print("S8.1 check passed.")


if __name__ == "__main__":
    main()
