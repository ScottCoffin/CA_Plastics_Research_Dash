"""Build the owner-only expert contact list for outreach (S9.6a).

Reads raw OpenAlex work snapshots under ``data/raw/openalex_works/`` and the expert
list in ``site/data/index.json``, then writes ``data/private/outreach_contacts.csv``.
Only emails printed in a work's ``raw_affiliation_strings`` on that expert's own
authorship are used. Opt-outs in ``data/private/outreach_optout.csv`` are removed. No network.

Stdout carries counts only; no email address is ever printed.

    py -3.14 scripts/build_outreach_contacts.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from atlas.outreach.contacts import (  # noqa: E402
    REPO_ROOT,
    contacts_from_openalex_works,
    email_matches_name,
    merge_opt_outs,
    short_openalex_id,
    write_contacts,
)


def _works_from_file(path: Path) -> list[dict] | None:
    """Return works from a page body (``results``) or a bare list; None if unreadable."""

    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(body, dict) and isinstance(body.get("response"), dict):
        body = body["response"]  # ingest snapshots wrap the page body
    if isinstance(body, dict) and isinstance(body.get("results"), list):
        return [work for work in body["results"] if isinstance(work, dict)]
    if isinstance(body, list):
        return [work for work in body if isinstance(work, dict)]
    return None


def _iter_works(raw_dir: Path) -> Iterator[dict]:
    if not raw_dir.is_dir():
        return
    for path in sorted(raw_dir.glob("**/*.json")):
        works = _works_from_file(path)
        if works:
            yield from works


def _load_experts(index_path: Path) -> dict[str, str]:
    """Return expert short author id -> display name from ``index.json`` ``authors``."""

    if not index_path.exists():
        return {}
    body = json.loads(index_path.read_text(encoding="utf-8"))
    experts: dict[str, str] = {}
    for author in body.get("authors", []) if isinstance(body, dict) else []:
        if not isinstance(author, dict):
            continue
        author_id = short_openalex_id(author.get("author_id"))
        if author_id:
            experts[author_id] = str(author.get("name") or "")
    return experts


def main(argv: list[str] | None = None, root: Path = REPO_ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--index", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="print counts; write nothing")
    args = parser.parse_args(argv)

    private = root / "data" / "private"
    raw_dir = args.raw_dir or root / "data" / "raw" / "openalex_works"
    index_path = args.index or root / "site" / "data" / "index.json"
    output = args.output or private / "outreach_contacts.csv"

    experts = _load_experts(index_path)
    found = contacts_from_openalex_works(_iter_works(raw_dir), set(experts))

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [
        {
            "author_id": author_id,
            "name": experts.get(author_id, ""),
            "email": email,
            "source": "openalex_affiliation",
            "first_seen_utc": stamp,
        }
        for author_id in sorted(found)
        for email in sorted(found[author_id])
        # Keep only addresses whose local part matches this expert's name.
        if email_matches_name(email, experts.get(author_id, ""))
    ]
    kept, removed = merge_opt_outs(rows, private / "outreach_optout.csv")

    print(f"experts total: {len(experts)}")
    print(f"experts with >=1 email: {len({row['author_id'] for row in kept})}")
    print(f"emails total: {len(kept)}")
    print(f"opt-outs removed: {removed}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    write_contacts(output, kept, root=root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
