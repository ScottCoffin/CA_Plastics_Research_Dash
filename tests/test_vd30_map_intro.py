"""VD-30: the homepage map intro. The four planes are groups that carry their own California clip,
travel in from their own edges on a sampled spring played with the Web Animations API (no library:
Motion cost about 64 KB gzip, over the hero budget). It plays on every load (owner 2026-11-17)
and is guarded by reduced motion, visibility and API support. Browser checks run outside pytest.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "framework" / "src" / "california" / "index.md"
CSS = ROOT / "framework" / "src" / "components" / "overview.css"
PLANES = ["water", "people", "money", "evidence"]
PIECE = re.compile(
    r'<g class="overview-piece" data-plane="(\w+)"><g clip-path="url\(#overview-ca\)">'
    r'<a href="[^"]+" tabindex="-1" aria-hidden="true"><polygon class="overview-plane" '
    r'data-plane="(\w+)" points="[^"]+"/></a></g>(.*?)</g>'
)


def _markup(page: str) -> str:
    start = page.index('<div class="atlas-overview">')
    return page[start : page.index("\n```js", start)]


def _js(page: str) -> str:
    return " ".join(re.findall(r"```js\s+(.*?)```", page, re.DOTALL))


def _rules(css: str, selector: str) -> str:
    """Every top-level rule body whose selector list contains `selector`, joined."""
    bodies = [
        match.group(2)
        for match in re.finditer(r"(?m)^([^{}@/]+?)\s*\{([^{}]*)\}", css)
        if selector in [part.strip() for part in match.group(1).split(",")]
    ]
    assert bodies, f"missing rule {selector}"
    return "\n".join(bodies)


def test_each_plane_is_a_group_with_its_own_california_clip() -> None:
    markup = _markup(INDEX.read_text(encoding="utf-8"))
    pieces = PIECE.findall(markup)

    assert [plane for plane, _, _ in pieces] == PLANES
    assert all(plane == polygon for plane, polygon, _ in pieces)
    # Four clipped groups and no shared outer clip, so each clip moves with its plane.
    assert markup.count('<g clip-path="url(#overview-ca)">') == 4


def test_half_circle_travels_with_the_people_plane() -> None:
    markup = _markup(INDEX.read_text(encoding="utf-8"))
    extras = {plane: extra for plane, _, extra in PIECE.findall(markup)}

    half_circle = (
        '<path d="M-330,70 A62,62 0 0 0 -206,70 Z" style="fill: var(--atlas-vermilion)" '
        'aria-hidden="true"/>'
    )
    assert extras["people"] == half_circle
    assert all(extras[plane] == "" for plane in ("water", "money", "evidence"))


def test_pieces_are_at_rest_in_the_markup_without_inline_transforms() -> None:
    markup = _markup(INDEX.read_text(encoding="utf-8"))

    assert not re.search(r'overview-piece[^>]*style="', markup)
    assert "--dx" not in markup and "--dy" not in markup


def test_old_settle_animation_and_its_classes_are_gone() -> None:
    page = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    for retired in ("overview-settle", "overview-plane-g", "--dx", "--dy"):
        assert retired not in css, retired
        assert retired not in page, retired


def test_no_animation_library_is_downloaded() -> None:
    page = INDEX.read_text(encoding="utf-8")

    # The spring is computed in the page; no npm: import, so nothing to wait for.
    assert "npm:motion" not in page and "npm:" not in _js(page)
    assert "piece.animate(frames," in _js(page)


def test_page_and_script_load_no_external_cdn() -> None:
    page = INDEX.read_text(encoding="utf-8")

    for host in ("cdn.jsdelivr.net", "unpkg.com", "esm.sh", "cdnjs.cloudflare.com"):
        assert host not in page, host


def test_spring_and_stagger_follow_the_owner_brief() -> None:
    js = _js(INDEX.read_text(encoding="utf-8"))

    # Owner chose the springy lock-in: underdamped (overshoot about 12%), 120 ms apart.
    assert "const ZETA = 0.55, OMEGA = 10, DURATION = 1100, STEPS = 66, GAP = 120;" in js
    assert "delay: i * GAP" in js
    assert "Math.exp(-ZETA * OMEGA * t)" in js
    assert "const tilt = {water: -8, people: 7, money: -7, evidence: 8};" in js


def test_each_plane_starts_from_its_own_edge() -> None:
    js = _js(INDEX.read_text(encoding="utf-8"))

    assert "water: (r) => [0, -(r.bottom + EDGE)]," in js  # from above the top edge
    assert "people: (r) => [-(r.right + EDGE), 0]," in js  # from the left edge
    assert "money: (r) => [vw - r.left + EDGE, 0]," in js  # from the right edge
    assert "evidence: (r) => [0, vh - r.top + EDGE]," in js  # from below the bottom edge
    assert "const unit = svg.getScreenCTM().a;" in js  # px to SVG user units


def test_intro_is_guarded_by_session_reduced_motion_visibility_and_support() -> None:
    js = _js(INDEX.read_text(encoding="utf-8"))

    # Owner 2026-11-17: the intro plays on every load, so there is no session guard.
    assert "sessionStorage" not in js and "atlas-map-intro" not in js
    assert 'matchMedia("(prefers-reduced-motion: reduce)").matches' in js
    assert "!figure.getClientRects().length" in js
    assert "if (!svg || pieces.length !== 4 || reduced" in js
    # Without the Web Animations API the map stays at rest.
    assert 'typeof Element.prototype.animate !== "function"' in js
    assert "else { cancelled = true; rest(); }" in js


def test_user_input_finishes_the_intro_at_once() -> None:
    js = _js(INDEX.read_text(encoding="utf-8"))

    assert (
        'window.addEventListener("pointerdown", finishNow, {once: true, signal: ac.signal});' in js
    )
    assert 'window.addEventListener("keydown", finishNow, {once: true, signal: ac.signal});' in js
    assert "control.complete()" in js
    assert "animation.complete = () => animation.finish();" in js
    assert "await Promise.allSettled(controls.map((animation) => animation.finished));" in js


def test_intro_moves_transforms_only_and_clears_them_at_rest() -> None:
    js = _js(INDEX.read_text(encoding="utf-8"))
    rest = js[js.index("const rest = () =>") : js.index("hero?.classList.add")]

    assert 'piece.style.transform = "";' in rest
    assert 'piece.style.transformOrigin = "";' in rest
    assert 'piece.style.transformBox = "";' in rest
    assert 'hero?.classList.remove("is-map-intro");' in rest
    # Layout is never touched: no size, position or margin writes, so the intro cannot move content.
    assert not re.search(r"style\.(width|height|top|left|margin|padding)", js)


def test_svg_overflows_and_only_the_intro_clips_the_hero() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert "overflow: visible;" in _rules(css, ".overview-figure svg")
    assert "overflow: clip;" in _rules(css, ".overview-hero.is-map-intro")
    # The hero itself must not clip permanently: the site-search listbox lives inside it.
    assert "overflow" not in _rules(css, ".overview-hero")
    assert "clip-path: inset(0 -100vmax);" in _rules(css, ".overview-hero")


def test_reduced_motion_block_no_longer_names_removed_classes() -> None:
    css = CSS.read_text(encoding="utf-8")
    # The first reduced-motion block is the Overview's; it closes at the column-0 brace.
    block = re.search(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", css, re.S)

    assert block, "overview reduced-motion block missing"
    assert ".overview-plane," in block.group(1)
    assert "overview-plane-g" not in block.group(1)
