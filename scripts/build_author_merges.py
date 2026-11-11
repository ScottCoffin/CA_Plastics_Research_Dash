"""Auto-merge OpenAlex author records that share a name and an institution.

Owner rule (2026-11-11): authors with the same name at the same institution are one
person. Names are compared after Unicode accent folding, lower-casing and removing
punctuation ("Andrew B. Gray" == "andrew b gray"; "Andrew Gray" stays separate).
Two records match when they share at least one institution ID in their authorships;
matches are closed transitively. The canonical record is the one with the most
CA-affiliated works, then most works, then the lowest ID.

Rows whose reason starts with the rule marker are regenerated on every run; any
hand-written rows in ``curation/author_merges.csv`` are kept, and their source IDs
are never re-merged. ``--check`` exits 1 when the committed file is stale.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

MERGES = Path("curation/author_merges.csv")
HEADER = ["from_author_id", "to_author_id", "reason", "reviewed_by", "reviewed_at"]
MARKER = "auto: same name and institution"
RULE_DATE = "2026-11-11"


def normalize_name(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name or "")
    folded = "".join(c for c in folded if not unicodedata.combining(c)).lower()
    folded = re.sub(r"[^a-z\s]", " ", folded.replace("‐", "-").replace("-", " "))
    return " ".join(folded.split())


def merge_rows(
    authors: list[dict], authorships: list[dict], keep: set[str] = frozenset()
) -> list[dict[str, str]]:
    names = {a["author_id"]: normalize_name(a.get("name") or "") for a in authors}
    stats = {
        a["author_id"]: (int(a.get("ca_works_count") or 0), 0) for a in authors if a["author_id"]
    }
    works: dict[str, set[str]] = defaultdict(set)
    by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in authorships:
        author = row.get("author_id")
        if not author or author in keep or not names.get(author):
            continue
        works[author].add(row.get("work_id"))
        for inst in row.get("institution_ids") or []:
            by_key[(names[author], inst)].add(author)
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for members in by_key.values():
        first, *rest = sorted(members)
        for other in rest:
            parent[find(other)] = find(first)
    groups: dict[str, list[str]] = defaultdict(list)
    for author in parent:
        groups[find(author)].append(author)
    rows = []
    for members in groups.values():
        if len(members) < 2:
            continue
        canonical = min(
            members, key=lambda a: (-stats.get(a, (0, 0))[0], -len(works.get(a, ())), a)
        )
        for member in sorted(members):
            if member != canonical:
                rows.append(
                    {
                        "from_author_id": member,
                        "to_author_id": canonical,
                        "reason": f"{MARKER} ({names[canonical]})",
                        "reviewed_by": "SC (rule)",
                        "reviewed_at": RULE_DATE,
                    }
                )
    return sorted(rows, key=lambda r: (r["to_author_id"], r["from_author_id"]))


def render(
    existing: Path,
    authors_path: Path,
    authorships_path: Path,
) -> str:
    kept: list[dict[str, str]] = []
    if existing.exists():
        with existing.open(encoding="utf-8", newline="") as stream:
            kept = [r for r in csv.DictReader(stream) if not r["reason"].startswith(MARKER)]
    manual = {r["from_author_id"] for r in kept} | {r["to_author_id"] for r in kept}
    authors = pq.read_table(authors_path, columns=["author_id", "name", "ca_works_count"])
    authorships = pq.read_table(
        authorships_path, columns=["work_id", "author_id", "institution_ids"]
    )
    rows = merge_rows(authors.to_pylist(), authorships.to_pylist(), keep=manual)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=HEADER, lineterminator="\n")
    writer.writeheader()
    for row in [*kept, *rows]:
        writer.writerow({k: row.get(k, "") for k in HEADER})
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=MERGES)
    parser.add_argument(
        "--authors", type=Path, default=Path("data/processed/normalized/authors.parquet")
    )
    parser.add_argument(
        "--authorships", type=Path, default=Path("data/processed/normalized/authorships.parquet")
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = render(args.output, args.authors, args.authorships)
    current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
    if args.check:
        if current.replace("\r\n", "\n") != text:
            print(f"{args.output} is stale; run scripts/build_author_merges.py", file=sys.stderr)
            return 1
        return 0
    args.output.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {text.count(chr(10)) - 1} merge rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
