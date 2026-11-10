"""SPK-1: measure HTTP range/CORS behaviour and lazy DuckDB-Wasm reads on a host.

Usage:
  py -3.14 spikes/spk1_hosting/measure.py --base https://host/path/spikes/spk1/ \
      [--probe https://host/path/spikes/spk1/probe.html] [--origin https://scottcoff.in]

Writes JSON to stdout. Network use is owner-authorized for SPK-1 (ADR-SPK-AUTH).
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

NAMES = ("p5", "p25", "p100")
HEADERS = (
    "accept-ranges",
    "content-range",
    "content-length",
    "content-encoding",
    "content-type",
    "access-control-allow-origin",
    "access-control-expose-headers",
    "cache-control",
    "etag",
)


def _request(url: str, method: str, origin: str, rng: str | None) -> dict[str, Any]:
    req = urllib.request.Request(url, method=method)
    req.add_header("Origin", origin)
    req.add_header("User-Agent", "ca-plastics-atlas-spk1/0.1")
    if rng:
        req.add_header("Range", rng)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read(4096) if method == "GET" else b""
            status, headers = resp.status, resp.headers
    except urllib.error.HTTPError as exc:
        status, headers, body = exc.code, exc.headers, b""
    out = {"status": status, "body_bytes_read": len(body)}
    out.update({name: headers.get(name) for name in HEADERS if headers.get(name) is not None})
    return out


def header_checks(base: str, origin: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name in NAMES:
        url = f"{base.rstrip('/')}/{name}.parquet"
        results[name] = {
            "head": _request(url, "HEAD", origin, None),
            "range_first_kb": _request(url, "GET", origin, "bytes=0-1023"),
            "range_tail": _request(url, "GET", origin, "bytes=-8"),
        }
    return results


def probe(probe_url: str, serve_origin: str | None = None) -> dict[str, Any]:
    """Run probe.html; with ``serve_origin``, serve the local copy at that origin.

    Interception lets a bucket be measured cross-origin from an origin its CORS
    policy allows without deploying the page there.
    """
    from playwright.sync_api import sync_playwright

    events: list[dict[str, Any]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        if serve_origin:
            html = (Path(__file__).parent / "probe.html").read_text(encoding="utf-8")
            prefix = probe_url.split("?", 1)[0]
            context.route(
                lambda url: url.split("?", 1)[0] == prefix,
                lambda route: route.fulfill(status=200, content_type="text/html", body=html),
            )

        def on_response(response) -> None:  # type: ignore[no-untyped-def]
            if ".parquet" in response.url:
                headers = response.headers
                events.append(
                    {
                        "file": response.url.rsplit("/", 1)[-1],
                        "status": response.status,
                        "request_range": response.request.headers.get("range"),
                        "content_length": int(headers.get("content-length", "0") or 0),
                        "content_range": headers.get("content-range"),
                    }
                )

        context.on("response", on_response)
        page = context.new_page()
        page.goto(probe_url, timeout=120_000)
        page.wait_for_function("window.__spk1 !== undefined", timeout=600_000)
        results = page.evaluate("window.__spk1")
        browser.close()
    per_file: dict[str, dict[str, int]] = {}
    for event in events:
        stats = per_file.setdefault(event["file"], {"requests": 0, "bytes": 0, "status_200": 0})
        stats["requests"] += 1
        stats["bytes"] += event["content_length"]
        stats["status_200"] += int(event["status"] == 200)
    return {"page_results": results, "transfer": per_file, "events_sample": events[:6]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--probe")
    parser.add_argument("--origin", default="https://scottcoff.in")
    parser.add_argument(
        "--serve-origin-probe",
        action="store_true",
        help="serve the local probe.html at the --probe URL instead of fetching it",
    )
    args = parser.parse_args()
    report: dict[str, Any] = {"base": args.base, "headers": header_checks(args.base, args.origin)}
    if args.probe:
        report["probe"] = probe(args.probe, args.origin if args.serve_origin_probe else None)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
