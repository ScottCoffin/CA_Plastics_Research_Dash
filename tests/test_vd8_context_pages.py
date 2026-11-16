"""VD-8: page-specific presentation for Policy, Resources, About, and Glossary."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMPONENTS = SRC / "components"


def test_policy_timeline_keeps_caveat_and_fits_narrow_viewports() -> None:
    page = (SRC / "policy.md").read_text(encoding="utf-8")
    styles = (COMPONENTS / "policy.css").read_text(encoding="utf-8")
    runtime = (COMPONENTS / "policy.js").read_text(encoding="utf-8")

    assert 'id="policy-timeline"' in page
    assert "Listing does not by itself create requirements" in runtime
    assert ".pol-item::before" in styles
    assert 'grid-template-areas: "date event" "date meta"' in styles
    assert "@media (max-width: 400px)" in styles
    assert ".pol-kind::before" in styles
    assert 'a[target="_blank"]::after' in styles
    assert ".pol-caveat" in styles


def test_resources_style_steward_and_reuse_as_badges() -> None:
    page = (SRC / "resources.md").read_text(encoding="utf-8")
    styles = (COMPONENTS / "resources.css").read_text(encoding="utf-8")
    runtime = (COMPONENTS / "resources.js").read_text(encoding="utf-8")

    assert 'id="resources-root"' in page
    assert 'labelled("Steward", entry.steward)' in runtime
    assert '"Reuse terms not recorded"' in runtime
    assert ".rs-relation + .rs-field" in styles
    assert "#resources-root .rs-badge" in styles


def test_about_citation_doi_is_monospace_and_limitations_remain_visible() -> None:
    page = (SRC / "about.md").read_text(encoding="utf-8")
    styles = (COMPONENTS / "about.css").read_text(encoding="utf-8")

    assert 'href="./components/about.css"' in page
    assert '<section class="card about-citation-card">' in page
    assert "10.5281/zenodo.24124016" in page
    assert '<section class="card about-limitations-card">' in page
    assert "no validated precision or recall is available yet" in page
    assert "font-family: ui-monospace" in styles
    assert "#observablehq-main p a" in styles
    assert "min-height: 24px" in styles


def test_glossary_terms_link_to_preserved_hash_targets_and_highlight() -> None:
    page = (SRC / "glossary.md").read_text(encoding="utf-8")
    styles = (COMPONENTS / "glossary.css").read_text(encoding="utf-8")
    ids = re.findall(r'<dt id="([^"]+)">', page)
    links = re.findall(r'<a class="glossary-term-link" href="#([^"]+)">', page)

    assert 'href="./components/glossary.css"' in page
    assert len(ids) == 15
    assert len(links) == 15
    assert links == ids
    assert ".glossary-term-link" in styles
    assert ".glossary dd a" in styles
    assert "min-height: 24px" in styles
    for state in (":link", ":visited", ":hover", ":focus", ":active"):
        assert f".atlas-skip-link{state}" in styles
    assert ".atlas-skip-link:visited" in styles
    assert "color: var(--atlas-on-brand)" in styles
    assert ".glossary dt:target" in styles
    assert "var(--atlas-brand-wash)" in styles
    assert 'font-family: "Barlow Semi Condensed"' in styles
