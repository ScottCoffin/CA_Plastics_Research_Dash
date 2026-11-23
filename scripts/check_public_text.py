"""Fail if internal project vocabulary appears in public page text.

Checks HTML text nodes (not comments, <script> or <style>) and JSON string values.
Stdlib only, offline. Usage:

    py -3.14 scripts/check_public_text.py [PATH ...] [--allow GLOB ...]

With no PATH, checks framework/dist (if built), site/index.html, site/california/expert.html,
site/grants.html, and the two public JSON files. A PATH may be an HTML/JSON file or a folder
(folders are searched for *.html). Exit 0 when clean, 1 on any forbidden match, 2 on bad input.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Internal project vocabulary that must not appear in visible public text.
FORBIDDEN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bEM-\d+\b", re.IGNORECASE),
    re.compile(r"\bS\d+\.\d+ export\b", re.IGNORECASE),
    re.compile(r"uploaded document; no URL", re.IGNORECASE),
    re.compile(r"awaits owner review", re.IGNORECASE),
    re.compile(r"pending owner review", re.IGNORECASE),
    re.compile(r"TODO-OWNER"),
    re.compile(r"Fixture snapshot", re.IGNORECASE),
    re.compile(r"plastic-v2-candidate", re.IGNORECASE),
    re.compile(r"Coming with", re.IGNORECASE),
]

# BQ-R1 (A3-D0): the public word is "Authors", never "Experts". Checked in HTML text nodes only.
# Allow-list: text inside <cite>/<code>/<q>/<kbd> or an element marked data-public-text="quoted"
# (work titles and other quoted text), and legacy file names / URLs (expert.html, experts/<id>/).
TERMINOLOGY_PATTERN = re.compile(r"\bexperts?\b(?!\.html|/)", re.IGNORECASE)
# Attribute values a reader sees or hears (checked like text nodes).
VISIBLE_ATTRS = {"placeholder", "title", "aria-label", "alt"}
# JSON string values under these top-level keys are public method text (terminology rule only).
JSON_TEXT_KEYS = ("method",)  # Atlas-written method text; linkout descriptions quote stewards
QUOTED_TAGS = {"cite", "code", "q", "kbd"}
# The classic site/index.html is not deployed since PLAT-1 (only its head tags are reused).
TERMINOLOGY_SKIP = {"site/index.html"}

DEFAULT_HTML = ["site/index.html", "site/california/expert.html", "site/grants.html"]
DEFAULT_JSON = [
    "site/data/dtsc_timeline.json",
    "site/data/linkouts.json",
    "site/data/network.json",
    "site/data/expert_badges.json",
    "site/data/pubmed_coverage.json",
]
SKIP_TAGS = {"script", "style"}


class _TextCollector(HTMLParser):
    """Collect (line, text) for text nodes outside <script> and <style>.

    Comments are never passed to handle_data, so they are skipped by default.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[tuple[int, str]] = []
        self.quoted: list[bool] = []
        self._skip_depth = 0
        self._quote_stack: list[tuple[str, bool]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        marked = tag in QUOTED_TAGS or dict(attrs).get("data-public-text") == "quoted"
        if marked or self._quote_stack:
            self._quote_stack.append((tag, marked))
        if not self._skip_depth:
            quoted = any(flag for _, flag in self._quote_stack)
            for name, value in attrs:
                if name in VISIBLE_ATTRS and value:
                    self.chunks.append((self.getpos()[0], value))
                    self.quoted.append(quoted)

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        for index in range(len(self._quote_stack) - 1, -1, -1):
            if self._quote_stack[index][0] == tag:
                del self._quote_stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.chunks.append((self.getpos()[0], data))
            self.quoted.append(any(marked for _, marked in self._quote_stack))


def _html_text(text: str, *, include_quoted: bool = True) -> list[tuple[str, str]]:
    """Return (location, visible text) pairs for an HTML document."""
    parser = _TextCollector()
    parser.feed(text)
    parser.close()
    return [
        (f"line {line}", chunk)
        for (line, chunk), quoted in zip(parser.chunks, parser.quoted, strict=True)
        if include_quoted or not quoted
    ]


def _json_strings(value: object, path: str = "$") -> list[tuple[str, str]]:
    """Return (location, string value) pairs for every string in a JSON document."""
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, dict):
        found: list[tuple[str, str]] = []
        for key, item in value.items():
            found.extend(_json_strings(item, f"{path}.{key}"))
        return found
    if isinstance(value, list):
        found = []
        for index, item in enumerate(value):
            found.extend(_json_strings(item, f"{path}[{index}]"))
        return found
    return []


def find_matches(path: Path) -> list[tuple[str, str, str]]:
    """Return (location, pattern, snippet) for each forbidden match in one file."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        pieces = _json_strings(json.loads(text))
    else:
        pieces = _html_text(text)
    matches: list[tuple[str, str, str]] = []
    checks = [(location, piece, FORBIDDEN_PATTERNS) for location, piece in pieces]
    rel = path.resolve().relative_to(ROOT).as_posix() if path.resolve().is_relative_to(ROOT) else ""
    if path.suffix == ".json":
        checks += [
            (location, piece, [TERMINOLOGY_PATTERN])
            for location, piece in pieces
            if any(location.startswith(f"$.{key}") for key in JSON_TEXT_KEYS)
        ]
    elif rel not in TERMINOLOGY_SKIP:
        checks += [
            (location, piece, [TERMINOLOGY_PATTERN])
            for location, piece in _html_text(text, include_quoted=False)
        ]
    for location, piece, patterns in checks:
        for pattern in patterns:
            found = pattern.search(piece)
            if found:
                snippet = " ".join(piece[max(0, found.start() - 40) : found.end() + 40].split())
                matches.append((location, found.group(0), snippet))
    return matches


def _collect_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.html")))
        else:
            files.append(path)
    return files


def _is_allowed(path: Path, allow: list[str]) -> bool:
    posix = path.as_posix()
    return any(
        fnmatch.fnmatch(posix, pattern) or fnmatch.fnmatch(path.name, pattern) for pattern in allow
    )


def _default_paths() -> list[Path]:
    paths: list[Path] = []
    dist = ROOT / "framework" / "dist"
    if dist.is_dir():
        paths.append(dist)
    paths.extend(ROOT / rel for rel in DEFAULT_HTML + DEFAULT_JSON)
    return [p for p in paths if p.exists()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths", nargs="*", help="HTML/JSON files or folders (default: public pages)"
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip files whose path or name matches this glob (repeatable)",
    )
    args = parser.parse_args(argv)

    if args.paths:
        targets = [Path(p) if Path(p).is_absolute() else ROOT / p for p in args.paths]
        missing = [str(p) for p in targets if not p.exists()]
        if missing:
            for item in missing:
                print(f"ERROR: not found: {item}", file=sys.stderr)
            return 2
    else:
        targets = _default_paths()

    files = [f for f in _collect_files(targets) if not _is_allowed(f, args.allow)]
    failures = 0
    for file in files:
        try:
            matches = find_matches(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"ERROR: cannot read {file}: {exc}", file=sys.stderr)
            return 2
        for location, pattern, snippet in matches:
            failures += 1
            print(f"FAIL: {file}: {location}: '{pattern}' in \"{snippet}\"")
    if failures:
        print(f"{failures} forbidden match(es) in {len(files)} file(s)")
        return 1
    print(f"OK: no internal vocabulary in {len(files)} public file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
