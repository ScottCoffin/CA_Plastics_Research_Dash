"""Fetch the Related resources icon for each link-out card (VD-32).

For every card in config/linkouts.yml, GET the homepage of its root_url once and use the first
usable icon, in this order: rel="apple-touch-icon" (largest), the largest rel="icon" (an SVG counts
as scalable), then /favicon.ico. Raster icons become a 64 x 64 transparent PNG with Pillow (the
largest frame of an .ico; a near-white background touching a corner is made transparent). An SVG
is kept as is, and only when it is self-contained: no script, no event attributes, no external
references. A card whose root_url is the logo source of a research network
(config/research_networks.yml) reuses that self-hosted logo instead of fetching.

An owner-chosen icon replaces the search (VD-35): set owner_source on a card's record in
config/linkout_icons.yml to a local image file or an https URL. That image is converted the same
way and recorded as source_kind owner_file or owner_url. A URL that several cards name is
downloaded once per run. The note field is free text for provenance and is kept as written.

Each outcome is written to config/linkout_icons.yml (source URL, fetch date, file path or error).
Icon files that already exist are skipped unless --refresh is given; cards whose last attempt
failed are retried. Failures are recorded and do not stop the run; the page then shows initials.

    py -3.14 scripts/fetch_linkout_icons.py [--refresh] [--only LO-1 LO-2 ...]
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import yaml
from PIL import Image, ImageDraw

from atlas import linkouts

ROOT = linkouts.ROOT
SITE_DIR = ROOT / "site"
ICON_DIR = SITE_DIR / "assets" / "linkouts"
ICONS_PATH = ROOT / "config" / "linkout_icons.yml"
NETWORKS_PATH = ROOT / "config" / "research_networks.yml"
USER_AGENT = "CA-Plastics-Research-Atlas/1.0 (+https://plastiverse.live)"
TIMEOUT_SECONDS = 15
POLITE_DELAY_SECONDS = 1.0
MAX_PAGE_BYTES = 2_000_000  # the head of the homepage is read; anything after is ignored
MAX_ICON_BYTES = 1_000_000
MAX_SVG_BYTES = 200_000
ICON_SIZE = 64
SCALABLE = 10_000  # sort key for SVG icons, which have no fixed size
SCHEMA_VERSION = 1
FIELDS = (
    "id",
    "initials",
    "icon_page",
    "owner_source",
    "skip_reason",
    "path",
    "format",
    "source_kind",
    "icon_url",
    "page_url",
    "fetched",
    "attempted",
    "error",
    "note",
)
STOPWORDS = {"a", "an", "and", "by", "for", "in", "of", "on", "the", "with", "key", "managed"}
HEADER = """\
# Icons for the Related resources cards (VD-32, owner request 2026-11-17).
# Each icon is the steward's own site icon (favicon or touch icon), resized to 64 x 64 and
# shown at 40 px only to identify the link; the card's title links to the resource. A card whose
# root_url is a research network's logo source reuses that self-hosted logo
# (config/research_networks.yml).
# initials: the two or three letters shown on a neutral plane when no icon is stored.
# owner_source (VD-35, owner request 2026-11-17): an owner-chosen icon, a local image file or an
# https URL. When set, it is used instead of searching the homepage. note: provenance, kept as is.
# path: relative to the site root, or null. error: the last failed attempt, retried next run.
# Rebuild the public JSON with `py -3.14 scripts/build_linkouts_json.py`. Fetch with
# `py -3.14 scripts/fetch_linkout_icons.py [--refresh] [--only LO-n]`.
"""


class IconError(ValueError):
    """An icon candidate cannot be used; the message is recorded in the icons file."""


class _IconLinks(HTMLParser):
    """Collect the <link> icon candidates of a homepage."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.apple: list[tuple[int, str]] = []
        self.icons: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        values = {key: (value or "").strip() for key, value in attrs}
        href = values.get("href", "")
        rel = values.get("rel", "").lower().split()
        if not href:
            return
        size = _icon_size(values.get("sizes", ""), values.get("type", ""), href)
        if "apple-touch-icon" in rel or "apple-touch-icon-precomposed" in rel:
            self.apple.append((size, href))
        elif "icon" in rel:
            self.icons.append((size, href))


def _icon_size(sizes: str, mime: str, href: str) -> int:
    """Largest side named in a sizes attribute; SVGs are scalable; unknown sizes sort last."""
    if "svg" in mime.lower() or href.lower().split("?")[0].endswith(".svg"):
        return SCALABLE
    named = [int(width) for width, _ in re.findall(r"(\d+)x(\d+)", sizes, flags=re.IGNORECASE)]
    return max(named, default=0)


def icon_candidates(html: str, page_url: str) -> list[tuple[str, str]]:
    """(kind, absolute URL) pairs in the order the script tries them, without repeats."""
    parser = _IconLinks()
    parser.feed(html)
    apple = sorted(parser.apple, key=lambda item: -item[0])
    icons = sorted(parser.icons, key=lambda item: -item[0])
    ordered = [
        *(("apple-touch-icon", urljoin(page_url, href)) for _, href in apple),
        *(("rel-icon", urljoin(page_url, href)) for _, href in icons),
        ("favicon.ico", urljoin(origin(page_url), "/favicon.ico")),
    ]
    return list(dict.fromkeys(ordered))


def origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/"


def _get(url: str, limit: int, *, truncate: bool = False) -> tuple[bytes, str]:
    """GET with the polite user agent and a timeout; returns (body, final URL after redirects)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(limit + 1)
        final = response.geturl()
    if len(body) > limit:
        if not truncate:
            raise IconError(f"larger than {limit} bytes")
        body = body[:limit]
    return body, final


def validate_svg(data: bytes) -> None:
    """Raise IconError unless the SVG is self-contained: no script, DTD, event handler or external
    reference, a single SVG root, and at most MAX_SVG_BYTES."""
    if len(data) > MAX_SVG_BYTES:
        raise IconError(f"SVG larger than {MAX_SVG_BYTES} bytes")
    try:
        lower = data.decode("utf-8").lower()
    except UnicodeDecodeError as exc:
        raise IconError("SVG is not UTF-8") from exc
    for token in ("<script", "<foreignobject", "<!doctype", "<!entity", "@import"):
        if token in lower:
            raise IconError(f"SVG contains {token}")
    if re.search(r"\son[a-z]+\s*=", lower):
        raise IconError("SVG has an event handler attribute")
    if re.search(r"(?:href|src)\s*=\s*[\"']\s*(?:https?:|//|javascript:)", lower):
        raise IconError("SVG refers to an external resource")
    if re.search(r"url\(\s*[\"']?\s*(?:https?:|//)", lower):
        raise IconError("SVG refers to an external resource")
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise IconError(f"SVG does not parse ({exc})") from exc
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise IconError("not an SVG document")


def _knock_out_corner_white(img: Image.Image) -> None:
    """Make a near-white background that touches a corner transparent (flood fill)."""
    width, height = img.size
    for seed in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        r, g, b, a = img.getpixel(seed)
        if a and min(r, g, b) >= 235:
            ImageDraw.floodfill(img, seed, (255, 255, 255, 0), thresh=24)


def raster_to_png(data: bytes) -> bytes:
    """A 64 x 64 transparent PNG that fits the image (largest .ico frame; no cropping)."""
    try:
        with Image.open(io.BytesIO(data)) as opened:
            img = opened.convert("RGBA")
    except Exception as exc:  # any decode failure makes this candidate unusable
        raise IconError(f"not a readable image ({type(exc).__name__})") from exc
    _knock_out_corner_white(img)
    width, height = img.size
    scale = ICON_SIZE / max(width, height)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    img = img.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((ICON_SIZE - size[0]) // 2, (ICON_SIZE - size[1]) // 2))
    out = io.BytesIO()
    canvas.save(out, "PNG", optimize=True)
    return out.getvalue()


def to_stored_icon(data: bytes) -> tuple[str, bytes]:
    """(extension, bytes) for an SVG (kept if self-contained) or a raster (converted to PNG)."""
    head = data.lstrip()[:400].lower()
    if head.startswith(b"<") and (b"<svg" in head or b"<?xml" in head):
        validate_svg(data)
        return "svg", data
    return "png", raster_to_png(data)


def _store(eid: str, ext: str, payload: bytes) -> str:
    """Write the icon file and remove any other extension for the same card; returns its path."""
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    for other in ("png", "svg"):
        stale = ICON_DIR / f"{eid.lower()}.{other}"
        if other != ext and stale.exists():
            stale.unlink()
    target = ICON_DIR / f"{eid.lower()}.{ext}"
    target.write_bytes(payload)
    return target.relative_to(SITE_DIR).as_posix()


def default_initials(steward: str) -> str:
    """Two letters from the first two significant words; edit config/linkout_icons.yml to change."""
    words = [w for w in re.findall(r"[A-Za-z]+", steward) if w.lower() not in STOPWORDS]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def network_logo_for(root_url: str, networks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A research network whose page is this card and that has a self-hosted logo, if any."""
    for network in networks:
        logo = network.get("logo") or {}
        if network.get("url") == root_url and logo.get("path"):
            return network
    return None


def attempt(
    entry: dict[str, Any], network: dict[str, Any] | None, today: str, icon_page: str | None
) -> dict[str, Any]:
    """Fetch and store one icon. Returns the fields to record; raises IconError on failure.

    icon_page (optional, hand-set) is a steward homepage to read instead of root_url's origin.
    """
    eid = entry["id"]
    root = entry["root_url"]
    if network is not None:
        logo = network["logo"]
        source = (SITE_DIR / logo["path"]).read_bytes()
        ext, payload = to_stored_icon(source)
        path = _store(eid, ext, payload)
        return {
            "path": path,
            "format": ext,
            "source_kind": f"research network logo ({network['id']})",
            "icon_url": logo.get("source_url"),
            "page_url": root,
            "fetched": today,
            "error": None,
        }
    home = icon_page or origin(root)
    errors: list[str] = []
    try:
        html_bytes, final_home = _get(home, MAX_PAGE_BYTES, truncate=True)
        candidates = icon_candidates(html_bytes.decode("utf-8", errors="replace"), final_home)
    except (OSError, ValueError) as exc:
        errors.append(f"homepage {home}: {exc}")
        final_home = home
        candidates = [("favicon.ico", urljoin(home, "/favicon.ico"))]
    for kind, url in candidates:
        time.sleep(POLITE_DELAY_SECONDS)
        try:
            data, _ = _get(url, MAX_ICON_BYTES)
            ext, payload = to_stored_icon(data)
        except (OSError, ValueError) as exc:
            errors.append(f"{kind} {url}: {exc}")
            continue
        return {
            "path": _store(eid, ext, payload),
            "format": ext,
            "source_kind": kind,
            "icon_url": url,
            "page_url": final_home,
            "fetched": today,
            "error": None,
        }
    raise IconError("; ".join(errors[-3:]) or "no icon candidates")


def is_url(source: str) -> bool:
    return source.startswith(("https://", "http://"))


def _owner_bytes(source: str) -> bytes:
    """The bytes of an owner_source: a URL (polite delay first) or a local file. Errors name only
    the file, not its folders, because the message is written to the icons file."""
    if is_url(source):
        time.sleep(POLITE_DELAY_SECONDS)
        data, _ = _get(source, MAX_ICON_BYTES)
        return data
    path = Path(source)
    try:
        size = path.stat().st_size
        if size > MAX_ICON_BYTES:
            raise IconError(f"owner file {path.name} larger than {MAX_ICON_BYTES} bytes")
        return path.read_bytes()
    except OSError as exc:
        raise IconError(f"owner file {path.name} cannot be read") from exc


def owner_attempt(
    entry: dict[str, Any], record: dict[str, Any], today: str, cache: dict[str, bytes]
) -> dict[str, Any]:
    """Store the owner-chosen icon named by record['owner_source'] (VD-35). Returns the fields to
    record; raises IconError on failure. cache holds URL bytes already downloaded in this run."""
    source = str(record["owner_source"]).strip()
    if source not in cache:
        cache[source] = _owner_bytes(source)
    ext, payload = to_stored_icon(cache[source])
    remote = is_url(source)
    return {
        "path": _store(entry["id"], ext, payload),
        "format": ext,
        "source_kind": "owner_url" if remote else "owner_file",
        "icon_url": source if remote else None,
        "page_url": record.get("icon_page"),
        "fetched": today,
        "error": None,
    }


def load_records(path: Path = ICONS_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("icons") or []
    return {row["id"]: row for row in rows if isinstance(row, dict) and "id" in row}


def write_records(records: list[dict[str, Any]], path: Path = ICONS_PATH) -> None:
    body = yaml.safe_dump(
        {"schema_version": SCHEMA_VERSION, "icons": records},
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    path.write_text(HEADER + body, encoding="utf-8", newline="\n")


def _has_file(record: dict[str, Any]) -> bool:
    path = record.get("path")
    return bool(path) and (SITE_DIR / path).is_file()


def _remove_icon(eid: str) -> None:
    for ext in ("png", "svg"):
        stale = ICON_DIR / f"{eid.lower()}.{ext}"
        if stale.exists():
            stale.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--refresh", action="store_true", help="fetch again even when a file exists"
    )
    parser.add_argument("--only", nargs="+", metavar="ID", help="only these card IDs, e.g. LO-12")
    args = parser.parse_args(argv)
    try:
        registry = linkouts.load_registry()
        errors = linkouts.validate_registry(registry)
        if errors:
            raise ValueError("invalid registry: " + "; ".join(errors))
        networks_data = yaml.safe_load(NETWORKS_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    networks = networks_data.get("networks") or []
    existing = load_records()
    wanted = {item.upper() for item in args.only} if args.only else None
    today = datetime.now(UTC).date().isoformat()
    records: list[dict[str, Any]] = []
    owner_cache: dict[str, bytes] = {}
    for entry in registry["entries"]:
        eid = entry["id"]
        record = dict(existing.get(eid) or {"id": eid})
        record.setdefault("initials", default_initials(entry["steward"]))
        run = wanted is None or eid in wanted
        if record.get("skip_reason"):
            _remove_icon(eid)
            record.update(path=None, format=None, source_kind=None, icon_url=None, error=None)
            print(f"{eid}: skipped ({record['skip_reason']})")
        elif not run or (not args.refresh and _has_file(record)):
            print(f"{eid}: kept ({record.get('path') or 'no icon'})")
        else:
            try:
                if record.get("owner_source"):
                    fields = owner_attempt(entry, record, today, owner_cache)
                else:
                    network = network_logo_for(entry["root_url"], networks)
                    fields = attempt(entry, network, today, record.get("icon_page"))
                record.update(attempted=None, **fields)
                print(f"{eid}: {record['source_kind']} -> {record['path']}")
            except (OSError, ValueError) as exc:
                if not _has_file(record):
                    record["path"] = None
                record.update(attempted=today, error=str(exc))
                print(f"{eid}: failed: {exc}")
        records.append({key: record.get(key) for key in FIELDS})
    write_records(records)
    usable = sum(1 for row in records if row["path"])
    print(f"icons: {usable} of {len(records)} cards have an icon; wrote {ICONS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
