"""Versioned annotation templates, validation, and inter-rater agreement.

This module handles annotation records only. It never creates labels, reads
model suggestions, or adjudicates disagreements.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ANNOTATION_FIELDS = (
    "work_id",
    "split",
    "sample_role",
    "year",
    "title",
    "abstract",
    "annotator",
    "guide_version",
    "plastic_related",
    "plastic_tier",
    "ca_sampled",
    "study_type",
    "domain_tags",
    "evidence_snippet",
    "evidence_source",
    "decision_status",
    "adjudicated_value",
    "adjudication_rationale",
)
LABEL_FIELDS = ("plastic_related", "plastic_tier", "ca_sampled", "study_type")
DOMAIN_TAGS = (
    "occurrence_and_monitoring",
    "analytical_methods",
    "fate_transport_and_sorption",
    "wastewater_and_treatment",
    "ecotoxicology_and_trophic_transfer",
    "soil_and_agriculture",
    "human_exposure_and_health_risk",
    "air",
)
_TRUTH = {"true", "false"}
_TIERS = {"core", "chemicals-in-plastics"}
_SAMPLING = {"yes", "partial", "no", "unclear"}
_SOURCES = {"title", "abstract", "full_text_locator"}
_STATUSES = {"complete", "adjudication_required"}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_frozen_guide(guide_path: str | Path, review_path: str | Path) -> str:
    """Return guide_v1 only when owner approval pins the current guide hash."""
    guide = Path(guide_path).read_text(encoding="utf-8")
    review = Path(review_path).read_text(encoding="utf-8")
    if not re.search(r"Status:\*\* approved; frozen as `guide_v1`", guide):
        raise ValueError("guide_v1 is not approved and frozen; annotation remains gated")
    if not re.search(r"Decision:\s*Approve `guide_v1` as written", review):
        raise ValueError("owner review does not record approval of guide_v1")
    owner = re.search(r"^- Owner:\s*(.*?)\s*$", review, re.MULTILINE)
    owner_value = owner.group(1).strip() if owner else ""
    owner_token = owner_value.strip(" [](){}").casefold()
    if owner_token in {
        "",
        "owner",
        "owner name",
        "tbd",
        "todo",
        "n/a",
        "na",
        "none",
        "unknown",
        "pending",
    } or re.fullmatch(r"[_ .-]+", owner_value):
        raise ValueError("owner review must name the approving owner")
    approval_date = re.search(r"^- Date:\s*(.*?)\s*$", review, re.MULTILINE)
    date_text = approval_date.group(1) if approval_date else ""
    try:
        parsed_date = dt.date.fromisoformat(date_text)
    except ValueError as error:
        raise ValueError("owner review date must be an ISO date (YYYY-MM-DD)") from error
    if parsed_date.isoformat() != date_text:
        raise ValueError("owner review date must be an ISO date (YYYY-MM-DD)")
    approved_hash = re.search(r"Approved guide SHA-256:\s*`?([0-9A-Fa-f]{64})", review)
    if not approved_hash or approved_hash.group(1).upper() != sha256_file(guide_path).upper():
        raise ValueError("approved guide hash is missing or does not match current guide content")
    return "guide_v1"


def export_templates(
    split_rows: list[dict[str, Any]],
    annotators: list[str],
    output_dir: str | Path,
    *,
    guide_version: str,
    include_test: bool = False,
    works_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[Path]:
    """Create one blank, split-scoped CSV per annotator; no labels are supplied."""
    if not guide_version.strip() or not annotators or any(not name.strip() for name in annotators):
        raise ValueError("guide_version and non-empty annotator names are required")
    if len(set(annotators)) != len(annotators):
        raise ValueError("annotator names must be unique")
    if len({_safe_name(name) for name in annotators}) != len(annotators):
        raise ValueError("annotator names collide after filename normalization")
    seen: set[str] = set()
    for row in split_rows:
        work_id = str(row.get("work_id", "")).strip()
        split = row.get("split")
        role = row.get("sample_role")
        if not work_id or work_id in seen:
            raise ValueError(f"missing or duplicate split work_id: {work_id!r}")
        seen.add(work_id)
        if split not in {"train", "dev", "test"} or role not in {"pool", "leak_test"}:
            raise ValueError(f"invalid split metadata for {work_id}")
        if works_by_id is not None and work_id not in works_by_id:
            raise ValueError(f"missing work metadata for {work_id}")
    eligible_rows = [row for row in split_rows if include_test or row["split"] != "test"]
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs = []
    for annotator in annotators:
        path = root / f"annotations_{_safe_name(annotator)}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=ANNOTATION_FIELDS)
            writer.writeheader()
            for row in sorted(eligible_rows, key=lambda item: str(item["work_id"])):
                writer.writerow(
                    {
                        "work_id": row["work_id"],
                        "split": row["split"],
                        "sample_role": row["sample_role"],
                        "year": (works_by_id or {}).get(str(row["work_id"]), {}).get("year", ""),
                        "title": (works_by_id or {}).get(str(row["work_id"]), {}).get("title", ""),
                        "abstract": (works_by_id or {})
                        .get(str(row["work_id"]), {})
                        .get("abstract", ""),
                        "annotator": annotator,
                        "guide_version": guide_version,
                        "plastic_related": "",
                        "plastic_tier": "",
                        "ca_sampled": "",
                        "study_type": "",
                        "domain_tags": "",
                        "evidence_snippet": "",
                        "evidence_source": "",
                        "decision_status": "",
                        "adjudicated_value": "",
                        "adjudication_rationale": "",
                    }
                )
        outputs.append(path)
    return outputs


def _safe_name(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in value).strip("_")
    if not safe:
        raise ValueError("annotator name must contain a filename-safe character")
    return safe


def _normalize_row(
    row: dict[str, str], split_index: dict[str, dict[str, Any]], guide_version: str
) -> dict[str, Any]:
    work_id = (row.get("work_id") or "").strip()
    if work_id not in split_index:
        raise ValueError(f"unknown work_id: {work_id}")
    expected = split_index[work_id]
    if (row.get("split") or "").strip() != expected["split"] or (
        row.get("sample_role") or ""
    ).strip() != expected["sample_role"]:
        raise ValueError(f"split metadata conflict for {work_id}")
    if (row.get("guide_version") or "").strip() != guide_version:
        raise ValueError(f"guide version mismatch for {work_id}")
    annotator = (row.get("annotator") or "").strip()
    if not annotator:
        raise ValueError(f"missing annotator for {work_id}")
    result: dict[str, Any] = {key: (row.get(key) or "").strip() for key in ANNOTATION_FIELDS}
    result.update(split=expected["split"], sample_role=expected["sample_role"], annotator=annotator)
    status = result["decision_status"]
    if status not in _STATUSES:
        raise ValueError(f"invalid decision_status for {work_id}: {status!r}")
    if status == "adjudication_required":
        if any(result[field] for field in LABEL_FIELDS) or result["domain_tags"]:
            raise ValueError(f"unresolved work {work_id} must not contain labels")
        if not result["evidence_snippet"]:
            raise ValueError(f"unresolved work {work_id} needs evidence or a decision note")
    else:
        if result["plastic_related"] not in _TRUTH:
            raise ValueError(f"invalid plastic_related for {work_id}")
        related = result["plastic_related"] == "true"
        if related and result["plastic_tier"] not in _TIERS:
            raise ValueError(f"invalid plastic_tier for {work_id}")
        if not related and result["plastic_tier"]:
            raise ValueError(f"negative work {work_id} cannot have a plastic_tier")
        # A negative work needs no further labels (owner, 2026-11-11): ca_sampled and
        # study_type are optional there and scored only on plastic-relevant gold (eval.py).
        if (related or result["ca_sampled"]) and result["ca_sampled"] not in _SAMPLING:
            raise ValueError(f"invalid ca_sampled for {work_id}")
        if related and not result["study_type"]:
            raise ValueError(f"missing study_type for {work_id}")
        tags = [tag.strip() for tag in result["domain_tags"].split("|") if tag.strip()]
        if len(tags) != len(set(tags)) or set(tags) - set(DOMAIN_TAGS):
            raise ValueError(f"invalid or duplicate domain_tags for {work_id}")
        result["domain_tags"] = sorted(tags)
        if bool(result["evidence_snippet"]) != bool(result["evidence_source"]):
            raise ValueError(f"evidence snippet and source must be supplied together for {work_id}")
        if result["evidence_source"] and result["evidence_source"] not in _SOURCES:
            raise ValueError(f"invalid evidence_source for {work_id}")
    if result["sample_role"] == "leak_test" and result["split"] != "test":
        raise ValueError(f"leak-test work {work_id} must remain in test")
    if result["adjudicated_value"] and not result["adjudication_rationale"]:
        raise ValueError(f"adjudication rationale required for {work_id}")
    return result


def import_annotations(
    paths: list[str | Path],
    split_rows: list[dict[str, Any]],
    *,
    guide_version: str,
    works_by_id: dict[str, dict[str, Any]] | None = None,
    include_test: bool = False,
) -> list[dict[str, Any]]:
    """Validate independent exports against frozen IDs/splits and guide version."""
    split_index = {str(row["work_id"]): row for row in split_rows}
    if len(split_index) != len(split_rows):
        raise ValueError("split manifest contains duplicate work_id values")
    imported: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path_value in paths:
        path = Path(path_value)
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != list(ANNOTATION_FIELDS):
                raise ValueError(f"annotation header mismatch in {path}")
            for row in reader:
                item = _normalize_row(row, split_index, guide_version)
                if item["split"] == "test" and not include_test:
                    raise ValueError("test-label import requires explicit include_test=True")
                if works_by_id is not None:
                    source = works_by_id.get(item["work_id"])
                    if source is None or any(
                        str(row.get(field) or "") != str(source.get(field) or "")
                        for field in ("year", "title", "abstract")
                    ):
                        raise ValueError(f"source metadata conflict for {item['work_id']}")
                key = (item["work_id"], item["annotator"])
                if key in seen:
                    raise ValueError(f"duplicate annotation for work/annotator: {key}")
                seen.add(key)
                imported.append(item)
    return sorted(imported, key=lambda item: (item["work_id"], item["annotator"]))


def _kappa(left: list[str], right: list[str]) -> dict[str, Any]:
    n = len(left)
    if not n:
        return {"n": 0, "observed_agreement": None, "kappa": None, "status": "no_pairs"}
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / n
    categories = set(left) | set(right)
    expected = sum(Counter(left)[cat] * Counter(right)[cat] for cat in categories) / (n * n)
    if expected == 1:
        return {
            "n": n,
            "observed_agreement": observed,
            "kappa": None,
            "status": "undefined_single_category",
        }
    return {
        "n": n,
        "observed_agreement": observed,
        "kappa": (observed - expected) / (1 - expected),
        "status": "ok",
    }


def _disagreement_items(by_work: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    items = []
    fields = list(LABEL_FIELDS) + [f"domain:{tag}" for tag in DOMAIN_TAGS]
    for work_id, values in sorted(by_work.items()):
        unresolved = any(row["decision_status"] != "complete" for row in values)
        if len(values) < 2 and not unresolved:
            continue
        annotations = {row["annotator"]: row for row in values}
        differing: dict[str, dict[str, Any]] = {}
        for field in fields:
            observed = {}
            for annotator, row in annotations.items():
                if field.startswith("domain:"):
                    tag = field.split(":", 1)[1]
                    value = tag in row["domain_tags"]
                else:
                    value = row[field]
                observed[annotator] = value
            if len({json.dumps(value, sort_keys=True) for value in observed.values()}) > 1:
                differing[field] = observed
        if differing or unresolved:
            items.append(
                {
                    "work_id": work_id,
                    "split": values[0]["split"],
                    "sample_role": values[0]["sample_role"],
                    "review_status": "unresolved",
                    "fields": differing,
                    "annotations": {
                        annotator: {
                            "decision_status": row["decision_status"],
                            "evidence_snippet": row["evidence_snippet"],
                            "evidence_source": row["evidence_source"],
                        }
                        for annotator, row in sorted(annotations.items())
                    },
                    "adjudication": {"value": None, "rationale": None},
                }
            )
    return items


def agreement_summary(rows: list[dict[str, Any]], *, split: str | None = None) -> dict[str, Any]:
    """Compute pairwise per-field Cohen kappa; test rows are opt-in by split."""
    split_rows = [row for row in rows if split is None or row["split"] == split]
    selected = [row for row in split_rows if row["decision_status"] == "complete"]
    by_work: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        by_work[row["work_id"]].append(row)
    review_by_work: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in split_rows:
        review_by_work[row["work_id"]].append(row)
    annotators = sorted({row["annotator"] for row in selected})
    pairs = [
        (annotators[i], annotators[j])
        for i in range(len(annotators))
        for j in range(i + 1, len(annotators))
    ]
    labels: dict[str, Any] = {}
    fields = list(LABEL_FIELDS)
    fields.extend(f"domain:{tag}" for tag in DOMAIN_TAGS)
    for first, second in pairs:
        pair_rows = [
            (work_id, {row["annotator"]: row for row in values})
            for work_id, values in sorted(by_work.items())
            if {row["annotator"] for row in values} >= {first, second}
        ]
        for field in fields:
            left_values, right_values = [], []
            for _, values in pair_rows:
                a, b = values[first], values[second]
                if field.startswith("domain:"):
                    tag = field.split(":", 1)[1]
                    left_values.append(str(tag in a["domain_tags"]))
                    right_values.append(str(tag in b["domain_tags"]))
                else:
                    left_values.append(str(a[field]))
                    right_values.append(str(b[field]))
            labels[f"{first}__{second}__{field}"] = _kappa(left_values, right_values)
    return {
        "schema_version": "annotation_agreement_v1",
        "guide_version": rows[0]["guide_version"] if rows else None,
        "split_filter": split,
        "annotators": annotators,
        "double_annotated_works": sum(1 for values in by_work.values() if len(values) >= 2),
        "labels": labels,
        "disagreements": _disagreement_items(review_by_work),
        "interpretation": "No adjudication or performance-threshold claim is made by this report.",
    }


def write_agreement_report(
    rows: list[dict[str, Any]], output: str | Path, *, split: str | None = None
) -> Path:
    report = agreement_summary(rows, split=split)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
