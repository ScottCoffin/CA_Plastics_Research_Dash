"""Ratchet Framework CSS colour literals against the pre-design baseline.

The Pacific Contour palette belongs in ``framework/src/design/tokens.css``. Existing
page-specific exceptions may remain while pages are adopted, but they cannot grow
or introduce a new literal for that stylesheet.

Usage: ``py -3.14 scripts/check_design_tokens.py``
"""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK_SRC = ROOT / "framework" / "src"
TOKEN_STYLESHEET = "design/tokens.css"
MAX_HEX_USES = 292  # Strictly below the 293 literals measured before VD-1.
HEX_COLOR = re.compile(
    r"(?<![\w-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})"
    r"(?![0-9a-fA-F])"
)

# (maximum occurrences, permitted values), recorded from Framework CSS immediately
# before VD-1. A stylesheet can remove literals freely, but cannot add a new colour
# or increase its count. Tokens are intentionally excluded from this baseline.
BASELINE_HEX_BY_FILE: dict[str, tuple[int, frozenset[str]]] = {
    "style.css": (1, frozenset({"#0b3d31"})),
    "components/ev_heatmap.css": (
        29,
        frozenset(
            {
                "#000000",
                "#0b4f8a",
                "#1d2a33",
                "#1d4ed8",
                "#3b4850",
                "#5e7480",
                "#b8c4ca",
                "#e8f1fb",
                "#fff",
                "#ffffff",
            }
        ),
    ),
    "components/ev_table.css": (
        47,
        frozenset(
            {
                "#0b4f8a",
                "#1a5fb4",
                "#1d2a33",
                "#3b4850",
                "#4a5860",
                "#5f6b72",
                "#6b777e",
                "#8a9499",
                "#9cc0e6",
                "#c9d1d6",
                "#d6e7f7",
                "#e1e6ea",
                "#e8f1fb",
                "#f0f6fc",
                "#f2f5f7",
                "#ffffff",
            }
        ),
    ),
    "components/experts.css": (
        34,
        frozenset(
            {
                "#043e32",
                "#075a46",
                "#0b3d31",
                "#17324d",
                "#1f7a66",
                "#24445a",
                "#536879",
                "#5c2300",
                "#8da7af",
                "#c45100",
                "#c8d8dc",
                "#e6eff2",
                "#e9f3f1",
                "#edf7f4",
                "#fbfdfd",
                "#ffe9cf",
                "#fff",
                "#ffffff",
            }
        ),
    ),
    "components/funding.css": (
        30,
        frozenset(
            {
                "#043e32",
                "#075a46",
                "#0b3d31",
                "#17324d",
                "#3b4850",
                "#536879",
                "#7a8c92",
                "#8da7af",
                "#9cc4b0",
                "#b8c4c8",
                "#c45100",
                "#c8d8dc",
                "#d4e8e4",
                "#dcebe9",
                "#e3efed",
                "#e6f2ec",
                "#edf5f4",
                "#f1f4f5",
                "#fff",
            }
        ),
    ),
    "components/funding_viz.css": (1, frozenset({"#4a6f93"})),
    "components/institution.css": (
        0,
        frozenset(),
    ),
    "components/institutions.css": (
        1,
        frozenset({"#cfe5f2"}),
    ),
    "components/monitoring.css": (
        55,
        frozenset(
            {
                "#043e32",
                "#075a46",
                "#0b3d31",
                "#0d1b24",
                "#17324d",
                "#1d2a33",
                "#254658",
                "#2f3d45",
                "#3d5560",
                "#3f6075",
                "#536879",
                "#56656d",
                "#5b6770",
                "#7d8775",
                "#8da7af",
                "#8fa5a7",
                "#b8ced0",
                "#c45100",
                "#c8d8dc",
                "#cfe5f2",
                "#d4e8e4",
                "#e3efed",
                "#edf5f4",
                "#edf7f4",
                "#eef1f2",
                "#f1efe4",
                "#f4f8fb",
                "#fbfdfd",
                "#fff",
                "#ffffff",
            }
        ),
    ),
    "components/network.css": (
        16,
        frozenset(
            {
                "#1d2a33",
                "#3b4850",
                "#9fb3ad",
                "#c9d6d2",
                "#dfe7e4",
                "#eef5f2",
                "#fbfdfc",
                "#ffffff",
            }
        ),
    ),
}
BASELINE_TOTAL = sum(count for count, _ in BASELINE_HEX_BY_FILE.values())


def audit_stylesheets(
    css_files: Mapping[str, str],
    *,
    baseline: Mapping[str, tuple[int, frozenset[str]]] = BASELINE_HEX_BY_FILE,
    max_total: int = MAX_HEX_USES,
) -> tuple[int, list[str]]:
    """Return the number of non-token literals and any ratchet violations."""
    total = 0
    problems: list[str] = []
    for filename, content in sorted(css_files.items()):
        if filename.replace("\\", "/") == TOKEN_STYLESHEET:
            continue
        colors = [match.group(0).lower() for match in HEX_COLOR.finditer(content)]
        if not colors:
            continue
        total += len(colors)
        entry = baseline.get(filename.replace("\\", "/"))
        if entry is None:
            problems.append(f"{filename}: contains hex colours but has no VD-1 baseline")
            continue
        max_file_uses, approved = entry
        if len(colors) > max_file_uses:
            problems.append(f"{filename}: {len(colors)} hex uses exceeds baseline {max_file_uses}")
        added = sorted(set(colors) - approved)
        if added:
            problems.append(f"{filename}: new unapproved hex colours: {', '.join(added)}")

    if total > max_total:
        problems.append(f"{total} Framework stylesheet hex uses exceeds limit {max_total}")
    return total, problems


def main() -> int:
    css_files = {
        path.relative_to(FRAMEWORK_SRC).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(FRAMEWORK_SRC.rglob("*.css"))
    }
    total, problems = audit_stylesheets(css_files)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    print(f"OK: {total} Framework stylesheet hex uses (< 293; baseline {BASELINE_TOTAL})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
