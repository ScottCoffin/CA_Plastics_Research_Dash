"""Link-out registry and weekly HTTP status check (Add-on A2 §8, EM-16).

Link, don't mirror: the registry only records where to link. Nothing here fetches
the linked resources' content; the live check reads at most 1 KiB and records status.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "config" / "linkouts.yml"
TIMELINE_PATH = ROOT / "config" / "dtsc_timeline.yml"
OUTPUT_PATH = ROOT / "docs" / "api_notes" / "linkouts_check.json"
EXPECTED_IDS = [f"LO-{number}" for number in range(1, 13)]
REQUIRED_KEYS = (
    "id",
    "name",
    "steward",
    "description",
    "description_source",
    "relation",
    "update_model",
    "terms_status",
    "terms",
    "reuse_mode",
    "root_url",
    "url_status",
    "deep_link_templates",
    "trigger_rules",
    "last_checked",
)
TERMS_RECORDED_IDS = {"LO-1"}
URL_STATUSES = {"as_stated", "owner_confirmed", "to_confirm", "unavailable"}
DISCLOSURE_LO8 = "The Atlas owner is a co-founder of Plastiverse (A2 §0 rule 7)."
FALLBACK_STATUSES = {403, 405, 501}
MAX_BODY_BYTES = 1024
TIMEOUT_SECONDS = 10
MAX_WORKERS = 3
USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
POLICY = "HEAD; GET fallback on 405/403/501; redirects not followed (Location reported)"

# transport(method, url) -> (HTTP status, Location header or None); may raise OSError.
Transport = Callable[[str, str], tuple[int, str | None]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Stop at 3xx so the status and Location are reported instead of followed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ARG002
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def urllib_transport(method: str, url: str) -> tuple[int, str | None]:
    """Live transport: stdlib urllib, 10 s timeout, at most 1 KiB read from a body."""
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    try:
        with _OPENER.open(request, timeout=TIMEOUT_SECONDS) as response:
            if method == "GET":
                response.read(MAX_BODY_BYTES)
            return response.status, response.headers.get("Location")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, exc.headers.get("Location")
        finally:
            exc.close()


def _is_https(url: object) -> bool:
    if not isinstance(url, str):
        return False
    parts = urlparse(url)
    return parts.scheme == "https" and bool(parts.netloc)


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Parse the registry YAML; YAML syntax errors surface as ValueError."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return data


def validate_registry(data: Any) -> list[str]:
    """Return a list of human-readable problems; an empty list means valid."""
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return ["registry must be a mapping with an 'entries' list"]
    errors: list[str] = []
    entries = data["entries"]
    ids = [entry.get("id") if isinstance(entry, dict) else None for entry in entries]
    for dup in sorted({i for i in ids if i is not None and ids.count(i) > 1}):
        errors.append(f"duplicate id {dup}")
    unexpected = sorted({str(i) for i in ids if i not in EXPECTED_IDS})
    for bad in unexpected:
        errors.append(f"unexpected id {bad}")
    for missing in [i for i in EXPECTED_IDS if i not in ids]:
        errors.append(f"missing id {missing}")
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("entry is not a mapping")
            continue
        errors.extend(_validate_entry(entry))
    if "minderoo" in json.dumps(data, ensure_ascii=False).lower():
        errors.append("Minderoo Plastic Health Map must not appear in the registry")
    return errors


def _validate_entry(entry: dict[str, Any]) -> list[str]:
    eid = entry.get("id", "?")
    errors = [f"{eid}: missing key {key}" for key in REQUIRED_KEYS if key not in entry]
    if errors:
        return errors
    for key in ("name", "steward", "description", "description_source", "relation"):
        if not isinstance(entry[key], str) or not entry[key].strip():
            errors.append(f"{eid}: {key} must be a non-empty string")
    if entry["update_model"] != "not stated" and not isinstance(entry["update_model"], str):
        errors.append(f"{eid}: update_model must be a string")
    if entry["reuse_mode"] != "link_only":
        errors.append(f"{eid}: reuse_mode must be link_only")
    expected_terms = "recorded" if eid in TERMS_RECORDED_IDS else "not recorded"
    if entry["terms_status"] != expected_terms:
        errors.append(f"{eid}: terms_status must be {expected_terms!r}")
    if entry["url_status"] not in URL_STATUSES:
        errors.append(f"{eid}: url_status must be one of {sorted(URL_STATUSES)}")
    root = entry["root_url"]
    if root is None:
        if entry["url_status"] != "unavailable":
            errors.append(f"{eid}: root_url may be null only when url_status is unavailable")
    elif not _is_https(root):
        errors.append(f"{eid}: root_url must be an https URL")
    errors.extend(_validate_templates(eid, entry["deep_link_templates"]))
    if not isinstance(entry["trigger_rules"], list):
        errors.append(f"{eid}: trigger_rules must be a list")
    if entry["last_checked"] is not None:
        errors.append(f"{eid}: last_checked must stay null in the YAML (see linkouts_check.json)")
    if eid == "LO-8" and entry.get("disclosure") != DISCLOSURE_LO8:
        errors.append("LO-8: disclosure must match the A2 §0 rule 7 wording")
    return errors


def _validate_templates(eid: str, templates: object) -> list[str]:
    if not isinstance(templates, list):
        return [f"{eid}: deep_link_templates must be a list"]
    errors: list[str] = []
    for item in templates:
        if not isinstance(item, dict):
            errors.append(f"{eid}: deep_link_template must be a mapping")
            continue
        template = item.get("template")
        if not isinstance(template, str) or not template.startswith("/"):
            errors.append(f"{eid}: template must start with '/'")
        if not _is_https(item.get("evidence_url")):
            errors.append(f"{eid}: template evidence_url must be an https URL")
    return errors


def timeline_source_urls(path: Path = TIMELINE_PATH) -> list[str]:
    """Return every source_url in the DTSC timeline file, or [] when it is absent."""
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML: {exc}") from exc
    entries = data.get("entries", []) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise ValueError(f"{path}: entries must be a list")
    urls: list[str] = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("source_url") is not None:
            if not _is_https(entry["source_url"]):
                raise ValueError(
                    f"{path}: source_url must be an https URL: {entry['source_url']!r}"
                )
            urls.append(entry["source_url"])
    return list(dict.fromkeys(urls))


def _check_one(url: str, call: Transport) -> dict[str, Any]:
    method = "HEAD"
    try:
        status, location = call("HEAD", url)
        if status in FALLBACK_STATUSES:
            method = "GET"
            status, location = call("GET", url)
        error = None
    except Exception as exc:  # a failed request is recorded, not raised
        status, location, error = None, None, f"{type(exc).__name__}: {exc}"
    ok = status is not None and 200 <= status < 300
    return {
        "method": method,
        "status": status,
        "location": location,
        "error": error,
        "ok": ok,
        "outcome": classify(status),
    }


def classify(status: int | None) -> str:
    """ok (2xx), redirect (3xx), restricted (401/403/429: access refused to an automated
    client, e.g. dtsc.ca.gov on 2026-11-11, not evidence the page is gone), or broken."""
    if status is None:
        return "broken"
    if 200 <= status < 300:
        return "ok"
    if 300 <= status < 400:
        return "redirect"
    if status in {401, 403, 429}:
        return "restricted"
    return "broken"


def check_links(urls: list[str], transport: Transport | None = None) -> dict[str, dict[str, Any]]:
    """HTTP-status check each unique URL with at most MAX_WORKERS concurrent workers."""
    call = transport or urllib_transport
    unique = list(dict.fromkeys(urls))
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(lambda url: _check_one(url, call), unique))
    return dict(zip(unique, results, strict=True))


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_live(
    registry_path: Path = REGISTRY_PATH,
    timeline_path: Path = TIMELINE_PATH,
    output_path: Path = OUTPUT_PATH,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Run the weekly check and write the status JSON; the YAML is never modified."""
    registry = load_registry(registry_path)
    errors = validate_registry(registry)
    if errors:
        raise ValueError("invalid registry: " + "; ".join(errors))
    entries = registry["entries"]
    timeline = timeline_source_urls(timeline_path)
    roots = [entry["root_url"] for entry in entries if entry["root_url"]]
    results = check_links([*roots, *timeline], transport)
    checked_at = _timestamp()
    payload: dict[str, Any] = {
        "checked_at": checked_at,
        "policy": POLICY,
        "entries": {},
        "timeline": {},
    }
    for entry in entries:
        root = entry["root_url"]
        record: dict[str, Any] = {"root_url": root, "url_status": entry["url_status"]}
        if root is None:
            record.update({"ok": None, "error": "no root_url recorded", "status": None})
        else:
            record.update(results[root])
        record["last_checked"] = checked_at
        payload["entries"][entry["id"]] = record
    for url in timeline:
        payload["timeline"][url] = {**results[url], "last_checked": checked_at}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


STRIP_FIELDS = (
    "id",
    "name",
    "steward",
    "description",
    "relation",
    "root_url",
    "topics",
    "default",
)
TOPIC_PREFIX = "topic="
DEFAULT_RULE = "default"


def parse_trigger_rules(rules: list[str]) -> dict[str, Any]:
    """Split display rules into {"topics": sorted unique tags, "default": bool}.

    "topic=<tag>" adds a topic; "default" sets the default flag; any other string
    (e.g. "weekly HTTP status check only") is not a display rule and is ignored.
    """
    topics: set[str] = set()
    default = False
    for rule in rules:
        if not isinstance(rule, str):
            continue
        text = rule.strip()
        if text.startswith(TOPIC_PREFIX):
            tag = text[len(TOPIC_PREFIX) :].strip()
            if tag:
                topics.add(tag)
        elif text == DEFAULT_RULE:
            default = True
    return {"topics": sorted(topics), "default": default}


def strip_entries(data: Any) -> list[dict[str, Any]]:
    """Public, display-only view of each registry entry, in file order.

    Raises ValueError when the registry fails validate_registry.
    """
    errors = validate_registry(data)
    if errors:
        raise ValueError("invalid link-out registry: " + "; ".join(errors))
    entries: list[dict[str, Any]] = []
    for entry in data["entries"]:
        rules = parse_trigger_rules(entry["trigger_rules"])
        public = {
            "id": entry["id"],
            "name": entry["name"],
            "steward": entry["steward"],
            "description": entry["description"],
            "relation": entry["relation"],
            "root_url": entry["root_url"],
            "topics": rules["topics"],
            "default": rules["default"],
        }
        entries.append({key: public[key] for key in STRIP_FIELDS})
    return entries
