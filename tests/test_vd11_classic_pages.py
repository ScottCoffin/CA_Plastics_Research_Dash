"""VD-11: the classic expert profile and the generated SEO pages use the Atlas tokens and fonts.

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
EXPERT = ROOT / "site" / "expert.html"
SITE = ROOT / "site"
FONT_FILES = {
    600: "BarlowSemiCondensed-SemiBold-latin.woff2",
    700: "BarlowSemiCondensed-Bold-latin.woff2",
}
ROUTING_SCRIPT_SHA256 = "ccc1a9dae62ee5fd9343dc097364483a6b7344e1f36f7e8b881ce9f6261b93fe"
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
FACE = re.compile(r"@font-face\s*\{([^}]*)\}")
REMOTE = re.compile(
    r"fonts\.googleapis\.com|fonts\.gstatic\.com|@import|url\(\s*['\"]?(?:https?:)?//"
    r"|<link[^>]+href\s*=\s*['\"]?https?:",
    re.IGNORECASE,
)

# expert.html :root variable -> tokens.css variable (main roles).
EXPERT_ROLES = {
    "--ink": "--atlas-ink",
    "--text": "--atlas-text",
    "--muted": "--atlas-muted",
    "--boundary": "--atlas-boundary",
    "--brand": "--atlas-brand",
    "--brand-dark": "--atlas-brand-strong",
    "--surface": "--atlas-surface",
    "--canvas": "--atlas-page",
    "--line": "--atlas-line",
    "--focus": "--atlas-accent",
}
# Token colours the SEO stylesheet must use for its main roles.
SEO_ROLES = (
    "--atlas-text",
    "--atlas-page",
    "--atlas-ink",
    "--atlas-brand",
    "--atlas-brand-strong",
    "--atlas-brand-action",
    "--atlas-accent",
    "--atlas-muted",
    "--atlas-line",
    "--atlas-surface",
)


def _tokens() -> dict[str, str]:
    text = TOKENS.read_text(encoding="utf-8")
    pairs = re.findall(r"(--atlas-[a-z-]+):\s*(#[0-9a-fA-F]{6});", text)
    return {name: value.lower() for name, value in pairs}


def _normalise(css: str) -> str:
    return re.sub(r"\s*:\s*", ":", re.sub(r"\s+", " ", css))


def _check_font_faces(css: str, url_prefix: str) -> None:
    faces: dict[int, str] = {}
    for body in FACE.findall(css):
        match = re.search(r"font-weight:\s*(\d+)", body)
        assert match, body
        faces[int(match.group(1))] = _normalise(body)
    assert set(faces) == set(FONT_FILES), f"expected 600 and 700 faces, got {sorted(faces)}"
    for weight, body in faces.items():
        filename = FONT_FILES[weight]
        assert 'font-family:"Barlow Semi Condensed"' in body
        assert "font-display:swap" in body
        assert f'url("{url_prefix}{filename}") format("woff2")' in body
        assert (SITE / url_prefix.lstrip("/") / filename).is_file(), filename


def test_expert_root_palette_matches_tokens() -> None:
    html = EXPERT.read_text(encoding="utf-8")
    root = re.search(r":root \{([^}]*)\}", html)
    assert root, "expert.html needs a :root palette"
    values = {
        name: value.lower()
        for name, value in re.findall(r"(--[a-z-]+):\s*(#[0-9a-fA-F]{6});", root.group(1))
    }
    tokens = _tokens()
    for local, token in EXPERT_ROLES.items():
        assert values.get(local) == tokens[token], f"{local} should equal {token} ({tokens[token]})"
    assert '--font-display: "Barlow Semi Condensed"' in root.group(1)


def test_seo_stylesheet_uses_only_token_colours() -> None:
    tokens = _tokens()
    used = set(HEX.findall(SEO_CSS.lower()))
    assert used <= set(tokens.values()), f"non-token colours: {sorted(used - set(tokens.values()))}"
    for name in SEO_ROLES:
        assert tokens[name] in used, f"SEO CSS should use {name} ({tokens[name]})"


def test_expert_page_declares_local_barlow_faces_with_swap() -> None:
    html = EXPERT.read_text(encoding="utf-8")
    style = html.split("<style>", 1)[1].split("</style>", 1)[0]
    _check_font_faces(style, "assets/fonts/")
    assert "font-family: var(--font-display);" in style
    assert "--font-display:" in style


def test_seo_stylesheet_declares_root_relative_barlow_faces() -> None:
    _check_font_faces(SEO_CSS, "/assets/fonts/")


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
        "`index.html#experts?author=${encodeURIComponent(raw)}`",
    ):
        assert snippet in html, snippet


def test_generated_seo_page_carries_tokens_and_keeps_profile_link(tmp_path: Path) -> None:
    site = tmp_path / "site"
    data = site / "data"
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
    page = (site / "experts" / "A1" / "index.html").read_text(encoding="utf-8")

    style = re.search(r"<style>(.*?)</style>", page, re.DOTALL)
    assert style, "the generated page keeps one inline stylesheet"
    assert style.group(1) == SEO_CSS
    _check_font_faces(style.group(1), "/assets/fonts/")
    assert not REMOTE.search(style.group(1))
    assert 'href="https://plastiverse.live/expert.html#author=A1"' in page
    assert "<h1>Ana Lee</h1>" in page


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
