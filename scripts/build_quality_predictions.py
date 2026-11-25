"""BQ-1.1b: write the prediction CSVs that ``scripts/bq1_estimate.py --predictions`` reads.

    py -3.14 scripts/build_quality_predictions.py [--ca-export-dir scratch/bq1/export_ca]

Writes (ignored, under ``data/processed/quality/``):

- ``predictions_california.csv``: one row per normalized California work. The displayed
  ``plastic_related``, tier, tags and study type come from the public export run in-process
  (``atlas.build.export_site.export_site``), so the curation precedence (owner review, AT-1
  overrides, accepted model labels, rule) is applied exactly as the site applies it. Works the
  export does not publish (non-CA authorship or suppressed) fall back to the rule label in
  ``data/processed/work_labels.parquet`` with ``label_source`` prefixed ``unpublished_``.
- ``predictions_global.csv``: one row per scored global frame row
  (``curation/gold_global_frame_v1.csv``). Global works are unscreened, so every query hit has
  ``pred_plastic_related = true`` and ``label_source = query``; band and theme group come from the
  frame, language from ``data/processed/global/works.parquet``.

Fields the sources do not carry (CA lens, CA band, CA language, global lens and tier) are left
blank; the estimators then report ``no_domain`` for the matching estimands rather than guessing.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pyarrow.parquet as pq  # noqa: E402

NORMALIZED_WORKS = ROOT / "data" / "processed" / "normalized" / "works.parquet"
WORK_LABELS = ROOT / "data" / "processed" / "work_labels.parquet"
GLOBAL_WORKS = ROOT / "data" / "processed" / "global" / "works.parquet"
GLOBAL_FRAME = ROOT / "curation" / "gold_global_frame_v1.csv"
OUT_DIR = ROOT / "data" / "processed" / "quality"
CA_PREDICTIONS = OUT_DIR / "predictions_california.csv"
GLOBAL_PREDICTIONS = OUT_DIR / "predictions_global.csv"
DEFAULT_CA_EXPORT = ROOT / "scratch" / "bq1" / "export_ca"
COLUMNS = (
    "work_id",
    "pred_plastic_related",
    "pred_plastic_tier",
    "pred_analytic_lens",
    "pred_domain_tags",
    "pred_study_type",
    "pred_band",
    "label_source",
    "theme_group",
    "language",
)


def _bool_text(value: object) -> str:
    return "true" if value is True else "false" if value is False else ""


def _join(values: object) -> str:
    return "|".join(str(v) for v in (values or []) if str(v))


def run_ca_export(out_dir: Path) -> list[dict[str, Any]]:
    """Run the public CA export into ``out_dir`` and return its slim works (index.json)."""
    from atlas.build.export_site import export_site

    export_site(
        works_path=ROOT / "data/processed/normalized/works.parquet",
        authors_path=ROOT / "data/processed/normalized/authors.parquet",
        authorships_path=ROOT / "data/processed/normalized/authorships.parquet",
        institutions_path=ROOT / "data/processed/normalized/institutions.parquet",
        labels_path=WORK_LABELS,
        suppressions_path=ROOT / "curation/suppressions.csv",
        work_overrides_path=ROOT / "curation/overrides_works.csv",
        work_relevance_path=ROOT / "curation/work_relevance.csv",
        model_relevance_path=ROOT / "curation/work_relevance_model.csv",
        author_metrics_path=None,
        author_merges_path=ROOT / "curation/author_merges.csv",
        query_config_path=ROOT / "config/queries.yml",
        output_dir=out_dir,
        generated_at="2026-01-01T00:00:00Z",
        profiles=None,
    )
    index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
    return list(index["works"])


def ca_prediction_rows(
    work_ids: list[str],
    labels: dict[str, dict[str, Any]],
    published: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """One prediction row per California work; unpublished works use the rule label."""
    rows = []
    for work_id in work_ids:
        label = labels.get(work_id, {})
        shown = published.get(work_id)
        if shown is not None:
            row = {
                "pred_plastic_related": _bool_text(shown.get("plastic_related")),
                "pred_plastic_tier": shown.get("plastic_tier") or "",
                "pred_domain_tags": _join(shown.get("domain_tags")),
                "pred_study_type": shown.get("study_type") or "",
                "label_source": label.get("label_source") or "",
            }
        else:
            row = {
                "pred_plastic_related": _bool_text(label.get("plastic_related")),
                "pred_plastic_tier": label.get("plastic_tier") or "",
                "pred_domain_tags": _join(label.get("domain_tags")),
                "pred_study_type": "",
                "label_source": f"unpublished_{label.get('label_source') or 'none'}",
            }
        rows.append(
            {
                "work_id": work_id,
                "pred_analytic_lens": "",
                "pred_band": "",
                "theme_group": "",
                "language": "",
                **row,
            }
        )
    return rows


def global_prediction_rows(
    frame: list[dict[str, str]], languages: dict[str, str]
) -> list[dict[str, str]]:
    """Global frame rows: every query hit is a predicted plastic-related work (unscreened)."""
    return [
        {
            "work_id": r["work_id"],
            "pred_plastic_related": "true",
            "pred_plastic_tier": "",
            "pred_analytic_lens": "",
            "pred_domain_tags": "",
            "pred_study_type": "",
            "pred_band": r["band"],
            "label_source": "query",
            "theme_group": r["theme_group"],
            "language": languages.get(r["work_id"], ""),
        }
        for r in frame
    ]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def build(ca_export_dir: Path) -> dict[str, int]:
    works = pq.read_table(NORMALIZED_WORKS, columns=["work_id"]).column("work_id").to_pylist()
    label_table = pq.read_table(WORK_LABELS).to_pylist()
    labels = {r["work_id"]: r for r in label_table if r.get("work_id")}
    published = {w["work_id"]: w for w in run_ca_export(ca_export_dir)}
    ca_rows = ca_prediction_rows(sorted(set(works)), labels, published)
    _write_csv(CA_PREDICTIONS, ca_rows)

    with GLOBAL_FRAME.open(encoding="utf-8", newline="") as handle:
        frame = [r for r in csv.DictReader(handle) if float(r["score"]) > 0]
    global_table = pq.read_table(GLOBAL_WORKS, columns=["work_id", "language"]).to_pylist()
    languages = {r["work_id"]: r["language"] or "" for r in global_table}
    global_rows = global_prediction_rows(frame, languages)
    _write_csv(GLOBAL_PREDICTIONS, global_rows)
    return {"california": len(ca_rows), "global": len(global_rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ca-export-dir", type=Path, default=DEFAULT_CA_EXPORT)
    args = parser.parse_args(argv)
    counts = build(args.ca_export_dir)
    print(
        f"wrote {CA_PREDICTIONS} ({counts['california']} rows) and "
        f"{GLOBAL_PREDICTIONS} ({counts['global']} rows)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
