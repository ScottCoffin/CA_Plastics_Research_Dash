"""Build the latin WOFF2 subsets of the Plastiverse Live brand fonts (PLAT-2).

Outputs in site/assets/fonts/:
- SchibstedGrotesk-Variable-latin.woff2: variable font, wght limited to 400-700.
- MartianMono-Regular-latin.woff2: static instance at wght 400 and wdth 87.5.

Both are subset to the Archivo unicode-range plus U+2192 and keep all layout features.
Each font's SIL OFL 1.1 text is copied beside it. Provenance: site/assets/fonts/PROVENANCE.md.

Run from the repository root. fonttools and brotli come from uv, so nothing is installed:

    uv run --no-project --with fonttools --with brotli python -I scripts/build_brand_fonts.py

The upstream TTFs and OFL texts come from google/fonts at pinned commits into the ignored
data/raw/fonts/ cache, and each file is checked against its SHA-256. Pass --offline to reuse
the cache without network access.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import fontTools
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw" / "fonts"
OUT_DIR = REPO_ROOT / "site" / "assets" / "fonts"
RAW_URL = "https://raw.githubusercontent.com/google/fonts/{commit}/ofl/{family}/{name}"
KB = 1024

# Copied from the Archivo @font-face in framework/observablehq.config.js.
ARCHIVO_UNICODE_RANGE = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, "
    "U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, "
    "U+FFFD"
)
# The landing page uses U+2192 (rightwards arrow), which the Archivo range leaves out.
EXTRA_CODEPOINTS = (0x2192,)
# Every output must contain these characters (escapes keep the source ASCII).
REQUIRED_TEXT = "Plastiverse Live 0123456789 → … – “”"


@dataclass(frozen=True)
class BrandFont:
    """One google/fonts family, the instancing it needs and the file it produces."""

    family: str  # directory under ofl/ in google/fonts
    upstream: str  # TTF file name in that directory
    commit: str  # google/fonts commit the files are pinned to
    sha256: str  # SHA-256 of the upstream TTF
    axes: dict[str, float | tuple[float, float]]  # tuple: keep the axis limited; float: pin it
    output: str  # WOFF2 file name in site/assets/fonts/
    max_bytes: int
    licence_output: str  # licence copy in site/assets/fonts/
    licence_sha256: str  # SHA-256 of the upstream OFL.txt

    @property
    def cache_name(self) -> str:
        """Local file name in data/raw/fonts/<family>/, e.g. SchibstedGrotesk-wght.ttf."""
        return self.upstream.replace("[", "-").replace("]", "").replace(",", "-")


BRAND_FONTS = (
    BrandFont(
        family="schibstedgrotesk",
        upstream="SchibstedGrotesk[wght].ttf",
        commit="cc054e5ee906ac9b9024971b64d821aa2561c582",
        sha256="6ceeadf6be8e1fd7687011c7fa38ed0edd1abe967a0b73d97caec183552e823d",
        axes={"wght": (400, 700)},
        output="SchibstedGrotesk-Variable-latin.woff2",
        max_bytes=45 * KB,
        licence_output="OFL-SchibstedGrotesk.txt",
        licence_sha256="3b4f3063b6ac7c1e403e2c4a5e8ef3a58190ff83ed7b15af66511858699139ce",
    ),
    BrandFont(
        family="martianmono",
        upstream="MartianMono[wdth,wght].ttf",
        commit="1386d6284a09c9c25d8c1db08717d6e42a44867d",
        sha256="c3467843ec1c2574b05fbcfd7147c7bfbcf63ddca8fc2bcb9d117f1bfb1b22e7",
        axes={"wght": 400, "wdth": 87.5},
        output="MartianMono-Regular-latin.woff2",
        max_bytes=30 * KB,
        licence_output="OFL-MartianMono.txt",
        licence_sha256="ddafd2c3f37ef1d83ef284ca63e159befd3820850c5e9eded14ca52eee92c256",
    ),
)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upstream_url(brand: BrandFont, name: str) -> str:
    return RAW_URL.format(
        commit=brand.commit,
        family=brand.family,
        name=urllib.parse.quote(name, safe=","),
    )


def fetch(url: str, dest: Path, expected_sha256: str, offline: bool) -> None:
    """Make dest hold the pinned upstream file, downloading it unless offline."""
    if not dest.exists():
        if offline:
            raise SystemExit(f"--offline: {dest} is not cached; run once without --offline")
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(dest.name + ".part")
        with urllib.request.urlopen(url, timeout=120) as response:
            partial.write_bytes(response.read())
        partial.replace(dest)
    actual = sha256_of(dest)
    if actual != expected_sha256:
        raise SystemExit(
            f"SHA-256 mismatch for {dest}: got {actual}, expected {expected_sha256}. "
            "Delete the cached file and rerun."
        )


def unicode_set() -> list[int]:
    """Codepoints kept by the subset: the Archivo unicode-range plus EXTRA_CODEPOINTS."""
    codepoints = set(EXTRA_CODEPOINTS)
    for item in ARCHIVO_UNICODE_RANGE.split(","):
        start, _, end = item.strip().removeprefix("U+").partition("-")
        codepoints.update(range(int(start, 16), int(end or start, 16) + 1))
    return sorted(codepoints)


def build(brand: BrandFont, source: Path) -> Path:
    """Instance the upstream TTF, subset it and write the WOFF2 into OUT_DIR."""
    font = instancer.instantiateVariableFont(TTFont(source), brand.axes, updateFontNames=True)
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["*"]
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=unicode_set())
    subsetter.subset(font)
    font.flavor = "woff2"
    # Keep head.modified from upstream: fontTools otherwise stamps the save time, which changes
    # the WOFF2 size by up to ~200 bytes between runs and breaks byte-identical rebuilds.
    font.recalcTimestamp = False
    out = OUT_DIR / brand.output
    font.save(out)
    return out


def verify(path: Path, brand: BrandFont) -> None:
    """Check WOFF2 magic, size budget, expected axes and glyph coverage of REQUIRED_TEXT."""
    data = path.read_bytes()
    if data[:4] != b"wOF2":
        raise SystemExit(f"{path.name}: not a WOFF2 file")
    if len(data) > brand.max_bytes:
        raise SystemExit(f"{path.name}: {len(data)} bytes exceeds the {brand.max_bytes} limit")
    font = TTFont(path)
    expected = {tag: limit for tag, limit in brand.axes.items() if isinstance(limit, tuple)}
    has_fvar = "fvar" in font
    if has_fvar != bool(expected):
        raise SystemExit(f"{path.name}: fvar present={has_fvar}, expected {bool(expected)}")
    if has_fvar:
        axes = {axis.axisTag: (axis.minValue, axis.maxValue) for axis in font["fvar"].axes}
        if axes != expected:
            raise SystemExit(f"{path.name}: axes {axes}, expected {expected}")
    cmap = font.getBestCmap()
    missing = [f"U+{ord(c):04X}" for c in REQUIRED_TEXT if not c.isspace() and ord(c) not in cmap]
    if missing:
        raise SystemExit(f"{path.name}: missing glyphs {', '.join(missing)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Plastiverse Live brand font subsets.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="reuse the cached upstream files in data/raw/fonts/ without network access",
    )
    args = parser.parse_args(argv)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"fontTools {fontTools.version}")
    for brand in BRAND_FONTS:
        family_dir = RAW_DIR / brand.family
        source = family_dir / brand.cache_name
        licence = family_dir / "OFL.txt"
        fetch(upstream_url(brand, brand.upstream), source, brand.sha256, args.offline)
        fetch(upstream_url(brand, "OFL.txt"), licence, brand.licence_sha256, args.offline)
        out = build(brand, source)
        shutil.copyfile(licence, OUT_DIR / brand.licence_output)
        verify(out, brand)
        print(f"{out.name}: {out.stat().st_size} bytes, sha256 {sha256_of(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
