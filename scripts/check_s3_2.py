"""Acceptance checks for the S3.2 static app shell.

The check is intentionally dependency-light: it validates the single-file
shell's required accessibility/data hooks and exercises the committed S3.1
fixture payloads without contacting OpenAlex.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DATA = SITE / "data"


def _read_json(name: str) -> dict:
    path = DATA / name
    assert path.exists(), f"missing site data payload: {path}"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{name} must be a JSON object"
    return payload


def main() -> None:
    html_path = SITE / "index.html"
    html = html_path.read_text(encoding="utf-8")
    required_markers = {
        "skip link": 'href="#main-content"',
        "tablist": 'role="tablist"',
        "Experts tab": 'data-tab="experts"',
        "Institutions tab": 'data-tab="institutions"',
        "Monitoring stub": 'data-tab="monitoring"',
        "Funding stub": 'data-tab="funding"',
        "About tab": 'data-tab="about"',
        "hash state": "window.location.hash",
        "CSV export": "text/csv;charset=utf-8",
        "data fetch": "data/index.json",
        "responsive layout": "@media (max-width",
    }
    for label, marker in required_markers.items():
        assert marker in html, f"app shell is missing {label}: {marker}"
    assert re.search(r'<main\s+id="main-content"', html), "main landmark is missing"
    assert html.count('role="tab"') == 5, "S3.2 requires exactly five navigation tabs"
    assert html.count('role="tabpanel"') == 5, "every tab needs a panel"

    index = _read_json("index.json")
    institutions = _read_json("institutions.json")
    aggregates = _read_json("aggregates.json")
    metadata = _read_json("build_metadata.json")
    assert index.get("schema_version") == "s3.1"
    assert isinstance(index.get("authors"), list) and index["authors"], "fixture authors are empty"
    assert isinstance(index.get("works"), list) and index["works"], "fixture works are empty"
    assert isinstance(institutions.get("institutions"), list) and institutions["institutions"], (
        "fixture institutions are empty"
    )
    assert {"by_year", "by_type", "by_tag"} <= set(aggregates), "aggregate contract is incomplete"
    assert metadata.get("schema_version") == "s3.1"
    assert metadata.get("payload_gzip_bytes", 0) < 3_000_000, (
        "fixture exceeds the C5 payload budget"
    )
    print(
        "S3.2 acceptance passed: accessible five-tab shell, hash/CSV hooks, "
        f"and fixture payloads ({len(index['authors'])} authors, {len(index['works'])} works)"
    )


if __name__ == "__main__":
    main()
