"""Rebuild the offline fixture outputs from scratch and prove the rebuild is deterministic (S10.3).

Runs the existing library builders on committed fixtures and institution registry
inputs only. Every output goes into a temporary directory; nothing is written to
``site/``, ``data/``, ``curation/``, or ``docs/``. The rebuild runs twice in two fresh
temporary directories, and the script fails unless every output file is byte-identical
between the runs. It then prints a manifest (path, bytes, sha256) of the first run.

Covered: S2.2 normalization, S2.3 labels, S3.1 site payloads, S8.1 grant normalization
with S8.6 de-duplication and the S8.10 ``grants.json`` export, and the S11.4 Atom feed.
Not covered: live ingestion, monitoring, open calls, status, and the institution and
geography builders. See ``docs/REPRODUCIBILITY.md``.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from atlas.build.export_site import export_site  # noqa: E402
from atlas.build.feed import write_feed  # noqa: E402
from atlas.build.grants_export import build_from_paths  # noqa: E402
from atlas.ingest.grants.dedupe import run_dedupe  # noqa: E402
from atlas.ingest.grants.normalize import normalize_grant, write_grants_parquet  # noqa: E402
from atlas.ingest.normalize import normalize_fixture  # noqa: E402
from atlas.nlp.labels import label_records, read_normalized_works  # noqa: E402

GENERATED_AT = "fixture"
WORKS_FIXTURE = REPO / "tests/fixtures/s2_2_openalex_works.json"
GRANTS_FIXTURE = REPO / "tests/fixtures/s8_1_grants.json"
INSTITUTIONS = REPO / "data/processed/institutions.parquet"
AUTHOR_OVERRIDES = REPO / "config/author_overrides.csv"
QUERIES = REPO / "config/queries.yml"
TAXONOMY = REPO / "config/taxonomy.yml"
MERGED_NAME = "grants_merged.parquet"


@dataclass(frozen=True)
class ManifestRow:
    path: str
    bytes: int
    sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(root: Path) -> list[ManifestRow]:
    """Return sorted (path, bytes, sha256) rows for every file under ``root``."""

    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rows.append(
            ManifestRow(
                path=path.relative_to(root).as_posix(),
                bytes=path.stat().st_size,
                sha256=_sha256(path),
            )
        )
    return rows


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _grant_rows() -> list[dict[str, Any]]:
    records = json.loads(GRANTS_FIXTURE.read_text(encoding="utf-8"))
    query_config = _load_yaml(QUERIES)
    taxonomy = _load_yaml(TAXONOMY)
    return [
        normalize_grant(
            copy.deepcopy(item["raw"]),
            source=item["source"],
            query_config=query_config,
            taxonomy=taxonomy,
        )
        for item in records
    ]


def rebuild(out: Path) -> Path:
    """Run every covered builder with fixture inputs, writing only under ``out``.

    Returns the public-layout directory ``out/site``.
    """

    site = out / "site"
    data = site / "data"
    normalized_dir = out / "normalized"
    labels_dir = out / "labels"
    interim = out / "interim" / "grants"
    for folder in (data, normalized_dir, labels_dir, interim, out / "qc"):
        folder.mkdir(parents=True, exist_ok=True)

    # S2.2 normalization and S2.3 labels from the committed works fixture.
    normalized = normalize_fixture(
        WORKS_FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=normalized_dir,
        qc_path=out / "qc" / "normalization_qc.md",
        author_overrides_path=AUTHOR_OVERRIDES,
        generated_at=GENERATED_AT,
    )
    labels = label_records(
        read_normalized_works(normalized.output_dir / "works.parquet"),
        json.loads(WORKS_FIXTURE.read_text(encoding="utf-8")),
        query_config_path=QUERIES,
        taxonomy_path=TAXONOMY,
        output_path=labels_dir / "work_labels.parquet",
        qc_path=out / "qc" / "labels_qc.md",
        source="fixture",
        generated_at=GENERATED_AT,
    )

    # S3.1 site payloads (index, authors, institutions, aggregates, build metadata).
    export_site(
        works_path=normalized.output_dir / "works.parquet",
        authors_path=normalized.output_dir / "authors.parquet",
        authorships_path=normalized.output_dir / "authorships.parquet",
        institutions_path=normalized.output_dir / "institutions.parquet",
        labels_path=labels.output_path,
        output_dir=data,
        generated_at=GENERATED_AT,
    )

    # S8.1 grant normalization, one table per source, then S8.6 de-duplication.
    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    for row in _grant_rows():
        rows_by_source.setdefault(str(row["source"]), []).append(row)
    for source, rows in sorted(rows_by_source.items()):
        write_grants_parquet(rows, interim / f"{source}.parquet")
    run_dedupe(
        interim_dir=interim,
        merged_out=interim / MERGED_NAME,
        map_out=interim / "grants_dedupe_map.csv",
        report_out=out / "qc" / "grants_overlap_report.md",
        status_path=interim / "state_funders_status.json",
    )

    # S8.10 grants export and S11.4 Atom feed, reading only the temporary outputs.
    build_from_paths(
        merged=interim / MERGED_NAME,
        institutions=INSTITUTIONS,
        dedupe_map=interim / "grants_dedupe_map.csv",
        output=data / "grants.json",
        generated_at=GENERATED_AT,
    )
    write_feed(data / "index.json", data / "grants.json", site / "feed.xml")
    return site


def verify_determinism() -> list[ManifestRow]:
    """Rebuild twice in fresh temporary directories and require identical outputs."""

    with tempfile.TemporaryDirectory(prefix="atlas-reproduce-a-") as first_dir:
        first = manifest(rebuild(Path(first_dir)).parent)
    with tempfile.TemporaryDirectory(prefix="atlas-reproduce-b-") as second_dir:
        second = manifest(rebuild(Path(second_dir)).parent)
    if first != second:
        by_path = {row.path: row for row in second}
        differing = sorted(row.path for row in first if by_path.get(row.path) != row) + sorted(
            {row.path for row in second} - {row.path for row in first}
        )
        raise SystemExit(f"Rebuild is not deterministic; differing outputs: {differing}")
    if not first:
        raise SystemExit("Rebuild produced no output files")
    return first


def main() -> int:
    rows = verify_determinism()
    print("Fixture rebuild is byte-identical across two runs. Manifest:")
    print("path\tbytes\tsha256")
    for row in rows:
        print(f"{row.path}\t{row.bytes}\t{row.sha256}")
    print(f"{len(rows)} files; {sum(row.bytes for row in rows)} bytes in total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
