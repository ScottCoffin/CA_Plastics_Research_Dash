"""Build site/data/california/pubmed_coverage.json and the PubMed miss-triage sheet (BQ-S9 part C).

Inputs: the stage-1 PubMed reference runs in data/interim/pubmed/ (not committed), the committed
normalized works table and site/data/california/index.json (the published subset).
No network calls. Coverage
counts come from atlas.qc.pubmed.coverage(); this script adds the miss sample, the triage sheet and
the JSON layout.

    py -3.14 scripts/build_pubmed_coverage_json.py          # write the JSON and the triage sheet
    py -3.14 scripts/build_pubmed_coverage_json.py --check  # fail when the committed JSON is stale

--check exits 0 with a SKIP message when the interim inputs are absent (CI has no interim data).
A triage sheet with any human entry is never overwritten; the JSON is rebuilt from its labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.nlp.active_relevance import wilson_interval  # noqa: E402
from atlas.qc.pubmed import (  # noqa: E402
    MANIFEST_SCHEMA,
    ROW_FIELDS,
    _norm_doi,
    _norm_pmid,
    coverage,
)
from atlas.regions.scope import region_data_dir  # noqa: E402

SCHEMA_VERSION = "bqs-pm-v1"
SAMPLE_SEED = 20261122
SAMPLE_CAP = 50
REFERENCE_SETS = ("r1", "r2")
REFERENCE_DESCRIPTIONS = {
    "r1": "PubMed MeSH-indexed microplastics records, California affiliation (narrow set)",
    "r2": "PubMed title and abstract plastics terms, California affiliation (broad set)",
}
INTERIM_DIR = ROOT / "data" / "interim" / "pubmed"
WORKS_PATH = ROOT / "data" / "processed" / "normalized" / "works.parquet"
INDEX_PATH = region_data_dir() / "index.json"
TAXONOMY_PATH = ROOT / "config" / "failure_taxonomy.yml"
TRIAGE_PATH = ROOT / "curation" / "pubmed_miss_triage_v1.csv"
OUTPUT_PATH = region_data_dir() / "pubmed_coverage.json"
TRIAGE_REL = "curation/pubmed_miss_triage_v1.csv"
OUTPUT_REL = "site/data/california/pubmed_coverage.json"
TRIAGE_COLUMNS = (
    "pmid",
    "doi",
    "pub_year",
    "reference_sets",
    "in_normalized_corpus",
    "atlas_work_id",
    "triage_class",
    "note",
    "reviewer",
    "reviewed_at",
)
HUMAN_COLUMNS = ("triage_class", "note", "reviewer", "reviewed_at")
SOURCE = (
    "NCBI PubMed E-utilities reference runs (stage 1, interim, not committed); Atlas works from "
    "data/processed/normalized/works.parquet, published subset from site/data/california/index.json"
)
DEFINITION = (
    "Coverage is the share of PubMed reference records that also appear among the published Atlas "
    "works, joined by PMID and then by DOI. Each reference set is a PubMed search for plastics "
    "papers with a California affiliation. Coverage is not a completeness rate for the field: the "
    "reference sets are search results, not samples of a defined population; the California filter "
    "(California[ad]) is approximate; and MeSH indexing lags and varies by record, so recent years "
    "look worse. A reference record that is not among the published works is a miss, and a miss is "
    "not automatically a false negative of the Atlas. False negatives are estimated only from a "
    "fixed-seed sample of misses that is triaged by hand into failure-taxonomy classes."
)
PENDING_STATUS = "pending owner triage"


class BuildError(RuntimeError):
    """An input is missing or inconsistent; nothing is written."""


class TriageOverwriteError(BuildError):
    """The triage sheet already holds human entries and must not be overwritten."""


class ReferenceRun(NamedTuple):
    """One stage-1 reference set: PMID rows plus its manifest and the manifest's byte hash."""

    name: str
    rows: list[dict[str, Any]]
    manifest: dict[str, Any]
    manifest_sha256: str


class AtlasWorks(NamedTuple):
    """Normalized works (all) and the published subset, both with work_id, pmid and doi."""

    normalized: list[dict[str, Any]]
    published: list[dict[str, Any]]


class Taxonomy(NamedTuple):
    """Failure-taxonomy version, class ids in file order, and the false-negative class ids."""

    version: str
    class_ids: list[str]
    false_negative_ids: list[str]


class _JoinIndex:
    """PMID-then-DOI lookup using the same keys and normalisers as ``coverage()``."""

    def __init__(self, works: Sequence[Mapping[str, Any]]) -> None:
        self._pmids: dict[str, str] = {}
        self._dois: dict[str, str] = {}
        for work in works:
            pmid = _norm_pmid(work.get("pmid"))
            doi = _norm_doi(work.get("doi"))
            if pmid is not None:
                self._pmids.setdefault(pmid, work["work_id"])
            if doi is not None:
                self._dois.setdefault(doi, work["work_id"])

    def match(self, row: Mapping[str, Any]) -> tuple[str, str] | None:
        """Return ``("pmid" | "doi", work_id)`` for the first join that hits, else None."""
        pmid = _norm_pmid(row.get("pmid"))
        if pmid is not None and pmid in self._pmids:
            return "pmid", self._pmids[pmid]
        doi = _norm_doi(row.get("doi"))
        if doi is not None and doi in self._dois:
            return "doi", self._dois[doi]
        return None


# --- Loading ------------------------------------------------------------------------------------


def _year(text: str | None) -> int | None:
    value = (text or "").strip()
    return int(value) if value.isdigit() else None


def read_reference_rows(path: Path) -> list[dict[str, Any]]:
    """Read one PMID CSV (columns ``ROW_FIELDS``); PMIDs must be numeric and unique."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ROW_FIELDS:
            raise BuildError(f"{path.name}: header must be {','.join(ROW_FIELDS)}")
        rows: list[dict[str, Any]] = []
        for line in reader:
            pmid = _norm_pmid(line.get("pmid"))
            if pmid is None:
                raise BuildError(f"{path.name}: PMID {line.get('pmid')!r} is not numeric")
            rows.append(
                {
                    "pmid": pmid,
                    "doi": (line.get("doi") or "").strip() or None,
                    "pub_year": _year(line.get("pub_year")),
                    "chunk_id": line.get("chunk_id") or "",
                    "partition": line.get("partition") or "",
                }
            )
    pmids = [row["pmid"] for row in rows]
    if len(set(pmids)) != len(pmids):
        raise BuildError(f"{path.name}: duplicate PMIDs")
    return rows


def load_reference_run(name: str, interim_dir: Path) -> ReferenceRun:
    """Load ``<name>_california_pmids.csv`` and its manifest, checking the manifest's counts."""
    manifest_path = interim_dir / f"{name}_california_manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise BuildError(f"{manifest_path.name}: schema must be {MANIFEST_SCHEMA}")
    if manifest.get("reference_set") != name:
        raise BuildError(f"{manifest_path.name}: reference_set must be {name}")
    rows = read_reference_rows(interim_dir / f"{name}_california_pmids.csv")
    if manifest.get("total_unique_pmids") != len(rows):
        raise BuildError(f"{manifest_path.name}: total_unique_pmids does not match the PMID CSV")
    return ReferenceRun(name, rows, manifest, hashlib.sha256(manifest_bytes).hexdigest())


def load_atlas(works_path: Path, index_path: Path) -> AtlasWorks:
    """Join the published work ids in index.json to the normalized table for PMID and DOI."""
    normalized = pq.read_table(works_path, columns=["work_id", "doi", "pmid"]).to_pylist()
    by_id = {row["work_id"]: row for row in normalized}
    if len(by_id) != len(normalized):
        raise BuildError("works.parquet has duplicate work_id values")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    published_ids = [work["work_id"] for work in index["works"]]
    if len(set(published_ids)) != len(published_ids):
        raise BuildError("site/data/california/index.json has duplicate work ids")
    absent = [work_id for work_id in published_ids if work_id not in by_id]
    if absent:
        raise BuildError(f"{len(absent)} published work ids are not in works.parquet")
    return AtlasWorks(normalized, [by_id[work_id] for work_id in published_ids])


def load_taxonomy(path: Path) -> Taxonomy:
    """Read class ids and the false-negative classes from config/failure_taxonomy.yml."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    classes = data["classes"]
    class_ids = [str(item["id"]) for item in classes]
    if len(set(class_ids)) != len(class_ids):
        raise BuildError("failure_taxonomy.yml has duplicate class ids")
    false_negative = [
        str(item["id"]) for item in classes if item.get("direction") == "false_negative"
    ]
    return Taxonomy(str(data["version"]), class_ids, false_negative)


def read_triage_sheet(path: Path) -> list[dict[str, str]] | None:
    """Return the triage sheet rows, or None when the file does not exist."""
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != TRIAGE_COLUMNS:
            raise BuildError(f"{path.name}: header must be {','.join(TRIAGE_COLUMNS)}")
        return [{key: value or "" for key, value in row.items()} for row in reader]


def has_human_entries(rows: Sequence[Mapping[str, str]]) -> bool:
    """True when any reviewer-entered column holds a non-blank value."""
    return any(str(row.get(column) or "").strip() for row in rows for column in HUMAN_COLUMNS)


# --- Miss sample --------------------------------------------------------------------------------


def select_misses(runs: Sequence[ReferenceRun], published: _JoinIndex) -> list[dict[str, Any]]:
    """Reference PMIDs (union over the sets) that the published works do not cover, by PMID."""
    found: dict[str, dict[str, Any]] = {}
    for run in runs:
        for row in run.rows:
            if published.match(row) is not None:
                continue
            entry = found.setdefault(
                row["pmid"],
                {"pmid": row["pmid"], "doi": None, "pub_year": None, "reference_sets": []},
            )
            if run.name not in entry["reference_sets"]:
                entry["reference_sets"].append(run.name)
            entry["doi"] = entry["doi"] or row["doi"]
            if entry["pub_year"] is None:
                entry["pub_year"] = row["pub_year"]
    return sorted(found.values(), key=lambda item: int(item["pmid"]))


def sample_key(pmid: str, seed: int = SAMPLE_SEED) -> str:
    """Sort key for the fixed-seed miss sample."""
    return hashlib.sha256(f"{seed}:{pmid}".encode()).hexdigest()


def select_sample(
    misses: Sequence[Mapping[str, Any]], *, seed: int = SAMPLE_SEED, cap: int = SAMPLE_CAP
) -> list[dict[str, Any]]:
    """Take the first ``min(cap, n)`` misses by ``sha256(seed:pmid)``; output in PMID order."""
    ranked = sorted(misses, key=lambda item: sample_key(item["pmid"], seed))
    chosen = ranked[: min(cap, len(ranked))]
    return sorted((dict(item) for item in chosen), key=lambda item: int(item["pmid"]))


def sheet_rows_for(
    sample: Sequence[Mapping[str, Any]], normalized: _JoinIndex
) -> list[dict[str, str]]:
    """Blank triage rows for the sample, with the normalized-corpus match where one exists."""
    rows: list[dict[str, str]] = []
    for item in sample:
        hit = normalized.match(item)
        rows.append(
            {
                "pmid": item["pmid"],
                "doi": item["doi"] or "",
                "pub_year": "" if item["pub_year"] is None else str(item["pub_year"]),
                "reference_sets": ";".join(item["reference_sets"]),
                "in_normalized_corpus": "true" if hit else "false",
                "atlas_work_id": hit[1] if hit else "",
                "triage_class": "",
                "note": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        )
    return rows


def triage_csv_text(rows: Sequence[Mapping[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=TRIAGE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def write_triage_sheet(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    """Write the sheet with LF line endings, refusing to replace one with human entries."""
    existing = read_triage_sheet(path)
    if existing is not None and has_human_entries(existing):
        raise TriageOverwriteError(
            f"{path.name} has reviewer entries; refusing to overwrite it (the JSON is still built)"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(triage_csv_text(rows).encode("utf-8"))


# --- Payload ------------------------------------------------------------------------------------


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _set_block(run: ReferenceRun, atlas: AtlasWorks, published: _JoinIndex) -> dict[str, Any]:
    against_published = coverage(run.rows, atlas.published)
    against_normalized = coverage(run.rows, atlas.normalized)
    misses = [row for row in run.rows if published.match(row) is None]
    found_unpublished = coverage(misses, atlas.normalized)["covered_total"]
    manifest = run.manifest
    return {
        "description": REFERENCE_DESCRIPTIONS[run.name],
        "affiliation": manifest.get("affiliation"),
        "stage": 1,
        "query_translation": manifest.get("query_translation"),
        "run_timestamp": manifest.get("run_timestamp"),
        "manifest_sha256": run.manifest_sha256,
        "reference_pmids": against_published["reference_total"],
        "found_published": against_published["covered_total"],
        "found_published_by_pmid": against_published["matched_by_pmid"],
        "found_published_by_doi": against_published["matched_by_doi"],
        "misses": against_published["reference_total"] - against_published["covered_total"],
        "found_unpublished_corpus": found_unpublished,
        "coverage_published": _round(against_published["coverage"]),
        "coverage_by_year": {
            year: {
                "reference": bucket["reference_total"],
                "found": bucket["covered_total"],
                "coverage": _round(bucket["coverage"]),
            }
            for year, bucket in against_published["by_year"].items()
        },
        "join_rate": {
            "published": _round(against_published["join_rate"]),
            "normalized": _round(against_normalized["join_rate"]),
        },
    }


def _triage_block(
    sample: Sequence[Mapping[str, Any]],
    misses: Sequence[Mapping[str, Any]],
    sheet: Sequence[Mapping[str, str]],
    taxonomy: Taxonomy,
) -> dict[str, Any]:
    labelled = [row for row in sheet if row["triage_class"].strip()]
    block: dict[str, Any] = {
        "sample_size": len(sample),
        "seed": SAMPLE_SEED,
        "sample_rule": f"first min({SAMPLE_CAP}, misses) misses by sha256(seed:pmid)",
        "misses_total": len(misses),
        "triage_file": TRIAGE_REL,
        "labelled": len(labelled),
        "false_negative_classes": taxonomy.false_negative_ids,
    }
    if labelled:
        fn_ids = set(taxonomy.false_negative_ids)
        count = sum(1 for row in labelled if row["triage_class"] in fn_ids)
        lower, upper = wilson_interval(count, len(labelled))
        block["false_negative_share"] = {
            "count": count,
            "n": len(labelled),
            "share": _round(count / len(labelled)),
            "wilson_95": [_round(lower), _round(upper)],
        }
    else:
        block["status"] = PENDING_STATUS
    return block


def build_payload(
    *,
    runs: Sequence[ReferenceRun],
    atlas: AtlasWorks,
    taxonomy: Taxonomy,
    existing_sheet: Sequence[Mapping[str, str]] | None,
    generated_at: str,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Return ``(payload, sheet_rows)``.

    ``sheet_rows`` is the fresh sample when there is no reviewer entry, or the existing labelled
    sheet (validated against the current sample) when there is one.
    """
    published = _JoinIndex(atlas.published)
    normalized = _JoinIndex(atlas.normalized)
    misses = select_misses(runs, published)
    sample = select_sample(misses)
    fresh = sheet_rows_for(sample, normalized)
    if existing_sheet is not None and has_human_entries(existing_sheet):
        if sorted(row["pmid"] for row in existing_sheet) != sorted(row["pmid"] for row in fresh):
            raise BuildError(
                "the triage sheet lists different PMIDs from the current miss sample; "
                "reconcile it by hand (it is not overwritten)"
            )
        known = set(taxonomy.class_ids)
        for row in existing_sheet:
            triage_class = row["triage_class"].strip()
            if triage_class and triage_class not in known:
                raise BuildError(f"triage_class {triage_class!r} is not in failure_taxonomy.yml")
        sheet_rows = [dict(row) for row in existing_sheet]
    else:
        sheet_rows = fresh

    reference_sets = {run.name: _set_block(run, atlas, published) for run in runs}
    atlas_corpus = {
        "published_works": len(atlas.published),
        "published_with_pmid": sum(
            1 for work in atlas.published if _norm_pmid(work.get("pmid")) is not None
        ),
        "normalized_works": len(atlas.normalized),
        "normalized_with_pmid": sum(
            1 for work in atlas.normalized if _norm_pmid(work.get("pmid")) is not None
        ),
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "manifest_schema": MANIFEST_SCHEMA,
        "failure_taxonomy_version": taxonomy.version,
        "stage": 1,
        "source": SOURCE,
        "definition": DEFINITION,
        "atlas_corpus": atlas_corpus,
        "reference_sets": reference_sets,
        "miss_triage": _triage_block(sample, misses, sheet_rows, taxonomy),
        "triage_classes": taxonomy.class_ids,
    }
    return payload, sheet_rows


def render_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"


def same_payload(committed: Mapping[str, Any], fresh: Mapping[str, Any]) -> bool:
    """Compare two payloads, ignoring the generation timestamp."""

    def strip(payload: Mapping[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if key != "generated_at"}

    return strip(committed) == strip(fresh)


# --- CLI ----------------------------------------------------------------------------------------


def _interim_inputs(interim_dir: Path) -> list[Path]:
    return [
        interim_dir / f"{name}_california_{kind}"
        for name in REFERENCE_SETS
        for kind in ("pmids.csv", "manifest.json")
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="fail when the committed JSON is stale"
    )
    args = parser.parse_args(argv)

    absent = [path for path in _interim_inputs(INTERIM_DIR) if not path.exists()]
    if absent:
        if args.check:
            print(
                "SKIP: PubMed interim inputs are absent (CI has no interim data); nothing checked"
            )
            return 0
        print(f"FAIL: missing interim input {absent[0]}", file=sys.stderr)
        return 1

    now = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        runs = [load_reference_run(name, INTERIM_DIR) for name in REFERENCE_SETS]
        atlas = load_atlas(WORKS_PATH, INDEX_PATH)
        taxonomy = load_taxonomy(TAXONOMY_PATH)
        sheet = read_triage_sheet(TRIAGE_PATH)
        payload, sheet_rows = build_payload(
            runs=runs, atlas=atlas, taxonomy=taxonomy, existing_sheet=sheet, generated_at=now
        )
    except (BuildError, OSError, ValueError, KeyError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if args.check:
        try:
            committed = json.loads(OUTPUT_PATH.read_bytes().decode("utf-8"))
        except OSError:
            print(f"FAIL: {OUTPUT_PATH.name} is missing; run without --check", file=sys.stderr)
            return 1
        if not same_payload(committed, payload):
            print(f"FAIL: {OUTPUT_PATH.name} is stale; rerun without --check", file=sys.stderr)
            return 1
        print(f"OK: {OUTPUT_PATH.name} is current")
        return 0

    if sheet is None or not has_human_entries(sheet):
        try:
            write_triage_sheet(TRIAGE_PATH, sheet_rows)
        except BuildError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        print(f"wrote {TRIAGE_REL} ({len(sheet_rows)} rows)")
    else:
        print(f"kept {TRIAGE_PATH.name} unchanged (reviewer entries present)")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_bytes(render_payload(payload).encode("utf-8"))
    print(f"wrote {OUTPUT_REL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
