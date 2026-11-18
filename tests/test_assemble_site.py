"""PLAT-1: the global page at the root, California at /california/, no redirect stubs."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas.build.assemble import RETIRED, assemble

CLASSIC_HEAD = (
    '<html lang="en"><head><title>Classic</title>'
    '<link rel="canonical" href="https://plastiverse.live/">'
    '<meta property="og:title" content="CA Plastics Research Atlas">'
    '<meta property="og:url" content="https://plastiverse.live/">'
    '<link rel="alternate" type="application/atom+xml" title="Feed" href="feed.xml">'
    '<script type="application/ld+json">{"@type": "WebSite", "url": "https://plastiverse.live/"}'
    "</script></head><body>classic tabs</body></html>"
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
            "expert.html": "stale root expert page",
            "california/expert.html": "classic expert",
            "california/experts/A1/index.html": "seo expert",
            "california/institutions/I1/index.html": "seo institution",
            "status.html": "status",
            "feed.xml": "<feed/>",
            "data/index.json": "{}",
            "experts/A1/index.html": "stale root seo expert",
            "app/old.html": "stale app copy",
        },
    )
    _tree(
        dist,
        {
            "index.html": "<html><head><title>Global</title></head><body>global home</body></html>",
            "california/index.html": (
                "<html><head><title>CA</title></head><body>ca home</body></html>"
            ),
            "california/experts.html": "app experts",
            "california/institution.html": "app institution",
            "california/funding.html": "app funding",
            "404.html": "not found",
            "_import/components/atlas.js": "export {}",
        },
    )
    return site, dist, tmp_path / "out"


def test_global_page_at_root_and_california_pages_below(layout) -> None:
    site, dist, out = layout
    counts = assemble(site, dist, out)
    home = (out / "index.html").read_text(encoding="utf-8")
    assert "global home" in home and "classic tabs" not in home
    assert (out / "california" / "experts.html").read_text(encoding="utf-8") == "app experts"
    assert (out / "_import" / "components" / "atlas.js").is_file()
    for kept in (
        "status.html",
        "feed.xml",
        "data/index.json",
        "california/expert.html",
        "california/experts/A1/index.html",
        "california/institutions/I1/index.html",
    ):
        assert (out / kept).is_file(), kept
    assert counts["pages"] == 4
    # The source tree is left untouched.
    assert (site / "grants.html").read_text(encoding="utf-8") == "classic grants"


def test_clean_break_leaves_no_old_addresses(layout) -> None:
    site, dist, out = layout
    assemble(site, dist, out)
    for name in RETIRED:
        assert not (out / name).exists(), name
    assert not list(out.rglob("*.html.stub"))
    assert "location.replace" not in (out / "california" / "index.html").read_text("utf-8")


def test_california_home_keeps_metadata_retargeted(layout) -> None:
    site, dist, out = layout
    assemble(site, dist, out)
    home = (out / "california" / "index.html").read_text(encoding="utf-8")
    assert '<link rel="canonical" href="https://plastiverse.live/california/">' in home
    assert '<meta property="og:url" content="https://plastiverse.live/california/">' in home
    assert '"url": "https://plastiverse.live/california/"' in home
    assert 'href="../feed.xml"' in home
    root = (out / "index.html").read_text(encoding="utf-8")
    assert '<link rel="canonical" href="https://plastiverse.live/">' in root
    assert 'href="feed.xml"' in root
    assemble(site, dist, out)  # idempotent: rebuilding never duplicates the block
    again = (out / "california" / "index.html").read_text(encoding="utf-8")
    assert again.count("atlas-head-metadata") == 1


def test_in_place_assembly_for_the_deploy(layout) -> None:
    site, dist, _ = layout
    counts = assemble(site, dist, site)
    assert "global home" in (site / "index.html").read_text(encoding="utf-8")
    for name in RETIRED:
        assert not (site / name).exists(), name
    assert counts["removed"] == 5  # app, grants, sem, root expert.html, root experts/
    assert (site / "california" / "expert.html").is_file()


def test_missing_build_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "site").mkdir()
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("x", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        assemble(tmp_path / "site", tmp_path / "dist", tmp_path / "out")
