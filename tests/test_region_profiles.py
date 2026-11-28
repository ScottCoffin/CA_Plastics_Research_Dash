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


def test_profile_stylesheet_matches_the_canonical_brand_tokens() -> None:
    tokens = BRP.TOKENS.read_text(encoding="utf-8")
    css = BRP.render_profile_css(tokens)
    assert BRP.PROFILE_CSS.read_text(encoding="utf-8") == css
    assert css.count("--pv-ground:") == 1
    assert "SchibstedGrotesk-Variable-latin.woff2" in css
    assert "MartianMono-Regular-latin.woff2" in css
    assert "https://" not in css


def test_profile_generator_checks_crlf_token_and_css_copies(tmp_path: Path, monkeypatch) -> None:
    canonical_tokens = BRP.TOKENS.read_text(encoding="utf-8")
    expected_css = BRP.render_profile_css(canonical_tokens)
    tokens = tmp_path / "tokens.css"
    stylesheet = tmp_path / "pv-profile.css"
    source = tmp_path / "expert.html"
    tokens.write_bytes(canonical_tokens.replace("\n", "\r\n").encode("utf-8"))
    stylesheet.write_bytes(expected_css.replace("\n", "\r\n").encode("utf-8"))
    source.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(BRP, "ROOT", tmp_path)
    monkeypatch.setattr(BRP, "SOURCE", source)
    monkeypatch.setattr(BRP, "TOKENS", tokens)
    monkeypatch.setattr(BRP, "PROFILE_CSS", stylesheet)
    monkeypatch.setattr(BRP, "REGIONS", ())

    assert BRP.main(["--check"]) == 0


def test_region_copy_reads_its_own_data_folder_only() -> None:
    page = BRP.render(BRP.SOURCE.read_text(encoding="utf-8"), "norway")
    assert "../data/california/" not in page
    assert page.count("../data/norway/") == 5
    assert "S.badgesPromise = Promise.resolve(null);" in page
    assert "../assets/pv-profile.css" in page
    assert 'href="../"' in page
    assert "logo_282.webp" in page


def test_a_changed_california_page_fails_loudly() -> None:
    with pytest.raises(ValueError):
        BRP.render("<html>no expected markers</html>", "norway")
