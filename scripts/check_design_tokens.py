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
MAX_HEX_USES = 0  # VD-17: no hex literals outside tokens.css (293 before VD-1).
HEX_COLOR = re.compile(
    r"(?<![\w-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})"
    r"(?![0-9a-fA-F])"
)

# (maximum occurrences, permitted values), recorded from Framework CSS immediately
# before VD-1. A stylesheet can remove literals freely, but cannot add a new colour
# or increase its count. Tokens are intentionally excluded from this baseline.
BASELINE_HEX_BY_FILE: dict[str, tuple[int, frozenset[str]]] = {
    "style.css": (0, frozenset()),
    "components/ev_heatmap.css": (0, frozenset()),
    "components/ev_table.css": (0, frozenset()),
    "components/experts.css": (0, frozenset()),
    "components/funding.css": (0, frozenset()),
    "components/funding_viz.css": (0, frozenset()),
    "components/institution.css": (
        0,
        frozenset(),
    ),
    "components/institutions.css": (0, frozenset()),
    "components/monitoring.css": (0, frozenset()),
    "components/network.css": (0, frozenset()),
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
    print(f"OK: {total} Framework stylesheet hex uses (limit {MAX_HEX_USES}; 293 before VD-1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
