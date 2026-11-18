"""Gold-label status counts from the owner's annotation sheet (stdlib only, read-only).

Run from the repository root:

    py -3.14 scripts/report_gold_status.py [--json] [--annotations PATH] [--splits PATH]

A work counts as labelled when its ``decision_status`` is ``complete``, the rule of
``atlas.gold_label_review.progress``. Split and sample role come from a join on ``work_id`` to
the split file. Leak-check works (``sample_role=leak_test``) form their own bucket even though the
split file stores them as ``split=test``. The evaluation set is the dev and test pool works
(ADR-GOLD-EVAL-SET-2026-11-11). The release check looks for ``curation/gold_v*`` files and
``gold_v*`` git tags.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ANNOTATIONS = ROOT / "curation" / "annotations" / "annotations_SC.csv"
DEFAULT_SPLITS = ROOT / "curation" / "splits_v2.csv"

COMPLETE = "complete"
ADJUDICATION = "adjudication_required"
EVAL_TARGET = 150  # ADR-GOLD-EVAL-SET-2026-11-11
EVAL_SPLITS = ("dev", "test")
POOL_ROLE = "pool"
LEAK_ROLE = "leak_test"
SPLIT_ORDER = ("train", "dev", "test", "leak-test")
ANNOTATION_COLUMNS = ("work_id", "decision_status", "plastic_related")
SPLIT_COLUMNS = ("work_id", "split", "sample_role")
RELEASE_GLOB = "gold_v*"
RELEASE_TAG_PREFIX = "gold_v"


def read_table(path: Path, required: Sequence[str]) -> list[dict[str, str]]:
    """Rows of a CSV with the required columns, stripped. A UTF-8 byte-order mark is accepted."""
    if not path.is_file():
        raise FileNotFoundError(f"file not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in required if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing column(s): {', '.join(missing)}")
        return [{name: (row.get(name) or "").strip() for name in required} for row in reader]


def index_by_work(rows: Sequence[dict[str, str]], path: Path) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        work_id = row["work_id"]
        if not work_id:
            raise ValueError(f"{path}: a row has a blank work_id")
        if work_id in index:
            raise ValueError(f"{path}: work_id {work_id} is listed more than once")
        index[work_id] = row
    return index


def bucket_of(split: str, sample_role: str) -> str:
    """Leak-check works are their own bucket, whatever split column they carry."""
    return "leak-test" if sample_role == LEAK_ROLE else split


def is_evaluation(split_row: dict[str, str]) -> bool:
    return split_row["split"] in EVAL_SPLITS and split_row["sample_role"] == POOL_ROLE


def _git_gold_tags(root: Path) -> list[str] | None:
    """Sorted ``gold*`` tags of the repository at ``root``; None when git cannot answer."""
    try:
        done = subprocess.run(
            ["git", "tag", "--list", "gold*"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return sorted(line.strip() for line in done.stdout.splitlines() if line.strip())


def gold_release(root: Path) -> dict[str, Any]:
    """Whether a gold release exists: a ``curation/gold_v*`` file or a ``gold_v*`` git tag."""
    files = sorted(path.name for path in (root / "curation").glob(RELEASE_GLOB) if path.is_file())
    git_tags = _git_gold_tags(root)
    release_tags = (
        None
        if git_tags is None
        else [tag for tag in git_tags if tag.startswith(RELEASE_TAG_PREFIX)]
    )
    if files or release_tags:
        status = "yes"
    elif git_tags is None:
        status = "unknown"
    else:
        status = "no"
    return {
        "status": status,
        "files": files,
        "git_tags": git_tags,
        "release_tags": release_tags,
    }


def _display(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def compute_status(annotations: Path, splits: Path, root: Path) -> dict[str, Any]:
    sheet = index_by_work(read_table(annotations, ANNOTATION_COLUMNS), annotations)
    split_index = index_by_work(read_table(splits, SPLIT_COLUMNS), splits)

    totals: Counter[str] = Counter()
    for split_row in split_index.values():
        totals[bucket_of(split_row["split"], split_row["sample_role"])] += 1

    labelled: Counter[str] = Counter()
    complete_rows = [row for row in sheet.values() if row["decision_status"] == COMPLETE]
    eval_labelled = 0
    for row in complete_rows:
        split_row = split_index.get(row["work_id"])
        if split_row is None:
            continue
        labelled[bucket_of(split_row["split"], split_row["sample_role"])] += 1
        if is_evaluation(split_row):
            eval_labelled += 1

    extra = sorted(set(totals) - set(SPLIT_ORDER))
    per_split = {
        name: {"labelled": labelled[name], "total": totals[name]} for name in [*SPLIT_ORDER, *extra]
    }
    eval_total = sum(1 for split_row in split_index.values() if is_evaluation(split_row))
    relevance = Counter(row["plastic_related"] or "(blank)" for row in complete_rows)

    return {
        "annotations": _display(annotations, root),
        "splits": _display(splits, root),
        "annotation_rows": len(sheet),
        "labelled_works": len(complete_rows),
        "adjudication_holds": sum(
            1 for row in sheet.values() if row["decision_status"] == ADJUDICATION
        ),
        "unlabelled_rows": sum(
            1 for row in sheet.values() if row["decision_status"] not in (COMPLETE, ADJUDICATION)
        ),
        "rows_without_split_entry": sum(1 for work_id in sheet if work_id not in split_index),
        "per_split": per_split,
        "evaluation_set": {
            "labelled": eval_labelled,
            "total": eval_total,
            "target": EVAL_TARGET,
            "remaining": max(EVAL_TARGET - eval_labelled, 0),
        },
        "plastic_related": dict(sorted(relevance.items())),
        "gold_release": gold_release(root),
    }


def _release_line(release: dict[str, Any]) -> str:
    if release["status"] == "yes":
        found = [*release["files"], *(release["release_tags"] or [])]
        return f"Gold release: yes ({', '.join(found)})"
    if release["status"] == "unknown":
        return "Gold release: unknown (no curation/gold_v* file; git tags could not be read)"
    return "Gold release: no (no curation/gold_v* file and no gold_v* git tag)"


def render_text(status: dict[str, Any]) -> str:
    evaluation = status["evaluation_set"]
    lines = [
        f"Annotation sheet: {status['annotations']}",
        f"Split file: {status['splits']}",
        f"Annotation rows: {status['annotation_rows']}",
        f"Unique works labelled (decision_status=complete): {status['labelled_works']}",
        "Adjudication holds (decision_status=adjudication_required): "
        f"{status['adjudication_holds']}",
        f"Unlabelled rows: {status['unlabelled_rows']}",
        f"Rows with no split-file entry: {status['rows_without_split_entry']}",
        "",
        "Labelled per split (labelled of works in the split file):",
    ]
    for name, counts in status["per_split"].items():
        lines.append(f"  {name:<10}{counts['labelled']:>4} of {counts['total']}")
    lines += [
        "",
        f"Evaluation set (dev+test pool): {evaluation['labelled']} of {evaluation['total']} "
        f"labelled; target {evaluation['target']}, remaining {evaluation['remaining']}",
        "",
        "plastic_related on labelled works:",
    ]
    if not status["plastic_related"]:
        lines.append("  (none)")
    for value, count in status["plastic_related"].items():
        lines.append(f"  {value:<10}{count:>4}")
    lines += ["", _release_line(status["gold_release"])]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gold-label status counts (read-only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=DEFAULT_ANNOTATIONS,
        help="owner annotation sheet (default: curation/annotations/annotations_SC.csv)",
    )
    parser.add_argument(
        "--splits",
        type=Path,
        default=DEFAULT_SPLITS,
        help="split file with work_id, split, sample_role (default: curation/splits_v2.csv)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args(argv)
    try:
        status = compute_status(args.annotations, args.splits, ROOT)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print(render_text(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
