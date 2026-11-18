"""Assemble the deployed site: classic ``site/`` plus the Observable Framework build (PLAT-1).

The classic static site (``site/``) supplies the data, assets, status page, feed, robots.txt,
llms.txt, the interactive expert profile (``california/expert.html``) and the deploy-built SEO
pages. The Framework build is copied over it:

* ``index.html`` is the global Plastiverse Live page;
* ``california/*.html`` are the California atlas pages (``california/index.html`` is its home).

PLAT-1 (2026-11-17) is a clean break: the addresses of the California pages before the move
(``/experts``, ``/app/<page>``, ``grants.html``, ``sem.html``, ``expert.html``, the classic
``index.html#<tab>`` links, root ``experts/<id>/`` pages) get no redirects. Their leftover copies
are removed from the output so they cannot be served stale. The California home keeps the classic
home's S3.8 metadata (canonical, Open Graph, Atom link, JSON-LD), retargeted to ``/california/``.
If the Framework build failed, the deploy skips this step and the classic site stays the root.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

BASE_URL = "https://plastiverse.live"
REGION = "california"
# Head elements of the classic home page that the California home must keep (S3.8 metadata).
HEAD_KEEP = (
    re.compile(r'<link rel="canonical"[^>]*>'),
    re.compile(r'<meta property="og:[^"]+"[^>]*>'),
    re.compile(r'<link rel="alternate" type="application/atom\+xml"[^>]*>'),
    re.compile(r'<script type="application/ld\+json">.*?</script>', re.S),
)
# Retired addresses (relative to the output root) removed from the output.
RETIRED = ("app", "grants.html", "sem.html", "expert.html", "experts", "institutions")
MARKER = "<!-- atlas-head-metadata -->"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _framework_pages(dist: Path) -> list[str]:
    region = dist / REGION
    return sorted(p.stem for p in region.glob("*.html") if p.stem != "404")


def home_head_extras(classic_index: Path, base_url: str = BASE_URL) -> str:
    """The classic home's S3.8 head metadata, retargeted to the California home."""
    if not classic_index.is_file():
        return ""
    head = classic_index.read_text(encoding="utf-8").split("</head>", 1)[0]
    found: list[str] = []
    for pattern in HEAD_KEEP:
        found.extend(match.group(0) for match in pattern.finditer(head))
    base = base_url.rstrip("/")
    text = "\n".join(found)
    text = text.replace(f'"{base}/"', f'"{base}/{REGION}/"')
    return text.replace('href="feed.xml"', 'href="../feed.xml"')


def root_head_extras(base_url: str = BASE_URL) -> str:
    """Canonical link and Atom feed link for the global page."""
    base = base_url.rstrip("/")
    return (
        f'<link rel="canonical" href="{base}/">\n'
        '<link rel="alternate" type="application/atom+xml" '
        'title="New CA plastics papers and awards" href="feed.xml">'
    )


def patch_head(page: Path, extras: str) -> None:
    """Insert ``extras`` before ``</head>`` once (idempotent)."""
    text = page.read_text(encoding="utf-8")
    if MARKER in text or not extras:
        return
    if "</head>" not in text:
        raise ValueError(f"{page} has no </head>")
    _write(page, text.replace("</head>", f"{MARKER}\n{extras}\n</head>", 1))


def assemble(site: Path, dist: Path, out: Path, *, base_url: str = BASE_URL) -> dict[str, int]:
    """Build ``out`` = classic ``site`` + Framework ``dist``, without the retired addresses.

    ``out`` may equal ``site`` (the deploy works in place on its checkout); otherwise ``site``
    is copied first and left untouched.
    """
    site, dist, out = Path(site), Path(dist), Path(out)
    if not (dist / "index.html").is_file() or not (dist / REGION / "index.html").is_file():
        raise FileNotFoundError(
            f"{dist} has no index.html or {REGION}/index.html; build the Framework app first"
        )
    extras = home_head_extras(site / "index.html", base_url)
    if out.resolve() != site.resolve():
        if out.exists():
            shutil.rmtree(out)
        top = site.resolve()

        def retired_at_top(folder: str, names: list[str]) -> set[str]:
            # Only the root's entries: california/experts/ must survive.
            return set(RETIRED) & set(names) if Path(folder).resolve() == top else set()

        shutil.copytree(site, out, ignore=retired_at_top)
    removed = 0
    for name in RETIRED:
        path = out / name
        if path.is_dir():
            shutil.rmtree(path)
            removed += 1
        elif path.exists():
            path.unlink()
            removed += 1
    shutil.copytree(dist, out, dirs_exist_ok=True)
    patch_head(out / REGION / "index.html", extras)
    patch_head(out / "index.html", root_head_extras(base_url))
    return {"pages": len(_framework_pages(dist)), "removed": removed}
