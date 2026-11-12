"""Build the AT-2 institution type carry-forward, v3.1 ranking and review queue.

Offline and deterministic. Reads committed inputs only and writes:

- ``config/institution_types.csv``: one row per California institution used on the
  site (``ca_flag`` true and at least one work), with its type and provenance.
- ``data/processed/institution_review_needs_v31.csv``: institutions newly in the
  v3.1 top 100 that were not in the old top-100 review list.
- ``docs/AT_2_VERIFICATION.md``: counts, method, top-20 ranking and new entrants.

``--check`` regenerates the outputs in memory and exits 1 when any committed output
is missing or differs from what the inputs produce.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from atlas.ingest.institutions import ATLAS_TYPES
from atlas.ingest.state_agencies import load_state_agencies

ROOT = Path(__file__).resolve().parents[1]
TOP_N = 100
TOP_TABLE_N = 20
TYPES_HEADER = (
    "inst_id",
    "display_name",
    "atlas_type",
    "type_source",
    "parent_id",
    "v31_work_count",
    "v31_rank",
    "needs_review",
)
REVIEW_HEADER = (
    "review_rank",
    "openalex_id",
    "display_name",
    "plastic_work_count",
    "proposed_atlas_type",
    "owner_atlas_type",
    "owner_reviewed_at",
    "owner_notes",
)


@dataclass(frozen=True)
class Paths:
    registry: Path = ROOT / "data/processed/institutions.parquet"
    corpus_institutions: Path = ROOT / "data/processed/normalized/institutions.parquet"
    authorships: Path = ROOT / "data/processed/normalized/authorships.parquet"
    works_overrides: Path = ROOT / "curation/overrides_works.csv"
    type_overrides: Path = ROOT / "config/institution_overrides.csv"
    old_top100: Path = ROOT / "data/processed/institution_review_top100.csv"
    site_institutions: Path = ROOT / "site/data/institutions.json"
    out_types: Path = ROOT / "config/institution_types.csv"
    out_review: Path = ROOT / "data/processed/institution_review_needs_v31.csv"
    out_doc: Path = ROOT / "docs/AT_2_VERIFICATION.md"


@dataclass(frozen=True)
class Inputs:
    registry: Mapping[str, Mapping[str, Any]]
    corpus: Mapping[str, Mapping[str, Any]]
    authorships: Sequence[tuple[str, Sequence[str]]]
    excluded_works: frozenset[str]
    overrides: Mapping[str, str]
    old_top100: Mapping[str, Mapping[str, str]]
    site: Sequence[Mapping[str, Any]]
    overrides_rows: int = 0
    works_override_rows: int = 0
    previous_review: Mapping[str, Mapping[str, str]] = field(default_factory=dict)


@dataclass
class Build:
    config_rows: list[dict[str, str]]
    review_rows: list[dict[str, str]]
    counts: dict[str, int]
    ranked: list[str]
    summary: dict[str, Any] = field(default_factory=dict)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def load_inputs(paths: Paths = Paths()) -> Inputs:
    registry = {row["openalex_id"]: row for row in pq.read_table(paths.registry).to_pylist()}
    # Synthetic state agencies without an OpenAlex record (config/ca_state_agencies.yml).
    for agency in load_state_agencies(ROOT / "config/ca_state_agencies.yml"):
        registry.setdefault(
            agency.id,
            {
                "openalex_id": agency.id,
                "display_name": agency.name,
                "atlas_type": agency.atlas_type,
                "lineage": [agency.parent_id, agency.id] if agency.parent_id else [agency.id],
            },
        )
    corpus = {row["inst_id"]: row for row in pq.read_table(paths.corpus_institutions).to_pylist()}
    authorships = [
        (row["work_id"], row["institution_ids"] or [])
        for row in pq.read_table(
            paths.authorships, columns=["work_id", "institution_ids"]
        ).to_pylist()
    ]
    works_rows = _read_csv(paths.works_overrides)
    excluded = frozenset(
        row["work_id"] for row in works_rows if row["field"] == "exclude" and row["value"] == "true"
    )
    type_rows = _read_csv(paths.type_overrides)
    overrides: dict[str, str] = {}
    for row in type_rows:
        if row["field"] != "atlas_type":
            raise ValueError(f"unexpected override field: {row['field']}")
        if row["value"] not in ATLAS_TYPES:
            raise ValueError(f"invalid atlas_type override: {row['value']}")
        if row["inst_id"] in overrides:
            raise ValueError(f"duplicate override for {row['inst_id']}")
        overrides[row["inst_id"]] = row["value"]
    old_top100 = {row["openalex_id"]: row for row in _read_csv(paths.old_top100)}
    site = json.loads(paths.site_institutions.read_text(encoding="utf-8"))["institutions"]
    previous_review = (
        {row["openalex_id"]: row for row in _read_csv(paths.out_review)}
        if paths.out_review.exists()
        else {}
    )
    return Inputs(
        registry=registry,
        corpus=corpus,
        authorships=authorships,
        excluded_works=excluded,
        overrides=overrides,
        old_top100=old_top100,
        site=site,
        overrides_rows=len(type_rows),
        works_override_rows=len(works_rows),
        previous_review=previous_review,
    )


def work_counts(
    authorships: Iterable[tuple[str, Sequence[str]]], excluded: frozenset[str]
) -> dict[str, int]:
    """Count distinct non-excluded works per institution."""

    works: dict[str, set[str]] = defaultdict(set)
    for work_id, inst_ids in authorships:
        if work_id in excluded:
            continue
        for inst_id in inst_ids:
            works[inst_id].add(work_id)
    return {inst_id: len(found) for inst_id, found in works.items()}


def rank_california(
    counts: Mapping[str, int], corpus: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    """Rank CA institutions with works by count, ties broken by inst_id."""

    eligible = [
        inst_id
        for inst_id, count in counts.items()
        if count > 0 and corpus.get(inst_id, {}).get("ca_flag")
    ]
    return sorted(eligible, key=lambda inst_id: (-counts[inst_id], inst_id))


def roll_up_parent(inst_id: str, lineage: Sequence[str] | None) -> str:
    """Return the last lineage entry that is not the institution itself, or ''."""

    return next((value for value in reversed(lineage or []) if value != inst_id), "")


def resolve_type(inst_id: str, inputs: Inputs) -> tuple[str, str]:
    """Return (atlas_type, type_source) using owner override > owner review > rule."""

    if inst_id in inputs.overrides:
        return inputs.overrides[inst_id], "owner_override"
    if inst_id in inputs.old_top100:
        row = inputs.old_top100[inst_id]
        return row["owner_atlas_type"] or row["proposed_atlas_type"], "owner_reviewed"
    return str(inputs.registry[inst_id]["atlas_type"]), "rule"


def build(inputs: Inputs) -> Build:
    counts = work_counts(inputs.authorships, inputs.excluded_works)
    ranked = rank_california(counts, inputs.corpus)
    rank_of = {inst_id: position for position, inst_id in enumerate(ranked, 1)}
    top_ids = ranked[:TOP_N]
    new_top = [inst_id for inst_id in top_ids if inst_id not in inputs.old_top100]
    new_top_set = set(new_top)

    site_ids = sorted(
        str(row["inst_id"]) for row in inputs.site if row["ca_flag"] and int(row["work_count"]) >= 1
    )
    config_rows: list[dict[str, str]] = []
    for inst_id in site_ids:
        registry_row = inputs.registry[inst_id]
        atlas_type, source = resolve_type(inst_id, inputs)
        if atlas_type != registry_row["atlas_type"]:
            raise ValueError(
                f"{inst_id} resolves to {atlas_type} but registry has "
                f"{registry_row['atlas_type']}; rebuild the registry first"
            )
        needs_review = source == "rule" and inst_id in new_top_set
        config_rows.append(
            {
                "inst_id": inst_id,
                "display_name": str(registry_row["display_name"]),
                "atlas_type": atlas_type,
                "type_source": source,
                "parent_id": roll_up_parent(inst_id, registry_row["lineage"]),
                "v31_work_count": str(counts.get(inst_id, 0)),
                "v31_rank": str(rank_of[inst_id]) if inst_id in rank_of else "",
                "needs_review": "true" if needs_review else "false",
            }
        )

    review_rows: list[dict[str, str]] = []
    for rank, inst_id in enumerate(top_ids, 1):
        if inst_id in inputs.old_top100:
            continue
        atlas_type, _ = resolve_type(inst_id, inputs)
        previous = inputs.previous_review.get(inst_id, {})
        review_rows.append(
            {
                "review_rank": str(rank),
                "openalex_id": inst_id,
                "display_name": str(inputs.registry[inst_id]["display_name"]),
                "plastic_work_count": str(counts[inst_id]),
                "proposed_atlas_type": atlas_type,
                # Owner decisions survive a rebuild; config/institution_overrides.csv
                # is what feeds them into atlas_type.
                "owner_atlas_type": previous.get("owner_atlas_type", ""),
                "owner_reviewed_at": previous.get("owner_reviewed_at", ""),
                "owner_notes": previous.get("owner_notes", ""),
            }
        )

    sources = [row["type_source"] for row in config_rows]
    site_set = set(site_ids)
    summary: dict[str, Any] = {
        "works_excluded": len(inputs.excluded_works),
        "corpus_works": len({work_id for work_id, _ in inputs.authorships}),
        "ca_with_works": len(ranked),
        "site_rows": len(config_rows),
        "owner_override": sources.count("owner_override"),
        "owner_reviewed": sources.count("owner_reviewed"),
        "rule": sources.count("rule"),
        "needs_review": sum(1 for row in config_rows if row["needs_review"] == "true"),
        "old_top100": len(inputs.old_top100),
        "old_top100_retained": sum(1 for i in top_ids if i in inputs.old_top100),
        "old_top100_on_site": sum(1 for i in inputs.old_top100 if i in site_set),
        "new_top100": len(new_top),
        "new_top100_names": [str(inputs.registry[i]["display_name"]) for i in new_top],
        "overrides_total": inputs.overrides_rows,
        "overrides_on_site": sum(1 for i in inputs.overrides if i in site_set),
        "overrides_off_site": sorted(i for i in inputs.overrides if i not in site_set),
        "tie_at_cutoff": counts[top_ids[-1]] if top_ids else 0,
        "tie_at_cutoff_size": sum(1 for i in ranked if counts[i] == counts[top_ids[-1]]),
        "tie_first_rank": next(
            rank for rank, i in enumerate(ranked, 1) if counts[i] == counts[top_ids[-1]]
        ),
        "tie_last_rank": max(
            rank for rank, i in enumerate(ranked, 1) if counts[i] == counts[top_ids[-1]]
        ),
    }
    return Build(config_rows, review_rows, counts, ranked, summary)


def render_csv(header: Sequence[str], rows: Iterable[Mapping[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(header), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _md_table(header: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return lines


def render_doc(inputs: Inputs, result: Build) -> bytes:
    s = result.summary
    names = {row["inst_id"]: row for row in result.config_rows}
    lines = [
        "# AT-2 institution type carry-forward verification",
        "",
        "Generated by `scripts/build_institution_types.py`; do not edit by hand.",
        "Check with `py -3.14 scripts/build_institution_types.py --check`.",
        "",
        "## Counts",
        "",
        f"- Works in the v3.1 corpus: {s['corpus_works']}; excluded by "
        f"`curation/overrides_works.csv` (`exclude` = true): {s['works_excluded']}.",
        f"- California institutions with at least one non-excluded v3.1 work: "
        f"{s['ca_with_works']}.",
        f"- Site institutions (`site/data/institutions.json`, ca_flag true, work_count >= 1): "
        f"{s['site_rows']}, one row each in `config/institution_types.csv`.",
        f"- type_source: owner_override {s['owner_override']}, "
        f"owner_reviewed {s['owner_reviewed']}, rule {s['rule']}.",
        f"- needs_review true (rule-typed and in the new top 100): {s['needs_review']}.",
        f"- Old top-100 review list: {s['old_top100']} institutions; {s['old_top100_retained']} "
        f"remain in the v3.1 top 100; {s['old_top100'] - s['old_top100_retained']} drop out. "
        f"{s['old_top100_on_site']} of the old list are on the site.",
        f"- Newly in the v3.1 top 100: {s['new_top100']}; written to "
        "`data/processed/institution_review_needs_v31.csv`.",
        f"- Owner overrides: {s['overrides_total']} rows; {s['overrides_on_site']} apply to site "
        "institutions. Not used on the site (no v3.1 works): "
        + (", ".join(s["overrides_off_site"]) or "none")
        + ".",
        f"- Rank {TOP_N} is a tie: {s['tie_at_cutoff_size']} institutions share the cut-off "
        f"count of {s['tie_at_cutoff']} work(s) (ranks {s['tie_first_rank']} to "
        f"{s['tie_last_rank']}); "
        "ties are ordered by inst_id, so membership at the boundary is arbitrary.",
        "",
        "## Method",
        "",
        "- Work count: distinct `work_id` values per `institution_ids` entry in "
        "`data/processed/normalized/authorships.parquet`, skipping works with `exclude` = true.",
        "- Ranking: CA institutions (`ca_flag` true in "
        "`data/processed/normalized/institutions.parquet`) with at least one work, sorted by count "
        "descending then inst_id ascending. v31_rank is the 1-based position in that order.",
        "- type_source precedence: owner_override (`config/institution_overrides.csv`), then "
        "owner_reviewed (old top-100 list; owner accepted the proposed type), then rule "
        "(`atlas_type` in `data/processed/institutions.parquet`). The resolved type must equal the "
        "registry type; the build fails otherwise.",
        "- parent_id: the last `lineage` entry in the registry that differs from the institution's "
        "own ID; blank when there is none. Lineage order is not consistent in the source, so this "
        "is a roll-up hint for review, not a guaranteed immediate parent.",
        "- needs_review: true only for rule-typed institutions in the new top 100. "
        "Owner-overridden new entrants are listed in the review CSV for completeness but carry "
        "needs_review false.",
        "- Notes written against the old query are dropped; the owner_notes column is blank "
        "throughout. No merger or subsidiary notes exist in the data files, so roll-ups rely on "
        "the registry lineage alone.",
        "",
        f"## Top {TOP_TABLE_N} by v3.1 work count",
        "",
    ]
    top_rows = []
    for rank, inst_id in enumerate(result.ranked[:TOP_TABLE_N], 1):
        row = names.get(inst_id)
        source = row["type_source"] if row else "not on site"
        atlas = row["atlas_type"] if row else str(inputs.registry[inst_id]["atlas_type"])
        top_rows.append(
            (
                rank,
                inst_id,
                str(inputs.registry[inst_id]["display_name"]),
                result.counts[inst_id],
                atlas,
                source,
                "new" if inst_id not in inputs.old_top100 else "old top 100",
            )
        )
    lines.extend(
        _md_table(
            ("Rank", "inst_id", "Name", "v3.1 works", "Type", "Type source", "Status"),
            top_rows,
        )
    )
    lines.extend(["", "## Newly in the v3.1 top 100", ""])
    new_rows = [
        (
            row["review_rank"],
            row["openalex_id"],
            row["display_name"],
            row["plastic_work_count"],
            row["proposed_atlas_type"],
        )
        for row in result.review_rows
    ]
    lines.extend(_md_table(("Rank", "inst_id", "Name", "v3.1 works", "Proposed type"), new_rows))
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def outputs(paths: Paths, inputs: Inputs, result: Build) -> dict[Path, bytes]:
    return {
        paths.out_types: render_csv(TYPES_HEADER, result.config_rows),
        paths.out_review: render_csv(REVIEW_HEADER, result.review_rows),
        paths.out_doc: render_doc(inputs, result),
    }


def _normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if committed outputs are missing or differ from the inputs",
    )
    args = parser.parse_args(argv)
    paths = Paths()
    inputs = load_inputs(paths)
    result = build(inputs)
    rendered = outputs(paths, inputs, result)
    if args.check:
        stale = [
            path.relative_to(ROOT).as_posix()
            for path, data in rendered.items()
            if not path.exists() or _normalize(path.read_bytes()) != data
        ]
        if stale:
            print("AT-2 outputs are stale; rerun scripts/build_institution_types.py:")
            for name in stale:
                print(f"  {name}")
            return 1
        print("AT-2 outputs are current")
        return 0
    for path, data in rendered.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(
        json.dumps(
            {k: v for k, v in result.summary.items() if k != "new_top100_names"},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
