"""Assemble the deployed site with the Observable Framework app at the root (owner H16 switch).

The classic static site (``site/``) still supplies the data, assets, status page, feed and the
deploy-built SEO pages. The Framework build is copied over it, so the Framework ``index.html``
becomes the home page, and every retired address becomes a small redirect stub:

* ``app/<page>`` (the app's address before the switch) -> ``<page>``
* ``index.html#<tab>?<params>`` (classic tabs) -> ``<tab>#<params>`` (script in the new home page)
* ``grants.html`` -> ``funding``; ``sem.html`` -> ``institution``. ``expert.html`` (the full
  expert profile) stays as it is unless the app gains its own ``expert`` page.
* ``experts/index.html`` and ``institutions/index.html`` -> the list pages, in case the host
  serves the SEO folders ``experts/<id>/`` instead of ``experts.html`` for ``/experts``.

Stubs keep the query string and the ``#hash``, carry ``noindex`` and a canonical link, and work
without JavaScript through a meta refresh (which drops the hash). If the Framework build failed,
the deploy skips this step and the classic site stays the root.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

BASE_URL = "https://plastiverse.live"
CLASSIC_TABS = ("experts", "institutions", "monitoring", "funding", "about")
# Head elements of the classic home page that the new home page must keep (S3.8 metadata).
HEAD_KEEP = (
    re.compile(r'<link rel="canonical"[^>]*>'),
    re.compile(r'<meta property="og:[^"]+"[^>]*>'),
    re.compile(r'<link rel="alternate" type="application/atom\+xml"[^>]*>'),
    re.compile(r'<script type="application/ld\+json">.*?</script>', re.S),
)
LEGACY_HASH_SCRIPT = (
    "<script>(function(){var m=location.hash.match(/^#("
    + "|".join(CLASSIC_TABS)
    + r')(?:\?(.*))?$/);if(m){location.replace(m[1]+(m[2]?"#"+m[2]:""));}})();</script>'
)
MARKER = "<!-- atlas-root-switch -->"


def stub_html(target: str, *, canonical: str, title: str = "Page moved") -> str:
    """A redirect page to ``target`` (relative URL) that keeps the query string and hash."""
    t = html.escape(target, quote=True)
    js_target = json.dumps(target)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex">\n'
        f"<title>{html.escape(title)} · CA Plastics Research Atlas</title>\n"
        f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">\n'
        f"<script>location.replace({js_target} + location.search + location.hash);</script>\n"
        f'<meta http-equiv="refresh" content="0; url={t}">\n'
        "</head>\n<body>\n"
        f'<p>This page has moved. Continue to <a href="{t}">the new page</a>.</p>\n'
        "</body>\n</html>\n"
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _framework_pages(dist: Path) -> list[str]:
    return sorted(p.stem for p in dist.glob("*.html") if p.stem not in {"index", "404"})


def _home_head_extras(classic_index: Path) -> str:
    if not classic_index.is_file():
        return ""
    text = classic_index.read_text(encoding="utf-8")
    head = text.split("</head>", 1)[0]
    found: list[str] = []
    for pattern in HEAD_KEEP:
        found.extend(match.group(0) for match in pattern.finditer(head))
    return "\n".join(found)


def patch_home(home: Path, extras: str) -> None:
    """Insert the classic head metadata and the legacy-tab redirect into the new home page."""
    text = home.read_text(encoding="utf-8")
    if MARKER in text:
        return
    block = "\n".join([MARKER, LEGACY_HASH_SCRIPT, extras]).strip() + "\n"
    if "</head>" not in text:
        raise ValueError(f"{home} has no </head>")
    _write(home, text.replace("</head>", block + "</head>", 1))


def assemble(site: Path, dist: Path, out: Path, *, base_url: str = BASE_URL) -> dict[str, int]:
    """Build ``out`` = classic ``site`` + Framework ``dist`` at the root + redirect stubs.

    ``out`` may equal ``site`` (the deploy works in place on its checkout); otherwise ``site``
    is copied first and left untouched.
    """
    site, dist, out = Path(site), Path(dist), Path(out)
    if not (dist / "index.html").is_file():
        raise FileNotFoundError(f"{dist} has no index.html; build the Framework app first")
    extras = _home_head_extras(site / "index.html")
    if out.resolve() != site.resolve():
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(site, out, ignore=shutil.ignore_patterns("app"))
    elif (out / "app").exists():
        shutil.rmtree(out / "app")
    shutil.copytree(dist, out, dirs_exist_ok=True)
    patch_home(out / "index.html", extras)

    pages = _framework_pages(dist)
    base = base_url.rstrip("/")
    stubs: dict[str, tuple[str, str]] = {"app/index.html": ("../", f"{base}/")}
    for page in pages:
        stubs[f"app/{page}.html"] = (f"../{page}", f"{base}/{page}")
    classic_moves = {
        "grants.html": "funding",
        "sem.html": "institution" if "institution" in pages else "institutions",
    }
    if "expert" in pages:
        classic_moves["expert.html"] = "expert"
    for name, target in classic_moves.items():
        stubs[name] = (target, f"{base}/{target}")
    for listing in ("experts", "institutions"):
        if listing in pages and not (out / listing / "index.html").exists():
            stubs[f"{listing}/index.html"] = (f"../{listing}.html", f"{base}/{listing}")
    for rel, (target, canonical) in stubs.items():
        _write(out / rel, stub_html(target, canonical=canonical))
    return {"pages": len(pages), "stubs": len(stubs)}
