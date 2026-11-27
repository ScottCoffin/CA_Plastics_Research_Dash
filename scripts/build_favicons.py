"""Build the site favicons from the main Plastiverse Live logo (FAVICON-MAIN, owner 2026-11-26).

Small sizes (16, 32, 48 px and favicon.ico) use the sun at the hub of the mark, the only part that
stays legible at tab size. Large sizes (180 px apple-touch-icon, 512 px) use the whole mark without
the wordmark, padded to a square on the logo's black ground. `favicon.svg` wraps the 32 px PNG so
old references to it show the same icon; it is one line with no newline so checkouts keep its
bytes. `site/favicon.ico` and `site/apple-touch-icon.png` are root
copies for browsers and iOS, which look there by default.

Usage:
    py -3.14 scripts/build_favicons.py [--check]
"""

from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "Plastiverse Live_ From Pollution to Progress.png"
SITE = ROOT / "site"
OUT = SITE / "assets"
# Root copies: name under site/ -> name under site/assets/.
ROOT_COPIES = {"favicon.ico": "favicon.ico", "apple-touch-icon.png": "apple-touch-icon.png"}
# Pixel boxes in the 1127 x 988 source.
MARK_BOX = (30, 20, 1110, 850)  # the mark without the "PLASTIVERSE LIVE" wordmark
SUN_BOX = (700, 330, 900, 530)  # the sun at the centre of the network
GROUND = (0, 0, 0)


def _square(image: Image.Image) -> Image.Image:
    side = max(image.size)
    canvas = Image.new("RGB", (side, side), GROUND)
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    return canvas


def _png(image: Image.Image, size: int) -> bytes:
    buf = io.BytesIO()
    image.resize((size, size), Image.LANCZOS).save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render() -> dict[str, bytes]:
    """Return file name -> bytes for every favicon asset."""
    source = Image.open(SOURCE).convert("RGB")
    mark = _square(source.crop(MARK_BOX))
    sun = _square(source.crop(SUN_BOX))
    ico = io.BytesIO()
    sun.resize((48, 48), Image.LANCZOS).save(
        ico, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)]
    )
    png32 = _png(sun, 32)
    data_uri = f"data:image/png;base64,{base64.b64encode(png32).decode()}"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">'
        f'<image width="32" height="32" href="{data_uri}"/>'
        "</svg>"  # no trailing newline: autocrlf cannot change the bytes on checkout
    ).encode()
    return {
        "favicon.ico": ico.getvalue(),
        "favicon-16.png": _png(sun, 16),
        "favicon-32.png": png32,
        "favicon.svg": svg,
        "apple-touch-icon.png": _png(mark, 180),
        "icon-512.png": _png(mark, 512),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when a committed icon differs")
    args = parser.parse_args(argv)
    assets = render()
    files = {OUT / name: data for name, data in assets.items()}
    files.update({SITE / name: assets[source] for name, source in ROOT_COPIES.items()})
    stale = [
        name for name, data in files.items() if not name.is_file() or name.read_bytes() != data
    ]
    if args.check:
        if stale:
            names = ", ".join(path.relative_to(ROOT).as_posix() for path in stale)
            print(f"stale favicons: {names} (run without --check)", file=sys.stderr)
            return 1
        print(f"ok: {len(files)} favicon files match the logo")
        return 0
    for path in stale:
        path.write_bytes(files[path])
    print(f"wrote {len(stale)} of {len(files)} favicon files under site/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
