"""CI guards for the daily OpenAlex ingest.

Each check returns a :class:`GuardResult` whose ``problems`` list is empty when
the input is acceptable. The guards run before the daily data commit so that a
changed OpenAlex payload shape, a missing normalized column, or an oversized
site payload stops the commit instead of publishing broken data.
"""

from __future__ import annotations

import gzip
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from atlas.ingest.normalize import (
    AUTHORS_SCHEMA,
    AUTHORSHIPS_SCHEMA,
    INSTITUTIONS_SCHEMA,
    WORKS_SCHEMA,
)
from atlas.ingest.openalex import RAW_SCHEMA

# Keys the normalizer reads from each raw OpenAlex work (see normalize_records).
REQUIRED_WORK_KEYS: tuple[str, ...] = (
    "id",
    "title",
    "publication_year",
    "publication_date",
    "type",
    "authorships",
    "primary_location",
    "open_access",
    "is_retracted",
    "cited_by_count",
)
REQUIRED_AUTHORSHIP_KEYS: tuple[str, ...] = ("author", "institutions")
NORMALIZED_TABLES: dict[str, pa.Schema] = {
    "works.parquet": WORKS_SCHEMA,
    "authorships.parquet": AUTHORSHIPS_SCHEMA,
    "authors.parquet": AUTHORS_SCHEMA,
    "institutions.parquet": INSTITUTIONS_SCHEMA,
}
INITIAL_PAYLOAD_FILES: tuple[str, ...] = (
    "index.json",
    "institutions.json",
    "aggregates.json",
    "build_metadata.json",
)
INDEX_KEYS: tuple[str, ...] = ("works", "authors", "generated_at")
INDEX_WORK_KEYS: tuple[str, ...] = ("work_id", "title", "year")
DEFAULT_INITIAL_GZIP_LIMIT = 3_000_000
DEFAULT_FILE_LIMIT = 25_000_000


@dataclass(frozen=True)
class GuardResult:
    """Problems found by one guard plus the measured values used to decide."""

    problems: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems


def _gzip_size(data: bytes) -> int:
    return len(gzip.compress(data, compresslevel=9, mtime=0))


def _record_problems(raw: object) -> set[str]:
    """Return the missing or malformed keys in one raw OpenAlex work JSON string."""

    try:
        record = json.loads(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return {"<unparseable raw_json>"}
    if not isinstance(record, dict):
        return {"<raw_json is not an object>"}
    problems = {key for key in REQUIRED_WORK_KEYS if key not in record}
    authorships = record.get("authorships")
    if "authorships" in record and not isinstance(authorships, list):
        problems.add("authorships (not a list)")
    elif isinstance(authorships, list):
        for item in authorships:
            if not isinstance(item, dict):
                problems.add("authorships[] (item not an object)")
                continue
            problems.update(
                f"authorships[].{key}" for key in REQUIRED_AUTHORSHIP_KEYS if key not in item
            )
    return problems


def check_raw_works(parquet_path: str | Path, sample: int = 200) -> GuardResult:
    """Check the raw works Parquet schema and a sample of its ``raw_json`` records."""

    path = Path(parquet_path)
    if not path.is_file():
        return GuardResult([f"raw works parquet missing: {path}"], {})
    rows = pq.ParquetFile(path).metadata.num_rows
    present = set(pq.read_schema(path).names)
    missing_columns = [name for name in RAW_SCHEMA.names if name not in present]
    if missing_columns:
        problem = f"raw works parquet missing columns: {', '.join(missing_columns)}"
        return GuardResult([problem], {"rows": rows})
    if rows == 0:
        # An empty day is a valid outcome: there is nothing to sample.
        return GuardResult([], {"rows": 0, "sampled": 0, "bad_records": 0})

    step = max(1, rows // max(1, sample))
    indices = list(range(0, rows, step))[: max(1, sample)]
    table = pq.read_table(path, columns=["raw_json"])
    values = table.column("raw_json").take(pa.array(indices, type=pa.int64())).to_pylist()

    missing: Counter[str] = Counter()
    bad_records = 0
    for raw in values:
        record_problems = _record_problems(raw)
        if record_problems:
            bad_records += 1
            missing.update(record_problems)

    sampled = len(values)
    problems = [
        f"raw_json missing {key!r} in {count} of {sampled} sampled records"
        for key, count in sorted(missing.items())
    ]
    if bad_records:
        problems.append(f"{bad_records} of {sampled} sampled raw_json records are bad")
    return GuardResult(problems, {"rows": rows, "sampled": sampled, "bad_records": bad_records})


def check_normalized(directory: str | Path) -> GuardResult:
    """Check that each normalized table has every schema field with the same type."""

    root = Path(directory)
    if not root.is_dir():
        return GuardResult([f"normalized directory missing: {root}"], {})
    problems: list[str] = []
    rows: dict[str, int] = {}
    for name, expected in NORMALIZED_TABLES.items():
        path = root / name
        if not path.is_file():
            problems.append(f"normalized table missing: {name}")
            continue
        try:
            actual = pq.read_schema(path)
            rows[name] = pq.ParquetFile(path).metadata.num_rows
        except (OSError, pa.ArrowException) as error:
            problems.append(f"normalized table unreadable: {name} ({error})")
            continue
        actual_types = {column.name: column.type for column in actual}
        for column in expected:
            if column.name not in actual_types:
                problems.append(f"{name} missing column {column.name!r}")
            elif actual_types[column.name] != column.type:
                problems.append(
                    f"{name} column {column.name!r} has type {actual_types[column.name]}, "
                    f"expected {column.type}"
                )
    return GuardResult(problems, {"rows": rows})


def _check_index(path: Path) -> tuple[list[str], dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"index.json does not parse: {error}"], {}
    if not isinstance(payload, dict):
        return ["index.json is not a JSON object"], {}
    problems = [f"index.json missing key {key!r}" for key in INDEX_KEYS if key not in payload]
    works = payload.get("works")
    if works is None:
        return problems, {}
    if not isinstance(works, list):
        problems.append("index.json 'works' is not a list")
        return problems, {}
    bad = sum(
        1
        for row in works
        if not isinstance(row, dict) or any(key not in row for key in INDEX_WORK_KEYS)
    )
    if bad:
        problems.append(
            f"{bad} of {len(works)} index.json work rows lack {', '.join(INDEX_WORK_KEYS)}"
        )
    return problems, {"index_works": len(works)}


def check_site_payload(
    site_data_dir: str | Path,
    *,
    initial_files: Sequence[str] = INITIAL_PAYLOAD_FILES,
    initial_gzip_limit: int = DEFAULT_INITIAL_GZIP_LIMIT,
    file_limit: int = DEFAULT_FILE_LIMIT,
) -> GuardResult:
    """Check the initial gzip payload, per-file size, and the index.json contract."""

    root = Path(site_data_dir)
    if not root.is_dir():
        return GuardResult([f"site data directory missing: {root}"], {})
    problems: list[str] = []
    gzip_total = 0
    for name in initial_files:
        path = root / name
        if not path.is_file():
            problems.append(f"initial payload file missing: {name}")
            continue
        gzip_total += _gzip_size(path.read_bytes())
    if gzip_total > initial_gzip_limit:
        problems.append(
            f"initial payload gzip is {gzip_total} bytes, over the {initial_gzip_limit} limit"
        )

    file_count = 0
    largest_name, largest_bytes = "", 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        file_count += 1
        size = path.stat().st_size
        relative = path.relative_to(root).as_posix()
        if size > largest_bytes:
            largest_name, largest_bytes = relative, size
        if size > file_limit:
            problems.append(f"{relative} is {size} bytes, over the {file_limit} byte file limit")

    metrics: dict[str, Any] = {
        "initial_gzip_bytes": gzip_total,
        "initial_gzip_limit": initial_gzip_limit,
        "largest_file": largest_name,
        "largest_file_bytes": largest_bytes,
        "file_limit": file_limit,
        "files": file_count,
    }
    index_path = root / "index.json"
    if index_path.is_file():
        index_problems, index_metrics = _check_index(index_path)
        problems.extend(index_problems)
        metrics.update(index_metrics)
    return GuardResult(problems, metrics)


def run_all(
    *,
    raw_path: str | Path | None = None,
    normalized_dir: str | Path | None = None,
    site_data_dir: str | Path | None = None,
    require_raw: bool = False,
    require_normalized: bool = False,
    require_site: bool = True,
    raw_sample: int = 200,
    initial_gzip_limit: int = DEFAULT_INITIAL_GZIP_LIMIT,
    file_limit: int = DEFAULT_FILE_LIMIT,
) -> dict[str, GuardResult]:
    """Run each check whose input exists, or whose input is required.

    Checks whose input is absent and not required are omitted from the result.
    A required input that is missing is reported as a problem by the check.
    """

    results: dict[str, GuardResult] = {}
    if raw_path is not None and (require_raw or Path(raw_path).exists()):
        results["raw_works"] = check_raw_works(raw_path, sample=raw_sample)
    if normalized_dir is not None and (require_normalized or Path(normalized_dir).exists()):
        results["normalized"] = check_normalized(normalized_dir)
    if site_data_dir is not None and (require_site or Path(site_data_dir).exists()):
        results["site_payload"] = check_site_payload(
            site_data_dir, initial_gzip_limit=initial_gzip_limit, file_limit=file_limit
        )
    return results
