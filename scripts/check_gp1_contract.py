"""GP-1 recorded California regression contract (docs/GLOBAL_PARITY.md, "GP-1 contract").

Every GP slice must leave the California atlas unchanged. This script checks three things against a
recorded contract (config/gp1_california_contract.json):

1. Routes: every recorded California route exists in the assembled site.
2. DOM smoke (Playwright Chromium, headless): each route loads with no page error and HTTP 200,
   its recorded root selector matches at least its minimum count, its <main> text is at least its
   minimum length, and there is no horizontal overflow at 390 px. Full-page screenshots at 1440 and
   390 px are written with --screenshots DIR (for human comparison only; not compared).
3. Link graph (offline, data files only): every author, institution and work reference that the
   UI turns into a link resolves. Broken links must be 0 (or listed in the contract allowlist).

Usage:
    py -3.14 scripts/check_gp1_contract.py --site scratch/gp1_site --record     # write the contract
    py -3.14 scripts/check_gp1_contract.py --site scratch/gp1_site  # compare (exit 1 on drift)
    py -3.14 scripts/check_gp1_contract.py --site scratch/gp1_site --screenshots scratch/gp1_shots
    py -3.14 scripts/check_gp1_contract.py --site scratch/gp1_site --links-only  # no browser

--site is an assembled deploy folder (scripts/assemble_site.py --out). The link graph reads its
data/california/ folder. The browser serves the folder on 127.0.0.1 on a free port and aborts every
request that is not to 127.0.0.1.
"""

from __future__ import annotations

import argparse
import functools
import json
import math
import sys
import threading
import time
from collections import Counter
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config" / "gp1_california_contract.json"
SCHEMA = "gp1-v1"
DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}
LOCAL_HOSTS = ("127.0.0.1", "localhost")
COUNT_FACTOR = 0.8  # recorded minimum = 80% of today's count
TEXT_FACTOR = 0.5  # recorded minimum text length = 50% of today's length
MIN_TEXT_FLOOR = 100
# Root selector per route (derived from the built pages on 2026-11-26). Anything else uses "main".
ROUTE_SELECTORS = {
    "/california/": "main a[href]",
    "/california/about": "main article",
    "/california/authors": "#experts-root .expert-card",
    "/california/evidence": "main table",
    "/california/funding": "main table",
    "/california/glossary": "main a[href]",
    "/california/institution": "main a[href]",
    "/california/institutions": "main article",
    "/california/monitoring": "main table",
    "/california/network": "main svg",
    "/california/policy": "main a[href]",
    "/california/quality": "main article",
    "/california/resources": "main a[href]",
    "/california/search": "main h1",
    "/california/styleguide": "main svg",
    "/california/topics": "main article",
    "/california/expert.html": "main a[href]",
}
CLASSIC_ROUTES = ("california/expert.html",)


# ---------------------------------------------------------------- routes


def california_routes(repo: Path = ROOT) -> list[dict]:
    """Framework California pages (framework/src/california/*.md) and the classic expert profile."""
    routes = []
    for md in sorted((repo / "framework" / "src" / "california").glob("*.md")):
        stem = md.stem
        if stem == "index":
            routes.append({"route": "/california/", "file": "california/index.html"})
        else:
            routes.append({"route": f"/california/{stem}", "file": f"california/{stem}.html"})
    for rel in CLASSIC_ROUTES:
        routes.append({"route": "/" + rel, "file": rel})
    return routes


def missing_routes(contract_routes: list[dict], site: Path) -> list[str]:
    return [r["file"] for r in contract_routes if not (site / r["file"]).is_file()]


def new_source_routes(contract_routes: list[dict], repo: Path = ROOT) -> list[str]:
    known = {r["route"] for r in contract_routes}
    return [r["route"] for r in california_routes(repo) if r["route"] not in known]


# ---------------------------------------------------------------- link graph (pure)


def _ids(rows: list[dict], key: str) -> set[str]:
    return {row[key] for row in rows}


def check_link_graph(
    index: dict,
    institutions: list[dict],
    institution_works: dict[str, dict],
    author_files: dict[str, dict],
) -> dict:
    """Check every author, institution and work reference the UI turns into a link.

    Inputs mirror site/data/california/: index.json (dict with "authors" and "works"),
    institutions.json rows, institution_works/<id>.json payloads keyed by file stem, and
    authors/<id>.json payloads keyed by file stem. Returns {"checked": {kind: n}, "unlinked":
    {kind: n}, "broken": [str], "info": {...}}.

    Rules:
    - An author reference is a profile link when the author is in the atlas index (institution
      experts with in_atlas_index true; co-authors that are indexed experts, as expert_page.js:211
      links them). A co-author that is not indexed is plain text, so it is counted under
      "unlinked", not checked.
    - Every indexed author needs an authors/<id>.json file.
    - Institution references must name an institutions.json row; work references must name a row of
      index.json works.
    """
    authors = index["authors"]
    works = index["works"]
    author_ids = _ids(authors, "author_id")
    work_ids = _ids(works, "work_id")
    inst_ids = _ids(institutions, "inst_id")
    checked: Counter[str] = Counter()
    unlinked: Counter[str] = Counter()
    broken: list[str] = []

    def bad(kind: str, src: str, target: str) -> None:
        broken.append(f"{kind}: {src} -> {target}")

    def inst_ref(kind: str, src: str, target: str) -> None:
        checked[kind] += 1
        if target not in inst_ids:
            bad(kind, src, target)

    def work_ref(kind: str, src: str, target: str) -> None:
        checked[kind] += 1
        if target not in work_ids:
            bad(kind, src, target)

    def author_ref(kind: str, src: str, target: str) -> None:
        checked[kind] += 1
        if target not in author_ids or target not in author_files:
            bad(kind, src, target)

    def expert_ref(kind: str, src: str, target: str) -> None:
        # Co-author ids in works: a profile link only when the author is indexed (expert_page.js).
        if target not in author_ids:
            unlinked[kind] += 1  # plain-text co-author, no profile link by design
            return
        author_ref(kind, src, target)

    for author in authors:
        src = f"author {author['author_id']}"
        checked["index.author->author_file"] += 1
        if author["author_id"] not in author_files:
            bad("index.author->author_file", src, author["author_id"])
        for inst in author["institution_ids"]:
            inst_ref("index.author->institution", src, inst)
        for work in author["work_ids"]:
            work_ref("index.author->work", src, work)

    for work in works:
        src = f"work {work['work_id']}"
        for aid in work["author_ids"]:
            expert_ref("index.work->author", src, aid)
        for inst in work["institution_ids"]:
            inst_ref("index.work->institution", src, inst)

    for row in institutions:
        src = f"institution {row['inst_id']}"
        for expert in row["top_experts"]:
            if expert.get("in_atlas_index"):
                author_ref("institutions.top_expert->author", src, expert["author_id"])
            else:
                unlinked["institutions.top_expert (not indexed)"] += 1

    for stem, payload in institution_works.items():
        src = f"institution_works {stem}"
        checked["institution_works.file->institution"] += 1
        if stem not in inst_ids:
            bad("institution_works.file->institution", src, stem)
        for expert in payload["experts"]:
            if expert.get("in_atlas_index"):
                author_ref("institution_works.expert->author", src, expert["author_id"])
            else:
                unlinked["institution_works.expert (not indexed)"] += 1
        for work in payload["works"]:
            work_ref("institution_works.work->work", src, work["work_id"])
            for aid in work["author_ids"]:
                expert_ref("institution_works.work->author", src, aid)
            for inst in work["institution_ids"]:
                inst_ref("institution_works.work->institution", src, inst)

    for stem, payload in author_files.items():
        src = f"authors {stem}"
        checked["author_file.file->author"] += 1
        if stem not in author_ids:
            bad("author_file.file->author", src, stem)
        for inst in payload["author"]["institution_ids"]:
            inst_ref("author_file.author->institution", src, inst)
        for work in payload["author"]["work_ids"]:
            work_ref("author_file.author->work", src, work)
        for work in payload["works"]:
            work_ref("author_file.work->work", src, work["work_id"])
            for aid in work["author_ids"]:
                expert_ref("author_file.work->author", src, aid)
            for inst in work["institution_ids"]:
                inst_ref("author_file.work->institution", src, inst)

    info = {
        "institutions_without_profile_file": len(inst_ids - set(institution_works)),
        "indexed_authors": len(author_ids),
        "indexed_works": len(work_ids),
        "institutions": len(inst_ids),
    }
    return {
        "checked": dict(sorted(checked.items())),
        "unlinked": dict(sorted(unlinked.items())),
        "broken": sorted(broken),
        "info": info,
    }


def load_link_inputs(data_dir: Path) -> dict:
    """Read the California data files the link graph needs (no browser, no network)."""
    index = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
    institutions = json.loads((data_dir / "institutions.json").read_text(encoding="utf-8"))
    institution_works = {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((data_dir / "institution_works").glob("*.json"))
    }
    author_files = {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((data_dir / "authors").glob("*.json"))
    }
    return {
        "index": index,
        "institutions": institutions["institutions"],
        "institution_works": institution_works,
        "author_files": author_files,
    }


def summarize_links(report: dict) -> dict:
    """The part of a link report that goes into the contract."""
    total = sum(report["checked"].values())
    return {
        "total_checked": total,
        "checked": report["checked"],
        "unlinked_by_design": report["unlinked"],
        "broken": len(report["broken"]),
        "allowlist": [],
    }


def compare_links(contract_links: dict, report: dict) -> list[str]:
    """Failures when the observed graph has a broken link that is not in the contract allowlist."""
    allowed = set(contract_links.get("allowlist", []))
    return [f"broken link: {b}" for b in report["broken"] if b not in allowed]


# ---------------------------------------------------------------- DOM contract (pure)


def min_count(recorded: int) -> int:
    return max(1, math.floor(recorded * COUNT_FACTOR))


def min_text(recorded: int) -> int:
    return max(MIN_TEXT_FLOOR, math.floor(recorded * TEXT_FACTOR))


def build_dom_entry(route: dict, observed: dict) -> dict:
    """Turn one observed page into a contract entry (counts recorded, minimums derived)."""
    return {
        "route": route["route"],
        "file": route["file"],
        "selector": observed["selector"],
        "recorded_count": observed["count"],
        "min_count": min_count(observed["count"]),
        "recorded_main_chars": observed["main_chars"],
        "min_main_chars": min_text(observed["main_chars"]),
    }


def compare_dom(contract_routes: list[dict], observed: dict[str, dict]) -> list[str]:
    """Failures for one observed run against the recorded contract (observed keyed by route)."""
    problems: list[str] = []
    for entry in contract_routes:
        name = entry["route"]
        seen = observed.get(name)
        if seen is None:
            problems.append(f"{name}: not observed")
            continue
        for err in seen.get("page_errors", []):
            problems.append(f"{name}: page error: {err}")
        if seen.get("status") not in (None, 200):
            problems.append(f"{name}: HTTP status {seen['status']}")
        if seen["count"] < entry["min_count"]:
            problems.append(
                f"{name}: {entry['selector']} matched {seen['count']}, "
                f"below the minimum {entry['min_count']}"
            )
        if seen["main_chars"] < entry["min_main_chars"]:
            problems.append(
                f"{name}: <main> text {seen['main_chars']} chars, below {entry['min_main_chars']}"
            )
        if seen.get("overflow_390", 0) > 0:
            problems.append(f"{name}: horizontal overflow at 390 px ({seen['overflow_390']} px)")
    return problems


def compare_routes_present(contract_routes: list[dict], site: Path) -> list[str]:
    return [f"route missing from site: {f}" for f in missing_routes(contract_routes, site)]


# ---------------------------------------------------------------- browser


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
        return


def _serve(site: Path) -> ThreadingHTTPServer:
    handler = functools.partial(_QuietHandler, directory=str(site))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)  # port 0: a free port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _observe_route(context, base: str, route: dict, shots: Path | None) -> dict:
    selector = ROUTE_SELECTORS.get(route["route"], "main")
    stem = route["route"].strip("/").replace("/", "_").replace(".", "_") or "index"
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)[:200]))
    status = None
    try:
        response = page.goto(f"{base}/{route['file']}", wait_until="load", timeout=30000)
        status = response.status if response is not None else None
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:  # noqa: BLE001 - a slow page is not a failure by itself
            pass
        count = page.locator(selector).count()
        main_chars = page.evaluate(
            "() => (document.querySelector('main') || document.body).innerText.length"
        )
        if shots is not None:
            page.screenshot(path=str(shots / f"{stem}-1440.png"), full_page=True)
        page.set_viewport_size(MOBILE)
        page.wait_for_timeout(300)
        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        if shots is not None:
            page.screenshot(path=str(shots / f"{stem}-390.png"), full_page=True)
    finally:
        page.close()
    return {
        "selector": selector,
        "count": count,
        "main_chars": main_chars,
        "status": status,
        "page_errors": errors,
        "overflow_390": overflow,
    }


def observe_dom(site: Path, routes: list[dict], shots: Path | None) -> dict[str, dict]:
    from playwright.sync_api import sync_playwright  # lazy: the link graph needs no browser

    server = _serve(site)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    observed: dict[str, dict] = {}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport=DESKTOP)

            def only_local(route, request) -> None:
                host = urlparse(request.url).hostname or ""
                if host in LOCAL_HOSTS:
                    route.continue_()
                else:
                    route.abort()

            context.route("**/*", only_local)
            context.set_default_timeout(30000)
            for route in routes:
                observed[route["route"]] = _observe_route(context, base, route, shots)
            browser.close()
    finally:
        server.shutdown()
    return observed


# ---------------------------------------------------------------- commands


def seo_entity_counts(site: Path) -> dict[str, int]:
    """Deploy-built SEO entity pages, if this folder has them (counted, not required)."""
    counts = {}
    for kind in ("experts", "institutions"):
        folder = site / "california" / kind
        if folder.is_dir():
            counts[f"california/{kind}"] = sum(1 for _ in folder.glob("*/index.html"))
    return counts


def build_contract(routes: list[dict], dom: dict[str, dict], links: dict, seo: dict) -> dict:
    return {
        "schema": SCHEMA,
        "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": (
            "Recorded by scripts/check_gp1_contract.py --record. Minimums are 80% of the recorded "
            "count (text: 50%). Re-record only when a California change is intended, and say why "
            "in the commit."
        ),
        "viewports": {"desktop": DESKTOP["width"], "mobile": MOBILE["width"]},
        "routes": [build_dom_entry(r, dom[r["route"]]) for r in routes],
        "seo_entity_pages": seo,
        "link_graph": links,
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--site", required=True, help="assembled site folder (assemble_site.py --out)"
    )
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--record", action="store_true", help="write the contract from this run")
    parser.add_argument("--screenshots", help="folder for full-page screenshots at 1440 and 390 px")
    parser.add_argument(
        "--links-only", action="store_true", help="skip the browser (link graph only)"
    )
    args = parser.parse_args(argv)

    started = time.monotonic()
    site = Path(args.site).resolve()
    contract_path = Path(args.contract)
    if not site.is_dir():
        print(f"FAIL: site folder not found: {site}")
        return 1

    if args.record:
        routes = california_routes()
    else:
        if not contract_path.is_file():
            print(f"FAIL: no contract at {contract_path}; run with --record first")
            return 1
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        routes = [{"route": r["route"], "file": r["file"]} for r in contract["routes"]]

    problems: list[str] = []
    missing = missing_routes(routes, site)
    problems += [f"route missing from site: {f}" for f in missing]

    t_links = time.monotonic()
    report = check_link_graph(**load_link_inputs(site / "data" / "california"))
    link_secs = time.monotonic() - t_links
    links = summarize_links(report)
    print(
        f"links: {links['total_checked']} checked, {links['broken']} broken, "
        f"{sum(links['unlinked_by_design'].values())} unlinked by design ({link_secs:.1f}s)"
    )
    for item in report["broken"][:20]:
        print(f"  broken: {item}")

    dom_secs = 0.0
    if not args.links_only and not missing:
        shots = Path(args.screenshots).resolve() if args.screenshots else None
        if shots is not None:
            shots.mkdir(parents=True, exist_ok=True)
        t_dom = time.monotonic()
        try:
            observed = observe_dom(site, routes, shots)
        except ImportError:
            print("FAIL: Playwright is not installed (pip install playwright)")
            return 1
        dom_secs = time.monotonic() - t_dom
        for route in routes:
            seen = observed[route["route"]]
            print(
                f"  {route['route']}: {seen['selector']} x{seen['count']}, "
                f"main {seen['main_chars']} chars, overflow@390 {seen['overflow_390']}px, "
                f"errors {len(seen['page_errors'])}"
            )
        if args.record:
            seo = seo_entity_counts(site)
            contract = build_contract(routes, observed, links, seo)
            contract_path.parent.mkdir(parents=True, exist_ok=True)
            contract_path.write_text(
                json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            print(f"recorded: {contract_path} ({len(routes)} routes)")
        else:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            problems += compare_dom(contract["routes"], observed)
            problems += compare_links(contract["link_graph"], report)
            for new in new_source_routes(contract["routes"]):
                print(f"note: framework page not in the contract (re-record to add): {new}")
    elif args.links_only and not args.record:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        problems += compare_links(contract["link_graph"], report)
    elif args.record:
        # Link graph recorded without a browser run is not allowed: the routes must be observed too.
        print("FAIL: --record needs the browser run (drop --links-only)")
        return 1

    total = time.monotonic() - started
    print(f"runtime: {total:.1f}s total (links {link_secs:.1f}s, browser {dom_secs:.1f}s)")
    for item in problems:
        print(f"FAIL: {item}")
    if problems:
        return 1
    print("GP-1 contract " + ("recorded" if args.record else "passed"))
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
