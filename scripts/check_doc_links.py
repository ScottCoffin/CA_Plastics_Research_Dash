"""Check local link targets in Markdown files without making network requests."""

from __future__ import annotations

import argparse
import os
import re
import sys
from bisect import bisect_right
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

_FENCE_START = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_INLINE_LINK = re.compile(r"!?\[(?:\\.|[^\]\\])*\]\(")
_REFERENCE_START = re.compile(r"(?m)^[ \t]{0,3}\[(?!\^)(?:\\.|[^\]\\])+\]:[ \t]*")
_SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}


def _blank(value: str) -> str:
    return "".join("\r" if char == "\r" else "\n" if char == "\n" else " " for char in value)


def _mask_nonlinks(text: str) -> str:
    masked_lines: list[str] = []
    fence: tuple[str, int] | None = None

    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        marker = _FENCE_START.match(content)
        if fence is not None:
            masked_lines.append(_blank(line))
            char, length = fence
            if re.match(rf"^ {{0,3}}{re.escape(char)}{{{length},}}[ \t]*$", content):
                fence = None
        elif marker is not None:
            token = marker.group(1)
            fence = (token[0], len(token))
            masked_lines.append(_blank(line))
        else:
            masked_lines.append(line)

    masked = "".join(masked_lines)
    masked = re.sub(r"<!--.*?-->", lambda match: _blank(match.group()), masked, flags=re.S)
    return re.sub(r"(`+).*?\1", lambda match: _blank(match.group()), masked, flags=re.S)


def _parse_inline_destination(text: str, position: int) -> str | None:
    index = position
    while index < len(text) and text[index].isspace():
        index += 1
    if index == len(text):
        return None

    if text[index] == "<":
        index += 1
        value: list[str] = []
        while index < len(text):
            char = text[index]
            if char == "\\" and index + 1 < len(text):
                value.append(text[index + 1])
                index += 2
            elif char == ">":
                return "".join(value)
            else:
                value.append(char)
                index += 1
        return None

    value = []
    nested = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            value.append(text[index + 1])
            index += 2
        elif char == "(":
            nested += 1
            value.append(char)
            index += 1
        elif char == ")":
            if nested == 0:
                break
            nested -= 1
            value.append(char)
            index += 1
        elif char.isspace() and nested == 0:
            break
        else:
            value.append(char)
            index += 1
    return "".join(value)


def _parse_reference_destination(text: str, position: int) -> str | None:
    index = position
    while index < len(text) and text[index].isspace():
        index += 1
    if index == len(text):
        return None

    if text[index] == "<":
        return _parse_inline_destination(text, index)

    value: list[str] = []
    while index < len(text) and not text[index].isspace():
        if text[index] == "\\" and index + 1 < len(text):
            value.append(text[index + 1])
            index += 2
        else:
            value.append(text[index])
            index += 1
    return "".join(value)


class _HTMLLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag
        line = self.getpos()[0]
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.links.append((value, line))


def _markdown_targets(text: str) -> list[tuple[str, int]]:
    masked = _mask_nonlinks(text)
    line_starts = [0, *(index + 1 for index, char in enumerate(masked) if char == "\n")]
    targets: list[tuple[str, int]] = []

    def line_for(position: int) -> int:
        return bisect_right(line_starts, position)

    for match in _INLINE_LINK.finditer(masked):
        target = _parse_inline_destination(masked, match.end())
        if target is not None:
            targets.append((target, line_for(match.start())))

    for match in _REFERENCE_START.finditer(masked):
        target = _parse_reference_destination(masked, match.end())
        if target is not None:
            targets.append((target, line_for(match.start())))

    html_parser = _HTMLLinkParser()
    html_parser.feed(masked)
    targets.extend(html_parser.links)
    return targets


def _local_target(root: Path, source: Path, target: str) -> Path | None:
    target = unescape(target.strip())
    try:
        parsed = urlsplit(target)
    except ValueError:
        return source.parent / target

    if parsed.scheme.lower() in {"http", "https", "mailto"} or parsed.netloc:
        return None
    if parsed.scheme:
        return None
    if not parsed.path:
        return None

    decoded_path = unquote(parsed.path)
    if decoded_path.startswith("/"):
        return root / decoded_path.lstrip("/\\")
    return source.parent / decoded_path


def _display(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _walk_markdown(directory: Path) -> list[Path]:
    files: list[Path] = []
    for current, directories, names in os.walk(directory):
        directories[:] = sorted(name for name in directories if name not in _SKIP_DIRS)
        files.extend(Path(current) / name for name in names if Path(name).suffix.lower() == ".md")
    return files


def _collect_files(paths: list[str], root: Path) -> tuple[list[Path], list[str]]:
    files: set[Path] = set()
    errors: list[str] = []
    requested = [Path(path) for path in paths] if paths else [root]

    for path in requested:
        candidate = path if path.is_absolute() else Path.cwd() / path
        candidate = candidate.resolve()
        if candidate.is_dir():
            files.update(_walk_markdown(candidate))
        elif candidate.is_file() and candidate.suffix.lower() == ".md":
            files.add(candidate)
        else:
            errors.append(f"not a Markdown file or directory: {candidate}")
    return sorted(files), errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="Markdown file or directory to check (defaults to the repository)",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    files, errors = _collect_files(args.paths, root)

    for source in files:
        try:
            text = source.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            errors.append(f"{source}: could not read Markdown file: {error}")
            continue
        for target, line in _markdown_targets(text):
            local_path = _local_target(root, source, target)
            if local_path is not None and not local_path.exists():
                errors.append(
                    f"{_display(source, root)}:{line}: missing local target "
                    f"{target!r} (resolved to {_display(local_path, root)})"
                )

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"Markdown links OK ({len(files)} file(s) checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
