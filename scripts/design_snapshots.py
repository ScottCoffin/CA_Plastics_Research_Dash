"""VD-12 global acceptance snapshots for the Framework site (a local Playwright script).

For each route at 1440x900 this records the DevTools platform fonts (CDP
CSS.getPlatformFontsForNode) of the h1, h2, p, sidebar link, header, button and td probes, the page
header, the icon sprites (``svg use[href^="#i-"]``), the charts with a Table view, the
Hasler-Susstrunk colourfulness M and the share of saturated pixels of the first-screen PNG, and the
woff2 transfer size. Each route also gets a full-page screenshot at 390x844. The script adds the
gzip size of the global design CSS and the distinct hex literals in
``framework/src/components/*.js``.
Lighthouse is not run here; see docs/VD_12_VERIFICATION.md.

    py -3.14 scripts/design_snapshots.py [--base URL] [--out DIR] [--routes KEY ...]

Writes <out>/<route>_1440_fold.png, <out>/<route>_390_full.png and <out>/design_snapshots.json,
then prints one line per route. "Saturated" follows the VD-12 brief: HSV saturation above 0.5 and
value above 0.3. The baseline file does not define its saturated share, so the two are compared as
recorded. The exit code is 0 once the measurements are written; gate results are in the JSON and
the table. Playwright and Pillow are imported inside functions, so importing this module (the unit
tests do) needs neither.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs" / "design" / "baseline_2026-11-14.json"
FRAMEWORK_SRC = ROOT / "framework" / "src"
DEFAULT_BASE = "https://plastiverse.live/"
DEFAULT_OUT = ROOT / "scratch" / "design_snapshots"

FOLD_VIEWPORT = {"width": 1440, "height": 900}
MOBILE_VIEWPORT = {"width": 390, "height": 844}
SETTLE_MS = 2000
NAV_TIMEOUT_MS = 90_000
FONT_TRANSFER_LIMIT = 60 * 1024
CSS_GZIP_LIMIT = 12 * 1024
COMPONENT_HEX_BASELINE = 53
DESIGN_CSS = ("design/tokens.css", "design/shell.css", "design/components.css")

# Route key -> path appended to the base URL. The keys are the baseline's route keys, in order;
# since PLAT-1 (2026-11-17) the California pages live under california/ and "home" is the
# California overview.
CA = "california/"
ROUTES: dict[str, str] = {
    "home": CA,
    "experts": CA + "authors",  # baseline key kept; the page moved to /authors (BQ-R1)
    "network": CA + "network",
    "institutions": CA + "institutions",
    "institution": CA + "institution#inst=I84218800",
    "monitoring": CA + "monitoring",
    "funding": CA + "funding",
    "evidence": CA + "evidence",
    "policy": CA + "policy",
    "resources": CA + "resources",
    "about": CA + "about",
    "glossary": CA + "glossary",
    "expert_profile": CA + "expert.html#author=A5036007957",
    "institution_page": CA + "institution#inst=I97018004",
}
DEFAULT_HEADER = ".atlas-page-head, .atlas-hero"  # the Overview hero is its page header (VD-5)
HEADER_SELECTOR = {"expert_profile": "header.site-header"}

# Probe -> (CSS selectors tried in order, pick the longest text). The page marks one visible element
# per probe (first with text, or the longest paragraph for body text), and CDP reads its fonts.
PROBES: dict[str, tuple[tuple[str, ...], bool]] = {
    "h1": (("main h1", "h1"), False),
    "h2": (("main h2", "h2"), False),
    "p": (("main p", "p"), True),
    "sidebar_link": (("#observablehq-sidebar a",), False),
    "header": (
        ("#observablehq-header a", "#observablehq-header span", "header.site-header p"),
        False,
    ),
    "button": (("main button",), False),
    "td": (("main td",), False),
}
BANNED_FONTS = frozenset({"Palatino Linotype", "Times New Roman", "Arial"})
DISPLAY_FONT = "Archivo"
SYSTEM_BODY_FACES = frozenset(
    {"Roboto", "Helvetica Neue", "Noto Sans", "system-ui", "-apple-system", "BlinkMacSystemFont"}
)
HEX_COLOR = re.compile(
    r"(?<![\w-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9a-fA-F])"
)
CHART_JS = """() => {
  // A card marked data-kind="table" is itself a table (Evidence publications), not a chart.
  const charts = [...document.querySelectorAll('.atlas-chart:not([data-kind="table"])')];
  const hasTable = (chart) => [...chart.querySelectorAll('.atlas-segmented button')]
    .some((b) => b.dataset.view === 'table' || /^table$/i.test(b.textContent.trim()));
  return {charts: charts.length, withTable: charts.filter(hasTable).length};
}"""
MARK_JS = """(probes) => {
  const text = (el) => el.textContent.trim();
  const visible = (el) => el.getClientRects().length > 0 && text(el).length > 0;
  const found = {};
  for (const [name, spec] of Object.entries(probes)) {
    let hit = null;
    for (const sel of spec.selectors) {
      const els = [...document.querySelectorAll(sel)].filter(visible);
      if (!els.length) continue;
      hit = spec.longest ? els.reduce((a, b) => (text(b).length > text(a).length ? b : a)) : els[0];
      break;
    }
    // DevTools reports fonts only for text nodes that are direct children, so mark the nearest
    // element that holds text directly (Observable wraps heading text in an anchor).
    const direct = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (hit && !direct(hit)) hit = [...hit.querySelectorAll('*')].find(direct) || hit;
    if (hit) hit.setAttribute('data-vd12-probe', name);
    found[name] = Boolean(hit);
  }
  return found;
}"""


def colourfulness_stats(pixels: Iterable[tuple[int, int, int]]) -> tuple[float, float]:
    """Return (Hasler-Susstrunk M, percent of pixels with HSV saturation > 0.5 and value > 0.3).

    M = sqrt(sd(rg)^2 + sd(yb)^2) + 0.3 * sqrt(mean(rg)^2 + mean(yb)^2), with rg = R - G and
    yb = (R + G) / 2 - B over 8-bit channels and population statistics. One pass over the pixels.
    """
    n = 0
    saturated = 0
    sum_rg = sum_rg2 = sum_yb = sum_yb2 = 0.0
    for r, g, b in pixels:
        rg = r - g
        yb = 0.5 * (r + g) - b
        n += 1
        sum_rg += rg
        sum_rg2 += rg * rg
        sum_yb += yb
        sum_yb2 += yb * yb
        hi = max(r, g, b)
        if hi and hi - min(r, g, b) > 0.5 * hi and hi > 0.3 * 255:
            saturated += 1
    if n == 0:
        return 0.0, 0.0
    mean_rg = sum_rg / n
    mean_yb = sum_yb / n
    sd_rg = math.sqrt(max(sum_rg2 / n - mean_rg * mean_rg, 0.0))
    sd_yb = math.sqrt(max(sum_yb2 / n - mean_yb * mean_yb, 0.0))
    m = math.hypot(sd_rg, sd_yb) + 0.3 * math.hypot(mean_rg, mean_yb)
    return m, 100.0 * saturated / n


def colourfulness(pixels: Iterable[tuple[int, int, int]]) -> float:
    """Hasler-Susstrunk colourfulness M of (r, g, b) pixels; 0.0 for an empty iterable."""
    return colourfulness_stats(pixels)[0]


def image_metrics(path: Path) -> tuple[float, float]:
    """Return (M, saturated percent) for a PNG; Pillow is imported here, not at module import."""
    from PIL import Image

    with Image.open(path) as img:
        data = img.convert("RGB").tobytes()
    return colourfulness_stats(zip(data[0::3], data[1::3], data[2::3], strict=True))


def font_problems(fonts: Mapping[str, list[str]]) -> list[str]:
    """Return the font rules a route breaks. A probe with no platform font is not judged."""
    problems: list[str] = []
    for probe, families in fonts.items():
        for family in families:
            if family in BANNED_FONTS:
                problems.append(f"{probe} renders {family}")
    for probe in ("h1", "h2"):
        families = fonts.get(probe) or []
        # Weight variants are reported as their own family, e.g. "Archivo ExtraBold".
        if families and not families[0].startswith(DISPLAY_FONT):
            problems.append(f"{probe} renders {families[0]}, not {DISPLAY_FONT}")
    body = fonts.get("p") or []
    # VD-25a: body text is Archivo too (one grotesk); the system face stays allowed.
    face = body[0] if body else ""
    accepted = face.startswith(("Segoe UI", DISPLAY_FONT)) or face in SYSTEM_BODY_FACES
    if body and not accepted:
        problems.append(f"p renders {body[0]}, not Archivo or the system face")
    return problems


def css_gzip_bytes() -> dict[str, int]:
    """Gzip size of each global design stylesheet, compressed one file at a time."""
    return {
        rel: len(gzip.compress((FRAMEWORK_SRC / rel).read_bytes(), compresslevel=9, mtime=0))
        for rel in DESIGN_CSS
    }


def component_hex_literals() -> tuple[int, int]:
    """Return (distinct, total) hex colour literals in framework/src/components/*.js (top level)."""
    found: list[str] = []
    for path in sorted((FRAMEWORK_SRC / "components").glob("*.js")):
        found += [match.lower() for match in HEX_COLOR.findall(path.read_text(encoding="utf-8"))]
    return len(set(found)), len(found)


def _is_woff2(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(".woff2")


def _transfer_bytes(response: Any) -> int:
    try:
        return int(response.request.sizes()["responseBodySize"])
    except Exception:  # noqa: BLE001 - fall back to the decoded body when sizes are unavailable
        return len(response.body())


def _platform_fonts(cdp: Any, probe: str) -> list[str]:
    """Return the platform font families (most glyphs first) of the node marked for ``probe``."""
    root = cdp.send("DOM.getDocument", {"depth": 1})["root"]["nodeId"]
    node_id = cdp.send(
        "DOM.querySelector", {"nodeId": root, "selector": f'[data-vd12-probe="{probe}"]'}
    )["nodeId"]
    if not node_id:
        return []
    fonts = cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node_id})["fonts"]
    ordered = sorted(fonts, key=lambda f: -f.get("glyphCount", 0))
    return [f["familyName"] for f in ordered]


def _load(page: Any, url: str) -> None:
    page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
    page.wait_for_load_state("networkidle", timeout=NAV_TIMEOUT_MS)
    page.wait_for_timeout(SETTLE_MS)


def measure_route(browser: Any, base: str, key: str, path: str, out: Path) -> dict[str, Any]:
    url = base + path
    header_selector = HEADER_SELECTOR.get(key, DEFAULT_HEADER)
    context = browser.new_context(viewport=FOLD_VIEWPORT)
    page = context.new_page()
    font_responses: list[Any] = []
    page.on("response", lambda r: font_responses.append(r) if _is_woff2(r.url) else None)
    _load(page, url)

    page.evaluate(
        MARK_JS,
        {
            name: {"selectors": list(sels), "longest": longest}
            for name, (sels, longest) in PROBES.items()
        },
    )
    cdp = context.new_cdp_session(page)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    fonts = {probe: _platform_fonts(cdp, probe) for probe in PROBES}

    fold_png = out / f"{key}_1440_fold.png"
    page.screenshot(path=str(fold_png))
    charts = page.evaluate(CHART_JS)
    icons = page.locator('svg use[href^="#i-"]').count()
    header_count = page.locator(header_selector).count()
    font_bytes = sum(_transfer_bytes(response) for response in font_responses)
    context.close()

    mobile = browser.new_context(viewport=MOBILE_VIEWPORT)
    mobile_page = mobile.new_page()
    _load(mobile_page, url)
    full_png = out / f"{key}_390_full.png"
    mobile_page.screenshot(path=str(full_png), full_page=True)
    mobile.close()

    colour_m, saturated = image_metrics(fold_png)
    problems = font_problems(fonts)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["routes"].get(key, {})
    return {
        "url": url,
        "fonts": fonts,
        "missing_probes": [probe for probe, families in fonts.items() if not families],
        "font_problems": problems,
        "fonts_ok": not problems,
        "header_selector": header_selector,
        "header_count": header_count,
        "header_ok": header_count > 0,
        "icons": icons,
        "icons_ok": icons >= 1,
        "charts": charts["charts"],
        "charts_with_table": charts["withTable"],
        "charts_ok": charts["withTable"] == charts["charts"],
        "colourfulness_M": round(colour_m, 2),
        "saturated_pct": round(saturated, 2),
        "baseline_colourfulness_M": baseline.get("fold_colourfulness_M"),
        "baseline_saturated_pct": baseline.get("fold_saturated_pct"),
        "font_transfer_bytes": font_bytes,
        "font_transfer_ok": font_bytes <= FONT_TRANSFER_LIMIT,
        "fold_png": str(fold_png),
        "full_390_png": str(full_png),
    }


def _yes_no(flag: bool) -> str:
    return "ok" if flag else "FAIL"


def _fmt(value: float | None, digits: int) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _print_table(results: Mapping[str, dict[str, Any]]) -> None:
    print(
        f"{'route':<17}{'fonts':<7}{'header':<8}{'icons':>6}{'charts':>8}"
        f"{'M now':>8}{'M base':>8}{'sat% now':>10}{'sat% base':>10}{'font KB':>9}"
    )
    for key, r in results.items():
        charts = f"{r['charts_with_table']}/{r['charts']}"
        print(
            f"{key:<17}{_yes_no(r['fonts_ok']):<7}{_yes_no(r['header_ok']):<8}{r['icons']:>6}"
            f"{charts:>8}{r['colourfulness_M']:>8.1f}"
            f"{_fmt(r['baseline_colourfulness_M'], 1):>8}{r['saturated_pct']:>10.2f}"
            f"{_fmt(r['baseline_saturated_pct'], 2):>10}{r['font_transfer_bytes'] / 1024:>9.1f}"
        )


def main(argv: list[str] | None = None) -> int:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--base", default=DEFAULT_BASE, help="Site base URL (default: live site)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output folder for PNGs and JSON")
    parser.add_argument(
        "--routes", nargs="+", choices=list(ROUTES), metavar="KEY", help="Subset of route keys"
    )
    args = parser.parse_args(argv)

    base = args.base if args.base.endswith("/") else args.base + "/"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    keys = args.routes or list(ROUTES)
    results: dict[str, dict[str, Any]] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for key in keys:
                results[key] = measure_route(browser, base, key, ROUTES[key], out)
        finally:
            browser.close()

    css = css_gzip_bytes()
    css_total = sum(css.values())
    distinct, total = component_hex_literals()
    summary = {
        "measured": date.today().isoformat(),
        "base": base,
        "baseline": BASELINE.relative_to(ROOT).as_posix(),
        "method": "Playwright Chromium 1440x900 fold and 390x844 full page; colourfulness is "
        "Hasler-Susstrunk M on the fold PNG; fonts from CDP CSS.getPlatformFontsForNode; "
        "lighthouse is not run by this script",
        "routes": results,
        "global": {
            "font_transfer_limit_bytes": FONT_TRANSFER_LIMIT,
            "css_gzip_bytes": css,
            "css_gzip_total_bytes": css_total,
            "css_gzip_limit_bytes": CSS_GZIP_LIMIT,
            "css_gzip_ok": css_total <= CSS_GZIP_LIMIT,
            "component_js_hex_distinct": distinct,
            "component_js_hex_total_uses": total,
            "component_js_hex_baseline_distinct": COMPONENT_HEX_BASELINE,
            "component_js_hex_ok": distinct < COMPONENT_HEX_BASELINE,
        },
    }
    (out / "design_snapshots.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    _print_table(results)
    print(
        f"design-tier CSS gzip {css_total} B (limit {CSS_GZIP_LIMIT} B); "
        f"component JS hex {distinct} distinct (baseline {COMPONENT_HEX_BASELINE}); wrote {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
