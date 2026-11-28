"""Generate the region author-profile pages from the California page (GP-2, registry regions).

`site/california/expert.html` is the one source. Each region copy (`site/<slug>/expert.html`) is the
California page with a fixed list of substitutions: its data folder, root-relative footer links, and
the California-only badge and research-network fetches switched off. Every substitution must match
the expected number of times, so a change to the California page that breaks a region copy fails
loudly here instead of drifting.

Usage:
    py -3.14 scripts/build_region_profiles.py [--check]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site" / "california" / "expert.html"
TOKENS = ROOT / "framework" / "src" / "design" / "tokens.css"
PROFILE_CSS = ROOT / "site" / "assets" / "pv-profile.css"
REGIONS = ("norway", "belgium")

# (old, new, expected count). "{slug}" is replaced by the region slug.
SUBSTITUTIONS: tuple[tuple[str, str, int], ...] = (
    ('<li><a href="./about">About</a></li>', '<li><a href="../california/about">About</a></li>', 1),
    (
        '<li><a href="./glossary">Glossary</a></li>',
        '<li><a href="../california/glossary">Glossary</a></li>',
        1,
    ),
    (
        '<li><a href="./about#how-to-cite">How to cite</a></li>',
        '<li><a href="../about#how-to-cite">How to cite</a></li>',
        1,
    ),
    (
        'S.badgesPromise = fetchJson("../data/california/expert_badges.json").catch(() => null);',
        "S.badgesPromise = Promise.resolve(null);",
        1,
    ),
    (
        'S.networksPromise = fetchJson("../data/california/research_networks.json")',
        "S.networksPromise = Promise.resolve(null)",
        1,
    ),
    (
        '"Counted only over works in the Atlas California corpus."',
        '"Counted only over works in this region\'s Atlas corpus."',
        1,
    ),
    ("../data/california/", "../data/{slug}/", 5),
)


def render(source: str, slug: str) -> str:
    """Return the region page for slug; raises ValueError when a substitution does not match."""
    text = source
    for old, new, expected in SUBSTITUTIONS:
        found = text.count(old)
        if found != expected:
            raise ValueError(f"{SOURCE.name}: expected {expected} x {old!r}, found {found}")
        text = text.replace(old, new.replace("{slug}", slug))
    return text


def render_profile_css(tokens: str) -> str:
    """Build the classic profile skin from the canonical Plastiverse token block."""
    marker = "/* PLAT-2 (2026-11-17"
    start = tokens.index(marker)
    root_start = tokens.index(":root {", start)
    root_end = tokens.index("\n}", root_start) + 2
    token_block = tokens[root_start:root_end]
    if "--pv-sans:" not in token_block or "--pv-mono:" not in token_block:
        raise ValueError("canonical Plastiverse token block is incomplete")
    rules = """
:root{color-scheme:light;--ink:var(--pv-ink);--text:var(--pv-ink);--muted:var(--pv-ink-2);--boundary:var(--pv-slate);--brand:var(--pv-coral-ink);--brand-dark:var(--pv-night);--surface:var(--pv-paper);--canvas:var(--pv-ground);--line:var(--pv-line);--focus:var(--pv-coral-ink);--font-display:var(--pv-sans);font-family:var(--pv-sans);color:var(--pv-ink);background:var(--pv-ground)}
body{line-height:1.55} a{color:var(--pv-coral-ink);text-underline-offset:.18em}
.seo-profile{margin:0;line-height:1.6;color:var(--pv-ink);background:var(--pv-ground);font-family:var(--pv-sans)}
.seo-profile .wrap{max-width:760px;margin:0 auto;padding:16px}.seo-profile
  header.wrap{max-width:none;padding:0;background:var(--pv-ground);color:var(--pv-ink);
    border-bottom:1px solid var(--pv-line)}
.seo-profile header.wrap p{max-width:760px;margin:0 auto;padding:12px
  16px;font-family:var(--pv-sans);font-weight:700}
.seo-profile header.wrap a{color:var(--pv-ink);text-decoration:none}.seo-profile
  h1,.seo-profile h2{font-family:var(--pv-sans);color:var(--pv-ink)}
.seo-profile
  .cta{border-radius:0;background:var(--pv-ink);color:var(--pv-on-dark)}.seo-profile
  .muted{color:var(--pv-ink-2)}
.skip-link{border:1px solid var(--pv-on-dark-line);border-radius:0;color:var(--pv-on-dark)}
.site-header{color:var(--pv-ink);background:var(--pv-ground);border-bottom:1px solid
  var(--pv-line)}
.header-inner,.page-main{width:min(74rem,calc(100% - 2*var(--pv-gut)))}
  .header-inner{padding:0 0 1.25rem}
.page-main{padding-top:.5rem}.plv-topline{min-height:60px;display:flex;align-items:center;margin:0
  0 1.5rem;border-bottom:1px solid var(--pv-line)}
.plv-brand{display:inline-flex;align-items:center;gap:10px;color:var(--pv-ink);text-decoration:none;letter-spacing:.015em;font-size:.9rem;font-weight:600}
.plv-mark{width:26px;height:26px;fill:none;stroke:var(--pv-gold);stroke-width:1.4;stroke-linecap:round}
.plv-mark circle{fill:var(--pv-gold);stroke:none}
.plv-wm{font-weight:700;letter-spacing:.09em;font-size:18px}
.plv-wm b{font-weight:700;color:var(--pv-coral-ink)}
.crumbs a,.expert-meta a,.affil-primary a{color:var(--pv-coral-ink)}
.eyebrow,.affil-primary .affil-country,.affil-primary .affil-source,.affil-primary
  .affil-none,.expert-now,.expert-now
  .now-year,.expert-meta,.header-meta{color:var(--pv-ink-2)}
.expert-now
  .now-badge{border-color:var(--pv-coral-ink);border-radius:0;color:var(--pv-ink);background:var(--pv-coral)}
.status-pill,.header-link,.expert-photo
  img{border-radius:0}.status-pill{color:var(--pv-ink);background:var(--pv-mint)}.status-pill[data-state=error]{color:var(--pv-ink);background:var(--pv-sun)}
.header-link,.expertise-statement{color:var(--pv-ink)}
.header-link{border-color:var(--pv-line);background:var(--pv-paper)}
.panel{margin-top:1.5rem;border-color:var(--pv-line);border-radius:0;background:var(--pv-paper)}
.metric,.pub,.affil-list li,.coauthor-list
  li,.grant,.dataset{border-color:var(--pv-line);border-radius:0;background:var(--pv-paper);box-shadow:none}
.metric
  dd,.affil-years,.pub-meta,.list-meta,#coauthor-count{font-family:var(--pv-mono);font-variant-numeric:tabular-nums}
.field input[type=search],.field
  select,.btn{border-color:var(--pv-line);border-radius:0;color:var(--pv-ink);background:var(--pv-paper)}.btn:hover{border-color:var(--pv-ink);background:var(--pv-wash)}
.active-chip{border-color:var(--pv-coral-ink);border-radius:0;background:var(--pv-cream);color:var(--pv-ink)}
.topic-filter[aria-pressed=true] .topic-chip{box-shadow:inset 0 0 0 2px
  var(--pv-ink)}.kw-chip,.topic-chip{border-radius:0}
.badge,.expert-badge{border-radius:0;color:var(--pv-ink);background:var(--pv-mint)}.badge.plastic{color:var(--pv-ink);background:var(--pv-coral)}.grant-note{color:var(--pv-coral-ink)}
.page-footer{margin-top:3rem;padding:2.5rem var(--pv-gut) calc(2.5rem +
  env(safe-area-inset-bottom));border:0;color:var(--pv-mint);background:var(--pv-night)}
.footer-inner{width:min(74rem,100%);margin:0
  auto;display:grid;grid-template-columns:minmax(120px,282px) 1fr;gap:24px
  48px;align-items:start}.footer-logo{display:block;width:min(100%,282px);height:auto}
.page-footer a{color:var(--pv-on-dark);font-size:1rem}.page-footer .footer-links{gap:.75rem
  1.5rem}.page-footer .footer-copy{margin:0 0 .75rem;color:var(--pv-mint)}
.expert-badge a:focus-visible{outline-color:var(--pv-coral-ink)}
:focus-visible{outline:3px solid
  var(--pv-coral-ink);outline-offset:3px}::selection{color:var(--pv-ink);background:var(--pv-sun)}
@media(max-width:40rem){.footer-inner{grid-template-columns:1fr}.footer-logo{width:180px}}"""
    fonts = """@font-face{font-family:"Schibsted Grotesk";font-style:normal;font-weight:400 700;
font-display:swap;src:url("./fonts/SchibstedGrotesk-Variable-latin.woff2") format("woff2")}
@font-face{font-family:"Martian Mono";font-style:normal;font-weight:400;font-display:swap;
src:url("./fonts/MartianMono-Regular-latin.woff2") format("woff2")}"""
    return (
        "/* Generated by scripts/build_region_profiles.py. */\n"
        f"{fonts}\n{token_block}\n{rules.strip()}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when a region copy is stale")
    args = parser.parse_args(argv)
    source = SOURCE.read_bytes().decode("utf-8")
    css = render_profile_css(TOKENS.read_text(encoding="utf-8"))
    current_css = PROFILE_CSS.read_text(encoding="utf-8") if PROFILE_CSS.is_file() else None
    css_stale = current_css != css
    stale = []
    for slug in REGIONS:
        target = ROOT / "site" / slug / "expert.html"
        page = render(source, slug)
        current = target.read_bytes().decode("utf-8") if target.is_file() else None
        if current == page:
            continue
        stale.append(target)
        if not args.check:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(page.encode("utf-8"))
    if css_stale and not args.check:
        PROFILE_CSS.parent.mkdir(parents=True, exist_ok=True)
        PROFILE_CSS.write_bytes(css.encode("utf-8"))
    if args.check:
        if stale or css_stale:
            names = ", ".join(p.relative_to(ROOT).as_posix() for p in stale)
            if css_stale:
                names = ", ".join(filter(None, [names, PROFILE_CSS.relative_to(ROOT).as_posix()]))
            print(f"stale region profiles/assets: {names} (run without --check)", file=sys.stderr)
            return 1
        print(
            f"ok: {len(REGIONS)} region profile pages match {SOURCE.relative_to(ROOT).as_posix()}"
        )
        return 0
    print(
        f"wrote {len(stale)} of {len(REGIONS)} region profile pages; "
        f"profile stylesheet updated: {css_stale}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
