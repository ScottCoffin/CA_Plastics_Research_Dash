"""UX-10: About has How to cite, a licence statement matching the licence files, and plain text."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABOUT = (ROOT / "framework" / "src" / "about.md").read_text(encoding="utf-8")


def test_how_to_cite_uses_the_release_doi_and_concept_doi() -> None:
    assert "## How to cite" in ABOUT
    assert "https://doi.org/${doi}" in ABOUT
    assert "10.5281/zenodo.24124016" in ABOUT


def test_licence_matches_committed_licence_files() -> None:
    assert "## Licence" in ABOUT
    assert "CC BY 4.0" in ABOUT and "CC BY 4.0" in (ROOT / "LICENSE-DATA.md").read_text("utf-8")
    assert "MIT licence" in ABOUT and "MIT License" in (ROOT / "LICENSE").read_text("utf-8")


def test_developer_vocabulary_is_gone() -> None:
    prose_phrases = ("export build time", "search=plastic", "candidate search query", "S3.1")
    for phrase in prose_phrases:
        assert phrase not in ABOUT, phrase
    assert "./glossary" in ABOUT
