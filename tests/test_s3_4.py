from __future__ import annotations

import json
from pathlib import Path


def test_institutions_view_has_leaderboard_trends_map_and_expert_links() -> None:
    html = Path("site/index.html").read_text(encoding="utf-8")
    for marker in (
        'id="institution-type-chips"',
        'id="institution-list"',
        'id="institution-map"',
        'class="sparkline"',
        "institution-expert-link",
        "clusterMap",
    ):
        assert marker in html


def test_fixture_has_a_mappable_qualifying_california_institution() -> None:
    institutions = json.loads(Path("site/data/institutions.json").read_text(encoding="utf-8"))[
        "institutions"
    ]
    works = json.loads(Path("site/data/index.json").read_text(encoding="utf-8"))["works"]
    qualifying = {
        row["inst_id"]
        for row in institutions
        if row["ca_flag"]
        and any(
            work["plastic_related"] is True and row["inst_id"] in work["institution_ids"]
            for work in works
        )
    }
    assert "I84218800" in qualifying
