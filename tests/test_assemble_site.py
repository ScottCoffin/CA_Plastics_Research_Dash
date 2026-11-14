"""Owner H16 switch: the Framework app becomes the site root with redirect stubs."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from atlas.build.assemble import CLASSIC_TABS, assemble, stub_html

CLASSIC_HEAD = (
    '<html lang="en"><head><title>Classic</title>'
    '<link rel="canonical" href="https://plastiverse.live/">'
    '<meta property="og:title" content="CA Plastics Research Atlas">'
    '<script type="application/ld+json">{"@type": "WebSite"}</script>'
    "</head><body>classic tabs</body></html>"
)


def _tree(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))


@pytest.fixture()
def layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    site, dist = tmp_path / "site", tmp_path / "dist"
    _tree(
        site,
        {
            "index.html": CLASSIC_HEAD,
            "grants.html": "classic grants",
            "sem.html": "classic sem",
            "expert.html": "classic expert",
            "status.html": "status",
            "feed.xml": "<feed/>",
            "data/index.json": "{}",
            "experts/A1/index.html": "seo expert",
            "institutions/I1/index.html": "seo institution",
            "app/old.html": "stale app copy",
        },
    )
    _tree(
        dist,
        {
            "index.html": "<html><head><title>App</title></head><body>app home</body></html>",
            "experts.html": "app experts",
            "institutions.html": "app institutions",
            "institution.html": "app institution",
            "funding.html": "app funding",
            "404.html": "not found",
            "_import/components/atlas.js": "export {}",
        },
    )
    return site, dist, tmp_path / "out"


def test_app_becomes_root_and_classic_files_stay(layout) -> None:
    site, dist, out = layout
    counts = assemble(site, dist, out)
    home = (out / "index.html").read_text(encoding="utf-8")
    assert "app home" in home and "classic tabs" not in home
    assert (out / "experts.html").read_text(encoding="utf-8") == "app experts"
    assert (out / "_import" / "components" / "atlas.js").is_file()
    for kept in ("status.html", "feed.xml", "data/index.json", "experts/A1/index.html"):
        assert (out / kept).is_file(), kept
    assert not (out / "app" / "old.html").exists(), "a stale /app/ copy must not survive"
    assert (site / "grants.html").read_text(encoding="utf-8") == "classic grants"
    assert counts["pages"] == 4


def test_home_keeps_classic_metadata_and_redirects_tab_hashes(layout) -> None:
    site, dist, out = layout
    assemble(site, dist, out)
    home = (out / "index.html").read_text(encoding="utf-8")
    assert '<link rel="canonical" href="https://plastiverse.live/">' in home
    assert '<meta property="og:title"' in home
    assert '"@type": "WebSite"' in home
    for tab in CLASSIC_TABS:
        assert tab in home
    assert home.index("atlas-root-switch") < home.index("</head>")
    assemble(site, dist, out)  # idempotent: rebuilding never duplicates the block
    assert (out / "index.html").read_text(encoding="utf-8").count("atlas-root-switch") == 1


def test_redirect_stubs(layout) -> None:
    site, dist, out = layout
    assemble(site, dist, out)

    def target(rel: str) -> str:
        text = (out / rel).read_text(encoding="utf-8")
        assert '<meta name="robots" content="noindex">' in text
        return re.search(r"location\.replace\(\"([^\"]*)\"", text).group(1)

    assert target("app/index.html") == "../"
    assert target("app/experts.html") == "../experts"
    assert target("app/institution.html") == "../institution"
    assert target("grants.html") == "funding"
    assert target("sem.html") == "institution"
    # No app expert page in this build: the classic full profile page stays.
    assert (out / "expert.html").read_text(encoding="utf-8") == "classic expert"
    # Safety net for hosts that serve the SEO folder for /experts: go to the file, not /experts.
    assert target("experts/index.html") == "../experts.html"
    assert target("institutions/index.html") == "../institutions.html"


def test_expert_stub_prefers_app_expert_page(layout) -> None:
    site, dist, out = layout
    (dist / "expert.html").write_text("app expert page", encoding="utf-8")
    assemble(site, dist, out)
    assert 'location.replace("expert"' in (out / "expert.html").read_text(encoding="utf-8")


def test_in_place_assembly_for_the_deploy(layout) -> None:
    site, dist, _ = layout
    assemble(site, dist, site)
    assert "app home" in (site / "index.html").read_text(encoding="utf-8")
    assert not (site / "app" / "old.html").exists()
    assert "location.replace" in (site / "app" / "index.html").read_text(encoding="utf-8")


def test_stub_keeps_hash_and_works_without_javascript() -> None:
    text = stub_html("funding", canonical="https://plastiverse.live/funding")
    assert 'location.replace("funding" + location.search + location.hash)' in text
    assert '<meta http-equiv="refresh" content="0; url=funding">' in text
    assert '<a href="funding">' in text


def test_missing_build_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "site").mkdir()
    (tmp_path / "dist").mkdir()
    with pytest.raises(FileNotFoundError):
        assemble(tmp_path / "site", tmp_path / "dist", tmp_path / "out")
