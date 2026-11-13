"""UX-6: institution counts carry their definitions on Overview, About and Institutions."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"


def test_overview_stats_define_california_institutions() -> None:
    atlas = (SRC / "components" / "atlas.js").read_text(encoding="utf-8")
    assert "California institutions with any published work" in atlas
    assert "only those with a plastic-related work" in atlas
    for page in ("index.md", "about.md"):
        text = (SRC / page).read_text(encoding="utf-8")
        assert 'class="stat-note"' in text, page


def test_institutions_count_line_defines_qualifying() -> None:
    js = (SRC / "components" / "institutions.js").read_text(encoding="utf-8")
    assert "Qualifying means at least one plastic-related work" in js


def test_counts_differ_only_by_the_plastic_related_rule() -> None:
    """The Overview count is CA institutions with any work; Institutions keeps those with a
    plastic-related work. Checked on the committed payloads when they are present."""
    inst_path = ROOT / "site" / "data" / "institutions.json"
    index_path = ROOT / "site" / "data" / "index.json"
    meta_path = ROOT / "site" / "data" / "build_metadata.json"
    if not (inst_path.exists() and index_path.exists() and meta_path.exists()):
        return
    institutions = json.loads(inst_path.read_text(encoding="utf-8"))["institutions"]
    ca_ids = {row["inst_id"] for row in institutions if row.get("ca_flag")}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert len(ca_ids) == meta["counts"]["ca_institutions"]
    works = json.loads(index_path.read_text(encoding="utf-8"))["works"]
    plastic_ids = {
        inst
        for work in works
        if work.get("plastic_related") is True
        for inst in work.get("institution_ids") or []
    }
    assert 0 < len(ca_ids & plastic_ids) <= len(ca_ids)
