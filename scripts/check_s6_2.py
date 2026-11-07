"""Acceptance check for real-source fragments and synthetic JATS fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from atlas.fulltext.jats import parse_jats


def main() -> int:
    synthetic = json.loads(
        Path("tests/fixtures/s6_2_jats_articles.json").read_text(encoding="utf-8")
    )
    assert len(synthetic) == 10, f"expected ten synthetic fixtures, found {len(synthetic)}"
    for record in synthetic:
        result = parse_jats(record["xml"])
        for target, expected_id in record["expected"].items():
            ids = {item["section_id"] for item in result["sections"][target]}
            assert (expected_id in ids) if expected_id else not ids, (
                record["article_id"],
                target,
                ids,
            )

    real = json.loads(
        Path("tests/fixtures/s6_2_real_article_fragments.json").read_text(encoding="utf-8")
    )
    assert len(real) == 10, f"expected ten real-article fixtures, found {len(real)}"
    for record in real:
        assert record["license"] == "cc by"
        result = parse_jats(record["xml"])
        for expected in record["expected_sections"]:
            rows = result["sections"][expected["target"]]
            assert any(
                row["section_id"] == expected["section_id"] and row["title"] == expected["title"]
                for row in rows
            ), (record["pmcid"], expected)
        assert result["fallback"] == record["expected_fallback"]
    print("S6.2 acceptance passed: ten real-article fragments and ten synthetic edge fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
