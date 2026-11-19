"""UX-10: About has How to cite, a licence statement matching the licence files, and plain text."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABOUT = (ROOT / "framework" / "src" / "california" / "about.md").read_text(encoding="utf-8")


def test_how_to_cite_uses_the_release_doi_and_concept_doi() -> None:
    assert '<h3 id="how-to-cite">How to cite</h3>' in ABOUT
    assert "https://doi.org/${doi}" in ABOUT
    assert "10.5281/zenodo.24124016" in ABOUT


def test_licence_matches_committed_licence_files() -> None:
    assert "<h3>Licence</h3>" in ABOUT
    assert "CC BY-NC 4.0" in ABOUT and "CC BY-NC 4.0" in (ROOT / "LICENSE-DATA.md").read_text(
        "utf-8"
    )
    assert "including commercially" not in ABOUT
    assert "PolyForm Noncommercial License 1.0.0" in ABOUT
    licence = (ROOT / "LICENSE").read_text("utf-8")
    assert licence.startswith("Required Notice: Copyright (c) 2026 Scott Coffin")
    assert "# PolyForm Noncommercial License 1.0.0" in licence and "MIT License" not in licence
    # Owner 2026-11-17: the licence names link to the public licence texts, not repository files.
    assert 'href="https://polyformproject.org/licenses/noncommercial/1.0.0"' in ABOUT
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


def test_licence_text_is_the_verbatim_polyform_noncommercial_1_0_0() -> None:
    # Owner 2026-11-18 (ADR-LICENSE-PFNC-2026-11-18): the code licence is PolyForm Noncommercial
    # 1.0.0, copied verbatim from polyformproject/polyform-licenses tag 1.0.0 (sha256 of the
    # upstream file below); only the Required Notice line is prepended.
    import hashlib

    text = (ROOT / "LICENSE").read_bytes().replace(b"\r\n", b"\n")
    notice, _, body = text.partition(b"\n\n")
    assert notice == b"Required Notice: Copyright (c) 2026 Scott Coffin (https://plastiverse.live)"
    digest = hashlib.sha256(body).hexdigest()
    assert digest == "c0ea4a896d2c8c394b29f9427589996db826cd501c512279ff0ed3ef48fabbe5"
