"""VD-29: the favicon data URI survives the Framework build, and a real /favicon.ico exists."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = (ROOT / "framework" / "observablehq.config.js").read_text(encoding="utf-8")


def test_favicon_uses_light_encoding_not_encode_uri_component() -> None:
    # Framework re-escapes "%" in a fully percent-encoded href (%3D became %253D).
    favicon = re.search(r"const FAVICON = .*?;\n", CONFIG, flags=re.S)
    assert favicon
    assert "encodeURIComponent" not in favicon.group(0)
    assert '.replaceAll("<", "%3C")' in favicon.group(0)
    assert '<link rel="icon" href="${FAVICON}">' in CONFIG


def test_static_icons_exist_for_non_framework_pages() -> None:
    assert (ROOT / "site" / "favicon.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"
    assert (ROOT / "site" / "assets" / "favicon.svg").is_file()
    assert (ROOT / "site" / "assets" / "apple-touch-icon.png").is_file()
