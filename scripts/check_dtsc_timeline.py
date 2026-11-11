"""Offline acceptance check for EM-18: curated DTSC regulatory timeline.

Validates config/dtsc_timeline.yml with src/atlas/dtsc_timeline.py. Makes no network calls.
Exit code 0 when the file validates, 1 otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.dtsc_timeline import DEFAULT_PATH, TimelineError, load_timeline  # noqa: E402


def main() -> int:
    try:
        data = load_timeline(DEFAULT_PATH)
    except (TimelineError, OSError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1
    entries = data["entries"]
    linked = sum(1 for e in entries if e["source_url"])
    print(f"PASS: {len(entries)} entries validated, {linked} with source_url, order newest_first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
