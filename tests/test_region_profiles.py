"""GP-2: region author-profile pages are generated from the California page and stay in step."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_region_profiles", ROOT / "scripts" / "build_region_profiles.py"
)
assert SPEC and SPEC.loader
BRP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BRP)


def test_committed_region_profiles_match_the_california_page() -> None:
    assert BRP.main(["--check"]) == 0


def test_region_copy_reads_its_own_data_folder_only() -> None:
    page = BRP.render(BRP.SOURCE.read_text(encoding="utf-8"), "norway")
    assert "../data/california/" not in page
    assert page.count("../data/norway/") == 5
    assert "S.badgesPromise = Promise.resolve(null);" in page


def test_a_changed_california_page_fails_loudly() -> None:
    with pytest.raises(ValueError):
        BRP.render("<html>no expected markers</html>", "norway")
