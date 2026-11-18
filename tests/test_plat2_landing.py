"""PLAT-2 landing and PLAT-2c ambassador page: static contract checks (no browser).

The browser acceptance is scripts/check_plat2.py (Playwright, run locally); these tests keep the
source honest in CI: approved copy, data/asset wiring, the ambassador role list, and the pure
helpers of the acceptance script.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
INDEX = SRC / "index.md"
ENGINE = SRC / "components" / "landing_story.js"
STYLE = SRC / "components" / "landing_story.css"
MOTION = SRC / "components" / "logo_motion.js"
SYNC = ROOT / "framework" / "scripts" / "sync_shared.mjs"
LANDING = ROOT / "site" / "assets" / "landing"


def _load_check():
    spec = importlib.util.spec_from_file_location(
        "check_plat2", ROOT / "scripts" / "check_plat2.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECK = _load_check()


def _plain(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    for entity, char in (
        ("&hellip;", "…"),
        ("&nbsp;", " "),
        ("&amp;", "&"),
        ("&ldquo;", "“"),
        ("&rdquo;", "”"),
    ):
        text = text.replace(entity, char)
    return " ".join(text.split())


def test_every_approved_caption_is_in_the_page_source() -> None:
    text = _plain(INDEX.read_text(encoding="utf-8"))
    missing = [c for c in CHECK.CAPTIONS if " ".join(c.split()) not in text]
    assert missing == []


def test_page_has_no_external_hosts_and_no_framework_interpolation() -> None:
    page = INDEX.read_text(encoding="utf-8")
    assert "fonts.googleapis" not in page and "fonts.gstatic" not in page
    assert "${" not in page
    assert "prototype" not in _plain(page).lower()


def test_page_hides_the_framework_shell_and_loads_the_engine() -> None:
    page = INDEX.read_text(encoding="utf-8")
    front = page.split("---", 2)[1]
    for key in ("sidebar: false", "header: false", "footer: false"):
        assert key in front
    assert "Schibsted Grotesk" in front and "Martian Mono" in front
    assert "U+2192" in front  # the arrow glyph the subset adds (fonts PROVENANCE.md)
    assert 'href="data:image/svg+xml;base64,' in front  # sunburst favicon
    assert 'from "./components/landing_story.js"' in page
    assert 'href="./ambassadors"' in page


def test_header_and_regions_band_link_the_global_explore_page() -> None:
    page = INDEX.read_text(encoding="utf-8")
    nav = re.search(r'<nav class="plv-nav".*?</nav>', page, re.S)
    assert nav is not None and 'href="./explore"' in nav.group(0)
    regions = page.split('id="regions"', 1)[1].split("</section>", 1)[0]
    assert 'class="plv-explore"' in regions and 'href="./explore"' in regions


def test_engine_reads_only_same_origin_data_and_assets() -> None:
    engine = ENGINE.read_text(encoding="utf-8")
    paths = set(re.findall(r'json\("([^"]+)"\)', engine))
    assert paths >= {
        "data/trend_global.json",
        "assets/landing/picnic.json",
        "assets/landing/papers.json",
        "data/global/world_raster.json",
        "assets/world/world.json",
    }
    for path in paths:
        assert (ROOT / "site" / path).is_file(), path
    assert "https://" not in re.sub(r"//.*", "", engine)


def test_engine_timeline_matches_the_spec_length() -> None:
    engine = ENGINE.read_text(encoding="utf-8")
    assert re.search(r"export const TOT = 31\.5;", engine)
    assert (
        len(
            re.findall(
                r'\["[a-z]+", \d+(?:\.\d+)?\]', engine.split("STILLS = [", 1)[1].split("];", 1)[0]
            )
        )
        == 10
    )
    css = STYLE.read_text(encoding="utf-8")
    assert "calc(31.5 * 95vh + 100vh)" in css


def test_landing_assets_referenced_by_the_page_exist() -> None:
    picnic = json.loads((LANDING / "picnic.json").read_text(encoding="utf-8"))
    for name in (picnic["blanket"]["src"], picnic["atlas"]["src"]):
        assert (LANDING / name).is_file()
    for paper in json.loads((LANDING / "papers.json").read_text(encoding="utf-8")):
        assert (LANDING / paper["src"]).is_file()
    sync = (ROOT / "framework" / "scripts" / "sync_shared.mjs").read_text(encoding="utf-8")
    for name in re.findall(r'"([a-z_0-9]+\.webp)"', sync):
        assert (LANDING / name).is_file(), name


def test_footer_logo_is_the_motion_poster_at_282_square() -> None:
    page = INDEX.read_text(encoding="utf-8")
    footer = page.split('<footer class="plv-foot"', 1)[1].split("</footer>", 1)[0]
    tags = re.findall(r"<img [^>]*>", footer)
    assert len(tags) == 1
    tag = tags[0]
    assert 'class="plv-flogo"' in tag
    assert 'src="./assets/landing/logo_motion_poster.webp"' in tag
    assert 'width="282" height="282"' in tag
    assert 'loading="lazy"' in tag
    assert (
        'alt="Plastiverse Live logo: scattered plastic fragments flow into a bright node '
        'and a network of research"' in tag
    )
    assert "logo_564.webp" not in footer
    assert 'import {mountLogoMotion} from "./components/logo_motion.js";' in page
    assert 'mountLogoMotion(document.querySelector(".plv-foot"));' in page


def test_logo_motion_module_respects_reduced_motion_and_loads_lazily() -> None:
    js = MOTION.read_text(encoding="utf-8")
    assert "export function mountLogoMotion(footer)" in js
    assert "prefers-reduced-motion: reduce" in js
    assert "IntersectionObserver" in js
    assert 'import {siteRoot} from "./atlas.js";' in js
    assert 'new URL("assets/landing/plastiverse_live.mp4", siteRoot())' in js
    assert '"Pause logo animation"' in js and '"Play logo animation"' in js
    assert "aria-hidden" in js and 'role", "img"' in js


def test_footer_animation_is_a_small_mp4_and_the_poster_is_564_square() -> None:
    video = LANDING / "plastiverse_live.mp4"
    assert video.is_file()
    assert video.stat().st_size < 1_000_000
    assert video.read_bytes()[4:8] == b"ftyp"
    with Image.open(LANDING / "logo_motion_poster.webp") as poster:
        assert poster.format == "WEBP"
        assert poster.size == (564, 564)


def test_sync_copies_the_motion_poster_with_the_other_landing_images() -> None:
    sync = SYNC.read_text(encoding="utf-8")
    block = re.search(r"LANDING_STATIC\s*=\s*\[(.*?)\]", sync, re.S)
    assert block is not None
    names = re.findall(r'"([^"]+)"', block.group(1))
    assert "logo_motion_poster.webp" in names
    # The MP4 loads at runtime from the site root; Framework must not copy it into src/.
    assert "plastiverse_live.mp4" not in names
    assert (LANDING / "logo_motion_poster.webp").is_file()


def test_ambassador_page_explains_the_role_and_shows_the_address_as_text() -> None:
    page = (SRC / "ambassadors.md").read_text(encoding="utf-8")
    text = _plain(page)
    assert "Ambassador onboarding opens soon." in text
    for duty in (
        "local institutions and experts",
        "community groups and networks",
        "monitoring data",
        "policy goals",
    ):
        assert duty in text, duty
    assert '<span class="pv-address">theplastiverse@gmail.com</span>' in page
    assert "mailto:theplastiverse@gmail.com" in page


def test_overlap_helpers() -> None:
    cap = {"cls": "cap c0 dk", "x0": 0, "y0": 0, "x1": 100, "y1": 50}
    assert CHECK.overlaps([cap], [{"kind": "picnic", "x0": 90, "y0": 40, "x1": 200, "y1": 200}])
    # touching within the 1 px tolerance is not an overlap
    assert not CHECK.overlaps([cap], [{"kind": "picnic", "x0": 99.5, "y0": 0, "x1": 200, "y1": 50}])
    assert not CHECK.overlaps([cap], [{"kind": "map", "x0": 0, "y0": 60, "x1": 100, "y1": 90}])


def test_heading_helper() -> None:
    assert CHECK.heading_problems([1, 2, 2, 2]) == []
    assert CHECK.heading_problems([2, 2]) == ["0 h1 elements (want 1)"]
    assert CHECK.heading_problems([1, 3]) == ["heading skips from h1 to h3"]
