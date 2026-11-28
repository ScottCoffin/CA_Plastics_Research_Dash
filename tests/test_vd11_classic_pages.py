"""VD-11: classic expert profiles and generated SEO pages use the shared Plastiverse tokens.

Presentation only. The colour values are copied from framework/src/design/tokens.css, so these
tests fail when either side drifts. The hash-routing script in site/expert.html must not change;
if it is changed on purpose, re-pin ROUTING_SCRIPT_SHA256 in the same commit.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from atlas.build.seo import CSS as SEO_CSS
from atlas.build.seo import build_site

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "framework" / "src" / "design" / "tokens.css"
EXPERT = ROOT / "site" / "california" / "expert.html"
SITE = ROOT / "site"
PROFILE_CSS = ROOT / "site" / "assets" / "pv-profile.css"
# Re-pinned by UX-32: the metrics <small> note moved inside its <dd> (axe definition-list).
# Re-pinned by PLAT-1 path move: the page moved to site/california/, so its data, asset and
# list links are relative to that folder (../data/, authors#author=, institution#inst=).
# Re-pinned by BQ-R1 (owner rename Experts -> Authors, A3-D0): visible copy, the page title and the
# list link route (authors#author=) changed; the hash parsing and route logic did not.
# Updated for PLAT-3 slice 3b: the only script change is the data path (data/california/...).
ROUTING_SCRIPT_SHA256 = "40f2598b6e4dd79d2e0f93824dccfe662b195ef44ed40a51eb0df3f7a8968eb4"
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
FACE = re.compile(r"@font-face\s*\{([^}]*)\}")
REMOTE = re.compile(
    r"fonts\.googleapis\.com|fonts\.gstatic\.com|@import|url\(\s*['\"]?(?:https?:)?//"
    r"|<link[^>]+href\s*=\s*['\"]?https?:",
    re.IGNORECASE,
)

# expert.html compatibility aliases -> canonical Plastiverse token variables.
EXPERT_ROLES = {
    "--ink": "--pv-ink",
    "--text": "--pv-ink",
    "--muted": "--pv-ink-2",
    "--boundary": "--pv-slate",
    "--brand": "--pv-coral-ink",
    "--brand-dark": "--pv-night",
    "--surface": "--pv-paper",
    "--canvas": "--pv-ground",
    "--line": "--pv-line",
    "--focus": "--pv-coral-ink",
}


def _pv_tokens() -> dict[str, str]:
    text = TOKENS.read_text(encoding="utf-8")
    pairs = re.findall(r"^\s*(--pv-[a-z0-9-]+):\s*(#[0-9a-fA-F]{6});", text, re.MULTILINE)
    return {name: value.lower() for name, value in pairs}


def _normalise(css: str) -> str:
    collapsed = re.sub(r"\s+", " ", css)
    return re.sub(r"\s*([:;])\s*", r"\1", collapsed)


def _check_font_faces(css: str, page_dir: Path) -> None:
    faces: dict[str, str] = {}
    for body in FACE.findall(css):
        match = re.search(r'font-family:\s*"([^"]+)"', body)
        assert match, body
        faces[match.group(1)] = _normalise(body)
    expected = {
        "Schibsted Grotesk": 'font-family:"Schibsted Grotesk";font-style:normal;'
        "font-weight:400 700;font-display:swap;"
        'src:url("./fonts/SchibstedGrotesk-Variable-latin.woff2") format("woff2")',
        "Martian Mono": 'font-family:"Martian Mono";font-style:normal;font-weight:400;'
        'font-display:swap;src:url("./fonts/MartianMono-Regular-latin.woff2") format("woff2")',
    }
    assert set(faces) == set(expected), f"unexpected self-hosted faces: {sorted(faces)}"
    fonts_dir = page_dir / "assets" / "fonts"
    for family, declaration in expected.items():
        assert declaration in faces[family]
    assert (fonts_dir / "SchibstedGrotesk-Variable-latin.woff2").is_file()
    assert (fonts_dir / "MartianMono-Regular-latin.woff2").is_file()


def test_expert_root_palette_matches_tokens() -> None:
    html = EXPERT.read_text(encoding="utf-8")
    root = re.search(r":root \{([^}]*)\}", html)
    assert root, "expert.html needs a :root palette"
    aliases = dict(re.findall(r"(--[a-z-]+):\s*var\((--pv-[a-z0-9-]+)\);", root.group(1)))
    for local, token in EXPERT_ROLES.items():
        assert aliases.get(local) == token, f"{local} should alias {token}"
    shared = PROFILE_CSS.read_text(encoding="utf-8")
    block = re.search(r":root \{([^}]*)\}", shared)
    assert block, "shared profile CSS embeds canonical --pv tokens"
    declared = {
        name: value.lower()
        for name, value in re.findall(r"(--pv-[a-z0-9-]+):\s*(#[0-9a-fA-F]{6});", block.group(1))
    }
    assert declared == _pv_tokens()
    assert "--font-display: var(--pv-sans)" in root.group(1)


def test_seo_stylesheet_uses_only_token_colours() -> None:
    shared = PROFILE_CSS.read_text(encoding="utf-8")
    comments_removed = re.sub(r"/\*.*?\*/", "", shared, flags=re.DOTALL)
    used = set(HEX.findall(comments_removed.lower()))
    assert used == set(_pv_tokens().values())
    assert "var(--pv-" in SEO_CSS


def test_expert_page_loads_shared_self_hosted_faces_with_swap() -> None:
    html = EXPERT.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="../assets/pv-profile.css">' in html
    _check_font_faces(PROFILE_CSS.read_text(encoding="utf-8"), SITE)


def test_seo_stylesheet_loads_shared_self_hosted_faces() -> None:
    assert "var(--pv-" in SEO_CSS
    _check_font_faces(PROFILE_CSS.read_text(encoding="utf-8"), SITE)


def test_no_remote_fonts_or_stylesheets() -> None:
    assert not REMOTE.search(EXPERT.read_text(encoding="utf-8"))
    assert not REMOTE.search(SEO_CSS)


def test_light_theme_only() -> None:
    assert "prefers-color-scheme" not in EXPERT.read_text(encoding="utf-8")
    assert "prefers-color-scheme" not in SEO_CSS
    assert ":root{color-scheme:light}" in SEO_CSS


def test_expert_hash_routing_is_unchanged() -> None:
    html = EXPERT.read_text(encoding="utf-8")
    script = re.search(r'<script id="expert-app">(.*?)</script>', html, re.DOTALL)
    assert script, "expert.html keeps its page script"
    digest = hashlib.sha256(script.group(1).encode("utf-8")).hexdigest()
    assert digest == ROUTING_SCRIPT_SHA256, (
        "the expert page script changed; VD-11 is presentation only"
    )
    for snippet in (
        "parseExpertId(location.search, location.hash)",
        'window.addEventListener("hashchange", route);',
        "`${location.pathname}#author=${encodeURIComponent(raw)}`",
        "`authors#author=${encodeURIComponent(raw)}`",
    ):
        assert snippet in html, snippet


def test_generated_seo_page_carries_tokens_and_keeps_profile_link(tmp_path: Path) -> None:
    site = tmp_path / "site"
    data = site / "data" / "california"
    _write(
        data / "index.json",
        {
            "authors": [
                {
                    "author_id": "A1",
                    "name": "Ana Lee",
                    "primary_affiliations": ["UC Davis"],
                }
            ]
        },
    )
    _write(data / "authors" / "A1.json", {"works": []})
    build_site(site, "https://plastiverse.live")
    page = (site / "california" / "experts" / "A1" / "index.html").read_text(encoding="utf-8")

    style = re.search(r"<style>(.*?)</style>", page, re.DOTALL)
    assert style, "the generated page keeps one inline stylesheet"
    assert style.group(1) == SEO_CSS
    _check_font_faces(PROFILE_CSS.read_text(encoding="utf-8"), SITE)
    assert 'href="https://plastiverse.live/assets/pv-profile.css"' in page
    assert not REMOTE.search(style.group(1))
    assert 'href="https://plastiverse.live/california/expert.html#author=A1"' in page
    assert '<span class="plv-wm" aria-hidden="true">PLASTIVERSE <b>LIVE</b></span>' in page
    assert "<script" in page and page.count("<script") == 1
    assert '<script type="application/ld+json">' in page
    assert "<script src=" not in page
    assert "<h1>Ana Lee</h1>" in page


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
