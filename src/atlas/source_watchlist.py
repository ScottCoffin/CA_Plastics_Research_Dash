"""Bounded public availability checks for explicitly deferred source pages."""

from __future__ import annotations

import hashlib
import json
import socket
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

MAX_SOURCES = 50
MAX_WORKERS = 3
MAX_BODY_BYTES = 1024
TIMEOUT_SECONDS = 8
ALLOWED_HOSTS = {"opc.ca.gov", "ceden.org"}
STATUS_PATH = Path("docs/api_notes/source_watch_s7_6.json")
DOC_PATH = Path("docs/SOURCES.md")
START = "<!-- S7.6 WATCHLIST START -->"
END = "<!-- S7.6 WATCHLIST END -->"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def _validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username:
        raise ValueError("watch URL must use an approved public HTTPS host")
    for result in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
        if not __import__("ipaddress").ip_address(result[4][0]).is_global:
            raise ValueError("watch host resolved to a non-public address")


def probe(url: str) -> dict[str, Any]:
    """Request only headers, falling back to a strictly bounded Range GET."""
    _validate_url(url)
    opener = urllib.request.build_opener(_NoRedirect())
    method = "HEAD"
    request = urllib.request.Request(
        url, method=method, headers={"User-Agent": "CA-Plastics-source-watch/1.0"}
    )
    try:
        response = opener.open(request, timeout=TIMEOUT_SECONDS)
    except urllib.error.HTTPError as error:
        if error.code not in {405, 501}:
            return _response(error.code, error.headers, method, 0)
        method = "GET"
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "CA-Plastics-source-watch/1.0",
                "Range": f"bytes=0-{MAX_BODY_BYTES - 1}",
            },
        )
        try:
            response = opener.open(request, timeout=TIMEOUT_SECONDS)
        except urllib.error.HTTPError as fallback:
            return _response(fallback.code, fallback.headers, method, 0)
    except (TimeoutError, OSError, urllib.error.URLError) as error:
        return {
            "http_status": None,
            "method": method,
            "bytes_read": 0,
            "error": type(error).__name__,
        }
    with response:
        n = len(response.read(MAX_BODY_BYTES)) if method == "GET" else 0
        return _response(response.status, response.headers, method, n)


def _response(code: int, headers: Any, method: str, n: int) -> dict[str, Any]:
    return {
        "http_status": code,
        "method": method,
        "bytes_read": n,
        "etag": headers.get("ETag"),
        "last_modified": headers.get("Last-Modified"),
        "content_length": headers.get("Content-Length"),
        "access_status": "reachable" if 200 <= code < 400 else "unavailable_or_restricted",
    }


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def run(watch_path: Path, status_path: Path, docs_path: Path, checked_at: str) -> dict[str, Any]:
    watch = json.loads(watch_path.read_text(encoding="utf-8"))
    sources = watch["sources"]
    if len(sources) > MAX_SOURCES or len({s["id"] for s in sources}) != len(sources):
        raise ValueError("watchlist must contain at most 50 unique identities")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        observations = list(pool.map(lambda s: probe(s["url"]), sources))
    old = (
        json.loads(status_path.read_text(encoding="utf-8"))
        if status_path.exists()
        else {"sources": {}}
    )
    old_sources = old.get("sources", {})
    result_sources: dict[str, Any] = {}
    for source, observation in zip(sources, observations, strict=True):
        prior = old_sources.get(source["id"], {})
        observation_digest = _digest(observation)
        changed = bool(
            prior.get("observation_digest") and prior["observation_digest"] != observation_digest
        )
        result_sources[source["id"]] = {
            "name": source["name"],
            "url": source["url"],
            "reason": source["reason"],
            "next_review": source["next_review"],
            "tier": "C",
            "status": "manual_review",
            "checked_at": checked_at,
            "observation": observation,
            "observation_digest": observation_digest,
            "change": "access_or_metadata_changed"
            if changed
            else "no_observed_change"
            if prior
            else "baseline",
        }
    payload = {"schema_version": 1, "checked_at": checked_at, "sources": result_sources}
    digest = _digest({key: value["observation_digest"] for key, value in result_sources.items()})
    history = old.get("history", [])
    if not history or history[-1].get("digest") != digest:
        history.append({"checked_at": checked_at, "digest": digest})
    payload["history"] = history[-100:]
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _update_docs(docs_path, payload)
    return payload


def _update_docs(path: Path, payload: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("docs/SOURCES.md must contain exactly one marked S7.6 block")
    rows = [
        "| Source | Reason / next review | URL | Last checked | Observed status / change | Tier |",
        "|---|---|---|---|---|---|",
    ]
    for record in payload["sources"].values():
        obs = record["observation"]
        observed = obs.get("http_status")
        if observed is None:
            observed = f"failed ({obs.get('error', 'unknown')})"
        status = f"{observed}; {record['change']}; manual review"
        rows.append(
            f"| {record['name']} | {record['reason']} / {record['next_review']} | "
            f"[{record['url']}]({record['url']}) | {record['checked_at']} | {status} | C |"
        )
    block = (
        START
        + "\n\nWeekly metadata-only checks. HTTP status, validators, and limited response "
        "metadata do not establish data availability, quality, or reuse rights.\n\n"
        + "\n".join(rows)
        + "\n\n"
        + END
    )
    begin = text.index(START)
    finish = text.index(END, begin) + len(END)
    path.write_text(text[:begin] + block + text[finish:], encoding="utf-8")


def main() -> None:
    run(
        Path("config/source_watchlist_s7_6.json"),
        STATUS_PATH,
        DOC_PATH,
        datetime.now(UTC).isoformat(timespec="seconds"),
    )


if __name__ == "__main__":
    main()
