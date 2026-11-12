"""AT-5 acceptance: Observable Framework shell guardrails (ADR-AT5-SHELL-2026-11-12).

Static checks (always; no Node needed):
  - @observablehq/framework pinned to exactly 1.13.4 in package.json and package-lock.json;
  - the config drops external stylesheets (globalStylesheets: []), and every nav page has a source;
  - every page sits at the top level of framework/src/ (data resolves as ../data/);
  - data files named in loadJson("...")/dataUrl("...") literals exist in site/data/;
  - the shared helpers copied by scripts/sync_shared.mjs exist in site/assets/.
Build checks (with --dist, after `npm run build`):
  - every page rendered; no external CDN or font hosts; no root-absolute asset paths;
  - per-page first-load payload (HTML + preloaded modules + stylesheets) <= 3 MB gzip (C5 landing).

Usage:
    py -3.14 scripts/check_at5.py                # static only (CI)
    py -3.14 scripts/check_at5.py --dist dist    # after building framework/dist
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "framework"
SRC = FW / "src"
SITE = ROOT / "site"
PIN = "1.13.4"
LANDING_GZIP_BUDGET = 3 * 1024 * 1024
EXTERNAL_HOSTS = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "cdn.jsdelivr.net",
    "unpkg.com",
    "esm.sh",
    "cdnjs.cloudflare.com",
)


def config_pages() -> list[str]:
    text = (FW / "observablehq.config.js").read_text(encoding="utf-8")
    return re.findall(r'path:\s*"/([^"]+)"', text)


def static_problems() -> list[str]:
    problems: list[str] = []
    package = json.loads((FW / "package.json").read_text(encoding="utf-8"))
    if package.get("dependencies", {}).get("@observablehq/framework") != PIN:
        problems.append(f"package.json must pin @observablehq/framework to exactly {PIN}")
    lock = json.loads((FW / "package-lock.json").read_text(encoding="utf-8"))
    locked = lock.get("packages", {}).get("node_modules/@observablehq/framework", {}).get("version")
    if locked != PIN:
        problems.append(f"package-lock.json has @observablehq/framework {locked}, expected {PIN}")

    config = (FW / "observablehq.config.js").read_text(encoding="utf-8")
    if not re.search(r"globalStylesheets:\s*\[\s*\]", config):
        problems.append("observablehq.config.js must set globalStylesheets: [] (no external fonts)")
    pages = config_pages()
    if not pages:
        problems.append("observablehq.config.js lists no pages")
    for page in [*pages, "index"]:
        if "/" in page:
            problems.append(
                f"page {page!r} must sit at the top level of src/ (data resolves as ../data/)"
            )
        if not (SRC / f"{page}.md").is_file():
            problems.append(f"missing page source framework/src/{page}.md")
    for md in SRC.glob("**/*.md"):
        if md.parent != SRC:
            problems.append(f"{md.relative_to(ROOT).as_posix()}: pages must be top-level")

    referenced: set[str] = set()
    for source in [*SRC.glob("*.md"), *SRC.glob("components/*.js")]:
        text = source.read_text(encoding="utf-8")
        referenced.update(re.findall(r'(?:loadJson|dataUrl)\(\s*"([^"$`]+)"', text))
    for name in sorted(referenced):
        if not (SITE / "data" / name).exists():
            problems.append(f"data file named in a page is missing: site/data/{name}")

    sync = (FW / "scripts" / "sync_shared.mjs").read_text(encoding="utf-8")
    block = re.search(r"SHARED_FILES\s*=\s*\[(.*?)\]", sync, re.S)
    for name in re.findall(r'"([^"]+)"', block.group(1) if block else ""):
        if not (SITE / "assets" / name).is_file():
            problems.append(f"sync_shared.mjs copies site/assets/{name}, which does not exist")
    return problems


def gzip_size(path: Path) -> int:
    return len(gzip.compress(path.read_bytes(), compresslevel=9))


def build_report(dist: Path) -> tuple[list[str], dict[str, int]]:
    problems: list[str] = []
    payloads: dict[str, int] = {}
    if not dist.is_dir():
        return [f"build folder {dist} not found; run `npm run build` in framework/"], payloads
    for page in ["index", *config_pages()]:
        html_path = dist / f"{page}.html"
        if not html_path.is_file():
            problems.append(f"page not rendered: {html_path.name}")
            continue
        html = html_path.read_text(encoding="utf-8")
        for host in EXTERNAL_HOSTS:
            if host in html:
                problems.append(f"{html_path.name} references external host {host}")
        if re.search(r'(?:src|href)="/(?!/)', html):
            problems.append(
                f"{html_path.name} uses a root-absolute asset path (breaks the /app/ subpath)"
            )
        assets = re.findall(r'<link rel="(?:modulepreload|stylesheet)" href="\./([^"]+)"', html)
        total = gzip_size(html_path)
        for asset in dict.fromkeys(assets):
            asset_path = dist / asset.split("?")[0]
            if asset_path.is_file():
                total += gzip_size(asset_path)
            else:
                problems.append(f"{html_path.name} preloads missing file {asset}")
        payloads[page] = total
        if total > LANDING_GZIP_BUDGET:
            problems.append(
                f"{html_path.name} first load {total} B gzip exceeds {LANDING_GZIP_BUDGET}"
            )
    for js in (dist / "_import").glob("**/*.js"):
        text = js.read_text(encoding="utf-8", errors="replace")
        for host in EXTERNAL_HOSTS:
            if host in text:
                problems.append(
                    f"{js.relative_to(dist).as_posix()} references external host {host}"
                )
    return problems, payloads


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dist", help="build folder under framework/ to check (e.g. dist)")
    args = parser.parse_args()
    problems = static_problems()
    payloads: dict[str, int] = {}
    if args.dist:
        build_problems, payloads = build_report(FW / args.dist)
        problems += build_problems
    print(
        json.dumps(
            {"pages": ["index", *config_pages()], "first_load_gzip_bytes": payloads}, indent=2
        )
    )
    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        return 1
    print("AT-5 checks passed" + (" (static + build)" if args.dist else " (static)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
