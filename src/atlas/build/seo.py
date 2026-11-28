"""Static SEO entity pages and sitemaps (S3.8).

``build_site`` writes crawlable HTML for every expert in the region's ``index.json`` and for
every California-connected institution with works, plus ``sitemap.xml`` and its child
sitemaps. The output is generated at deploy time (gitignored) and links into the
interactive app. Only public bibliographic fields are written: abstracts and contact
details are never copied. Stdlib only, offline and deterministic.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from atlas.regions.scope import region_data_folder

DEFAULT_BASE_URL = "https://plastiverse.live"
ATLAS_NAME = "CA Plastics Research Atlas"
DISCLAIMER = "Independent research atlas; profiles are generated from public bibliographic data."
MAX_URLS_PER_SITEMAP = 50_000
DESCRIPTION_LIMIT = 160
PROFILE_WORK_LIMIT = 10
TOPIC_LIMIT = 5
# PLAT-1 (2026-11-17): the California atlas lives under /california/ (clean break, no redirects);
# the site root is the global Plastiverse Live page. Entity pages are written below
# ``site_dir/california/``. The interactive expert profile (california/expert.html) and feed.xml
# are deliberately absent from the sitemap.
REGION_PATH = "/california"
PAGE_PATHS = (
    "/",
    "/explore",
    f"{REGION_PATH}/",
    f"{REGION_PATH}/authors",
    f"{REGION_PATH}/network",
    f"{REGION_PATH}/institutions",
    f"{REGION_PATH}/monitoring",
    f"{REGION_PATH}/funding",
    f"{REGION_PATH}/evidence",
    f"{REGION_PATH}/policy",
    f"{REGION_PATH}/resources",
    f"{REGION_PATH}/glossary",
    f"{REGION_PATH}/about",
)
SAFE_ID = re.compile(r"[A-Za-z0-9_-]+")
TOPIC_LABEL = re.compile(r'^\s*([A-Za-z0-9_]+):\s*\{\s*label:\s*"([^"]+)"', re.MULTILINE)
HTTPS_URL = re.compile(r"https://[^\s<>\"]+")
ROR_ID = re.compile(r"[0-9a-z]{9}")
LASTMOD = re.compile(r"\d{4}-\d{2}-\d{2}")

# Atlas tokens (framework/src/design/tokens.css, VD-11). tests/test_vd11_classic_pages.py
# checks that these hex values match that file. Fonts are self-hosted at the site root, so
# the page never requests a font or stylesheet from another host.
_DISPLAY_STACK = '"Schibsted Grotesk", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
_BODY_STACK = '"Schibsted Grotesk", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
CSS = "\n".join(
    [
        ":root{color-scheme:light}",
        "body{margin:0;line-height:1.6;color:var(--pv-ink);background:var(--pv-ground);"
        f"font-family:{_BODY_STACK}}}",
        ".wrap{max-width:760px;margin:0 auto;padding:16px}",
        "header.wrap{max-width:none;padding:0;background:var(--pv-ground);color:var(--pv-ink)}",
        "header.wrap p{max-width:760px;margin:0 auto;padding:12px 16px;"
        f"font-family:{_DISPLAY_STACK};font-weight:700}}",
        "header.wrap a{color:var(--pv-ink);text-decoration:none}",
        "header.wrap a:focus-visible{outline-color:var(--pv-coral-ink)}",
        f"h1{{font-family:{_DISPLAY_STACK};font-size:clamp(1.8rem, 1.4rem + 1.4vw, 2.4rem);"
        "font-weight:700;line-height:1.05;color:var(--pv-ink);margin:.3em 0;text-wrap:balance}",
        f"h2{{font-family:{_DISPLAY_STACK};font-size:1.375rem;font-weight:700;"
        "line-height:1.2;color:var(--pv-ink);margin:1.4em 0 .4em}",
        "a{color:var(--pv-coral-ink)}",
        "a:focus-visible{outline:3px solid var(--pv-coral-ink);outline-offset:2px}",
        ".muted{color:var(--pv-ink-2);font-size:.95rem}",
        ".cta{display:inline-block;margin:.6em 0;padding:.6em 1em;border-radius:8px;",
        "  background:var(--pv-ink);color:var(--pv-on-dark);font-weight:600;text-decoration:none}",
        ".skip{position:absolute;left:-999px}",
        ".skip:focus{left:8px;top:8px;background:var(--pv-paper);padding:4px 8px}",
        "footer.wrap{margin-top:24px;border-top:1px solid var(--pv-line)}",
        "li{margin:.3em 0}",
    ]
)

_PLV_MARK = (
    '<svg class="plv-mark" width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">'
    '<circle cx="13" cy="13" r="5"/><g>'
    '<line x1="20.60" y1="13.00" x2="23.40" y2="13.00"/>'
    '<line x1="20.02" y1="15.91" x2="23.72" y2="17.44"/>'
    '<line x1="18.37" y1="18.37" x2="20.35" y2="20.35"/>'
    '<line x1="15.91" y1="20.02" x2="17.44" y2="23.72"/>'
    '<line x1="13.00" y1="20.60" x2="13.00" y2="23.40"/>'
    '<line x1="10.09" y1="20.02" x2="8.56" y2="23.72"/>'
    '<line x1="7.63" y1="18.37" x2="5.65" y2="20.35"/>'
    '<line x1="5.98" y1="15.91" x2="2.28" y2="17.44"/>'
    '<line x1="5.40" y1="13.00" x2="2.60" y2="13.00"/>'
    '<line x1="5.98" y1="10.09" x2="2.28" y2="8.56"/>'
    '<line x1="7.63" y1="7.63" x2="5.65" y2="5.65"/>'
    '<line x1="10.09" y1="5.98" x2="8.56" y2="2.28"/>'
    '<line x1="13.00" y1="5.40" x2="13.00" y2="2.60"/>'
    '<line x1="15.91" y1="5.98" x2="17.44" y2="2.28"/>'
    '<line x1="18.37" y1="7.63" x2="20.35" y2="5.65"/>'
    '<line x1="20.02" y1="10.09" x2="23.72" y2="8.56"/>'
    "</g></svg>"
)


def is_safe_id(value: Any) -> bool:
    """Return True when an ID is safe to use as a path segment (``^[A-Za-z0-9_-]+$``)."""
    return isinstance(value, str) and SAFE_ID.fullmatch(value) is not None


def esc(value: Any) -> str:
    """HTML-escape any data value, quotes included."""
    return html.escape("" if value is None else str(value), quote=True)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def _clip(text: str) -> str:
    text = _text(text)
    if len(text) <= DESCRIPTION_LIMIT:
        return text
    return text[: DESCRIPTION_LIMIT - 3].rstrip() + "..."


def _https(value: Any) -> str | None:
    text = _text(value)
    return text if HTTPS_URL.fullmatch(text) else None


def _doi_url(value: Any) -> str | None:
    text = _text(value)
    if text.startswith("10."):
        text = f"https://doi.org/{text}"
    return _https(text)


def _orcid_url(value: Any) -> str | None:
    url = _https(value)
    return url if url and url.startswith("https://orcid.org/") else None


def _ror_url(value: Any) -> str | None:
    text = _text(value)
    if ROR_ID.fullmatch(text):
        return f"https://ror.org/{text}"
    url = _https(text)
    return url if url and url.startswith("https://ror.org/") else None


def _normalise_base(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if not HTTPS_URL.fullmatch(base):
        raise ValueError(f"base URL must be absolute https: {base_url!r}")
    return base


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write(path: Path, text: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return len(text.encode("utf-8"))


def load_topic_labels(topics_js: Path) -> dict[str, str]:
    """Return topic tag -> label from ``assets/topics.js``, in file (display) order."""
    if not topics_js.is_file():
        return {}
    text = topics_js.read_text(encoding="utf-8")
    return {match.group(1): match.group(2) for match in TOPIC_LABEL.finditer(text)}


def _topic_label(tag: str, labels: dict[str, str]) -> str:
    if tag in labels:
        return labels[tag]
    return _sentence(_text(re.sub(r"[_:]+", " ", tag)))


def _top_topics(tags: Any, labels: dict[str, str]) -> list[str]:
    rank = {tag: position for position, tag in enumerate(labels)}
    unique = dict.fromkeys(tag for tag in tags if isinstance(tag, str) and tag)
    ordered = sorted(unique, key=lambda tag: (rank.get(tag, len(rank)), tag))
    names = [_topic_label(tag, labels) for tag in ordered]
    return [name for name in names if name][:TOPIC_LIMIT]


def _json_ld(data: dict[str, Any]) -> str:
    """Serialise JSON-LD so no data value can close the script element."""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _page(
    *,
    base: str = DEFAULT_BASE_URL,
    title: str,
    description: str,
    canonical: str,
    og_type: str,
    body: str,
    schema: dict[str, Any],
) -> str:
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{esc(title)}</title>",
        f'<meta name="description" content="{esc(description)}">',
        f'<link rel="canonical" href="{esc(canonical)}">',
        '<link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">',
        '<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">',
        '<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">',
        f'<meta property="og:type" content="{esc(og_type)}">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(description)}">',
        f'<meta property="og:url" content="{esc(canonical)}">',
        f'<meta property="og:site_name" content="{esc(ATLAS_NAME)}">',
        '<meta name="twitter:card" content="summary">',
        f'<script type="application/ld+json">{_json_ld(schema)}</script>',
        f"<style>{CSS}</style>",
        f'<link rel="stylesheet" href="{esc(base)}/assets/pv-profile.css">',
        "</head>",
        '<body class="seo-profile">',
        body,
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(lines)


def _chrome_top(base: str) -> list[str]:
    return [
        '<a class="skip" href="#main">Skip to content</a>',
        f'<header class="wrap"><p><a class="plv-brand" href="{esc(base)}" '
        f'aria-label="Plastiverse Live home">{_PLV_MARK}'
        '<span class="plv-wm" aria-hidden="true">PLASTIVERSE <b>LIVE</b></span>'
        f"</a></p></header>",
        '<main class="wrap" id="main">',
    ]


def _chrome_bottom(base: str) -> list[str]:
    return [
        f'<p><a href="{esc(base)}{REGION_PATH}/">Back to the {esc(ATLAS_NAME)}</a></p>',
        "</main>",
        '<footer class="page-footer"><div class="footer-inner">'
        f'<img class="footer-logo" src="{esc(base)}/assets/landing/logo_282.webp" '
        'width="282" height="282" '
        'alt="Plastiverse Live: From Pollution to Progress">'
        f'<p class="footer-copy">{esc(DISCLAIMER)}</p></div></footer>',
    ]


def _expert_page(
    author: dict[str, Any], works: list[Any], labels: dict[str, str], base: str
) -> str:
    aid = author["author_id"]
    name = _text(author.get("name")) or aid
    affiliations = [a for a in (_text(x) for x in author.get("primary_affiliations") or []) if a]
    primary = affiliations[0] if affiliations else ""
    topics = _top_topics(author.get("domain_tags") or [], labels)
    plastic_count = _int(author.get("plastic_works_count"))
    citations = _int(author.get("plastic_citations"))
    url = f"{base}{REGION_PATH}/experts/{aid}/"
    interactive = f"{base}{REGION_PATH}/expert.html#author={aid}"
    orcid = _orcid_url(author.get("orcid"))

    summary = f"{name}, {primary}." if primary else f"{name}."
    summary += (
        f" {plastic_count} plastic-related works and {citations} plastic-related citations"
        " in the Atlas."
    )
    if topics:
        summary += f" Topics: {', '.join(topics[:3])}."
    description = _clip(summary)

    outside = ""
    if author.get("current_in_ca") is False:
        last = _int(author.get("last_ca_year"))
        outside = (
            f"Now outside California (last California affiliation {last})"
            if last
            else "Now outside California"
        )

    ranked = sorted(
        (w for w in works if isinstance(w, dict) and w.get("plastic_related")),
        key=lambda w: (
            -_int(w.get("cited_by_count")),
            -_int(w.get("year")),
            _text(w.get("title")),
        ),
    )[:PROFILE_WORK_LIMIT]
    items = []
    for work in ranked:
        year = _int(work.get("year"))
        meta_parts = [
            str(year) if year else "",
            _text(work.get("journal")),
            f"{_int(work.get('cited_by_count'))} citations",
        ]
        meta = " · ".join(part for part in meta_parts if part)
        doi = _doi_url(work.get("doi"))
        link = f' <a href="{esc(doi)}" rel="noopener">DOI</a>' if doi else ""
        items.append(
            '<li><span data-public-text="quoted">'
            + esc(_text(work.get("title")) or "Untitled work")
            + '</span><br><span class="muted">'
            + esc(meta)
            + "</span>"
            + link
            + "</li>"
        )

    parts = _chrome_top(base)
    parts.append(f"<h1>{esc(name)}</h1>")
    if primary:
        parts.append(f'<p class="affil">{esc(primary)}</p>')
    if outside:
        parts.append(f'<p class="muted">{esc(outside)}</p>')
    parts.append(
        f'<p><a class="cta" href="{esc(interactive)}">Open the interactive profile</a></p>'
    )
    stats = [
        f"{_int(author.get('work_count'))} works in the Atlas snapshot",
        f"{plastic_count} plastic-related works",
        f"{_int(author.get('ca_works_count'))} California-connected works",
        f"{citations} plastic-related citations",
    ]
    parts.append("<h2>Research summary</h2>")
    parts.append("<ul>" + "".join(f"<li>{esc(s)}</li>" for s in stats) + "</ul>")
    if topics:
        parts.append("<h2>Topics</h2>")
        parts.append("<ul>" + "".join(f"<li>{esc(t)}</li>" for t in topics) + "</ul>")
    parts.append("<h2>Plastic-related works</h2>")
    if items:
        parts.append("<ol>" + "".join(items) + "</ol>")
    else:
        parts.append('<p class="muted">No plastic-related works in this snapshot.</p>')
    identifiers = []
    if orcid:
        identifiers.append(f'<li><a href="{esc(orcid)}" rel="noopener">ORCID</a></li>')
    identifiers.append(
        f'<li><a href="https://openalex.org/{esc(aid)}" rel="noopener">OpenAlex</a></li>'
    )
    parts.append("<h2>Identifiers</h2>")
    parts.append("<ul>" + "".join(identifiers) + "</ul>")
    parts.extend(_chrome_bottom(base))

    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": name,
        "url": url,
        "sameAs": [u for u in (orcid, f"https://openalex.org/{aid}") if u],
    }
    if affiliations:
        schema["affiliation"] = [{"@type": "Organization", "name": a} for a in affiliations]
    if topics:
        schema["knowsAbout"] = topics
    return _page(
        base=base,
        title=f"{name} — plastics researcher | {ATLAS_NAME}",
        description=description,
        canonical=url,
        og_type="profile",
        body="\n".join(parts),
        schema=schema,
    )


def _load_networks(path: Path) -> list[dict[str, Any]]:
    """Network entries from ``research_networks.json`` that have a name and an https URL."""
    cards: list[dict[str, Any]] = []
    for network in _read_json(path).get("networks") or []:
        if isinstance(network, dict) and _https(network.get("url")) and _text(network.get("name")):
            cards.append(network)
    return cards


def _network_ids(network: dict[str, Any], key: str) -> list[Any]:
    ids = network.get(key)
    return ids if isinstance(ids, list) else []


def _network_link(network: dict[str, Any]) -> str:
    return f'<a href="{esc(_https(network["url"]))}">{esc(_text(network["name"]))}</a>'


def _sub_organization(network: dict[str, Any], base: str) -> dict[str, Any]:
    card: dict[str, Any] = {
        "@type": "Organization",
        "name": _text(network["name"]),
        "url": _https(network["url"]),
    }
    description = _text(network.get("description"))
    if description:
        card["description"] = description
    logo = network.get("logo")
    path = _text(logo.get("path")) if isinstance(logo, dict) else ""
    if path and not path.startswith("/") and ".." not in path.split("/"):
        card["logo"] = f"{base}/{path}"
    return card


def _institution_page(
    inst: dict[str, Any],
    experts: dict[str, str],
    base: str,
    networks: list[dict[str, Any]] | None = None,
) -> str:
    iid = inst["inst_id"]
    name = _text(inst.get("name")) or iid
    city = _text(inst.get("city"))
    kind = _sentence(_text(inst.get("atlas_type")))
    count = _int(inst.get("work_count"))
    ror = _ror_url(inst.get("ror"))
    url = f"{base}{REGION_PATH}/institutions/{iid}/"

    place = f", {city}" if city else ""
    description = _clip(f"{name}{place}. {count} works in the {ATLAS_NAME}.")

    linked: list[tuple[str, str]] = []
    seen: set[str] = set()
    for expert in inst.get("top_experts") or []:
        if not isinstance(expert, dict):
            continue
        aid = expert.get("author_id")
        if not is_safe_id(aid) or aid not in experts or aid in seen:
            continue
        seen.add(aid)
        linked.append((aid, experts[aid]))

    hosted = [n for n in networks or [] if iid in _network_ids(n, "host_institution_ids")]
    member = [n for n in networks or [] if iid in _network_ids(n, "member_institution_ids")]

    parts = _chrome_top(base)
    parts.append(f"<h1>{esc(name)}</h1>")
    facts = [f"Type: {kind}" if kind else "", f"City: {city}" if city else ""]
    facts.append(f"{count} works in the Atlas")
    parts.append("<ul>" + "".join(f"<li>{esc(f)}</li>" for f in facts if f) + "</ul>")
    if hosted or member:
        items = [f"<li>{_network_link(n)} — hosted here</li>" for n in hosted]
        items += [
            f"<li>{_network_link(n)} — researchers here are listed contributors</li>"
            for n in member
        ]
        parts.append("<h2>Research networks</h2>")
        parts.append("<ul>" + "".join(items) + "</ul>")
        for network in hosted + member:
            disclosure = _text(network.get("disclosure"))
            if disclosure:
                parts.append(f"<p>Disclosure: {esc(disclosure)}</p>")
    if linked:
        parts.append("<h2>Top authors</h2>")
        items = [
            f'<li><a href="{esc(base)}{REGION_PATH}/experts/{aid}/">{esc(ename)}</a></li>'
            for aid, ename in linked
        ]
        parts.append("<ul>" + "".join(items) + "</ul>")
    parts.extend(_chrome_bottom(base))

    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": name,
        "url": url,
        "description": description,
    }
    if city:
        schema["address"] = {"@type": "PostalAddress", "addressLocality": city}
    if ror:
        schema["sameAs"] = [ror]
    if hosted:
        schema["subOrganization"] = [_sub_organization(n, base) for n in hosted]
    return _page(
        base=base,
        title=f"{name} — plastics research | {ATLAS_NAME}",
        description=description,
        canonical=url,
        og_type="website",
        body="\n".join(parts),
        schema=schema,
    )


def _lastmod(build_meta: dict[str, Any]) -> str | None:
    match = LASTMOD.match(_text(build_meta.get("generated_at")))
    return match.group(0) if match else None


def _urlset(entries: list[tuple[str, str | None]]) -> str:
    if len(entries) > MAX_URLS_PER_SITEMAP:
        raise ValueError(f"sitemap has {len(entries)} URLs; the limit is {MAX_URLS_PER_SITEMAP}")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_escape(loc)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _sitemap_index(entries: list[tuple[str, str | None]]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod in entries:
        lines.append("  <sitemap>")
        lines.append(f"    <loc>{xml_escape(loc)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </sitemap>")
    lines.append("</sitemapindex>")
    return "\n".join(lines) + "\n"


def build_site(site_dir: Path, base_url: str = DEFAULT_BASE_URL) -> dict[str, int]:
    """Write expert/institution pages under ``site_dir/california`` and sitemaps under ``site_dir``.

    Returns counts of pages, sitemap URLs and bytes written. Input is read from
    ``site_dir/data``; topic labels come from ``site_dir/assets/topics.js`` when present.
    Research networks come from ``site_dir/data/<region>/research_networks.json`` when present (a
    missing file means no networks).
    """
    base = _normalise_base(base_url)
    data_dir = site_dir / "data" / region_data_folder()
    region_dir = site_dir / REGION_PATH.strip("/")
    index = _read_json(data_dir / "index.json")

    experts: dict[str, dict[str, Any]] = {}
    for author in index.get("authors") or []:
        if isinstance(author, dict) and is_safe_id(author.get("author_id")):
            experts.setdefault(author["author_id"], author)
    expert_names = {aid: (_text(a.get("name")) or aid) for aid, a in experts.items()}
    labels = load_topic_labels(site_dir / "assets" / "topics.js")
    networks = _load_networks(data_dir / "research_networks.json")

    written = 0
    for aid, author in experts.items():
        profile = _read_json(data_dir / "authors" / f"{aid}.json")
        works = profile.get("works") or []
        page = _expert_page(author, works, labels, base)
        written += _write(region_dir / "experts" / aid / "index.html", page)

    institutions: dict[str, dict[str, Any]] = {}
    for inst in _read_json(data_dir / "institutions.json").get("institutions") or []:
        if not isinstance(inst, dict) or not is_safe_id(inst.get("inst_id")):
            continue
        if inst.get("ca_flag") is True and _int(inst.get("work_count")) > 0:
            institutions.setdefault(inst["inst_id"], inst)
    for iid, inst in institutions.items():
        page = _institution_page(inst, expert_names, base, networks)
        written += _write(region_dir / "institutions" / iid / "index.html", page)

    lastmod = _lastmod(_read_json(data_dir / "build_metadata.json"))
    sitemaps = {
        "sitemap-pages.xml": [(f"{base}{path}", lastmod) for path in PAGE_PATHS],
        "sitemap-experts.xml": [
            (f"{base}{REGION_PATH}/experts/{aid}/", lastmod) for aid in experts
        ],
        "sitemap-institutions.xml": [
            (f"{base}{REGION_PATH}/institutions/{iid}/", lastmod) for iid in institutions
        ],
    }
    for filename, entries in sitemaps.items():
        written += _write(site_dir / filename, _urlset(entries))
    index_entries = [(f"{base}/{filename}", lastmod) for filename in sitemaps]
    written += _write(site_dir / "sitemap.xml", _sitemap_index(index_entries))

    return {
        "experts": len(experts),
        "institutions": len(institutions),
        "sitemap_urls": sum(len(entries) for entries in sitemaps.values()),
        "bytes": written,
    }
