"""DuckDB institution analytics built from the normalized tables.

Every count shown to users is computed by DuckDB SQL. The bootstrap stability step uses numpy
only on the work-institution weights that DuckDB computed; its point values are read back from
DuckDB.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

UNAFFILIATED = "unaffiliated"
ALL_TAG = "_all"
TABLE_NAMES = (
    "work_inst_weights",
    "inst_counts",
    "inst_stability",
    "year_tag",
    "tag_cooccurrence",
    "topic_cooccurrence",
    "inst_cooccurrence",
)
# Tables written to output_dir. work_inst_weights is the audit trail for every fractional count.
OUTPUT_TABLES = TABLE_NAMES


@dataclass(frozen=True)
class AnalyticsResult:
    output_dir: Path
    manifest: dict[str, Any]
    row_counts: dict[str, int] = field(default_factory=dict)


def _lit(value: str | Path) -> str:
    """Return a single-quoted SQL string literal."""
    text = value.as_posix() if isinstance(value, Path) else str(value)
    return "'" + text.replace("'", "''") + "'"


def _as_bool_or_none(value: Any) -> bool | None:
    if value is True:
        return True
    if value is False:
        return False
    return None


def _register_scope(con: duckdb.DuckDBPyConnection, scope_path: Path | None) -> None:
    """Create table `scope` (work_id, plastic_related, domain_tags).

    Without a scope file every work is in scope, has no plastic flag and has no domain tags.
    """
    if scope_path is None:
        con.execute(
            """CREATE TABLE scope AS
               SELECT work_id, CAST(NULL AS BOOLEAN) AS plastic_related,
                      CAST([] AS VARCHAR[]) AS domain_tags
               FROM works_all"""
        )
        return
    payload = json.loads(Path(scope_path).read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in payload.get("works", []):
        work_id = entry["work_id"]
        if work_id in seen:
            raise ValueError(f"duplicate work_id in scope file: {work_id}")
        seen.add(work_id)
        rows.append(
            {
                "work_id": work_id,
                "plastic_related": _as_bool_or_none(entry.get("plastic_related")),
                "domain_tags": [str(t) for t in (entry.get("domain_tags") or []) if t],
            }
        )
    schema = pa.schema(
        [
            ("work_id", pa.string()),
            ("plastic_related", pa.bool_()),
            ("domain_tags", pa.list_(pa.string())),
        ]
    )
    con.register("scope_src", pa.Table.from_pylist(rows, schema=schema))
    con.execute("CREATE TABLE scope AS SELECT * FROM scope_src")
    con.unregister("scope_src")


def _scope_and_exclusions(
    con: duckdb.DuckDBPyConnection,
    works_path: Path,
    scope_path: Path | None,
    plastic_only: bool,
) -> dict[str, Any]:
    """Create works_all, scope, in_scope_works and work_index; return exclusion counts."""
    columns = pq.read_schema(works_path).names
    retracted = "coalesce(is_retracted, false)" if "is_retracted" in columns else "false"
    con.execute(
        f"""CREATE TABLE works_all AS
            SELECT work_id, year, {retracted} AS is_retracted, openalex_topics
            FROM read_parquet({_lit(works_path)})"""
    )
    _register_scope(con, scope_path)
    # The plastic filter needs the scope file, because plastic_related only lives there.
    apply_plastic = bool(plastic_only and scope_path is not None)
    flag = "true" if apply_plastic else "false"
    counts = con.execute(
        f"""SELECT
              count(*) FILTER (WHERE w.is_retracted) AS excluded_retracted,
              count(*) FILTER (WHERE NOT w.is_retracted AND s.work_id IS NULL)
                AS excluded_not_in_scope,
              count(*) FILTER (WHERE NOT w.is_retracted AND s.work_id IS NOT NULL
                AND {flag} AND s.plastic_related IS NOT TRUE) AS excluded_not_plastic,
              count(*) AS total_works_in_table
            FROM works_all w LEFT JOIN scope s ON s.work_id = w.work_id"""
    ).fetchone()
    scope_missing = con.execute(
        "SELECT count(*) FROM scope WHERE work_id NOT IN (SELECT work_id FROM works_all)"
    ).fetchone()[0]
    con.execute(
        f"""CREATE TABLE in_scope_works AS
            SELECT w.work_id, w.year, w.openalex_topics, s.domain_tags
            FROM works_all w JOIN scope s ON s.work_id = w.work_id
            WHERE NOT w.is_retracted AND ({flag} = false OR s.plastic_related IS TRUE)"""
    )
    con.execute(
        """CREATE TABLE works_scoped AS
           SELECT work_id, year, openalex_topics, domain_tags,
                  row_number() OVER (ORDER BY work_id) - 1 AS work_idx
           FROM in_scope_works"""
    )
    n_works = con.execute("SELECT count(*) FROM works_scoped").fetchone()[0]
    return {
        "apply_plastic_filter": apply_plastic,
        "total_works_in_table": int(counts[3]),
        "excluded_retracted": int(counts[0]),
        "excluded_not_in_scope": int(counts[1]),
        "excluded_not_plastic_related": int(counts[2]),
        "n_works": int(n_works),
        "scope_ids_missing_from_works": int(scope_missing),
    }


def _build_authorships(con: duckdb.DuckDBPyConnection, authorships_path: Path) -> None:
    """Create authorships_slim (work_id, author_key, inst_id) for in-scope works only."""
    con.execute(
        f"""CREATE TABLE authorships_raw AS
            SELECT a.work_id, a.author_id, a.institution_ids, a.file_row_number
            FROM read_parquet({_lit(authorships_path)}, file_row_number = true) a
            JOIN works_scoped w ON w.work_id = a.work_id"""
    )
    con.execute(
        f"""CREATE TABLE authorships_slim AS
            SELECT DISTINCT work_id, author_key, inst_id FROM (
              SELECT work_id,
                     CASE WHEN coalesce(author_id, '') = ''
                          THEN 'anon:' || work_id || ':' || file_row_number
                          ELSE author_id END AS author_key,
                     CASE WHEN inst IS NULL OR inst = '' THEN '{UNAFFILIATED}'
                          ELSE inst END AS inst_id
              FROM (
                SELECT *, unnest(
                  CASE WHEN coalesce(len(institution_ids), 0) = 0
                       THEN list_value(CAST(NULL AS VARCHAR))
                       ELSE institution_ids END) AS inst
                FROM authorships_raw
              )
            )
            UNION
            SELECT w.work_id, 'anon:' || w.work_id || ':none', '{UNAFFILIATED}'
            FROM works_scoped w
            WHERE w.work_id NOT IN (SELECT work_id FROM authorships_raw)"""
    )


def _build_weights(con: duckdb.DuckDBPyConnection) -> None:
    """Create work_inst_weights with the spec SQL, keyed on author_key."""
    con.execute(
        """CREATE TABLE work_inst_weights AS
           WITH a AS (SELECT work_id, author_key, count(DISTINCT inst_id) AS k
                      FROM authorships_slim GROUP BY 1, 2),
                n AS (SELECT work_id, count(DISTINCT author_key) AS n
                      FROM authorships_slim GROUP BY 1)
           SELECT s.work_id, s.inst_id, sum((1.0 / n.n) * (1.0 / a.k)) AS w
           FROM authorships_slim s
           JOIN a USING (work_id, author_key)
           JOIN n USING (work_id)
           GROUP BY 1, 2"""
    )
    bad = con.execute(
        """SELECT work_id, sum(w) AS total FROM work_inst_weights
           GROUP BY 1 HAVING abs(sum(w) - 1.0) > 1e-9 LIMIT 5"""
    ).fetchall()
    if bad:
        raise ValueError(f"work weights do not sum to 1: {bad}")


def _register_institutions(con: duckdb.DuckDBPyConnection, institutions_path: Path) -> None:
    con.execute(
        f"""CREATE TABLE institutions AS
            SELECT inst_id, name, atlas_type, parent_system, coalesce(ca_flag, false) AS ca_flag
            FROM read_parquet({_lit(institutions_path)})"""
    )


def _build_inst_counts(con: duckdb.DuckDBPyConnection) -> None:
    """Create inst_counts; ranks cover CA institutions only.

    Fractional ranks are computed on ROUND(works_frac, 9) so that float summation order cannot
    split institutions that tie in exact arithmetic.
    """
    con.execute(
        f"""CREATE TABLE inst_counts AS
            WITH agg AS (
              SELECT inst_id, count(DISTINCT work_id) AS works_full, sum(w) AS works_frac
              FROM work_inst_weights GROUP BY 1
            ),
            joined AS (
              SELECT g.inst_id,
                     coalesce(i.name, CASE WHEN g.inst_id = '{UNAFFILIATED}'
                                           THEN 'Unaffiliated' END) AS name,
                     i.atlas_type, i.parent_system,
                     (g.inst_id <> '{UNAFFILIATED}' AND coalesce(i.ca_flag, false)) AS ca_flag,
                     g.works_full, g.works_frac
              FROM agg g LEFT JOIN institutions i ON i.inst_id = g.inst_id
            ),
            ranked AS (
              SELECT *,
                     RANK() OVER (PARTITION BY ca_flag ORDER BY works_full DESC) AS r_full,
                     RANK() OVER (PARTITION BY ca_flag
                                  ORDER BY round(works_frac, 9) DESC) AS r_frac
              FROM joined
            )
            SELECT inst_id, name, atlas_type, parent_system, ca_flag, works_full, works_frac,
                   CASE WHEN ca_flag THEN r_full END AS rank_full,
                   CASE WHEN ca_flag THEN r_frac END AS rank_frac
            FROM ranked
            ORDER BY ca_flag DESC, works_frac DESC, inst_id"""
    )
    con.execute(
        """CREATE TABLE ca_index AS
           SELECT inst_id, row_number() OVER (ORDER BY inst_id) - 1 AS ca_idx
           FROM inst_counts WHERE ca_flag"""
    )


def bootstrap_stability(
    *,
    point_frac: np.ndarray,
    point_rank: np.ndarray,
    work_idx: np.ndarray,
    ca_idx: np.ndarray,
    weight: np.ndarray,
    n_works: int,
    replicates: int,
    seed: int,
) -> dict[str, np.ndarray]:
    """Multinomial-over-works bootstrap of CA institution fractional counts and ranks.

    Arrays are indexed by ca_idx (0..K-1, ordered by inst_id). Returns the interval arrays for
    every CA institution plus a not_distinguishable flag, which compares each institution with
    its neighbours in point rank order.
    """
    k = int(point_frac.shape[0])
    if replicates < 1:
        raise ValueError("bootstrap replicates must be at least 1")
    if n_works < 1:
        raise ValueError("no in-scope works to bootstrap")
    empty = np.zeros(0, dtype=np.int64)
    if k == 0:
        return {
            "frac_lo": np.zeros(0),
            "frac_hi": np.zeros(0),
            "rank_lo": empty,
            "rank_hi": empty,
            "widened": np.zeros(0, dtype=bool),
            "not_distinguishable": np.zeros(0, dtype=bool),
            "order": empty,
        }
    rng = np.random.default_rng(seed)
    pvals = np.full(n_works, 1.0 / n_works)
    counts = np.zeros((replicates, k))
    ranks = np.zeros((replicates, k), dtype=np.int64)
    for b in range(replicates):
        c = rng.multinomial(n_works, pvals)
        counts[b] = np.bincount(ca_idx, weights=weight * c[work_idx], minlength=k)[:k]
        srt = np.sort(counts[b])
        # Competition ranking: 1 + number of institutions strictly greater.
        ranks[b] = 1 + k - np.searchsorted(srt, counts[b], side="right")
    frac_lo, frac_hi = np.percentile(counts, [2.5, 97.5], axis=0)
    rlo, rhi = np.percentile(ranks, [2.5, 97.5], axis=0)
    rank_lo = np.floor(rlo).astype(np.int64)
    rank_hi = np.ceil(rhi).astype(np.int64)
    # Clamp so the point estimate always lies inside its interval.
    new_frac_lo = np.minimum(frac_lo, point_frac)
    new_frac_hi = np.maximum(frac_hi, point_frac)
    new_rank_lo = np.minimum(rank_lo, point_rank)
    new_rank_hi = np.maximum(rank_hi, point_rank)
    widened = (
        (new_frac_lo != frac_lo)
        | (new_frac_hi != frac_hi)
        | (new_rank_lo != rank_lo)
        | (new_rank_hi != rank_hi)
    )
    order = np.lexsort((np.arange(k), point_rank))
    not_distinguishable = np.zeros(k, dtype=bool)
    for pos in range(k):
        i = order[pos]
        for q in (pos - 1, pos + 1):
            if 0 <= q < k:
                j = order[q]
                if new_rank_lo[i] <= new_rank_hi[j] and new_rank_lo[j] <= new_rank_hi[i]:
                    not_distinguishable[i] = True
    return {
        "frac_lo": new_frac_lo,
        "frac_hi": new_frac_hi,
        "rank_lo": new_rank_lo,
        "rank_hi": new_rank_hi,
        "widened": widened,
        "not_distinguishable": not_distinguishable,
        "order": order,
    }


_STABILITY_SCHEMA = pa.schema(
    [
        ("inst_id", pa.string()),
        ("works_frac", pa.float64()),
        ("frac_lo", pa.float64()),
        ("frac_hi", pa.float64()),
        ("rank_frac", pa.int64()),
        ("rank_lo", pa.int64()),
        ("rank_hi", pa.int64()),
        ("widened", pa.bool_()),
        ("not_distinguishable", pa.bool_()),
    ]
)


def _build_inst_stability(
    con: duckdb.DuckDBPyConnection, replicates: int, seed: int, top_n: int
) -> None:
    n_works = con.execute("SELECT count(*) FROM works_scoped").fetchone()[0]
    points = con.execute(
        """SELECT ci.inst_id, ic.works_frac, ic.rank_frac
           FROM ca_index ci JOIN inst_counts ic USING (inst_id)
           ORDER BY ci.ca_idx"""
    ).fetchall()
    inst_ids = [row[0] for row in points]
    point_frac = np.array([row[1] for row in points], dtype=np.float64)
    point_rank = np.array([row[2] for row in points], dtype=np.int64)
    weights = con.execute(
        """SELECT ws.work_idx, ci.ca_idx, wiw.w
           FROM work_inst_weights wiw
           JOIN works_scoped ws ON ws.work_id = wiw.work_id
           JOIN ca_index ci ON ci.inst_id = wiw.inst_id"""
    ).fetchnumpy()
    result = bootstrap_stability(
        point_frac=point_frac,
        point_rank=point_rank,
        work_idx=np.asarray(weights["work_idx"], dtype=np.int64),
        ca_idx=np.asarray(weights["ca_idx"], dtype=np.int64),
        weight=np.asarray(weights["w"], dtype=np.float64),
        n_works=int(n_works),
        replicates=replicates,
        seed=seed,
    )
    keep = result["order"][:top_n]
    table = pa.table(
        {
            "inst_id": pa.array([inst_ids[i] for i in keep], type=pa.string()),
            "works_frac": pa.array(point_frac[keep], type=pa.float64()),
            "frac_lo": pa.array(result["frac_lo"][keep], type=pa.float64()),
            "frac_hi": pa.array(result["frac_hi"][keep], type=pa.float64()),
            "rank_frac": pa.array(point_rank[keep], type=pa.int64()),
            "rank_lo": pa.array(result["rank_lo"][keep], type=pa.int64()),
            "rank_hi": pa.array(result["rank_hi"][keep], type=pa.int64()),
            "widened": pa.array(result["widened"][keep], type=pa.bool_()),
            "not_distinguishable": pa.array(result["not_distinguishable"][keep], type=pa.bool_()),
        },
        schema=_STABILITY_SCHEMA,
    )
    con.register("stab_src", table)
    con.execute("CREATE TABLE inst_stability AS SELECT * FROM stab_src ORDER BY rank_frac, inst_id")
    con.unregister("stab_src")


def _build_year_tag(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        f"""CREATE TABLE year_tag AS
            SELECT year, tag, count(DISTINCT work_id) AS works FROM (
              SELECT year, work_id, unnest(domain_tags) AS tag FROM works_scoped
              UNION ALL
              SELECT year, work_id, '{ALL_TAG}' AS tag FROM works_scoped
            ) WHERE tag IS NOT NULL AND tag <> ''
            GROUP BY 1, 2 ORDER BY 1, 2"""
    )


def _cooccurrence(
    con: duckdb.DuckDBPyConnection,
    table: str,
    column: str,
    out_a: str,
    out_b: str,
    min_works: int,
) -> None:
    """Create a pair table from a list column of works_scoped, keeping pairs with a < b."""
    con.execute(
        f"""CREATE TABLE {table} AS
            WITH items AS (
              SELECT DISTINCT work_id, item FROM (
                SELECT work_id, unnest({column}) AS item FROM works_scoped
              ) WHERE item IS NOT NULL AND item <> ''
            )
            SELECT a.item AS {out_a}, b.item AS {out_b}, count(*) AS works
            FROM items a JOIN items b ON a.work_id = b.work_id AND a.item < b.item
            GROUP BY 1, 2
            HAVING count(*) >= {int(min_works)}
            ORDER BY works DESC, 1, 2"""
    )


def _build_inst_cooccurrence(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """CREATE TABLE inst_cooccurrence AS
           WITH ca AS (
             SELECT DISTINCT wiw.work_id, wiw.inst_id
             FROM work_inst_weights wiw JOIN inst_counts ic USING (inst_id)
             WHERE ic.ca_flag
           )
           SELECT a.inst_id AS inst_a, b.inst_id AS inst_b, count(*) AS works
           FROM ca a JOIN ca b ON a.work_id = b.work_id AND a.inst_id < b.inst_id
           GROUP BY 1, 2 ORDER BY works DESC, 1, 2"""
    )


def _write_tables(con: duckdb.DuckDBPyConnection, staging: Path) -> dict[str, int]:
    rows: dict[str, int] = {}
    for name in OUTPUT_TABLES:
        target = (staging / f"{name}.parquet").as_posix()
        con.execute(
            f"COPY (SELECT * FROM {name}) TO {_lit(target)} (FORMAT PARQUET, COMPRESSION zstd)"
        )
        rows[name] = int(con.execute(f"SELECT count(*) FROM {name}").fetchone()[0])
    return rows


def _swap_into_place(staging: Path, final: Path) -> None:
    """Move a fully written staging directory into place, keeping the old one until success."""
    final.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if final.exists():
        backup = final.with_name(f"{final.name}.old-{uuid.uuid4().hex[:8]}")
        final.rename(backup)
    try:
        staging.rename(final)
    except BaseException:
        if backup is not None:
            backup.rename(final)
        raise
    if backup is not None:
        shutil.rmtree(backup, ignore_errors=True)


def build_analytics(
    *,
    works_path: Path | str,
    authorships_path: Path | str,
    institutions_path: Path | str,
    scope_path: Path | str | None = None,
    output_dir: Path | str,
    plastic_only: bool = True,
    bootstrap_replicates: int = 1000,
    top_n: int = 200,
    seed: int = 20261111,
    topic_min_pair: int = 2,
    generated_at: str | None = None,
) -> AnalyticsResult:
    """Build the institution analytics tables and write them to output_dir atomically."""
    started = time.perf_counter()
    works_path = Path(works_path)
    authorships_path = Path(authorships_path)
    institutions_path = Path(institutions_path)
    scope_file = Path(scope_path) if scope_path is not None else None
    output_dir = Path(output_dir)

    con = duckdb.connect(":memory:")
    # Parallel float SUM() adds in a run-dependent order, which changes the last bit of
    # works_frac between builds. One thread keeps the output byte-reproducible for a seed.
    con.execute("SET threads = 1")
    staging = output_dir.with_name(f"{output_dir.name}.tmp-{uuid.uuid4().hex[:8]}")
    try:
        exclusions = _scope_and_exclusions(con, works_path, scope_file, plastic_only)
        _build_authorships(con, authorships_path)
        _build_weights(con)
        _register_institutions(con, institutions_path)
        _build_inst_counts(con)
        _build_inst_stability(con, bootstrap_replicates, seed, top_n)
        _build_year_tag(con)
        _cooccurrence(con, "tag_cooccurrence", "domain_tags", "tag_a", "tag_b", 1)
        _cooccurrence(
            con, "topic_cooccurrence", "openalex_topics", "topic_a", "topic_b", topic_min_pair
        )
        _build_inst_cooccurrence(con)

        staging.mkdir(parents=True, exist_ok=False)
        row_counts = _write_tables(con, staging)
        manifest = {
            "generated_at": generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
            "duckdb_version": duckdb.__version__,
            "inputs": {
                "works": works_path.as_posix(),
                "authorships": authorships_path.as_posix(),
                "institutions": institutions_path.as_posix(),
                "scope": scope_file.as_posix() if scope_file else None,
            },
            "plastic_only": plastic_only,
            "plastic_filter_applied": exclusions["apply_plastic_filter"],
            "exclusions": {
                "total_works_in_table": exclusions["total_works_in_table"],
                "retracted": exclusions["excluded_retracted"],
                "not_in_scope": exclusions["excluded_not_in_scope"],
                "not_plastic_related": exclusions["excluded_not_plastic_related"],
            },
            "scope_ids_missing_from_works": exclusions["scope_ids_missing_from_works"],
            "n_works": exclusions["n_works"],
            "bootstrap_replicates": bootstrap_replicates,
            "seed": seed,
            "top_n": top_n,
            "topic_min_pair": topic_min_pair,
            "parquet": {"compression": "zstd", "row_groups": "duckdb default"},
            "rows": row_counts,
            "runtime_s": round(time.perf_counter() - started, 3),
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _swap_into_place(staging, output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        con.close()
    return AnalyticsResult(output_dir=output_dir, manifest=manifest, row_counts=row_counts)


# ---------------------------------------------------------------------------------------------
# Fixture: a hand-checked 10-work corpus shared by the tests and scripts/check_at3.py.
# ---------------------------------------------------------------------------------------------

# (inst_id, name, atlas_type, parent_system, ca_flag)
FIXTURE_INSTITUTIONS = [
    ("I_A", "Institution A", "university", "UC", True),
    ("I_B", "Institution B", "university", "CSU", True),
    ("I_C", "Institution C", "agency", "State", True),
    ("I_X", "Out-of-state Institution", "university", None, False),
]

# (work_id, year, is_retracted, openalex_topics, plastic_related, domain_tags,
#  authorships as (author_id, [inst_ids]); author_id "" means an anonymous author)
FIXTURE_WORKS: list[tuple[Any, ...]] = [
    # W1 Leiden-style: 5 authors, two affiliated with A only -> A 0.4, unaffiliated 0.6.
    (
        "W1",
        2020,
        False,
        ["T1", "T2"],
        True,
        ["water"],
        [("a1", ["I_A"]), ("a2", ["I_A"]), ("a3", []), ("a4", []), ("a5", [])],
    ),
    # W2 multi-affiliated author: p has {A, B} -> 1/2 * 1/2 each; q has {B} -> 1/2.
    # A 0.25, B 0.75.
    (
        "W2",
        2019,
        False,
        ["T1", "T2", "T3"],
        True,
        ["water", "health"],
        [("b1", ["I_A", "I_B"]), ("b2", ["I_B"])],
    ),
    # W3 retracted: excluded everywhere (would have been A 1.0).
    ("W3", 2021, True, ["T1"], True, ["water"], [("c1", ["I_A"])]),
    # W4 plastic_related false: excluded under plastic_only, C 1.0 when included.
    ("W4", 2022, False, ["T1"], False, ["health"], [("d1", ["I_C"])]),
    # W5 no authorship rows at all -> unaffiliated 1.0.
    ("W5", 2021, False, ["T1"], True, ["health"], []),
    # W6 two anonymous authors (never merged) plus z1: B 1/3 + 1/3, C 1/3.
    (
        "W6",
        2021,
        False,
        ["T2", "T3"],
        True,
        ["water"],
        [("", ["I_B"]), ("", ["I_B"]), ("z1", ["I_C"])],
    ),
    # W7 non-CA institution counted but not ranked: X 0.5, A 0.5.
    ("W7", 2020, False, ["T1"], True, [], [("e1", ["I_X"]), ("e2", ["I_A"])]),
    # W8 three authors: A 1/3, B 2/3.
    (
        "W8",
        2022,
        False,
        ["T2"],
        True,
        ["health"],
        [("f1", ["I_A"]), ("f2", ["I_B"]), ("f3", ["I_B"])],
    ),
    # W9 two authors: C 0.5, A 0.5.
    (
        "W9",
        2023,
        False,
        ["T1", "T3"],
        True,
        ["water", "health"],
        [("g1", ["I_C"]), ("g2", ["I_A"])],
    ),
    # W10 four authors: p1 {B,C} -> 1/8 each; p2 {B} -> 1/4; p3 {C} -> 1/4; p4 none -> 1/4.
    # B 0.375, C 0.375, unaffiliated 0.25.
    (
        "W10",
        2024,
        False,
        ["T1", "T2"],
        True,
        ["health"],
        [("h1", ["I_B", "I_C"]), ("h2", ["I_B"]), ("h3", ["I_C"]), ("h4", [])],
    ),
]


def write_fixture(directory: Path, *, include_retracted: bool = True) -> dict[str, Path]:
    """Write the fixture as parquet and scope JSON into directory; return the paths."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    work_cols: dict[str, Any] = {
        "work_id": [],
        "year": [],
        "openalex_topics": [],
    }
    if include_retracted:
        work_cols["is_retracted"] = []
    scope_rows: list[dict[str, Any]] = []
    auth_rows: dict[str, list[Any]] = {
        "work_id": [],
        "author_id": [],
        "position": [],
        "institution_ids": [],
    }
    for work_id, year, retracted, topics, plastic, tags, authors in FIXTURE_WORKS:
        work_cols["work_id"].append(work_id)
        work_cols["year"].append(year)
        work_cols["openalex_topics"].append(topics)
        if include_retracted:
            work_cols["is_retracted"].append(retracted)
        scope_rows.append({"work_id": work_id, "plastic_related": plastic, "domain_tags": tags})
        for position, (author_id, insts) in enumerate(authors):
            auth_rows["work_id"].append(work_id)
            auth_rows["author_id"].append(author_id)
            auth_rows["position"].append("first" if position == 0 else "additional")
            auth_rows["institution_ids"].append(insts)
    works_path = directory / "works.parquet"
    pq.write_table(
        pa.table(
            {
                "work_id": pa.array(work_cols["work_id"], pa.string()),
                "year": pa.array(work_cols["year"], pa.int64()),
                **(
                    {"is_retracted": pa.array(work_cols["is_retracted"], pa.bool_())}
                    if include_retracted
                    else {}
                ),
                "openalex_topics": pa.array(work_cols["openalex_topics"], pa.list_(pa.string())),
            }
        ),
        works_path,
    )
    auth_path = directory / "authorships.parquet"
    pq.write_table(
        pa.table(
            {
                "work_id": pa.array(auth_rows["work_id"], pa.string()),
                "author_id": pa.array(auth_rows["author_id"], pa.string()),
                "position": pa.array(auth_rows["position"], pa.string()),
                "institution_ids": pa.array(auth_rows["institution_ids"], pa.list_(pa.string())),
            }
        ),
        auth_path,
    )
    inst_path = directory / "institutions.parquet"
    pq.write_table(
        pa.table(
            {
                "inst_id": pa.array([r[0] for r in FIXTURE_INSTITUTIONS], pa.string()),
                "name": pa.array([r[1] for r in FIXTURE_INSTITUTIONS], pa.string()),
                "atlas_type": pa.array([r[2] for r in FIXTURE_INSTITUTIONS], pa.string()),
                "parent_system": pa.array([r[3] for r in FIXTURE_INSTITUTIONS], pa.string()),
                "ca_flag": pa.array([r[4] for r in FIXTURE_INSTITUTIONS], pa.bool_()),
            }
        ),
        inst_path,
    )
    scope_path = directory / "scope.json"
    scope_path.write_text(json.dumps({"works": scope_rows}, indent=2), encoding="utf-8")
    return {
        "works": works_path,
        "authorships": auth_path,
        "institutions": inst_path,
        "scope": scope_path,
    }
