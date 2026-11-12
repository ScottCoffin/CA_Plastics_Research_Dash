"""Pure logic for the owner's gold-label review app (scripts/review_gold_labels_app.py).

No Streamlit here. The row rules are the ones ``atlas.nlp.annotation.import_annotations``
applies (``_normalize_row`` is called directly), so a row this module accepts is a row the
importer accepts. The sheet is read and written line by line so that rows other than the
one being saved keep their exact bytes (including the UTF-8 BOM written by
``export_templates``).
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from atlas.ingest.normalize import _abstract_from_inverted_index
from atlas.nlp.annotation import (
    _STATUSES,
    ANNOTATION_FIELDS,
    _normalize_row,
    export_templates,
)

ANNOTATOR = "SC"
GUIDE_VERSION = "guide_v2"
SHEET_NAME = f"annotations_{ANNOTATOR}.csv"
MAX_SNIPPET_CHARS = 300
SPLIT_ORDER = ("test", "dev", "train")
# Dev and test are labelled before train: dev sets thresholds, test is frozen (F3).
QUEUE_SPLIT_RANK = {"dev": 0, "test": 1, "train": 2}
VIEWS = (
    "Unlabelled (dev+test first)",
    "Unlabelled (all)",
    "All",
    "Needs adjudication",
)
# Form fields the owner edits. Save and next writes these plus decision_status only.
FORM_FIELDS = (
    "plastic_related",
    "plastic_tier",
    "ca_sampled",
    "study_type",
    "domain_tags",
    "evidence_snippet",
    "evidence_source",
)

# Display order for the radio buttons. The sets are the importer's own (annotation.py);
# tests check that these tuples cover exactly the same values.
TIER_OPTIONS = ("core", "chemicals-in-plastics")
SAMPLING_OPTIONS = ("yes", "partial", "no", "unclear")
SOURCE_OPTIONS = ("title", "abstract", "full_text_locator")

TIER_HELP = {
    "core": "Plastics, debris or particles are the primary subject (guide_v1 section 2).",
    "chemicals-in-plastics": (
        "Additives or chemicals in, from or associated with plastics, when chemical identity "
        "or exposure is central (guide_v1 section 2)."
    ),
}
SAMPLING_HELP = {
    "yes": "Explicit field collection or deployed monitoring in California land or state waters.",
    "partial": "Footprint straddles the CA boundary or includes offshore beyond 3 nm (G-4).",
    "no": "Mention, review, modelling, lab-only work, or sampling outside California.",
    "unclear": "Sampling is indicated but the site or sampling role cannot be determined.",
}

# study_type values for the dropdown. Source: docs/LABELING_GUIDE_A2_ADDENDUM.md section 1.1
# (guide_v2, the version this sheet uses); the same 14 values are listed under
# study_type.values in config/taxonomy.yml. guide_v1 (docs/LABELING_GUIDE.md) defines none.
# unclear_other is left out on purpose: the guide says it is always routed to needs_review,
# so the owner uses "Needs adjudication" for those works instead.
STUDY_TYPES: dict[str, str] = {
    "field_occurrence": (
        "Field sampling measuring levels or characteristics (environmental, biological, food, "
        "drinking water, dust, indoor air); monitoring, surveys, citizen science. A new method "
        "validated on field samples is method_development."
    ),
    "source_emission": (
        "Release from a product, material or activity. Post-release transport is pathway_load."
    ),
    "pathway_load": (
        "Concentration, flux or loading through stormwater, wastewater, agricultural runoff or "
        "air. Evaluating a control is mitigation_eval."
    ),
    "fate_transport": (
        "Degradation, weathering, sorption, settling, advection, burial. Lab or field."
    ),
    "exposure_lab_toxicity": (
        "Controlled lab exposure of organisms, tissues or cells. Cross-checked against ToMEx "
        "aquatic DOIs (EM-15)."
    ),
    "mesocosm_semifield": "Microcosm, mesocosm, enclosure.",
    "human_exposure_health": (
        "Human subjects or samples: biomonitoring, tissue detection, epidemiology. Intake "
        "estimates from literature values are modelling_risk."
    ),
    "method_development": (
        "Sampling, extraction, identification, quantification, QA/QC, interlaboratory studies."
    ),
    "modelling_risk": (
        "Transport, exposure or load models; risk assessment; threshold derivation. "
        "Meta-analysis is review_synthesis."
    ),
    "mitigation_eval": (
        "Empirical evaluation of controls: treatment, BMPs, LID, filters, alternatives, policy "
        "effectiveness."
    ),
    "policy_social": (
        "Policy analysis, economics, behaviour, equity, tribal engagement, education."
    ),
    "review_synthesis": (
        "Narrative, systematic or scoping review; meta-analysis; evidence map; bibliometric. "
        "An OpenAlex type of 'review' is only a prior."
    ),
    "data_resource": "Dataset, database, software or tool.",
    "perspective_guidance": (
        "Commentary, editorial, guidance, strategy or report with no primary data."
    ),
}


# --- corpus and sample -----------------------------------------------------------------


def normalize_work_id(text: str) -> str:
    """'1234' and ' w1234 ' both mean 'W1234'."""
    value = text.strip().upper()
    return f"W{value}" if value.isdigit() else value


def load_splits(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"work_id", "sample_role", "split"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path}: needs work_id, sample_role and split columns")
        return [dict(row) for row in reader]


LEAK_CANDIDATES = Path("data/interim/leak_candidates.parquet")
RAW_WORKS = Path("data/interim/works_raw.parquet")


def load_works(
    path: Path,
    work_ids: Iterable[str] | None = None,
    *,
    fallbacks: Sequence[Path] = (LEAK_CANDIDATES, RAW_WORKS),
) -> dict[str, dict[str, Any]]:
    """work_id -> {work_id, title, abstract, year}.

    The normalized works parquet comes first. The S4.2 leak-test works come from outside
    the corpus (``leak_candidates.parquet``), and a few pool works were collapsed or
    suppressed at normalization, so missing ids fall back to those files and then to the
    raw OpenAlex table (``raw_json``).
    """
    wanted = None if work_ids is None else set(work_ids)
    out: dict[str, dict[str, Any]] = {}

    def take(record: Mapping[str, Any]) -> None:
        work_id = str(record["work_id"])
        if (wanted is None or work_id in wanted) and work_id not in out:
            out[work_id] = {k: record.get(k) for k in ("work_id", "title", "abstract", "year")}

    for record in pq.read_table(path, columns=["work_id", "title", "abstract", "year"]).to_pylist():
        take(record)
    for fallback in fallbacks:
        if wanted is not None and wanted <= out.keys():
            break
        if not Path(fallback).exists():
            continue
        names = pq.read_schema(fallback).names
        if "raw_json" in names:
            for row in pq.read_table(fallback, columns=["openalex_id", "raw_json"]).to_pylist():
                work = json.loads(row["raw_json"] or "{}")
                take(
                    {
                        "work_id": str(row["openalex_id"]).rsplit("/", 1)[-1],
                        "title": work.get("title") or work.get("display_name") or "",
                        "abstract": _abstract_from_inverted_index(
                            work.get("abstract_inverted_index")
                        ),
                        "year": work.get("publication_year"),
                    }
                )
        elif {"work_id", "title", "year"} <= set(names):
            cols = [c for c in ("work_id", "title", "abstract", "year") if c in names]
            for record in pq.read_table(fallback, columns=cols).to_pylist():
                take(record)
    return out


def split_index(split_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["work_id"]): dict(row) for row in split_rows}


def _sheet_works(works_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Metadata for the sheet: year and title only. Abstracts stay in the parquet."""
    return {
        work_id: {
            "year": record.get("year", ""),
            "title": record.get("title", ""),
            "abstract": "",
        }
        for work_id, record in works_by_id.items()
    }


def ensure_sheet(
    path: Path,
    split_rows: Sequence[Mapping[str, Any]],
    works_by_id: Mapping[str, Mapping[str, Any]],
) -> bool:
    """Create the blank SC sheet at ``path`` if it is missing. Never overwrites.

    Returns True when a sheet was created. Every split row needs metadata in
    ``works_by_id``; ``export_templates`` enforces that and this module does not paper
    over it with blank titles.
    """
    if path.exists():
        return False
    missing = [str(row["work_id"]) for row in split_rows if str(row["work_id"]) not in works_by_id]
    if missing:
        raise ValueError(
            f"{len(missing)} split work(s) have no title/year in the works parquet "
            f"(first: {missing[0]}); the sheet cannot be created until they are present"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=path.parent) as scratch:
        (made,) = export_templates(
            list(split_rows),
            [ANNOTATOR],
            scratch,
            guide_version=GUIDE_VERSION,
            include_test=True,
            works_by_id=_sheet_works(works_by_id),
        )
        os.replace(made, path)
    return True


# --- sheet IO (byte-preserving) --------------------------------------------------------


@dataclass(frozen=True)
class _Parsed:
    bom: str
    records: list[tuple[str, list[str]]]  # (raw text including line ending, fields)


def _parse(path: Path) -> _Parsed:
    raw = path.read_bytes().decode("utf-8")
    bom = "﻿" if raw.startswith("﻿") else ""
    text = raw[len(bom) :]
    lines = io.StringIO(text, newline="").readlines()
    reader = csv.reader(lines)
    records: list[tuple[str, list[str]]] = []
    start = 0
    for fields in reader:
        end = reader.line_num
        records.append(("".join(lines[start:end]), fields))
        start = end
    if not records or records[0][1] != list(ANNOTATION_FIELDS):
        raise ValueError(f"annotation header mismatch in {path}")
    return _Parsed(bom, records)


def _as_dicts(parsed: _Parsed) -> list[tuple[int, dict[str, str]]]:
    """(record index, row dict) for data records; blank lines are skipped."""
    out = []
    for index, (_, fields) in enumerate(parsed.records[1:], start=1):
        if not fields:
            continue
        padded = fields + [""] * (len(ANNOTATION_FIELDS) - len(fields))
        out.append((index, dict(zip(ANNOTATION_FIELDS, padded, strict=False))))
    return out


def read_rows(path: Path) -> list[dict[str, str]]:
    rows = [row for _, row in _as_dicts(_parse(path))]
    seen: set[str] = set()
    for row in rows:
        if row["work_id"] in seen:
            raise ValueError(f"{path}: work_id {row['work_id']} is listed more than once")
        seen.add(row["work_id"])
    return rows


def _write_atomic(path: Path, text: str) -> None:
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(text.encode("utf-8"))
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def update_row(path: Path, work_id: str, values: Mapping[str, str]) -> None:
    """Rewrite one row's named fields. Other records keep their original bytes."""
    unknown = set(values) - set(ANNOTATION_FIELDS)
    if unknown:
        raise KeyError(f"unknown annotation field(s): {sorted(unknown)}")
    parsed = _parse(path)
    matches = [i for i, row in _as_dicts(parsed) if row["work_id"] == work_id]
    if not matches:
        raise KeyError(work_id)
    if len(matches) > 1:
        raise ValueError(f"{path}: work_id {work_id} is listed more than once")
    index = matches[0]
    raw, fields = parsed.records[index]
    terminator = "\r\n" if raw.endswith("\r\n") else "\n"
    padded = fields + [""] * (len(ANNOTATION_FIELDS) - len(fields))
    row = dict(zip(ANNOTATION_FIELDS, padded, strict=False))
    row.update({key: str(value) for key, value in values.items()})
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator=terminator).writerow(
        [row[field] for field in ANNOTATION_FIELDS]
    )
    records = list(parsed.records)
    records[index] = (buffer.getvalue(), fields)
    _write_atomic(path, parsed.bom + "".join(text for text, _ in records))


# --- validation and form mapping -------------------------------------------------------


def validate_row(
    row: Mapping[str, str],
    splits: Mapping[str, Mapping[str, Any]],
    guide_version: str = GUIDE_VERSION,
) -> dict[str, Any]:
    """Raise ValueError exactly when ``import_annotations`` would, plus the app's own limits."""
    if len(str(row.get("evidence_snippet") or "")) > MAX_SNIPPET_CHARS:
        raise ValueError(f"evidence snippet is longer than {MAX_SNIPPET_CHARS} characters")
    return _normalize_row(dict(row), dict(splits), guide_version)


def values_from_form(form: Mapping[str, Any], decision_status: str) -> dict[str, str]:
    """Map widget values to the sheet fields for one save.

    A negative work gets no tier and no domain tags (guide_v1 section 2). An adjudication
    hold clears every label, because the importer rejects labels on unresolved rows, and
    keeps the evidence note, which the importer requires.
    """
    if decision_status not in _STATUSES:
        raise ValueError(f"invalid decision_status: {decision_status!r}")

    def text(key: str) -> str:
        return str(form.get(key) or "").strip()

    snippet = text("evidence_snippet")
    source = text("evidence_source")
    if decision_status == "adjudication_required":
        return {
            "plastic_related": "",
            "plastic_tier": "",
            "ca_sampled": "",
            "study_type": "",
            "domain_tags": "",
            "evidence_snippet": snippet,
            "evidence_source": source,
            "decision_status": decision_status,
        }
    related = text("plastic_related") == "true"
    tags = sorted({str(tag) for tag in (form.get("domain_tags") or []) if str(tag).strip()})
    return {
        "plastic_related": text("plastic_related"),
        "plastic_tier": text("plastic_tier") if related else "",
        "ca_sampled": text("ca_sampled"),
        "study_type": text("study_type"),
        "domain_tags": "|".join(tags) if related else "",
        "evidence_snippet": snippet,
        "evidence_source": source,
        "decision_status": decision_status,
    }


def save_decision(
    path: Path,
    work_id: str,
    form: Mapping[str, Any],
    decision_status: str,
    splits: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    """Validate the merged row, then write only that row. Raises ValueError on bad input."""
    current = {row["work_id"]: row for row in read_rows(path)}
    if work_id not in current:
        raise KeyError(work_id)
    values = values_from_form(form, decision_status)
    validate_row({**current[work_id], **values}, splits)
    update_row(path, work_id, values)
    return values


# --- queues, progress and navigation ---------------------------------------------------


def is_unlabelled(row: Mapping[str, str]) -> bool:
    return row["decision_status"] not in _STATUSES


def queue(rows: Sequence[Mapping[str, str]], view: str) -> list[dict[str, str]]:
    """Work list for one view. 'Unlabelled' excludes both complete and adjudication holds."""
    by_work = sorted(rows, key=lambda row: row["work_id"])
    by_priority = sorted(
        rows,
        key=lambda row: (QUEUE_SPLIT_RANK.get(row["split"], 9), row["work_id"]),
    )
    if view == "Unlabelled (dev+test first)":
        return [dict(r) for r in by_priority if is_unlabelled(r)]
    if view == "Unlabelled (all)":
        return [dict(r) for r in by_work if is_unlabelled(r)]
    if view == "All":
        return [dict(r) for r in by_priority]
    if view == "Needs adjudication":
        return [dict(r) for r in by_work if r["decision_status"] == "adjudication_required"]
    raise ValueError(f"unknown view: {view!r}")


def progress(rows: Sequence[Mapping[str, str]]) -> dict[str, tuple[int, int]]:
    """split -> (labelled, total); 'labelled' means decision_status is complete."""
    out: dict[str, tuple[int, int]] = {}
    for split in SPLIT_ORDER:
        members = [row for row in rows if row["split"] == split]
        done = sum(1 for row in members if row["decision_status"] == "complete")
        out[split] = (done, len(members))
    return out


def find_work(rows: Sequence[Mapping[str, str]], text: str) -> dict[str, str] | None:
    if not text.strip():
        return None
    wanted = normalize_work_id(text)
    for row in rows:
        if row["work_id"] == wanted:
            return dict(row)
    return None


def position_after(before: Sequence[str], after: Sequence[str], work_id: str, pos: int) -> int:
    """Where to point after acting on ``work_id``.

    If the work left the queue, the next work has slid into its slot. If it stayed (an
    adjudication hold in the 'All' view, or a skip), move one step forward. A work that is
    not in the queue (found by search) leaves the position alone.
    """
    if work_id not in before:
        return pos
    index = before.index(work_id)
    return index if work_id not in after else index + 1
