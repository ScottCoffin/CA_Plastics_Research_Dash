"""PLAT-2 acceptance: the Plastiverse Live landing page (docs/PLAT_2_LANDING_SPEC.md section 9).

Offline: Playwright against a locally served, assembled build. Checks

1. copy: every caption string of spec section 4 is in the DOM verbatim;
2. no overlap: at the middle and the end of every beat, at 1440x900 and 390x844, no visible
   caption text box intersects a drawn visual (``window.__landingDebug.visualRects()``);
3. accessibility: axe reports 0 violations; one h1, headings never skip a level; the skip link
   targets #evidence;
4. reduced motion: no sticky stage, ten stills, each with its caption;
5. external requests: none to any host but the site's own; no console errors.

Screenshots of every checked position go to ``--out`` (contact sheet ``contact_<w>.png``).
Lighthouse (performance) runs separately: ``~/tools/ux-audit/ux_audit.py <base> "" --lighthouse``.

Usage:
    py -3.14 scripts/serve_framework_preview.py --assembled <dir> --port 8794 &
    py -3.14 scripts/check_plat2.py --base http://127.0.0.1:8794/CA_Plastics_Research_Dash/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
AXE = Path.home() / "tools" / "ux-audit" / "node_modules" / "axe-core" / "axe.min.js"
VIEWPORTS = ((1440, 900), (390, 844))
# Spec section 4, exact copy.
CAPTIONS = (
    "Plastic is everywhere…",
    "Microplastics were first described in the ocean more than 50 years ago.",
    "Now picture every particle as a published study. Thousands more arrive every year.",
    "Connected, studies become knowledge.",
    "Grouped by what they study and linked by who did the work, scattered results start to "
    "form a picture.",
    "Put to work, knowledge becomes understanding.",
    "Plastic pollution research is expanding at an unprecedented pace.",
    "The world needs innovative tools to turn data into knowledge and solutions to effectively "
    "react to this global crisis.",
    "See where the evidence is, worldwide, and where it is missing.",
    "A live evidence map sorts every study by what it examines and where.",
    "See who works with whom, and forge new connections.",
    "Collaboration networks show the research communities and the people who bridge them.",
    "The problem is global.",
    "Plastics research now comes from almost every country.",
    "Local knowledge and connections matter.",
    "Regional atlases zoom in on the people, monitoring, funding and policy of one place. "
    "Powered by local experts and community leaders.",
    "Join the movement, and become a local ambassador",
    "California is live; Norway is next.",
)
# (beat, middle, end) in scroll units; the end is just before the beat's captions fade out.
BEATS = (
    ("1 picnic under the title", 1.0, 1.35),
    ("2 shattering", 2.2, 2.9),
    ("3 cloud forms", 3.3, 3.7),
    ("4 cloud, Carpenter", 4.7, 5.3),
    ("5 papers", 6.2, 7.1),
    ("6 mandala", 9.4, 10.4),
    ("7 bulb and burst", 11.9, 12.8),
    ("8 chart builds", 15.0, 17.2),
    ("9 annotated chart", 19.5, 20.5),
    ("10 evidence grid", 22.5, 23.3),
    ("11 network", 25.2, 26.0),
    ("12 world map", 27.9, 28.4),
    ("13 California", 30.2, 31.4),
)
STILLS = 10


def intersects(a: dict[str, float], b: dict[str, float], pad: float = 0.0) -> bool:
    return (
        a["x0"] < b["x1"] - pad
        and b["x0"] + pad < a["x1"]
        and a["y0"] < b["y1"] - pad
        and b["y0"] + pad < a["y1"]
    )


def overlaps(captions: list[dict[str, Any]], visuals: list[dict[str, Any]]) -> list[str]:
    """Caption boxes that intersect a visual (1 px tolerance for anti-aliasing)."""
    found = []
    for cap in captions:
        for vis in visuals:
            if intersects(cap, vis, pad=1.0):
                found.append(
                    f"{cap['cls'].split()[1] if ' ' in cap['cls'] else cap['cls']} x {vis['kind']}"
                )
                break
    return found


def heading_problems(levels: list[int]) -> list[str]:
    problems = []
    if levels.count(1) != 1:
        problems.append(f"{levels.count(1)} h1 elements (want 1)")
    for prev, cur in zip(levels, levels[1:], strict=False):
        if cur > prev + 1:
            problems.append(f"heading skips from h{prev} to h{cur}")
    return problems


def scroll_to_units(page: Any, units: float) -> None:
    page.evaluate(
        """(u) => {
          const story = document.getElementById('plv-story');
          const top = story.getBoundingClientRect().top + scrollY;
          const range = story.offsetHeight - innerHeight;
          scrollTo({top: top + range * u / window.__landingDebug.TOT, behavior: 'instant'});
        }""",
        units,
    )
    page.wait_for_timeout(120)
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def check_viewport(browser: Any, base: str, w: int, h: int, out: Path) -> dict[str, Any]:
    ctx = browser.new_context(viewport={"width": w, "height": h})
    page = ctx.new_page()
    host = urlsplit(base).netloc
    external, console_errors = [], []
    page.on(
        "request",
        lambda r: (
            external.append(r.url)
            if urlsplit(r.url).netloc not in ("", host) and not r.url.startswith("data:")
            else None
        ),
    )
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.goto(base, wait_until="networkidle")
    page.wait_for_function(
        "() => window.__landingDebug && window.__landingDebug.ready", timeout=30000
    )
    page.evaluate("() => window.__landingDebug.enable()")
    result: dict[str, Any] = {"viewport": f"{w}x{h}", "overlaps": {}, "shots": []}
    text = page.evaluate("() => document.querySelector('.plv').textContent.replace(/\\s+/g, ' ')")
    result["missing_copy"] = [c for c in CAPTIONS if " ".join(c.split()) not in text]
    for name, mid, end in BEATS:
        for label, units in (("mid", mid), ("end", end)):
            scroll_to_units(page, units)
            caps = page.evaluate("() => window.__landingDebug.captionRects()")
            vis = page.evaluate("() => window.__landingDebug.visualRects()")
            hits = overlaps(caps, vis)
            if hits:
                result["overlaps"][f"{name} ({label} {units})"] = sorted(set(hits))
            shot = out / f"{w}_{units:05.2f}.png"
            page.screenshot(path=str(shot))
            result["shots"].append(str(shot))
    levels = page.evaluate(
        "() => [...document.querySelectorAll('.plv h1, .plv h2, .plv h3')]"
        ".filter(h => !h.closest('.plv-stills')).map(h => +h.tagName[1])"
    )
    result["heading_problems"] = heading_problems(levels)
    result["skip_link"] = page.evaluate(
        "() => { const a = document.querySelector('.plv .skip'); "
        "return a && a.getAttribute('href'); }"
    )
    if AXE.is_file():
        page.evaluate("() => scrollTo(0, 0)")
        page.add_script_tag(path=str(AXE))
        violations = page.evaluate(
            "async () => (await axe.run(document)).violations"
            ".map(v => v.id + ': ' + v.nodes.length)"
        )
        result["axe"] = violations
    else:
        result["axe"] = ["axe-core not found; skipped"]
    result["external_requests"] = sorted(set(external))
    result["console_errors"] = console_errors
    ctx.close()
    return result


def check_reduced(browser: Any, base: str) -> dict[str, Any]:
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(base, wait_until="networkidle")
    page.wait_for_function(
        "() => window.__landingDebug && window.__landingDebug.ready", timeout=30000
    )
    info = page.evaluate(
        """() => ({
          reduced: document.querySelector('.plv').classList.contains('reduced'),
          stageShown: getComputedStyle(document.getElementById('plv-stage')).display !== 'none',
          stills: [...document.querySelectorAll('.plv-still')].map(f => ({
            beat: f.dataset.beat,
            captions: [...f.querySelectorAll('.cap')]
              .filter(c => getComputedStyle(c).opacity === '1').length,
          })),
        })"""
    )
    ctx.close()
    return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, help="URL of the global landing page")
    parser.add_argument("--out", default=str(ROOT / "scratch" / "plat2"))
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    failures: list[str] = []
    report: dict[str, Any] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for w, h in VIEWPORTS:
            r = check_viewport(browser, args.base, w, h, out)
            report[r["viewport"]] = r
            for key in ("missing_copy", "heading_problems", "external_requests", "console_errors"):
                if r[key]:
                    failures.append(f"{r['viewport']} {key}: {r[key]}")
            if r["axe"]:
                failures.append(f"{r['viewport']} axe: {r['axe']}")
            for where, hits in r["overlaps"].items():
                failures.append(f"{r['viewport']} overlap at {where}: {hits}")
            if r["skip_link"] != "#evidence":
                failures.append(f"{r['viewport']} skip link targets {r['skip_link']!r}")
        red = check_reduced(browser, args.base)
        report["reduced_motion"] = red
        if not red["reduced"] or red["stageShown"]:
            failures.append("reduced motion: sticky stage still shown")
        if len(red["stills"]) != STILLS:
            failures.append(f"reduced motion: {len(red['stills'])} stills (want {STILLS})")
        bare = [s["beat"] for s in red["stills"] if s["captions"] == 0]
        if bare:
            failures.append(f"reduced motion: stills without a caption: {bare}")
        browser.close()
    contact_sheets(out)
    (out / "check_plat2.json").write_text(
        json.dumps({"failures": failures, **report}, indent=2), encoding="utf-8"
    )
    for line in failures:
        print("FAIL", line)
    print(f"PLAT-2 check: {len(failures)} failure(s); report {out / 'check_plat2.json'}")
    return 1 if failures else 0


def contact_sheets(out: Path) -> None:
    """One sheet per viewport width, five shots per row (needs Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        return
    for w, _ in VIEWPORTS:
        shots = sorted(out.glob(f"{w}_*.png"))
        if not shots:
            continue
        thumbs = [Image.open(s).convert("RGB") for s in shots]
        tw = 360 if w > 600 else 160
        th = round(thumbs[0].height * tw / thumbs[0].width)
        cols = 5
        sheet = Image.new("RGB", (cols * tw, -(-len(thumbs) // cols) * th), "white")
        for i, im in enumerate(thumbs):
            sheet.paste(im.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
        sheet.save(out / f"contact_{w}.png")


if __name__ == "__main__":
    sys.exit(main())
