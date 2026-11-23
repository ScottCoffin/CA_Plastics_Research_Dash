"""BQ-V.0 Sigma.js benchmark runner (synthetic graph, offline).

Serves scripts/bench/ and the Observable npm cache (sigma 3.0.3, graphology 0.26.0)
on 127.0.0.1, drives headless Microsoft Edge with Playwright, and writes JSON results.

Desktop: 1280x800, no throttling. Mobile: Playwright "Pixel 7" device with
CDP Emulation.setCPUThrottlingRate 4. Each size runs up to 3 times; a failed run
(crash, timeout, error) is recorded once and not retried.

Usage (from the repo root):
    py -3.14 scripts/bench/bq_v0_sigma_bench.py
    py -3.14 scripts/bench/bq_v0_sigma_bench.py --sizes 5000 --modes desktop --repeats 1
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

BENCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = BENCH_DIR.parents[1]
NPM_CACHE = REPO_ROOT / "framework" / "src" / ".observablehq" / "cache" / "_npm"
DEFAULT_OUT = REPO_ROOT / "scratch" / "bq_v0" / "results.json"
PAGE = "/bq_v0_sigma_bench.html"

SIZES = (5000, 20000, 60000, 150000)
MODES = ("desktop", "mobile")
REPEATS = 3
SEED = 20261122
PATH_MS = 4000
RUN_LIMIT_S = 60
CPU_THROTTLE_RATE = 4
PIXEL_7 = "Pixel 7"
DESKTOP_VIEWPORT = {"width": 1280, "height": 800}
TTI_TARGET_MS = 3000
FPS_TARGET = 30


class _BenchHandler(http.server.SimpleHTTPRequestHandler):
    """Serves scripts/bench/ at / and the npm cache at /npm/. Nothing else."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
    }

    def translate_path(self, path: str) -> str:
        clean = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        root, rel = (
            (NPM_CACHE, clean[len("/npm/") :])
            if clean.startswith("/npm/")
            else (
                BENCH_DIR,
                clean.lstrip("/"),
            )
        )
        target = (root / rel).resolve()
        if target != root.resolve() and root.resolve() not in target.parents:
            return str(BENCH_DIR / "__not_found__")  # Path escaped the served folder.
        return str(target)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


def start_server() -> tuple[http.server.ThreadingHTTPServer, str]:
    """Start the local server on a free 127.0.0.1 port and return it with its base URL."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _BenchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}"


def machine_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "os": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "logical_cpus": os.cpu_count(),
        "cpu_name": None,
        "ram_gb": None,
    }
    script = (
        "Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name;"
        "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        if lines:
            info["cpu_name"] = lines[0]
        if len(lines) > 1:
            info["ram_gb"] = round(int(lines[1]) / 2**30, 1)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        info["machine_probe_error"] = str(exc)[:200]
    return info


def _context_options(mode: str, playwright: Any) -> dict[str, Any]:
    if mode == "mobile":
        return dict(playwright.devices[PIXEL_7])
    return {"viewport": DESKTOP_VIEWPORT, "device_scale_factor": 1}


def run_once(
    browser: Any, playwright: Any, mode: str, n: int, base_url: str, repeat: int
) -> dict[str, Any]:
    """Load the page, run one size, and return the record (status ok, timeout, crash or error)."""
    record: dict[str, Any] = {"mode": mode, "n": n, "repeat": repeat, "status": "ok"}
    context = browser.new_context(**_context_options(mode, playwright))
    page = context.new_page()
    state: dict[str, Any] = {"crashed": False}
    page_errors: list[str] = []
    console_errors: list[str] = []
    page.on("crash", lambda _page: state.update(crashed=True))
    page.on("pageerror", lambda exc: page_errors.append(str(exc)[:300]))
    page.on(
        "console",
        lambda msg: console_errors.append(msg.text[:300]) if msg.type == "error" else None,
    )
    started = time.perf_counter()
    try:
        if mode == "mobile":
            cdp = context.new_cdp_session(page)
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": CPU_THROTTLE_RATE})
        page.goto(base_url + PAGE, wait_until="load", timeout=30000)
        page.wait_for_function("window.benchApi !== undefined", timeout=30000, polling=100)
        page.evaluate(
            """(cfg) => {
                window.__benchDone = false;
                window.__benchResult = null;
                window.__benchError = null;
                window.benchApi.run(cfg).then(
                    (r) => { window.__benchResult = r; window.__benchDone = true; },
                    (e) => {
                        window.__benchError = String((e && e.stack) || e);
                        window.__benchDone = true;
                    }
                );
            }""",
            {"n": n, "seed": SEED, "durationMs": PATH_MS},
        )
        page.wait_for_function(
            "window.__benchDone === true", timeout=RUN_LIMIT_S * 1000, polling=250
        )
        outcome = page.evaluate(
            "() => ({result: window.__benchResult, error: window.__benchError})"
        )
        if outcome["error"]:
            record["status"] = "error"
            record["error"] = outcome["error"][:500]
        else:
            record.update(outcome["result"])
    except PlaywrightTimeout:
        record["status"] = "timeout"
    except PlaywrightError as exc:
        record["status"] = "crash" if state["crashed"] else "error"
        record["error"] = str(exc).splitlines()[0][:300]
    finally:
        record["wall_s"] = round(time.perf_counter() - started, 2)
        record["crashed"] = state["crashed"]
        record["page_errors"] = page_errors[:5]
        record["console_errors"] = console_errors[:5]
        try:
            context.close()
        except PlaywrightError:
            pass
    return record


def summarise(
    runs: list[dict[str, Any]], modes: list[str], sizes: list[int], repeats: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mode in modes:
        for n in sizes:
            group = [r for r in runs if r["mode"] == mode and r["n"] == n]
            ok = [r for r in group if r["status"] == "ok"]
            row: dict[str, Any] = {
                "mode": mode,
                "n": n,
                "runs_attempted": len(group),
                "runs_ok": len(ok),
                "statuses": [r["status"] for r in group],
                "tti_ms_median": None,
                "fps_median": None,
                "meets_targets": False,
            }
            if ok:
                ttis = [r["tti_ms"] for r in ok if r.get("tti_ms") is not None]
                if ttis:
                    row["tti_ms_median"] = round(statistics.median(ttis), 1)
                row["fps_median"] = round(statistics.median(r["fps"] for r in ok), 1)
            row["meets_targets"] = bool(
                len(ok) == repeats
                and row["tti_ms_median"] is not None
                and row["tti_ms_median"] <= TTI_TARGET_MS
                and row["fps_median"] >= FPS_TARGET
            )
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--sizes", default=",".join(str(s) for s in SIZES))
    parser.add_argument("--modes", default=",".join(MODES))
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for mode in modes:
        if mode not in MODES:
            parser.error(f"unknown mode {mode!r}")

    server, base_url = start_server()
    runs: list[dict[str, Any]] = []
    browser_version = None
    started_utc = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            browser_version = browser.version
            try:
                for mode in modes:
                    for n in sizes:
                        for repeat in range(1, args.repeats + 1):
                            rec = run_once(browser, p, mode, n, base_url, repeat)
                            runs.append(rec)
                            tti = rec.get("tti_ms")
                            print(
                                f"{mode:7s} n={n:>6d} rep={repeat} status={rec['status']:<7s} "
                                f"tti_ms={tti if tti is None else round(tti)} "
                                f"fps={round(rec['fps'], 1) if 'fps' in rec else None} "
                                f"wall_s={rec['wall_s']}",
                                flush=True,
                            )
                            if rec["status"] != "ok":
                                break  # Record the failure once; do not loop on it.
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()

    summary = summarise(runs, modes, sizes, args.repeats)
    result = {
        "started_utc": started_utc,
        "machine": machine_info(),
        "browser": {
            "name": "Microsoft Edge (Playwright channel msedge)",
            "version": browser_version,
        },
        "libraries": {
            "sigma": "3.0.3",
            "graphology": "0.26.0",
            "source": "framework/src/.observablehq/cache/_npm",
        },
        "method": {
            "graph": "synthetic, seeded (mulberry32), mean degree 6, 50 clusters, "
            "90% intra-cluster edges, random preset x/y, Pareto-like weights",
            "seed": SEED,
            "tti": "graphology build + new Sigma + first presented frame + wheel-triggered frame",
            "fps": "frames rendered by sigma during a 4 s scripted camera pan/zoom",
            "desktop": {"viewport": DESKTOP_VIEWPORT, "device_scale_factor": 1},
            "mobile": {"device": PIXEL_7, "cpu_throttling_rate": CPU_THROTTLE_RATE},
            "run_limit_s": RUN_LIMIT_S,
            "repeats": args.repeats,
            "targets": {"tti_ms_max": TTI_TARGET_MS, "fps_min": FPS_TARGET},
        },
        "runs": runs,
        "summary": summary,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"results: {args.out}")
    for row in summary:
        print(
            f"{row['mode']:7s} n={row['n']:>6d} ok={row['runs_ok']}/{row['runs_attempted']} "
            f"tti_ms_median={row['tti_ms_median']} fps_median={row['fps_median']} "
            f"meets_targets={row['meets_targets']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
