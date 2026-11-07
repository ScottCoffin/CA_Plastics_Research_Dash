"""Acceptance checks for the S3.3 Experts workflow.

This remains dependency-light: it checks the static UI contract and validates
that every committed fixture author has a detail document for the drawer.
Real-browser interaction and the screenshot are recorded separately in the
S3.3 verification note.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DATA = SITE / "data"


def main() -> None:
    html = (SITE / "index.html").read_text(encoding="utf-8")
    required = {
        "tag filter": 'id="tag-filter"',
        "institution type filter": 'id="institution-type-filter"',
        "institution filter": 'id="institution-filter"',
        "year range": 'id="year-from"',
        "CA basis filter": 'id="ca-basis-filter"',
        "OA filter": 'id="oa-filter"',
        "virtualized list": "renderVirtualRows",
        "virtual list role": 'role="list"',
        "researcher drawer": 'id="researcher-drawer"',
        "works list": "works-list",
        "report an error": "Report an error",
        "screenshot hook": "expert-link",
    }
    for label, marker in required.items():
        assert marker in html, f"S3.3 shell is missing {label}: {marker}"
    assert 'style="transform:translateY(' in html, "virtual rows must be positioned by index"
    assert "data/authors/${encodeURIComponent(authorId)}.json" in html

    index = json.loads((DATA / "index.json").read_text(encoding="utf-8"))
    authors = index.get("authors", [])
    assert authors, "fixture authors are empty"
    for author in authors:
        detail_path = DATA / "authors" / f"{author['author_id']}.json"
        assert detail_path.exists(), f"missing detail payload for {author['author_id']}"
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        assert detail.get("author", {}).get("author_id") == author["author_id"]
        assert isinstance(detail.get("works"), list)
    print(
        "S3.3 acceptance passed: filters, virtualized list, detail drawer, "
        f"and {len(authors)} author detail payloads verified"
    )


if __name__ == "__main__":
    main()
