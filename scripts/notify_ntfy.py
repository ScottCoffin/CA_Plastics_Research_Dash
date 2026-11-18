"""Post one ntfy alert when the daily refresh adds new California plastics papers (NOTIFY-AB).

Counts works in ``site/data/works_detail.json`` that are plastic-related and whose ``work_id``
is absent from the copy written before the run (``--previous``). Posts one message to the ntfy
topic in ``config/notifications.yml`` when there are any, and nothing otherwise. The topic is
public, so no secret is needed.

Failures never fail the workflow: a missing file, a bad config or a network error prints a
WARNING on stderr and exits 0.

    py -3.14 scripts/notify_ntfy.py --previous <older works_detail.json> [--dry-run]
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "notifications.yml"
DEFAULT_CURRENT = ROOT / "site" / "data" / "works_detail.json"
CLICK_URL = "https://plastiverse.live/california/evidence#ev-recent"
TAGS = "microscope"
USER_AGENT = "ca-plastics-research-atlas-notify"
TIMEOUT_SECONDS = 15
TITLE_CHARS = 90
TOPIC_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")

Opener = Callable[..., Any]


@dataclass(frozen=True)
class Settings:
    topic: str
    server: str
    max_titles: int


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def load_settings(path: Path = DEFAULT_CONFIG) -> Settings:
    """Read the ``ntfy`` block of the notifications config; raise ValueError when unusable."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    block = data.get("ntfy") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        raise ValueError("config has no ntfy block")
    topic = str(block.get("topic", "")).strip()
    server = str(block.get("server", "https://ntfy.sh")).strip().rstrip("/")
    max_titles = block.get("max_titles", 5)
    if not TOPIC_PATTERN.fullmatch(topic):
        raise ValueError("ntfy.topic must be 1-64 letters, digits, '-' or '_'")
    if not server.startswith("https://"):
        raise ValueError("ntfy.server must be an https URL")
    if not isinstance(max_titles, int) or isinstance(max_titles, bool) or max_titles < 1:
        raise ValueError("ntfy.max_titles must be a whole number of at least 1")
    return Settings(topic=topic, server=server, max_titles=max_titles)


def read_works(path: Path, label: str) -> list[dict[str, Any]] | None:
    """Return the ``works`` rows of a works_detail file, or None after a WARNING."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        warn(f"{label} works file unreadable ({path}): {exc}")
        return None
    rows = payload.get("works") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        warn(f"{label} works file has no works list ({path})")
        return None
    return [row for row in rows if isinstance(row, dict)]


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def _year(row: Mapping[str, Any]) -> int:
    year = row.get("year")
    return year if isinstance(year, int) and not isinstance(year, bool) else 0


def new_plastic_works(
    current: Sequence[Mapping[str, Any]], previous: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """Plastic-related works in ``current`` whose work_id is not in ``previous``, newest first.

    A work that was already published and is only re-labelled plastic-related is not new.
    """
    known = {str(row.get("work_id") or "") for row in previous}
    fresh = [
        row
        for row in current
        if row.get("plastic_related") is True
        and row.get("work_id")
        and str(row["work_id"]) not in known
    ]
    return sorted(
        fresh,
        key=lambda row: (-_year(row), _clean(row.get("title")).casefold(), str(row["work_id"])),
    )


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_message(works: Sequence[Mapping[str, Any]], max_titles: int) -> tuple[str, str]:
    """Return (title, body): the count, then up to ``max_titles`` titles and "and N more"."""
    count = len(works)
    noun = "paper" if count == 1 else "papers"
    title = f"{count} new California plastics {noun}"
    lines = [
        "- " + _truncate(_clean(row.get("title")) or "Untitled work", TITLE_CHARS)
        for row in works[:max_titles]
    ]
    if count > max_titles:
        lines.append(f"and {count - max_titles} more")
    return title, "\n".join(lines)


def build_request(settings: Settings, title: str, body: str) -> tuple[str, dict[str, str], bytes]:
    url = f"{settings.server}/{settings.topic}"
    headers = {"Title": title, "Click": CLICK_URL, "Tags": TAGS, "User-Agent": USER_AGENT}
    return url, headers, body.encode("utf-8")


def dry_run_text(url: str, headers: Mapping[str, str], body: str) -> str:
    head = [f"POST {url}"] + [f"{name}: {headers[name]}" for name in ("Title", "Click", "Tags")]
    text = "\n".join(head) + "\n\n" + body
    # A redirected console may not encode every title character; show '?' rather than crash.
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


def post_alert(
    url: str, headers: Mapping[str, str], data: bytes, *, opener: Opener | None = None
) -> bool:
    """POST the alert; return False after a WARNING on any failure. Never raises."""
    open_url = opener or urllib.request.urlopen
    request = urllib.request.Request(url, data=data, headers=dict(headers), method="POST")
    try:
        with open_url(request, timeout=TIMEOUT_SECONDS) as response:
            status = int(getattr(response, "status", 200))
    except (OSError, ValueError, http.client.HTTPException) as exc:  # HTTPError is an OSError
        warn(f"ntfy alert not sent: {exc}")
        return False
    if not 200 <= status < 300:
        warn(f"ntfy alert not sent: HTTP {status}")
        return False
    return True


def main(argv: list[str] | None = None, *, opener: Opener | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--previous", type=Path, required=True, help="works_detail.json from before this run"
    )
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true", help="print the request; send nothing")
    args = parser.parse_args(argv)

    try:
        settings = load_settings(args.config)
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        warn(f"no ntfy alert; notification config unusable: {exc}")
        return 0
    previous = read_works(args.previous, "previous")
    current = read_works(args.current, "current")
    if previous is None or current is None:
        return 0
    fresh = new_plastic_works(current, previous)
    if not fresh:
        print("No new California plastics papers; no ntfy alert.")
        return 0
    title, body = build_message(fresh, settings.max_titles)
    url, headers, data = build_request(settings, title, body)
    if args.dry_run:
        print(dry_run_text(url, headers, body))
        return 0
    if post_alert(url, headers, data, opener=opener):
        print(f"Sent ntfy alert: {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
