"""Tests for the S3.8 static SEO pages and sitemaps (synthetic fixtures only)."""

from __future__ import annotations

import html as html_module
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from atlas.build.seo import (
    _doi_url,
    _orcid_url,
    _ror_url,
    build_site,
    is_safe_id,
)

BASE = "https://plastiverse.live"
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
NAME_WITH_MARKUP = "Ana <script>alert(1)</script> & Co"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    data = site / "data"
    authors = [
        {
            "author_id": "A1",
            "name": NAME_WITH_MARKUP,
            "orcid": "https://orcid.org/0000-0001-0000-0001",
            "primary_affiliations": ["UC Davis & Partners"],
            "domain_tags": ["analytical_methods", "air", "made_up_tag"],
            "work_count": 3,
            "ca_works_count": 3,
            "plastic_works_count": 2,
            "plastic_citations": 40,
            "current_in_ca": True,
            "last_ca_year": 2024,
        },
        {
            "author_id": "A2",
            "name": "Ben Lee",
            "orcid": "",
            "primary_affiliations": ["Oregon State University"],
            "domain_tags": [],
            "work_count": 1,
            "ca_works_count": 0,
            "plastic_works_count": 0,
            "plastic_citations": 0,
            "current_in_ca": False,
            "last_ca_year": 2019,
        },
        {"author_id": "../escape", "name": "Bad path"},
        {"author_id": "A3 space", "name": "Bad space"},
    ]
    _write_json(data / "index.json", {"authors": authors, "works": []})
    _write_json(
        data / "authors" / "A1.json",
        {
            "author": {"author_id": "A1", "email": "someone@example.org"},
            "works": [
                {
                    "title": "Microplastics in soil",
                    "doi": "https://doi.org/10.1000/xyz",
                    "year": 2022,
                    "journal": "Journal One",
                    "plastic_related": True,
                    "cited_by_count": 30,
                    "abstract": "SECRET ABSTRACT TEXT",
                },
                {
                    "title": "Unrelated study",
                    "doi": "10.1000/unrelated",
                    "year": 2021,
                    "journal": "Journal Two",
                    "plastic_related": False,
                    "cited_by_count": 999,
                },
                {
                    "title": "Plastic in air",
                    "doi": "10.2000/bare",
                    "year": 2023,
                    "journal": None,
                    "plastic_related": True,
                    "cited_by_count": 5,
                },
            ],
        },
    )
    _write_json(
        data / "institutions.json",
        {
            "institutions": [
                {
                    "inst_id": "I1",
                    "name": "Calif Lab",
                    "city": "Sacramento",
                    "atlas_type": "state-agency",
                    "work_count": 5,
                    "ca_flag": True,
                    "ror": "04vnq7t77",
                    "top_experts": [
                        {"author_id": "A1", "name": NAME_WITH_MARKUP},
                        {"author_id": "MISSING", "name": "Not in index"},
                    ],
                },
                {"inst_id": "I2", "name": "Outside", "work_count": 9, "ca_flag": False},
                {"inst_id": "I3", "name": "Empty", "work_count": 0, "ca_flag": True},
                {"inst_id": "../bad", "name": "Bad", "work_count": 4, "ca_flag": True},
            ]
        },
    )
    _write_json(data / "build_metadata.json", {"generated_at": "2026-11-13T16:30:47+00:00"})
    (site / "assets").mkdir(parents=True, exist_ok=True)
    (site / "assets" / "topics.js").write_text(
        "const TOPICS = {\n"
        '  analytical_methods: { label: "Analytical methods", color: "#eda100", order: 4 },\n'
        '  air: { label: "Air & atmosphere", color: "#e34948", order: 8 }\n'
        "};\n",
        encoding="utf-8",
    )
    return site


@pytest.fixture
def built(tmp_path: Path) -> tuple[Path, dict[str, int]]:
    site = _make_site(tmp_path)
    counts = build_site(site, BASE)
    return site, counts


def _jsonld(html: str) -> dict:
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert len(blocks) == 1
    return json.loads(blocks[0])


def test_builds_expert_and_institution_pages_and_skips_bad_ids(built) -> None:
    site, counts = built
    assert counts["experts"] == 2
    assert counts["institutions"] == 1
    assert sorted(p.name for p in (site / "experts").iterdir()) == ["A1", "A2"]
    assert sorted(p.name for p in (site / "institutions").iterdir()) == ["I1"]
    assert not (site / "escape").exists()
    assert (site / "experts" / "A1" / "index.html").is_file()


def test_escapes_names_and_keeps_jsonld_parseable(built) -> None:
    site, _ = built
    html = (site / "experts" / "A1" / "index.html").read_text(encoding="utf-8")
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "&amp; Partners" in html
    assert html.count("</script>") == 1
    data = _jsonld(html)
    assert data["@type"] == "Person"
    assert data["name"] == NAME_WITH_MARKUP
    assert data["knowsAbout"] == ["Analytical methods", "Air & atmosphere", "Made up tag"]
    assert data["sameAs"] == [
        "https://orcid.org/0000-0001-0000-0001",
        "https://openalex.org/A1",
    ]


def test_head_tags_are_unique_and_canonical_is_absolute(built) -> None:
    site, _ = built
    html = (site / "experts" / "A1" / "index.html").read_text(encoding="utf-8")
    assert html.count("<title>") == 1
    assert '<html lang="en">' in html
    assert html.count('<meta name="description"') == 1
    assert '<link rel="canonical" href="https://plastiverse.live/experts/A1/">' in html
    assert 'name="twitter:card" content="summary"' in html
    description = re.search(r'<meta name="description" content="([^"]*)"', html)
    assert description is not None
    assert len(html_module.unescape(description.group(1))) <= 160


def test_expert_page_links_app_and_works_without_leaking_data(built) -> None:
    site, _ = built
    html = (site / "experts" / "A1" / "index.html").read_text(encoding="utf-8")
    assert "https://plastiverse.live/expert.html#author=A1" in html
    assert "Open the interactive profile" in html
    assert "Microplastics in soil" in html
    assert 'href="https://doi.org/10.1000/xyz"' in html
    assert "https://doi.org/10.2000/bare" in html
    assert "Unrelated study" not in html
    assert "someone@example.org" not in html
    assert "SECRET ABSTRACT" not in html
    assert "abstract" not in html.lower()


def test_outside_california_line_only_for_non_ca_experts(built) -> None:
    site, _ = built
    outside = (site / "experts" / "A2" / "index.html").read_text(encoding="utf-8")
    inside = (site / "experts" / "A1" / "index.html").read_text(encoding="utf-8")
    assert "Now outside California (last California affiliation 2019)" in outside
    assert "Now outside California" not in inside


def test_institution_page_links_only_known_experts_and_uses_ror(built) -> None:
    site, _ = built
    html = (site / "institutions" / "I1" / "index.html").read_text(encoding="utf-8")
    assert html.count("<title>") == 1
    assert 'href="https://plastiverse.live/experts/A1/"' in html
    assert "MISSING" not in html
    data = _jsonld(html)
    assert data["@type"] == "Organization"
    assert data["sameAs"] == ["https://ror.org/04vnq7t77"]
    assert data["address"] == {"@type": "PostalAddress", "addressLocality": "Sacramento"}


def test_sitemap_index_and_children(built) -> None:
    site, _ = built
    index = ET.parse(site / "sitemap.xml").getroot()
    index_locs = [el.text for el in index.iter(f"{SITEMAP_NS}loc")]
    assert index_locs == [
        f"{BASE}/sitemap-pages.xml",
        f"{BASE}/sitemap-experts.xml",
        f"{BASE}/sitemap-institutions.xml",
    ]
    pages = ET.parse(site / "sitemap-pages.xml").getroot()
    page_locs = [el.text for el in pages.iter(f"{SITEMAP_NS}loc")]
    assert f"{BASE}/" in page_locs
    assert f"{BASE}/evidence" in page_locs
    assert f"{BASE}/about" in page_locs
    assert f"{BASE}/network" in page_locs
    # The Framework app is the root (H16); /app/ paths are redirect stubs, never listed.
    assert not any("/app/" in loc for loc in page_locs)
    assert not any("grants.html" in loc or "feed.xml" in loc for loc in page_locs)
    experts = ET.parse(site / "sitemap-experts.xml").getroot()
    assert [el.text for el in experts.iter(f"{SITEMAP_NS}loc")] == [
        f"{BASE}/experts/A1/",
        f"{BASE}/experts/A2/",
    ]
    institutions = ET.parse(site / "sitemap-institutions.xml").getroot()
    assert [el.text for el in institutions.iter(f"{SITEMAP_NS}loc")] == [f"{BASE}/institutions/I1/"]
    lastmods = [el.text for el in experts.iter(f"{SITEMAP_NS}lastmod")]
    assert lastmods == ["2026-11-13", "2026-11-13"]


def test_sitemap_escapes_and_stays_absolute(built) -> None:
    site, _ = built
    for name in ("sitemap-pages.xml", "sitemap-experts.xml", "sitemap-institutions.xml"):
        root = ET.parse(site / name).getroot()
        for loc in root.iter(f"{SITEMAP_NS}loc"):
            assert loc.text is not None and loc.text.startswith(f"{BASE}/")


def test_rejects_non_https_base(tmp_path: Path) -> None:
    site = _make_site(tmp_path)
    with pytest.raises(ValueError):
        build_site(site, "http://plastiverse.live")


def test_id_and_url_normalisers() -> None:
    assert is_safe_id("A5000014168")
    assert is_safe_id("CAAG-OEHHA")
    assert not is_safe_id("../x")
    assert not is_safe_id("a b")
    assert not is_safe_id("")
    assert _doi_url("10.1/abc") == "https://doi.org/10.1/abc"
    assert _doi_url("https://doi.org/10.1/abc") == "https://doi.org/10.1/abc"
    assert _doi_url("javascript:alert(1)") is None
    assert _orcid_url("https://orcid.org/0000-0001-0000-0001") is not None
    assert _orcid_url("https://example.org/x") is None
    assert _ror_url("04vnq7t77") == "https://ror.org/04vnq7t77"
    assert _ror_url("") is None
