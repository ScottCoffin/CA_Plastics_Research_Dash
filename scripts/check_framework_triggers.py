"""Check the triggers for revisiting the deferred Observable Framework migration (AT-5/AT-6).

ADR-FRAMEWORK-REVISIT-2026-11-11 defers the site rewrite and names objective trigger
points. This script measures them from committed files and reports any that fired.
It never fails the build: a fired trigger prints a GitHub Actions ``::warning::``
annotation (and a plain line locally) so the lead re-opens the decision. Exit code is
0 unless ``--strict`` is given.

Triggers (any one fires):
  T1 corpus size: exported works in site/data/index.json > 10,000
  T2 payload: initial payload (top-level site/data files, gzip) > 1,500,000 bytes
     (half of the C5 3 MB budget)
  T3 A2 visual build-out: any of EM-5..EM-12 checked off, or EM-5 marked in progress
  T4 maintainability: site/index.html > 300,000 bytes, or more than 6 hand-built pages
     in site/*.html
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKS_LIMIT = 10_000
PAYLOAD_LIMIT = 1_500_000
INDEX_BYTES_LIMIT = 300_000
PAGES_LIMIT = 6
A2_VISUAL_TASKS = [f"EM-{n}" for n in range(5, 13)]


def measure(root: Path = ROOT) -> dict[str, object]:
    data = root / "site" / "data"
    index = json.loads((data / "index.json").read_text(encoding="utf-8"))
    metadata = json.loads((data / "build_metadata.json").read_text(encoding="utf-8"))
    initial = sum(
        int(item.get("gzip_bytes", 0))
        for name, item in (metadata.get("files") or {}).items()
        if "/" not in name
    )
    todo = (root / ".agent" / "TODO.md").read_text(encoding="utf-8")
    checked = [
        task
        for task in A2_VISUAL_TASKS
        if re.search(rf"^- \[x\] \*\*{re.escape(task)}\*\*", todo, re.MULTILINE)
    ]
    em5_line = re.search(r"^- \[ \] \*\*EM-5\*\*.*$", todo, re.MULTILINE)
    em5_started = bool(em5_line and re.search(r"in progress|partial", em5_line.group(0), re.I))
    pages = sorted(p.name for p in (root / "site").glob("*.html"))
    return {
        "works": len(index.get("works") or []),
        "initial_gzip_bytes": initial,
        "a2_visual_tasks_done": checked,
        "em5_started": em5_started,
        "index_html_bytes": (root / "site" / "index.html").stat().st_size,
        "pages": pages,
    }


def fired(m: dict[str, object]) -> list[str]:
    hits = []
    if int(m["works"]) > WORKS_LIMIT:
        hits.append(f"T1 corpus size: {m['works']} works > {WORKS_LIMIT}")
    if int(m["initial_gzip_bytes"]) > PAYLOAD_LIMIT:
        hits.append(f"T2 payload: {m['initial_gzip_bytes']} gzip bytes > {PAYLOAD_LIMIT}")
    if m["a2_visual_tasks_done"] or m["em5_started"]:
        hits.append(
            "T3 A2 visual build-out started: "
            + (", ".join(m["a2_visual_tasks_done"]) or "EM-5 in progress")
        )
    if int(m["index_html_bytes"]) > INDEX_BYTES_LIMIT or len(m["pages"]) > PAGES_LIMIT:
        hits.append(
            f"T4 maintainability: index.html {m['index_html_bytes']} bytes, {len(m['pages'])} pages"
        )
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit 1 when a trigger fired")
    args = parser.parse_args(argv)
    m = measure()
    hits = fired(m)
    print(
        "Framework revisit triggers: "
        f"works={m['works']} initial_gzip={m['initial_gzip_bytes']} "
        f"index_html={m['index_html_bytes']} pages={len(m['pages'])} "
        f"a2_done={m['a2_visual_tasks_done'] or 'none'}"
    )
    for hit in hits:
        message = (
            f"Revisit AT-5/AT-6 Observable Framework decision "
            f"(ADR-FRAMEWORK-REVISIT-2026-11-11): {hit}"
        )
        print(f"::warning::{message}" if os.environ.get("GITHUB_ACTIONS") else message)
    if not hits:
        print("No trigger fired; AT-5/AT-6 stay deferred.")
    return 1 if hits and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
