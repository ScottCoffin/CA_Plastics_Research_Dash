"""Acceptance check for the S3.8 search-findability outputs (stdlib only, offline).

Validates ``robots.txt``, the sitemap index and child sitemaps, a sample of expert pages
(all institution pages) for head tags, parseable JSON-LD of the right ``@type``, and
the absence of email addresses and abstract text. Exits 1 with messages on failure.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_BASE_URL = "https://plastiverse.live"
MAX_URLS_PER_SITEMAP = 50_000
MIN_EXPERT_SAMPLE = 20
EXPERT_SAMPLE_SIZE = 25
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
JSON_LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)
ROOT = Path(__file__).resolve().parents[1]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def check_robots(site: Path, base: str) -> list[str]:
    path = site / "robots.txt"
    if not path.is_file():
        return [f"missing {path.name}"]
    text = path.read_text(encoding="utf-8")
    if f"Sitemap: {base}/sitemap.xml" not in text:
        return [f"{path.name} does not reference {base}/sitemap.xml"]
    return []


def check_sitemaps(site: Path, base: str) -> list[str]:
    errors: list[str] = []
    index_path = site / "sitemap.xml"
    if not index_path.is_file():
        return ["missing sitemap.xml"]
    try:
        index = ET.parse(index_path).getroot()
    except ET.ParseError as exc:
        return [f"sitemap.xml is not well-formed: {exc}"]
    if _local(index.tag) != "sitemapindex":
        errors.append("sitemap.xml root is not sitemapindex")
    locs = [el.text or "" for el in index.iter(f"{SITEMAP_NS}loc")]
    if not locs:
        errors.append("sitemap.xml lists no child sitemaps")
    for loc in locs:
        errors.extend(_check_loc(loc, base, "sitemap.xml"))
        child = site / loc.removeprefix(base + "/")
        if not child.is_file():
            errors.append(f"child sitemap missing on disk: {child.name}")
            continue
        try:
            urlset = ET.parse(child).getroot()
        except ET.ParseError as exc:
            errors.append(f"{child.name} is not well-formed: {exc}")
            continue
        urls = [el.text or "" for el in urlset.iter(f"{SITEMAP_NS}loc")]
        if len(urls) > MAX_URLS_PER_SITEMAP:
            errors.append(f"{child.name} has {len(urls)} URLs (max {MAX_URLS_PER_SITEMAP})")
        if not urls:
            errors.append(f"{child.name} has no URLs")
        for url in urls:
            errors.extend(_check_loc(url, base, child.name))
    return errors


def _check_loc(loc: str, base: str, source: str) -> list[str]:
    if not loc.startswith("https://") or not loc.startswith(base + "/"):
        return [f"{source}: <loc> is not an absolute https URL under {base}: {loc}"]
    return []


def check_page(path: Path, base: str, expected_type: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    label = str(path.relative_to(path.parents[2]))
    errors: list[str] = []
    if text.count("<title>") != 1:
        errors.append(f"{label}: expected exactly one <title>")
    if len(re.findall(r'<meta name="description" content="[^"]+">', text)) != 1:
        errors.append(f"{label}: expected exactly one meta description")
    canonicals = re.findall(r'<link rel="canonical" href="([^"]+)">', text)
    if len(canonicals) != 1 or not canonicals[0].startswith(base + "/"):
        errors.append(f"{label}: expected one canonical under {base}")
    blocks = JSON_LD.findall(text)
    if len(blocks) != 1:
        errors.append(f"{label}: expected exactly one JSON-LD block")
    else:
        try:
            data = json.loads(blocks[0])
        except json.JSONDecodeError as exc:
            errors.append(f"{label}: JSON-LD does not parse: {exc}")
        else:
            if not isinstance(data, dict) or data.get("@type") != expected_type:
                errors.append(f"{label}: JSON-LD @type is not {expected_type}")
    if EMAIL.search(text):
        errors.append(f"{label}: email-like string found")
    if "abstract" in text.lower():
        errors.append(f"{label}: abstract text found")
    return errors


def _sample(paths: list[Path]) -> list[Path]:
    if len(paths) <= EXPERT_SAMPLE_SIZE:
        return paths
    step = len(paths) / EXPERT_SAMPLE_SIZE
    return [paths[int(i * step)] for i in range(EXPERT_SAMPLE_SIZE)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    parser.add_argument("--base", default=DEFAULT_BASE_URL)
    args = parser.parse_args(argv)
    site: Path = args.site
    base = args.base.rstrip("/")

    errors = check_robots(site, base) + check_sitemaps(site, base)

    expert_pages = sorted((site / "experts").glob("*/index.html"))
    institution_pages = sorted((site / "institutions").glob("*/index.html"))
    if len(expert_pages) < MIN_EXPERT_SAMPLE:
        errors.append(f"only {len(expert_pages)} expert pages; need >= {MIN_EXPERT_SAMPLE}")
    if not institution_pages:
        errors.append("no institution pages found")
    for page in _sample(expert_pages):
        errors.extend(check_page(page, base, "Person"))
    for page in institution_pages:
        errors.extend(check_page(page, base, "Organization"))

    if errors:
        for message in errors[:50]:
            print(f"FAIL: {message}", file=sys.stderr)
        if len(errors) > 50:
            print(f"FAIL: ... {len(errors) - 50} more", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "expert_pages": len(expert_pages),
                "expert_pages_sampled": len(_sample(expert_pages)),
                "institution_pages": len(institution_pages),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
