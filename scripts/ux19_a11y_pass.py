"""Assisted WCAG 2.2 AA pass over every public route (UX-19); writes a failure table only.

Automated tools find only part of the problems, so this script automates the checklist steps a
person would do by hand and leaves judgement items (screen-reader wording, meaning of colour)
to the report's manual section:

* axe-core (WCAG 2.0/2.1/2.2 A and AA tags) per route at 1280 px;
* a full keyboard Tab walk: focus visible (2.4.7), focus not hidden under a fixed header
  (2.4.11), no keyboard trap (2.1.2), and pointer-only controls that Tab never reaches (2.1.1);
* live regions where a page has filters (4.1.3); 24 px target size (2.5.8);
* reflow at 320 px, i.e. 400% zoom of a 1280 px window (1.4.10);
* page title (2.4.2), lang (3.1.1), one h1 and no skipped heading levels (1.3.1), zoom allowed.

    py -3.14 scripts/ux19_a11y_pass.py --base http://127.0.0.1:8790/CA_Plastics_Research_Dash/ \
        [--out scratch/ux19] [--routes experts network]

Serve the assembled site first (scripts/assemble_site.py, then
scripts/serve_framework_preview.py --assembled <dir> --port 8790). Writes <out>/results.json and
<out>/failures.md (route, element, criterion, proposed fix). Read-only; no fixes are made.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

AXE = Path.home() / "tools" / "ux-audit" / "node_modules" / "axe-core" / "axe.min.js"
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
ROUTES = [
    "",
    "experts",
    "network",
    "institutions",
    "institution#inst=I84218800",
    "monitoring",
    "funding",
    "evidence",
    "policy",
    "resources",
    "about",
    "glossary",
    "expert.html#author=A5031423229",
    "status.html",
]
MAX_TABS = 400

PAGE_FACTS = """() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const label = (el) => (el.getAttribute('aria-label') || el.textContent || el.id || el.tagName)
    .trim().replace(/\\s+/g, ' ').slice(0, 60);
  const heads = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(vis)
    .map((h) => Number(h.tagName[1]));
  const skips = []; heads.forEach((lvl, i) => { if (i && lvl > heads[i - 1] + 1)
    skips.push(`h${heads[i - 1]} -> h${lvl}`); });
  const vp = document.querySelector('meta[name=viewport]');
  const filters = document.querySelectorAll('form input, form select, select, input[type=search]');
  const live = document.querySelectorAll('[aria-live], [role=status], [role=alert], output');
  const pointerOnly = [...document.querySelectorAll('body *')].filter((el) => vis(el)
    && getComputedStyle(el).cursor === 'pointer'
    && !el.closest('a[href],button,input,select,textarea,summary,label,[tabindex]')
    && !['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'SUMMARY', 'LABEL'].includes(el.tagName)
    && !el.parentElement?.closest('[style*="cursor"]')
    && el.tagName !== 'CANVAS')
    .slice(0, 8).map((el) => `${el.tagName.toLowerCase()}.${[...el.classList].join('.')}`);
  const small = [...document.querySelectorAll('a[href],button,input,select,[role=button]')]
    .filter((el) => { if (!vis(el)) return false; const r = el.getBoundingClientRect();
      if (r.width >= 24 && r.height >= 24) return false;
      if (el.tagName === 'A' && el.closest('p,li,td,dd,figcaption')) return false;  // inline
      if (el.type === 'checkbox' || el.type === 'radio') return !el.closest('label');
      return true; })
    .slice(0, 8).map((el) => `${el.tagName.toLowerCase()} "${label(el)}"`);
  return { title: document.title, lang: document.documentElement.lang,
    viewport: vp ? vp.content : '', h1: heads.filter((l) => l === 1).length, skips,
    filters: filters.length, live: live.length, pointerOnly, small };
}"""

FOCUS_STATE = """() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const s = getComputedStyle(el); const r = el.getBoundingClientRect();
  const ring = (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0)
    || (s.boxShadow && s.boxShadow !== 'none');
  const cx = Math.min(Math.max(r.left + r.width / 2, 0), innerWidth - 1);
  const cy = Math.min(Math.max(r.top + Math.min(r.height / 2, 10), 0), innerHeight - 1);
  const top = document.elementFromPoint(cx, cy);
  const hidden = r.width > 0 && top && !(el === top || el.contains(top) || top.contains(el))
    && !!top.closest('header, #observablehq-header, [style*="fixed"], .sticky');
  const name = (el.getAttribute('aria-label') || el.textContent || el.getAttribute('name')
    || el.id || '').trim().replace(/\\s+/g, ' ').slice(0, 50);
  const path = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
    + (el.classList.length ? '.' + [...el.classList].slice(0, 2).join('.') : '');
  return { path, name, ring, hidden, size: r.width * r.height };
}"""

OVERFLOW = """(width) => {
  const doc = document.documentElement.scrollWidth;
  const scroller = (el) => { for (let p = el.parentElement; p; p = p.parentElement) {
    const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden')
      return true; } return false; };
  const wide = [...document.querySelectorAll('body *')].filter((el) => {
    const r = el.getBoundingClientRect();
    return r.right > width + 1 && r.width > 0 && !scroller(el);
  }).slice(0, 5).map((el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
    + (el.classList.length ? '.' + [...el.classList].slice(0, 2).join('.') : ''));
  return { doc, wide };
}"""


def criterion_for(tags: list[str]) -> str:
    """'1.4.3' style criterion from axe tags such as 'wcag143'."""
    for tag in tags:
        if tag.startswith("wcag") and tag[4:].isdigit() and len(tag) >= 7:
            digits = tag[4:]
            return f"{digits[0]}.{digits[1]}.{digits[2:]}"
    return "best practice"


def audit_route(browser: Any, base: str, route: str) -> tuple[list[dict], dict]:
    rows: list[dict] = []

    def fail(element: str, criterion: str, problem: str, fix: str) -> None:
        rows.append(
            {
                "route": "/" + route,
                "element": element,
                "criterion": criterion,
                "problem": problem,
                "fix": fix,
            }
        )

    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(base + route, wait_until="networkidle")
    page.wait_for_timeout(1500)
    facts = page.evaluate(PAGE_FACTS)
    if not facts["title"].strip():
        fail("<title>", "2.4.2", "page has no title", "set a page title")
    if not facts["lang"]:
        fail("<html>", "3.1.1", "no lang attribute", 'add lang="en"')
    if "maximum-scale=1" in facts["viewport"] or "user-scalable=no" in facts["viewport"]:
        fail("meta viewport", "1.4.4", "zoom is blocked", "drop maximum-scale / user-scalable")
    if facts["h1"] != 1:
        fail("headings", "1.3.1", f"{facts['h1']} visible h1 elements", "keep exactly one h1")
    for skip in facts["skips"]:
        fail("headings", "1.3.1", f"heading level skipped ({skip})", "use the next level")
    if facts["filters"] and not facts["live"]:
        fail(
            "result counts",
            "4.1.3",
            "filters change results but the page has no live region",
            'announce counts with role="status"',
        )
    for item in facts["pointerOnly"]:
        fail(
            item,
            "2.1.1",
            "looks clickable (pointer cursor) but is not a focusable control",
            "use a button or link, or add tabindex and key handling",
        )
    for item in facts["small"]:
        fail(item, "2.5.8", "target smaller than 24 x 24 px", "pad the control to 24 px")

    page.add_script_tag(content=AXE.read_text(encoding="utf-8"))
    violations = page.evaluate(
        "async (tags) => (await axe.run(document, {runOnly: {type: 'tag', values: tags}}))"
        ".violations.map(v => ({id: v.id, tags: v.tags, help: v.help,"
        " nodes: v.nodes.slice(0, 3).map(n => n.target.join(' '))}))",
        AXE_TAGS,
    )
    for violation in violations:
        for node in violation["nodes"]:
            criterion = criterion_for(violation["tags"])
            fail(node, criterion, f"axe {violation['id']}", violation["help"])

    # Keyboard walk: Tab until focus returns to the start, stalls, or MAX_TABS.
    seen: list[str] = []
    stuck = 0
    no_ring: dict[str, str] = {}
    hidden: dict[str, str] = {}
    page.evaluate("() => { document.activeElement && document.activeElement.blur(); }")
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        state = page.evaluate(FOCUS_STATE)
        if state is None:
            if seen:
                break
            continue
        key = f"{state['path']} '{state['name']}'"
        if seen and key == seen[-1]:
            stuck += 1
            if stuck >= 3:
                fail(key, "2.1.2", "Tab does not move focus on (possible trap)", "release focus")
                break
        else:
            stuck = 0
        if seen and key == seen[0]:
            break
        seen.append(key)
        if not state["ring"]:
            no_ring.setdefault(state["path"], key)
        if state["hidden"]:
            hidden.setdefault(state["path"], key)
    for key in list(no_ring.values())[:8]:
        fail(key, "2.4.7", "no visible focus indicator", "add a :focus-visible outline")
    for key in list(hidden.values())[:8]:
        fail(key, "2.4.11", "focused control is covered by the fixed header", "scroll-padding-top")

    page.set_viewport_size({"width": 320, "height": 640})
    page.wait_for_timeout(600)
    overflow = page.evaluate(OVERFLOW, 320)
    if overflow["doc"] > 321:
        fail(
            ", ".join(overflow["wide"]) or "page",
            "1.4.10",
            f"page scrolls sideways at 320 px ({overflow['doc']} px wide)",
            "let the element wrap or scroll inside its own container",
        )
    page.close()
    summary = {
        "route": "/" + route,
        "tab_stops": len(seen),
        "axe": len(violations),
        "errors": errors[:3],
        "live_regions": facts["live"],
    }
    return rows, summary


def write_markdown(path: Path, rows: list[dict], summaries: list[dict]) -> None:
    lines = [
        "| Route | Element | Criterion | Problem | Proposed fix |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        cells = [r["route"], f"`{r['element']}`", r["criterion"], r["problem"], r["fix"]]
        lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    lines += ["", "| Route | Tab stops | axe rules failed | Live regions | Page errors |"]
    lines.append("|---|---|---|---|---|")
    for s in summaries:
        lines.append(
            f"| {s['route']} | {s['tab_stops']} | {s['axe']} | {s['live_regions']} | "
            f"{len(s['errors'])} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", default="http://127.0.0.1:8790/CA_Plastics_Research_Dash/")
    parser.add_argument("--out", default="scratch/ux19")
    parser.add_argument("--routes", nargs="*", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    from playwright.sync_api import sync_playwright

    base = args.base.rstrip("/") + "/"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    summaries: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge")
        for route in args.routes if args.routes is not None else ROUTES:
            found, summary = audit_route(browser, base, route)
            rows += found
            summaries.append(summary)
            print(f"/{route}: {len(found)} failures, {summary['tab_stops']} tab stops")
        browser.close()
    (out / "results.json").write_text(
        json.dumps({"failures": rows, "routes": summaries}, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    write_markdown(out / "failures.md", rows, summaries)
    print(f"{len(rows)} failures -> {out / 'failures.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
