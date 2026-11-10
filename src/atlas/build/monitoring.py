"""Rights-aware, compact export for the Stage 7.5 monitoring view."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from atlas.dataset_discovery import canonical_doi
from atlas.ingest.monitoring.registry import load_registry

SCHEMA_VERSION = "s7.5"
PUBLICATION_PATH = Path("config/monitoring_publication.yml")
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


def load_publication_clearances(path: Path = PUBLICATION_PATH) -> dict[str, dict[str, Any]]:
    """Return ``{dataset_id: clearance}`` for datasets whose rows may be published."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    cleared = (payload or {}).get("cleared") or {}
    if not isinstance(cleared, dict):
        raise ValueError(f"{path}: 'cleared' must be a mapping")
    for dataset_id, entry in cleared.items():
        missing = [key for key in ("license", "basis", "attribution") if not (entry or {}).get(key)]
        if missing:
            raise ValueError(f"{path}: clearance for {dataset_id} lacks {missing}")
    return cleared


def build_monitoring_payload(
    registry: dict[str, Any],
    *,
    samples: list[dict[str, Any]] | None = None,
    private_preview: bool = False,
    clearances: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
    work_links: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the monitoring payload.

    Without samples the output is the zero-observation public catalogue. Samples
    are published only when every row's dataset has a recorded clearance
    (``clearances``, from ``config/monitoring_publication.yml``); otherwise they
    need explicit private-preview mode, which is tagged and kept out of ``site/``.
    Both modes keep only the small display schema, so QC detail cannot leak.
    ``work_links`` (S9.2 rows) is optional; without it no ``linked_works`` keys are added.
    """
    rows = samples or []
    cleared = dict(clearances or {})
    if private_preview and cleared:
        raise ValueError("choose private preview or cleared publication, not both")
    if rows and not private_preview:
        uncleared = sorted({str(row.get("dataset_id")) for row in rows} - set(cleared))
        if not cleared or uncleared:
            raise PermissionError(
                f"sample observations without a publication clearance: {uncleared or 'all'}"
            )
    if private_preview and not rows:
        raise ValueError("private preview requested but no local samples were supplied")
    datasets = [_public_dataset(row) for row in registry["datasets"]]
    if work_links:
        _attach_linked_works(datasets, list(registry["datasets"]), work_links)
    dataset_ids = {row["id"] for row in datasets}
    if rows:
        unknown = sorted({row.get("dataset_id") for row in rows} - dataset_ids)
        if unknown:
            raise ValueError(f"sample rows reference unknown registry datasets: {unknown}")
        samples_out = [
            {key: row.get(key) for key in PRIVATE_SAMPLE_FIELDS if key in row}
            for row in sorted(rows, key=lambda row: str(row.get("sample_id", "")))
        ]
        for dataset in datasets:
            if not any(row.get("dataset_id") == dataset["id"] for row in samples_out):
                continue
            if private_preview:
                dataset["measurement_status"] = "private_local_preview_rights_unresolved"
                continue
            clearance = cleared[dataset["id"]]
            dataset["measurement_status"] = "published_rights_cleared"
            dataset["publication_license"] = {
                "id": clearance["license"],
                "url": clearance.get("license_url"),
                "basis": clearance["basis"],
            }
            dataset["citation"] = clearance["attribution"]
    else:
        samples_out = []
    if private_preview:
        mode, basis = "private_preview", "local preview observations only"
    elif samples_out:
        mode, basis = "public_cleared", "rights-cleared observations from listed datasets only"
    else:
        mode, basis = "public_catalogue", "no cleared public sample rows"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "publication_mode": mode,
        "sample_count": len(samples_out),
        "coverage_basis": basis,
        "datasets": datasets,
        "samples": samples_out,
    }


def write_monitoring_payload(payload: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
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


def build_public_export(
    output: str | Path = "site/data/monitoring.json",
    *,
    samples_path: str | Path | None = None,
) -> Path:
    """Build the public payload: the catalogue plus rows from cleared datasets only.

    ``samples_path`` (a normalized S7.3 ``samples.json``) is optional; without it
    the output is the zero-observation catalogue.
    """
    rows = None
    clearances = None
    if samples_path is not None:
        rows = json.loads(Path(samples_path).read_text(encoding="utf-8"))
        clearances = load_publication_clearances()
    payload = build_monitoring_payload(load_registry(), samples=rows, clearances=clearances)
    return write_monitoring_payload(payload, output)
