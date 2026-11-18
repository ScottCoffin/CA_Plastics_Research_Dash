"""Offline checks for the self-hosted Plastiverse Live brand fonts (PLAT-2).

scripts/build_brand_fonts.py builds the subsets. These tests only read the committed
outputs, so fontTools is not required.
"""

from pathlib import Path

import pytest

FONTS_DIR = Path(__file__).resolve().parents[1] / "site" / "assets" / "fonts"
KB = 1024
WOFF2_MAGIC = b"wOF2"
BRAND_FONTS = (
    ("SchibstedGrotesk-Variable-latin.woff2", 45 * KB),
    ("MartianMono-Regular-latin.woff2", 30 * KB),
)
OFL_TEXTS = ("OFL-SchibstedGrotesk.txt", "OFL-MartianMono.txt")


@pytest.mark.parametrize(("name", "max_bytes"), BRAND_FONTS)
def test_brand_font_is_woff2_within_size_target(name, max_bytes):
    path = FONTS_DIR / name
    assert path.is_file(), f"missing {path}"
    data = path.read_bytes()
    assert data[:4] == WOFF2_MAGIC, f"{name} is not WOFF2"
    assert len(data) <= max_bytes, f"{name} is {len(data)} bytes; target is {max_bytes}"


@pytest.mark.parametrize("name", OFL_TEXTS)
def test_brand_font_ofl_licence_present(name):
    path = FONTS_DIR / name
    assert path.is_file(), f"missing {path}"
    assert "SIL OPEN FONT LICENSE Version 1.1" in path.read_text(encoding="utf-8")
