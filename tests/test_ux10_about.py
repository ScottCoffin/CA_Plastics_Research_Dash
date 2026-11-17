"""UX-10: About has How to cite, a licence statement matching the licence files, and plain text."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABOUT = (ROOT / "framework" / "src" / "about.md").read_text(encoding="utf-8")


def test_how_to_cite_uses_the_release_doi_and_concept_doi() -> None:
    assert '<h3 id="how-to-cite">How to cite</h3>' in ABOUT
    assert "https://doi.org/${doi}" in ABOUT
    assert "10.5281/zenodo.24124016" in ABOUT


def test_licence_matches_committed_licence_files() -> None:
    assert "<h3>Licence</h3>" in ABOUT
    assert "CC BY 4.0" in ABOUT and "CC BY 4.0" in (ROOT / "LICENSE-DATA.md").read_text("utf-8")
    assert "MIT licence" in ABOUT and "MIT License" in (ROOT / "LICENSE").read_text("utf-8")
    # Owner 2026-11-17: the licence names link to the public licence texts, not repository files.
    assert 'href="https://opensource.org/license/mit"' in ABOUT
    assert "LICENSE-DATA.md" not in ABOUT and "/blob/main/" not in ABOUT


def test_developer_vocabulary_is_gone() -> None:
    prose_phrases = ("export build time", "search=plastic", "candidate search query", "S3.1")
    for phrase in prose_phrases:
        assert phrase not in ABOUT, phrase
    assert "./glossary" in ABOUT


def test_pipeline_health_links_are_real_links_not_literal_markup() -> None:
    # VD-18: the status and feed links sit in one html expression, not bare <a href=${...}> text.
    assert '${html`<p>Pipeline health: <a href="${classicUrl("status.html")}">' in ABOUT
    assert (
        '<a href="${classicUrl("feed.xml")}" type="application/atom+xml">'
        "Subscribe (Atom feed)</a>.</p>`}"
    ) in ABOUT
    assert "<a href=${classicUrl" not in ABOUT
