"""Turn approved ambassador contributions into a reviewable repository change (AMB-1 step 4).

Reads GET {api}/export/approved (or a saved export with --input) and applies:

- stream ``confirm`` (confirm, correct, not_relevant): edits the item named by ``payload.item_id``
  in ``regions/<slug>/region.yml``. ``item_id`` is ``<slug>:<section or kind>:<0-based index>``.
- stream ``knowledge``: appends a ``draft`` item to the matching section (``correction`` edits one).
- consensus ``case_answers``: rows in ``curation/ambassador_labels.csv``, newest per (region, case).

Every payload string is validated again here; an invalid item is skipped with a printed reason.
Region files are edited line by line, so comments and untouched items keep their bytes. The
watermark in ``curation/ambassador_export_state.json`` advances only after every file is written.
The token (``AMB_EXPORT_TOKEN``) is read from the environment and is never printed or logged.

Usage:
    py -3.14 scripts/ambassador_export_pr.py [--dry-run] [--input FILE] [--api-url URL]
"""

from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API_URL = "https://api.plastiverse.live"
DEFAULT_STATE = ROOT / "curation" / "ambassador_export_state.json"
DEFAULT_LABELS = ROOT / "curation" / "ambassador_labels.csv"
DEFAULT_REGIONS = ROOT / "regions"
TOKEN_ENV = "AMB_EXPORT_TOKEN"
LABEL_COLUMNS = ("region", "case_id", "answer", "correct_value", "answered_at_iso", "source")
LABEL_SOURCE = "ambassador_consensus"

# Same section ids and item fields that scripts/build_region_pages.py enforces (region-v1).
SECTION_IDS = ("funding", "monitoring", "policy", "research_networks", "local_terms", "geography")
ITEM_STATUSES = ("to_confirm", "draft", "confirmed", "not_relevant")
ITEM_KEYS = frozenset({"name", "url", "kind", "status", "note"})
ITEM_KEY_ORDER = ("name", "url", "kind", "status", "note")

# Knowledge kind -> (section id, item kind). region-v1 has no `community` section, so community and
# volunteer groups go under research_networks, item kind "community" (docs/AMBASSADOR_EXPORT.md).
# Kinds not listed here (event, media, researcher) have no section and are skipped.
KNOWLEDGE_SECTIONS = {
    "funder": ("funding", "funder"),
    "policy": ("policy", "policy"),
    "dataset": ("monitoring", "dataset"),
    "research_network": ("research_networks", "research_network"),
    "institution": ("research_networks", "institute"),
    "community_group": ("research_networks", "community"),
    "volunteer_group": ("research_networks", "community"),
    "community_knowledge": ("research_networks", "community"),
}
REQUIRE_URL = frozenset(
    {"funder", "policy", "dataset", "research_network", "community_group", "volunteer_group"}
)
CONFIRM_KINDS = frozenset({"confirm", "correct", "not_relevant"})

MAX_LENGTH = {
    "name": 200,
    "url": 500,
    "description": 1000,
    "note": 1000,
    "item_id": 200,
    "answer": 40,
    "correct_value": 200,
    "case_id": 80,
}
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,40}$")
ITEM_ID_RE = re.compile(r"^([a-z][a-z0-9-]{0,40}):([a-z_]{1,40}):(\d{1,4})$")
CASE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
CONTROL_OR_HTML_RE = re.compile(r"[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SECTION_LINE_RE = re.compile(r"^  - id: (\S+)\s*$")
ITEM_LINE_RE = re.compile(r"^      - \{.*\}\s*$")
MAX_MS = 253402300799000  # 9999-12-31T23:59:59Z


class ExportError(Exception):
    """A fatal problem: nothing is written and the watermark does not move."""


# ---------------------------------------------------------------- validation helpers


def clean_text(value: Any, field: str) -> str | None:
    """Trimmed text within the field's cap, with no control characters, angle brackets or HTML."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > MAX_LENGTH[field] or CONTROL_OR_HTML_RE.search(text):
        return None
    return text


def clean_url(value: Any) -> str | None:
    """https only, no credentials, no whitespace."""
    text = clean_text(value, "url")
    if text is None or re.search(r"\s", text):
        return None
    try:
        parts = urllib.parse.urlsplit(text)
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return None
    return text


def optional(payload: dict, field: str, cleaner: Any) -> tuple[bool, Any]:
    """(valid, value). A missing or empty field is valid with value None."""
    raw = payload.get(field)
    if raw in (None, ""):
        return True, None
    value = cleaner(raw)
    return value is not None, value


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def payload_of(record: dict) -> dict | None:
    payload = record.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return None
    return payload if isinstance(payload, dict) else None


def iso_from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ms_from_iso(text: str) -> int:
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000)


def locate_item(data: dict, item_id: str | None, slug: str) -> tuple[dict, dict] | None:
    """Return (section, item) for ``<slug>:<section id or kind>:<n>``, or None."""
    match = ITEM_ID_RE.match(item_id or "")
    if not match or match.group(1) != slug:
        return None
    key, index = match.group(2), int(match.group(3))
    sections = data.get("sections") or []
    for section in sections:
        if section.get("id") == key:
            items = section.get("items") or []
            return (section, items[index]) if index < len(items) else None
    hits = [(s, it) for s in sections for it in s.get("items") or [] if it.get("kind") == key]
    return hits[index] if index < len(hits) else None


def region_problem(data: dict) -> str | None:
    """The region-v1 rules that build_region_pages.py enforces. None when the region is valid."""
    sections = data.get("sections")
    if not isinstance(sections, list) or tuple(s.get("id") for s in sections) != SECTION_IDS:
        return "sections must be the six region-v1 sections in order"
    for section in sections:
        items = section.get("items")
        if not isinstance(items, list) or not items:
            return f"section {section['id']} has no items"
        for item in items:
            if not isinstance(item, dict) or set(item) != ITEM_KEYS:
                return f"section {section['id']} has an item with the wrong keys"
            if item["status"] not in ITEM_STATUSES:
                return f"section {section['id']} has a bad status"
            url = item["url"]
            if not isinstance(url, str) or (url and not url.startswith("https://")):
                return f"section {section['id']} has a non-https url"
            if not isinstance(item["note"], str) or not item["note"].strip():
                return f"section {section['id']} has an empty note"
    return None


# ---------------------------------------------------------------- region.yml line editing


def render_item(item: dict) -> str:
    fields = ", ".join(f"{k}: {json.dumps(item[k], ensure_ascii=False)}" for k in ITEM_KEY_ORDER)
    return f"      - {{{fields}}}\n"


def item_line_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Map section id -> [first, last+1) line range of its flow-style item lines."""
    section = None
    ranges: dict[str, tuple[int, int]] = {}
    counts: Counter = Counter()
    for index, line in enumerate(lines):
        found = SECTION_LINE_RE.match(line)
        if found:
            section = found.group(1)
        elif section and ITEM_LINE_RE.match(line):
            first = ranges.get(section, (index, index))[0]
            ranges[section] = (first, index + 1)
            counts[section] += 1
    for sid, (first, last) in ranges.items():
        if last - first != counts[sid]:
            raise ExportError(f"section {sid} items are not contiguous; edit region.yml by hand")
    return ranges


def render_region(text: str, original: dict, data: dict) -> str:
    """Rewrite only the item lines whose content changed. Everything else keeps its bytes."""
    lines = text.splitlines(keepends=True)
    ranges = item_line_ranges(lines)
    original_items = {s["id"]: s["items"] for s in original["sections"]}
    out = list(lines)
    for section in reversed(data["sections"]):
        sid = section["id"]
        if sid not in ranges:
            raise ExportError(f"region.yml has no item lines for section {sid}")
        first, last = ranges[sid]
        before = lines[first:last]
        orig = original_items[sid]
        new_lines = []
        for i, item in enumerate(section["items"]):
            keep = i < len(orig) and item == orig[i] and i < len(before)
            new_lines.append(before[i] if keep else render_item(item))
        out[first:last] = new_lines
    new_text = "".join(out)
    if yaml.safe_load(new_text) != data:
        raise ExportError("rendered region.yml does not match the edited data; nothing written")
    return new_text


# ---------------------------------------------------------------- applying submissions


class Applier:
    """Holds the region files and label rows in memory; nothing touches disk until write_all()."""

    def __init__(self, regions_dir: Path, labels: dict[tuple[str, str], dict]) -> None:
        self.regions_dir = regions_dir
        self.original: dict[str, tuple[str, dict]] = {}
        self.docs: dict[str, dict] = {}
        self.changed: set[str] = set()
        self.labels = labels
        self.labels_changed = False
        self.applied: Counter = Counter()
        self.skipped: list[tuple[str, str]] = []

    def region_path(self, slug: str) -> Path:
        return self.regions_dir / slug / "region.yml"

    def load(self, slug: str) -> dict | None:
        if slug not in self.docs:
            path = self.region_path(slug)
            if not path.is_file():
                return None
            text = path.read_text(encoding="utf-8")
            loaded = yaml.safe_load(text)
            if not isinstance(loaded, dict):
                raise ExportError(f"{path} is not a mapping")
            self.original[slug] = (text, copy.deepcopy(loaded))
            self.docs[slug] = loaded
        return self.docs[slug]

    def skip(self, record_id: str, reason: str) -> None:
        self.skipped.append((record_id, reason))

    def submission(self, sub: dict, credit: str | None) -> str | None:
        """Apply one approved submission. Returns a skip reason, or None when applied."""
        slug = sub.get("region")
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            return "invalid region"
        data = self.load(slug)
        if data is None:
            return "no regions/<slug>/region.yml for this region"
        if "sections" not in data:
            return "region has no placeholder sections"
        payload = payload_of(sub)
        if payload is None:
            return "payload is not an object"
        kind = sub.get("kind")
        stream = sub.get("stream")
        snapshot = copy.deepcopy(data)
        if stream == "confirm":
            reason = self._confirm(slug, data, kind, payload, credit)
        elif stream == "knowledge":
            reason = self._knowledge(slug, data, kind, payload, credit)
        else:
            return "unknown stream"
        if reason is None:
            reason = region_problem(data)
            if reason is not None:
                reason = f"would make region.yml invalid ({reason})"
        if reason is not None:
            self.docs[slug] = snapshot
            return reason
        self.changed.add(slug)
        self.applied[(slug, f"{stream}:{kind}")] += 1
        return None

    def _confirm(
        self, slug: str, data: dict, kind: Any, payload: dict, credit: str | None
    ) -> str | None:
        if kind not in CONFIRM_KINDS:
            return "unknown confirm kind"
        found = locate_item(data, clean_text(payload.get("item_id"), "item_id"), slug)
        if found is None:
            return "item_id does not match an item in region.yml"
        section, item = found
        if kind == "not_relevant":
            # Marked, never removed: item ids are positions, so removing one would shift later ids.
            item["status"] = "not_relevant"
            return None
        if kind == "correct":
            ok_name, name = optional(payload, "name", lambda v: clean_text(v, "name"))
            ok_url, url = optional(payload, "url", clean_url)
            if not (ok_name and ok_url):
                return "invalid name or url"
            if name is None and url is None:
                return "correction has no name or url"
            if name is not None:
                item["name"] = name
            if url is not None:
                item["url"] = url
        item["status"] = "confirmed"
        if credit:
            item["note"] = f"{item['note']} Confirmed by {credit}."
        return None

    def _knowledge(
        self, slug: str, data: dict, kind: Any, payload: dict, credit: str | None
    ) -> str | None:
        if kind == "correction":
            return self._correction(slug, data, payload, credit)
        if kind not in KNOWLEDGE_SECTIONS:
            return f"no region section for kind {kind!r}"
        section_id, item_kind = KNOWLEDGE_SECTIONS[kind]
        name = clean_text(payload.get("name"), "name")
        if name is None:
            return "invalid or missing name"
        ok_url, url = optional(payload, "url", clean_url)
        if not ok_url:
            return "invalid url (https only)"
        if url is None:
            if kind in REQUIRE_URL:
                return "missing url"
            url = ""
        ok_desc, description = optional(
            payload, "description", lambda v: clean_text(v, "description")
        )
        if not ok_desc:
            return "invalid description"
        note = (
            description
            or "Added from an ambassador submission; not yet confirmed by a local expert."
        )
        if credit:
            note += f" Suggested by {credit}."
        section = next(s for s in data["sections"] if s["id"] == section_id)
        for existing in section["items"]:
            if existing["name"].casefold() == name.casefold() and existing["url"] == url:
                return "duplicate of an existing item"
        section["items"].append(
            {"name": name, "url": url, "kind": item_kind, "status": "draft", "note": note}
        )
        return None

    def _correction(self, slug: str, data: dict, payload: dict, credit: str | None) -> str | None:
        found = locate_item(data, clean_text(payload.get("item_id"), "item_id"), slug)
        if found is None:
            return "item_id does not match an item in region.yml"
        ok_name, name = optional(payload, "name", lambda v: clean_text(v, "name"))
        ok_url, url = optional(payload, "url", clean_url)
        ok_desc, description = optional(
            payload, "description", lambda v: clean_text(v, "description")
        )
        if not (ok_name and ok_url and ok_desc):
            return "invalid correction field"
        if name is None and url is None and description is None:
            return "correction has no fields"
        _, item = found
        if name is not None:
            item["name"] = name
        if url is not None:
            item["url"] = url
        if description is not None:
            item["note"] = description
        item["status"] = "draft"
        if credit:
            item["note"] = f"{item['note']} Corrected by {credit}."
        return None

    def consensus(self, row: dict) -> str | None:
        """Keep the newest consensus answer per (region, case_id)."""
        slug = row.get("region")
        case_id = row.get("case_id")
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            return "invalid region"
        if not isinstance(case_id, str) or not CASE_ID_RE.match(case_id):
            return "invalid case_id"
        answer = clean_text(row.get("answer"), "answer")
        ok_value, correct_value = optional(
            row, "correct_value", lambda v: clean_text(v, "correct_value")
        )
        at = row.get("answered_at")
        if answer is None or not ok_value or not is_int(at) or not 0 <= at <= MAX_MS:
            return "invalid answer, correct_value or answered_at"
        key = (slug, case_id)
        existing = self.labels.get(key)
        if existing is not None and existing["ms"] > at:
            return "older than the stored answer"
        self.labels[key] = {
            "ms": at,
            "row": {
                "region": slug,
                "case_id": case_id,
                "answer": answer,
                "correct_value": correct_value or "",
                "answered_at_iso": iso_from_ms(at),
                "source": LABEL_SOURCE,
            },
        }
        self.labels_changed = True
        self.applied[(slug, "consensus")] += 1
        return None


# ---------------------------------------------------------------- I/O


def read_state(path: Path) -> tuple[int, list[int]]:
    if not path.exists():
        return 0, []
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ExportError(f"{path.name} is not valid JSON") from exc
    since = state.get("since")
    if not is_int(since) or since < 0:
        raise ExportError("state 'since' must be a non-negative integer")
    ids = state.get("boundary_ids", [])
    if not isinstance(ids, list) or not all(is_int(i) for i in ids):
        raise ExportError("state 'boundary_ids' must be a list of integers")
    return since, ids


def read_labels(path: Path) -> dict[tuple[str, str], dict]:
    labels: dict[tuple[str, str], dict] = {}
    if not path.exists():
        return labels
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not (row.get("region") and row.get("case_id")):
                continue
            try:
                ms = ms_from_iso(row["answered_at_iso"])
            except (KeyError, TypeError, ValueError):
                raise ExportError(f"{path.name} has a row with a bad answered_at_iso") from None
            labels[(row["region"], row["case_id"])] = {
                "ms": ms,
                "row": {col: row.get(col, "") or "" for col in LABEL_COLUMNS},
            }
    return labels


def fetch_export(api_url: str, since: int, token: str) -> dict:
    """GET the approved export. The token is sent only in the header and never echoed."""
    if not api_url.startswith("https://"):
        raise ExportError("--api-url must be https")
    query = urllib.parse.urlencode({"since": since})
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/export/approved?{query}",
        # Cloudflare's browser check answers 403 to the default Python-urllib agent before the
        # Worker runs, so the job names itself.
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "plastiverse-export-job/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise ExportError(f"export request failed with HTTP {exc.code}") from None
    except (urllib.error.URLError, OSError):
        raise ExportError("export request failed (network error)") from None
    try:
        data = json.loads(body)
    except ValueError:
        raise ExportError("export response is not JSON") from None
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise ExportError("export response is not ok")
    return data


def load_export(args: argparse.Namespace, since: int) -> dict:
    if args.input:
        try:
            data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ExportError(f"cannot read --input: {type(exc).__name__}") from None
        if not isinstance(data, dict):
            raise ExportError("--input is not an export object")
        return data
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise ExportError(f"{TOKEN_ENV} is not set")
    return fetch_export(args.api_url, since, token)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, path)


def write_labels(path: Path, labels: dict[tuple[str, str], dict]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=LABEL_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for entry in labels.values():
        writer.writerow(entry["row"])
    write_text(path, buffer.getvalue())


def summary_markdown(applier: Applier, since_before: int, since_after: int) -> str:
    rows = sorted(applier.applied.items())
    lines = [
        "Approved ambassador contributions, exported since "
        f"{since_before} (new watermark {since_after}). Counts only; review each change.",
        "",
        "| Region | Kind | Applied |",
        "| --- | --- | ---: |",
    ]
    lines += [f"| {slug} | {kind} | {count} |" for (slug, kind), count in rows]
    if not rows:
        lines.append("| (none) | | 0 |")
    lines += [
        "",
        f"Skipped records: {len(applier.skipped)} (listed in the job log by id, no personal data).",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- main


def run(args: argparse.Namespace) -> int:
    since, boundary = read_state(args.since_file)
    export = load_export(args, since)

    labels = read_labels(args.labels_file)
    applier = Applier(args.regions_dir, labels)
    times: list[int] = []
    sub_times: list[tuple[int, int | None]] = []

    for sub in export.get("submissions") or []:
        if not isinstance(sub, dict):
            continue
        sub_id = sub.get("id") if is_int(sub.get("id")) else None
        label = str(sub_id) if sub_id is not None else "?"
        at = sub.get("decided_at")
        if not is_int(at):
            applier.skip(label, "invalid decided_at")
            continue
        times.append(at)
        sub_times.append((at, sub_id))
        if at < since or (at == since and sub_id in boundary):
            continue
        credit = clean_text(sub.get("credit_name"), "name")
        reason = applier.submission(sub, credit)
        if reason is not None:
            applier.skip(label, reason)
            print(f"skip submission {label}: {reason}")

    for row in export.get("case_answers") or []:
        if not isinstance(row, dict):
            continue
        at = row.get("answered_at")
        if not is_int(at):
            applier.skip("case", "invalid answered_at")
            continue
        times.append(at)
        if at < since:
            continue
        reason = applier.consensus(row)
        if reason is not None:
            applier.skip("case", reason)
            print(f"skip case answer ({row.get('region')}): {reason}")

    newest = max([since, *times])
    new_boundary = {sid for at, sid in sub_times if at == newest and sid is not None}
    if newest == since:
        new_boundary |= set(boundary)
    new_state = {"since": newest, "boundary_ids": sorted(new_boundary)}

    print(
        f"submissions in export: {len(export.get('submissions') or [])}, "
        f"case answers: {len(export.get('case_answers') or [])}"
    )
    for (slug, kind), count in sorted(applier.applied.items()):
        print(f"applied {count} x {slug} {kind}")
    print(f"skipped: {len(applier.skipped)}; watermark {since} -> {newest}")

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    # Build every region text first so a rendering problem writes nothing.
    texts = {}
    for slug in sorted(applier.changed):
        original_text, original = applier.original[slug]
        texts[applier.region_path(slug)] = render_region(
            original_text, original, applier.docs[slug]
        )
    for path, text in texts.items():
        write_text(path, text)
    if applier.labels_changed:
        write_labels(args.labels_file, applier.labels)
    if args.summary_file:
        write_text(args.summary_file, summary_markdown(applier, since, newest))
    write_text(args.since_file, json.dumps(new_state, indent=2) + "\n")
    labels_state = "updated" if applier.labels_changed else "unchanged"
    print(f"wrote {len(texts)} region file(s); labels {labels_state}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--since-file", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--input", help="saved export JSON (offline); skips the API call")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--regions-dir", type=Path, default=DEFAULT_REGIONS)
    parser.add_argument("--labels-file", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--summary-file", type=Path, help="write a counts-only markdown summary")
    parser.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except ExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: file operation failed ({type(exc).__name__}); nothing was marked exported")
        return 1


if __name__ == "__main__":
    sys.exit(main())
