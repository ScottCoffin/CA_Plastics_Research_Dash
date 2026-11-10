"""Write the SPK-2 Parquet fixture with one DuckDB writer version.

Run through uv so the writer version is pinned per invocation, e.g.:
    uv run --no-project --with duckdb==1.1.1 python write_fixture.py --out DIR

Writes three files into DIR (zstd default row groups, zstd with 10000-row
row groups, snappy control) plus expected.json holding the values the browser
checks must reproduce. Expected values come from the writer's own in-memory
table, so they describe what the writer intended to store.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from datetime import UTC, datetime, timedelta

import duckdb

N_ROWS = 30_000
SEED = 20261109
VOCAB = ["ecotox", "policy", "health", "fate", "monitoring", "recycling", "biodegradation"]
TITLES = [
    "Río Grande microplásticos",
    "Ensayo de 5 µm en agua",
    "Estudio de PET",
    "Caracterización de fibras",
]
OPTIONS = {
    "zstd_default": "(FORMAT PARQUET, COMPRESSION zstd)",
    "zstd_rg10k": "(FORMAT PARQUET, COMPRESSION zstd, ROW_GROUP_SIZE 10000)",
    "snappy": "(FORMAT PARQUET, COMPRESSION snappy)",
}


def make_rows() -> list[tuple]:
    rng = random.Random(SEED)
    rows = []
    epoch = datetime(2000, 1, 1)
    for i in range(N_ROWS):
        published = epoch + timedelta(
            seconds=rng.randrange(0, 26 * 365 * 86400),
            microseconds=rng.randrange(1_000_000),
        )
        updated = (
            published
            + timedelta(seconds=rng.randrange(0, 10_000_000), microseconds=rng.randrange(1_000_000))
        ).replace(tzinfo=UTC)
        r = rng.random()
        if r < 0.05:
            tags = None
        elif r < 0.15:
            tags = []
        else:
            tags = rng.sample(VOCAB, rng.randint(1, 4))
        inst_ids = (
            None if rng.random() < 0.03 else [rng.randint(1, 500) for _ in range(rng.randint(0, 3))]
        )
        score = None if rng.random() < 0.01 else rng.random() * 100
        ca_led = None if rng.random() < 0.1 else rng.random() < 0.4
        title = f"{TITLES[i % len(TITLES)]} {i}"
        rows.append(
            (
                f"W{i:06d}",
                2000 + rng.randrange(27),
                published,
                updated,
                tags,
                inst_ids,
                score,
                ca_led,
                title,
            )
        )
    return rows


def expected_values(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    con.execute("SET TimeZone='UTC'")
    queries = {
        "count": "SELECT CAST(COUNT(*) AS VARCHAR) FROM fx",
        "sum_year": "SELECT CAST(SUM(year) AS VARCHAR) FROM fx",
        "ecotox_contains": (
            "SELECT CAST(COUNT(*) FILTER (WHERE list_contains(tags, 'ecotox')) AS VARCHAR) FROM fx"
        ),
        "unnest_tags": "SELECT CAST(COUNT(*) AS VARCHAR) FROM (SELECT UNNEST(tags) AS t FROM fx)",
        "max_published": "SELECT CAST(MAX(published) AS VARCHAR) FROM fx",
        "max_updated": "SELECT CAST(MAX(updated) AS VARCHAR) FROM fx",
        "null_ca_led": "SELECT CAST(COUNT(*) FILTER (WHERE ca_led IS NULL) AS VARCHAR) FROM fx",
        "true_ca_led": "SELECT CAST(COUNT(*) FILTER (WHERE ca_led) AS VARCHAR) FROM fx",
        "rio_title_count": (
            "SELECT CAST(COUNT(*) FILTER (WHERE title LIKE '%Río%') AS VARCHAR) FROM fx"
        ),
        "um_title_count": (
            "SELECT CAST(COUNT(*) FILTER (WHERE title LIKE '%µm%') AS VARCHAR) FROM fx"
        ),
        "title_W000000": "SELECT title FROM fx WHERE work_id = 'W000000'",
        "title_W000001": "SELECT title FROM fx WHERE work_id = 'W000001'",
        "tags_W000003": "SELECT CAST(tags AS VARCHAR) FROM fx WHERE work_id = 'W000003'",
        "inst_ids_W000003": "SELECT CAST(inst_ids AS VARCHAR) FROM fx WHERE work_id = 'W000003'",
    }
    out = {}
    for name, sql in queries.items():
        out[name] = con.execute(sql).fetchone()[0]
    out["select_star_limit5_rows"] = "5"
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output directory (created if missing)")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    con = duckdb.connect()
    con.execute(
        "CREATE TABLE fx (work_id VARCHAR, year SMALLINT, published TIMESTAMP, "
        "updated TIMESTAMPTZ, tags VARCHAR[], inst_ids INTEGER[], score DOUBLE, "
        "ca_led BOOLEAN, title VARCHAR)"
    )
    con.executemany("INSERT INTO fx VALUES (?,?,?,?,?,?,?,?,?)", make_rows())

    sizes = {}
    for opt, clause in OPTIONS.items():
        path = os.path.join(args.out, f"{opt}.parquet").replace("\\", "/")
        con.execute(f"COPY fx TO '{path}' {clause}")
        sizes[opt] = os.path.getsize(path)

    expected = expected_values(con)
    meta = {
        "duckdb_version": duckdb.__version__,
        "n_rows": N_ROWS,
        "seed": SEED,
        "file_sizes_bytes": sizes,
        "expected": expected,
    }
    with open(os.path.join(args.out, "expected.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print(json.dumps({"duckdb_version": duckdb.__version__, "file_sizes_bytes": sizes}))


if __name__ == "__main__":
    main()
