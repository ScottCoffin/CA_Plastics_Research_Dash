"""Acceptance checks for the S3.4 Institutions workflow."""

from __future__ import annotations

import json
from pathlib import Path

SITE = Path("site")


def main() -> None:
    html = (SITE / "index.html").read_text(encoding="utf-8")
    required = {
        "institution type chips": 'id="institution-type-chips"',
        "institution leaderboard": 'id="institution-list"',
        "institution count": 'id="institution-count"',
        "sparklines": 'class="sparkline"',
        "clustered map": 'id="institution-map"',
        "Experts links": "institution-expert-link",
        "tagged-work metric": "tagged works all time",
    }
    for label, marker in required.items():
        assert marker in html, f"S3.4 shell is missing {label}: {marker}"

    payload = json.loads((SITE / "data" / "institutions.json").read_text(encoding="utf-8"))
    index = json.loads((SITE / "data" / "index.json").read_text(encoding="utf-8"))
    institutions = payload.get("institutions", [])
    works = index.get("works", [])
    qualifying = {
        institution["inst_id"]
        for institution in institutions
        if any(
            work.get("plastic_related") is True
            and institution["inst_id"] in (work.get("institution_ids") or [])
            for work in works
        )
    }
    assert qualifying, "fixture has no tagged institutions"
    assert "I84218800" in qualifying, "California fixture institution is absent"
    assert "clusterMap" in html and "institution-map-marker" in html
    print(
        f"S3.4 acceptance passed: {len(qualifying)} qualifying institutions, "
        "leaderboard, trends, type chips, map, and Experts links verified"
    )


if __name__ == "__main__":
    main()
