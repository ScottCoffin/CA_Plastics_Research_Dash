"""Weekly metadata-only watch for CEDEN microplastics rows on data.ca.gov.

Counts rows whose Unit is a microplastics unit in each datastore-active yearly
resource of the CEDEN surface water chemistry package. The counts are
availability metadata only; they are not data quality, completeness, or reuse
evidence.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

API_BASE = "https://data.ca.gov/api/3/action"
PACKAGE_ID = "surface-water-chemistry-results"
PACKAGE_URL = "https://data.ca.gov/dataset/surface-water-chemistry-results"
UNITS = ["particles/L", "particles/g", "particles/kg", "particles/m3"]
FILTERS = json.dumps({"Unit": UNITS}, sort_keys=True)
PROJECT_FIELDS = "Program,ParentProject,Project"
PAGE_SIZE = 1000
MAX_REQUESTS = 40
SPACING_SECONDS = 0.3
TIMEOUT_SECONDS = 30
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
MAX_HISTORY = 100
USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
STATUS_PATH = Path("docs/api_notes/ceden_watch.json")
DOC_PATH = Path("docs/SOURCES.md")
START = "<!-- S7.8 CEDEN WATCH START -->"
END = "<!-- S7.8 CEDEN WATCH END -->"
S76_END = "<!-- S7.6 WATCHLIST END -->"

Transport = Callable[[str, dict[str, Any]], Any]


class RequestBudgetExceeded(Exception):
    """Raised instead of sending a request beyond MAX_REQUESTS."""


class _Budget:
    def __init__(self, transport: Transport) -> None:
        self.transport = transport
        self.used = 0

    def __call__(self, action: str, params: dict[str, Any]) -> Any:
        if self.used >= MAX_REQUESTS:
            raise RequestBudgetExceeded("request budget exhausted")
        self.used += 1
        return self.transport(action, params)


class DataCaTransport:
    """Live CKAN client: stdlib urllib, fixed host, spaced and time-limited requests."""

    def __init__(self) -> None:
        self._last: float | None = None

    def __call__(self, action: str, params: dict[str, Any]) -> Any:
        if self._last is not None:
            wait = SPACING_SECONDS - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        self._last = time.monotonic()
        url = f"{API_BASE}/{action}?{urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("CKAN response exceeded the size cap")
        payload = json.loads(body.decode("utf-8"))
        if payload.get("success") is not True:
            raise ValueError("CKAN reported success=false")
        return payload["result"]


class FixtureError(TimeoutError):
    """Offline stand-in for a transport failure; recorded by its class name."""


def offline_transport(fixture: dict[str, Any]) -> Transport:
    """Serve package_show and datastore_search from a fixture document.

    Shape: {"package_show": {"result": {...}} | {"error": true},
            "datastore": {resource_id: {"total": int, "records": [...]} | {"error": true}}}
    """

    def call(action: str, params: dict[str, Any]) -> Any:
        if action == "package_show":
            entry = fixture["package_show"]
            if entry.get("error"):
                raise FixtureError("fixture package_show failure")
            return entry["result"]
        entry = fixture["datastore"][params["resource_id"]]
        if entry.get("error"):
            raise FixtureError("fixture datastore failure")
        limit, offset = int(params["limit"]), int(params.get("offset", 0))
        if limit == 0:
            return {"total": entry["total"]}
        return {"total": entry["total"], "records": entry["records"][offset : offset + limit]}

    return call


def _project_key(record: dict[str, Any]) -> str:
    parts = [str(record.get(field) or "").strip() for field in PROJECT_FIELDS.split(",")]
    return " / ".join(part for part in parts if part) or "(blank)"


def _observe(call: Transport, resource_id: str) -> dict[str, Any]:
    """Return counts for one resource, or an error. A failure is never a zero."""
    try:
        total = int(
            call(
                "datastore_search",
                {
                    "resource_id": resource_id,
                    "filters": FILTERS,
                    "limit": 0,
                },
            )["total"]
        )
        counts: dict[str, int] = {}
        seen = 0
        while total > 0 and seen < total:
            result = call(
                "datastore_search",
                {
                    "resource_id": resource_id,
                    "filters": FILTERS,
                    "fields": PROJECT_FIELDS,
                    "limit": PAGE_SIZE,
                    "offset": seen,
                },
            )
            records = result["records"]
            if not records:
                raise ValueError("project page was empty before the total was reached")
            for record in records:
                key = _project_key(record)
                counts[key] = counts.get(key, 0) + 1
            seen += len(records)
    except Exception as error:  # every transport or parse failure is recorded
        return {"rows": None, "projects": None, "error": type(error).__name__}
    return {"rows": total, "projects": dict(sorted(counts.items())), "error": None}


def _classify(observed: dict[str, Any], good: dict[str, Any] | None, has_prior: bool) -> str:
    if observed["error"] is not None:
        return "failed"
    if good is None:
        if not has_prior:
            return "baseline"
        return "new_rows" if observed["rows"] > 0 else "no_change"
    if set(observed["projects"]) - set(good["projects"]):
        return "new_project"
    if observed["rows"] > good["rows"]:
        return "new_rows"
    return "no_change"


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_watch(
    transport: Transport, checked_at: str, status_path: Path, docs_path: Path
) -> dict[str, Any]:
    """List datastore-active resources, count microplastics rows, classify, and write outputs."""
    old = _load(status_path)
    prior = old.get("resources", {})
    has_prior = bool(old)
    call = _Budget(transport)
    package_error: str | None = None
    records: dict[str, Any] = {}
    try:
        package = call("package_show", {"id": PACKAGE_ID})
        listed = [
            resource
            for resource in package["resources"]
            # Only the yearly CSV tables: the "Parquet - All Years" ZIP is flagged
            # datastore_active but its count lookup fails (2026-11-10) and duplicates them.
            if resource.get("datastore_active") is True
            and str(resource.get("format", "")).upper() == "CSV"
        ]
    except Exception as error:  # the listing failed; keep prior records untouched
        package_error = type(error).__name__
        records = prior
    else:
        for resource in sorted(listed, key=lambda r: (r.get("name", ""), r["id"])):
            resource_id = resource["id"]
            observed = _observe(call, resource_id)
            prior_good = prior.get(resource_id, {}).get("good")
            change = _classify(observed, prior_good, has_prior)
            if observed["error"] is None:
                good: dict[str, Any] | None = {
                    "rows": observed["rows"],
                    "projects": observed["projects"],
                }
            else:
                good = prior_good
            new_projects = (
                sorted(set(observed["projects"]) - set(prior_good["projects"]))
                if change == "new_project"
                else []
            )
            records[resource_id] = {
                "name": resource.get("name", resource_id),
                "rows": observed["rows"],
                "projects": observed["projects"],
                "error": observed["error"],
                "classification": change,
                "new_projects": new_projects,
                "good": good,
            }
    summary = {
        rid: {"rows": r["rows"], "projects": r["projects"], "error": r["error"]}
        for rid, r in records.items()
    }
    digest = _digest({"package_error": package_error, "resources": summary})
    history = old.get("history", [])
    if not history or history[-1].get("digest") != digest:
        history.append({"checked_at": checked_at, "digest": digest})
    payload = {
        "schema_version": 1,
        "checked_at": checked_at,
        "package_id": PACKAGE_ID,
        "units": UNITS,
        "package_error": package_error,
        "requests": call.used,
        "resources": records,
        "history": history[-MAX_HISTORY:],
    }
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    _update_docs(docs_path, payload)
    return payload


def _cell(value: str) -> str:
    return value.replace("|", "\\|")


def _block(payload: dict[str, Any]) -> str:
    lines = [
        START,
        "",
        "Weekly metadata-only CEDEN check. Row counts are availability metadata from the "
        "data.ca.gov datastore, not data quality, completeness, or reuse rights.",
        "",
        f"Checked {payload['checked_at']} against [{PACKAGE_ID}]({PACKAGE_URL}); "
        f"units: {', '.join(payload['units'])}.",
        "",
    ]
    if payload["package_error"]:
        lines.append(
            f"Resource listing failed ({payload['package_error']}); no counts were taken "
            "this run, and prior records are kept unchanged."
        )
    else:
        records = payload["resources"]
        rows = sorted(
            (r for r in records.values() if r["rows"]),
            key=lambda r: r["name"],
        )
        failed = sorted(r["name"] for r in records.values() if r["error"] is not None)
        lines += [
            "| Resource | Rows | Distinct projects | Projects (rows) |",
            "|---|---|---|---|",
        ]
        for record in rows:
            names = "; ".join(f"{_cell(k)} ({v})" for k, v in record["projects"].items())
            lines.append(
                f"| {_cell(record['name'])} | {record['rows']} | {len(record['projects'])} "
                f"| {names} |"
            )
        if not rows:
            lines.append("| (none) | 0 | 0 | |")
        total = sum(r["rows"] for r in records.values() if r["rows"])
        lines += ["", f"Total microplastics rows across checked resources: {total}."]
        if failed:
            failures = ", ".join(
                f"{_cell(r['name'])} ({r['error']})"
                for r in sorted(records.values(), key=lambda r: r["name"])
                if r["error"] is not None
            )
            lines.append(f"Failed lookups (not treated as zero): {failures}.")
        new = [
            f"{_cell(r['name'])}: {_cell(project)}"
            for r in sorted(records.values(), key=lambda r: r["name"])
            for project in r["new_projects"]
        ]
        lines.append("New projects flagged: " + ("; ".join(new) if new else "none") + ".")
    lines += ["", END]
    return "\n".join(lines)


def _update_docs(path: Path, payload: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(START) > 1 or text.count(END) > 1:
        raise ValueError("docs/SOURCES.md must contain at most one S7.8 CEDEN block")
    if text.count(START) != text.count(END):
        raise ValueError("docs/SOURCES.md has an unpaired S7.8 CEDEN marker")
    block = _block(payload)
    if START in text:
        begin = text.index(START)
        finish = text.index(END, begin) + len(END)
        text = text[:begin] + block + text[finish:]
    else:
        if text.count(S76_END) != 1:
            raise ValueError("docs/SOURCES.md must contain exactly one S7.6 block end")
        anchor = text.index(S76_END) + len(S76_END)
        text = text[:anchor] + "\n\n" + block + text[anchor:]
    path.write_text(text, encoding="utf-8", newline="\n")


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def main(argv: list[str] | None = None) -> dict[str, Any]:
    """Run the watch with the live client, or an offline fixture when one is given."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-fixture", type=Path, default=None)
    parser.add_argument("--status-path", type=Path, default=STATUS_PATH)
    parser.add_argument("--docs-path", type=Path, default=DOC_PATH)
    args = parser.parse_args(argv)
    if args.offline_fixture is None:
        transport: Transport = DataCaTransport()
    else:
        fixture = json.loads(args.offline_fixture.read_text(encoding="utf-8"))
        transport = offline_transport(fixture)
    return run_watch(transport, _timestamp(), args.status_path, args.docs_path)
