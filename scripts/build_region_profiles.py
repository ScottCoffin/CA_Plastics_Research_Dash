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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when a region copy is stale")
    args = parser.parse_args(argv)
    source = SOURCE.read_bytes().decode("utf-8")
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
    if args.check:
        if stale:
            names = ", ".join(p.relative_to(ROOT).as_posix() for p in stale)
            print(f"stale region profiles: {names} (run without --check)", file=sys.stderr)
            return 1
        print(
            f"ok: {len(REGIONS)} region profile pages match {SOURCE.relative_to(ROOT).as_posix()}"
        )
        return 0
    print(f"wrote {len(stale)} of {len(REGIONS)} region profile pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
