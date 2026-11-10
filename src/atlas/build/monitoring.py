"""Rights-aware, compact export for the Stage 7.5 monitoring view."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from atlas.dataset_discovery import canonical_doi
from atlas.ingest.monitoring.registry import load_registry

SCHEMA_VERSION = "s7.5"
PRIVATE_SAMPLE_FIELDS = (
    "sample_id",
    "dataset_id",
    "lat",
    "lon",
    "date",
    "matrix",
    "method",
    "concentration_value",
    "concentration_unit",
    "particle_count",
    "in_ca_land",
    "in_ca_state_waters",
    "contributor",
    "contributor_in_ca",
    "citation",
)


def _date_text(value: Any) -> str | None:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value if isinstance(value, str) else None


def _public_dataset(entry: dict[str, Any]) -> dict[str, Any]:
    """Keep source metadata/citations while avoiding unsupported data claims."""
    return {
        "id": entry["id"],
        "seed_eligible": entry["seed_eligible"],
        "name": entry["name"],
        "steward": entry["steward"],
        "entity_type": entry["entity_type"],
        "status": entry["status"],
        "region": entry["region"],
        "sample_matrix": entry["sample_matrix"],
        "plastic_classes": entry["plastic_classes"],
        "access_tier": entry["access_tier"],
        "url": entry["url"],
        "access_method": entry["access_method"],
        "format": entry["format"],
        "cadence": entry["cadence"],
        "license": entry["license"],
        "provenance_type": entry["provenance_type"],
        "provenance_url": entry["provenance_url"],
        "provenance_note": entry["provenance_note"],
        "evidence_excerpt": entry.get("evidence_excerpt"),
        "last_checked": _date_text(entry["last_checked"]),
        "citation": entry["provenance_note"],
        "contributor_in_ca": entry.get("contributor_in_ca"),
        "measurement_status": "catalogue_only",
    }


def _attach_linked_works(
    datasets: list[dict[str, Any]],
    registry_rows: list[dict[str, Any]],
    work_links: Sequence[Mapping[str, Any]],
) -> None:
    """Add ``linked_works`` to registry rows whose URL or provenance DOI matches a link.

    Matching uses canonical DOIs only; rows without a matching link keep no key.
    """
    by_doi: dict[str, set[tuple[str, str]]] = {}
    for link in work_links:
        doi = canonical_doi(str(link.get("dataset_doi") or ""))
        work_id = str(link.get("work_id") or "")
        evidence = str(link.get("evidence_type") or "")
        if doi and work_id and evidence:
            by_doi.setdefault(doi, set()).add((work_id, evidence))
    for dataset, entry in zip(datasets, registry_rows, strict=True):
        dois = {canonical_doi(str(entry.get(field) or "")) for field in ("url", "provenance_url")}
        pairs = sorted({pair for doi in dois if doi for pair in by_doi.get(doi, set())})
        if pairs:
            dataset["linked_works"] = [
                {"work_id": work_id, "evidence_type": evidence} for work_id, evidence in pairs
            ]


def build_monitoring_payload(
    registry: dict[str, Any],
    *,
    samples: list[dict[str, Any]] | None = None,
    private_preview: bool = False,
    generated_at: str | None = None,
    work_links: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a source-catalogue payload; include rows only for explicit private preview.

    Public output always has zero observations. Private previews are tagged and
    restricted to a small display schema so the local QC payload cannot leak.
    ``work_links`` (S9.2 rows) is optional; without it no ``linked_works`` keys are added.
    """
    rows = samples or []
    if rows and not private_preview:
        raise PermissionError("sample observations require explicit private-preview mode")
    if private_preview and not rows:
        raise ValueError("private preview requested but no local samples were supplied")
    datasets = [_public_dataset(row) for row in registry["datasets"]]
    if work_links:
        _attach_linked_works(datasets, list(registry["datasets"]), work_links)
    dataset_ids = {row["id"] for row in datasets}
    if private_preview:
        unknown = sorted({row.get("dataset_id") for row in rows} - dataset_ids)
        if unknown:
            raise ValueError(f"sample rows reference unknown registry datasets: {unknown}")
        samples_out = [
            {key: row.get(key) for key in PRIVATE_SAMPLE_FIELDS if key in row}
            for row in sorted(rows, key=lambda row: str(row.get("sample_id", "")))
        ]
        for dataset in datasets:
            if any(row.get("dataset_id") == dataset["id"] for row in samples_out):
                dataset["measurement_status"] = "private_local_preview_rights_unresolved"
    else:
        samples_out = []
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "publication_mode": "private_preview" if private_preview else "public_catalogue",
        "sample_count": len(samples_out),
        "coverage_basis": "local preview observations only"
        if private_preview
        else "no cleared public sample rows",
        "datasets": datasets,
        "samples": samples_out,
    }


def write_monitoring_payload(payload: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


def require_private_output_outside_site(
    path: str | Path, *, site_root: str | Path = "site"
) -> Path:
    """Resolve aliases and reject private payload targets inside the public site tree."""
    target = Path(path).resolve()
    public_root = Path(site_root).resolve()
    if target == public_root or public_root in target.parents:
        raise ValueError("private monitoring preview output must be outside the public site tree")
    return target


def build_public_export(output: str | Path = "site/data/monitoring.json") -> Path:
    """Build the default public source catalogue, never local measurements."""
    return write_monitoring_payload(build_monitoring_payload(load_registry()), output)
