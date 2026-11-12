"""Render Framework pages in headless Edge/Chrome and report text and errors (AT-5 local smoke).

Serves site/ + framework/<dist>/ like GitHub Pages (serve_framework_preview.py), dumps each
page's DOM after scripts run, and fails when a page shows a Framework cell error or lacks the
expected text. Needs a local Chromium-family browser; offline otherwise (reads committed data).

Usage:
    py -3.14 scripts/smoke_framework_pages.py about index --dist dist --port 8766
    py -3.14 scripts/smoke_framework_pages.py funding --expect funding=Award --show
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from serve_framework_preview import PREFIX, serve_in_background  # noqa: E402

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google-chrome",
    "chromium",
    "chromium-browser",
]


def find_browser() -> str | None:
    env = os.environ.get("ATLAS_SMOKE_BROWSER")
    for candidate in [env, *BROWSERS] if env else BROWSERS:
        if candidate and (Path(candidate).is_file() or shutil.which(candidate)):
            return candidate
    return None


def dump_dom(browser: str, url: str, budget_ms: int) -> str:
    with tempfile.TemporaryDirectory(prefix="at5_smoke_") as profile:
        result = subprocess.run(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                f"--user-data-dir={profile}",
                f"--virtual-time-budget={budget_ms}",
                "--dump-dom",
                url,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    return result.stdout


def main_text(dom: str) -> str:
    match = re.search(r"<main.*?</main>", dom, re.S)
    text = re.sub(r"<[^>]+>", " ", match.group(0) if match else dom)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def cell_errors(dom: str) -> list[str]:
    errors = re.findall(r'class="observablehq--error"[^>]*>(.*?)</', dom, re.S)
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", e))).strip() for e in errors]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "pages", nargs="+", help="page names under app/ (index, about, funding, ...)"
    )
    parser.add_argument("--dist", default="dist")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--budget-ms", type=int, default=8000)
    parser.add_argument(
        "--expect", action="append", default=[], help="page=text that must appear in <main>"
    )
    parser.add_argument(
        "--show", action="store_true", help="print the first 600 characters of each page's text"
    )
    args = parser.parse_args()

    browser = find_browser()
    if browser is None:
        print("SKIP: no Chromium-family browser found (set ATLAS_SMOKE_BROWSER)")
        return 0
    expectations: dict[str, list[str]] = {}
    for item in args.expect:
        page, _, text = item.partition("=")
        expectations.setdefault(page, []).append(text)

    server = serve_in_background(args.port, args.dist)
    failures = 0
    try:
        for page in args.pages:
            url = f"http://127.0.0.1:{args.port}{PREFIX}/app/{'' if page == 'index' else page}"
            dom = dump_dom(browser, url, args.budget_ms)
            text = main_text(dom)
            problems = [f"cell error: {e}" for e in cell_errors(dom)]
            if not text:
                problems.append("empty <main>")
            problems += [
                f"missing text: {t!r}" for t in expectations.get(page, []) if t not in text
            ]
            status = "FAIL" if problems else "PASS"
            failures += bool(problems)
            print(f"{status} {page}: {len(text)} chars" + "".join(f"\n  - {p}" for p in problems))
            if args.show:
                print(f"  text: {text[:600]}")
    finally:
        server.shutdown()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
