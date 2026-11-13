"""UX-16: every count-based /app/ view carries a "volume, not strength" caption."""

from __future__ import annotations

from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "framework" / "src"


@pytest.mark.parametrize("page", ["experts.md", "funding.md", "evidence.md"])
def test_count_views_have_volume_caption(page: str) -> None:
    text = (SRC / page).read_text(encoding="utf-8")
    assert text.count('class="data-note volume-caption"') == 1, page
    assert "not strength" in text or "not the strength" in text, page


def test_institutions_keeps_its_original_caption() -> None:
    assert "it is not a quality ranking" in (SRC / "institutions.md").read_text(encoding="utf-8")
