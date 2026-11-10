"""SPK-4 runner: bit-mask facets vs Mosaic crossfilter (gate G-FACET).

Builds seeded synthetic data (N = 30k and 100k), writes a Parquet copy through
DuckDB 1.1.1 (via uv), serves the pages from scratch/spk4/www, and drives both
pages in headless Chromium. Measures payload, cold start and update latency,
and checks counts against a Python reference.

Usage: py -3.14 spikes/spk4_facets/run_spike.py [--sizes 30000 100000] [--runs 5]
Outputs go under scratch/spk4/ (gitignored); results are printed and saved as JSON.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import shutil
import statistics
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / "scratch" / "spk4"
WWW = SCRATCH / "www"
sys.path.insert(0, str(HERE))
import build_bitsets as bb  # noqa: E402

DUCKDB_PIN = "duckdb==1.1.1"
MOSAIC_PIN = {"@uwdata/mosaic-core": "0.34.1", "@uwdata/mosaic-sql": "0.34.1"}
MOSAIC_RELEASED = "2026-10-24"  # npm time for 0.34.1 (core, sql); newest release >= 14 days old
BUDGET_MS = {30000: 50, 100000: 150}
LANDING_BUDGET_GZ = 3 * 1024 * 1024

OPS = [
    {"type": "toggle", "facet": "year", "label": "2010"},
    {"type": "toggle", "facet": "institution_type", "label": "University"},
    {"type": "toggle", "facet": "year", "label": "2011"},
    {"type": "toggle", "facet": "year", "label": "2012"},
    {"type": "toggle", "facet": "dom_marine", "label": "yes"},
    {"type": "toggle", "facet": "oa_status", "label": "Gold"},
    {"type": "toggle", "facet": "compartment", "label": "water"},
    {"type": "toggle", "facet": "compartment", "label": "sediment"},
    {"type": "toggle", "facet": "ca_basis", "label": "Statewide"},
    {"type": "toggle", "facet": "flag_peer_reviewed", "label": "yes"},
    {"type": "toggle", "facet": "study_type", "label": "Field survey"},
    {"type": "toggle", "facet": "institution", "label": "Institution 001"},
    {"type": "toggle", "facet": "year", "label": "2010"},
    {"type": "toggle", "facet": "dom_marine", "label": "yes"},
    {"type": "toggle", "facet": "year", "label": "2012"},
    {"type": "toggle", "facet": "institution_type", "label": "Government"},
    {"type": "toggle", "facet": "oa_status", "label": "Hybrid"},
    {"type": "toggle", "facet": "compartment", "label": "water"},
    {"type": "toggle", "facet": "study_type", "label": "Modelling"},
    {"type": "clear"},
]

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".bin": "application/octet-stream",
    ".parquet": "application/octet-stream",
}
GZIP_EXT = {".html", ".js", ".json", ".bin"}
_GZ_CACHE: dict[Path, bytes] = {}
_GZ_LOCK = threading.Lock()


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # silence request logging
        pass

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        rel = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path).lstrip("/")
        path = (WWW / (rel or "bitmask.html")).resolve()
        if not path.is_file() or WWW.resolve() not in path.parents:
            self.send_error(404)
            return
        body = path.read_bytes()
        headers = {"Content-Type": CONTENT_TYPES.get(path.suffix, "application/octet-stream")}
        if path.suffix in GZIP_EXT and "gzip" in self.headers.get("Accept-Encoding", ""):
            with _GZ_LOCK:
                if path not in _GZ_CACHE:
                    _GZ_CACHE[path] = gzip.compress(body, 9)
            body = _GZ_CACHE[path]
            headers["Content-Encoding"] = "gzip"
        self.send_response(200)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def start_server() -> tuple[ThreadingHTTPServer, int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def csv_to_parquet(csv_path: Path, parquet_path: Path) -> None:
    """Write Parquet with DuckDB 1.1.1 through uv (no global install)."""
    sql = (
        f"COPY (SELECT * FROM read_csv('{csv_path.as_posix()}', header=true)) "
        f"TO '{parquet_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    subprocess.run(
        [
            "uv",
            "run",
            "--no-project",
            "--with",
            DUCKDB_PIN,
            "python",
            "-c",
            f"import duckdb; duckdb.sql({sql!r})",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def reference_counts(labels_by_rec: list[set], defs: list, sel: dict) -> dict:
    """Python ground truth: facet-excluded (cross-filter) counts for every label."""
    active = {f: set(v) for f, v in sel.items() if v}
    counts = {f"{f}|{lab}": 0 for f, labs in defs for lab in labs}
    for labs in labels_by_rec:
        failing = [f for f, vals in active.items() if not any((f, v) in labs for v in vals)]
        if len(failing) > 1:
            continue
        for facet, label in labs:
            if not failing or facet == failing[0]:
                counts[f"{facet}|{label}"] += 1
    return counts


def make_states(defs: list, n: int, k: int = 10) -> list[dict]:
    rng = random.Random(n)
    by_name = dict(defs)
    names = [f for f, _ in defs]
    states = []
    for _ in range(k):
        state = {}
        for f in rng.sample(names, rng.randint(1, 3)):
            labs = by_name[f]
            state[f] = rng.sample(labs, rng.randint(1, min(2, len(labs))))
        states.append(state)
    return states


def summarize_transfers(reqs: list) -> dict:
    out = {"local_data": 0, "local_html_js": 0, "cdn_js": 0, "cdn_wasm": 0, "other": 0}
    for req in reqs:
        try:
            size = req.sizes()["responseBodySize"]
        except Exception:  # noqa: BLE001 (request may not have finished)
            continue
        url = req.url
        if url.startswith("http://127.0.0.1"):
            key = "local_data" if url.endswith((".json", ".bin", ".parquet")) else "local_html_js"
        elif "cdn.jsdelivr.net" in url:
            key = "cdn_wasm" if ".wasm" in url else "cdn_js"
        else:
            key = "other"
        out[key] += size
    out["total"] = sum(v for k, v in out.items())
    return out


def run_page(context, url: str, ops: list, states: list, ref: list, reqs: list) -> dict:
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    t_nav = time.perf_counter()
    page.goto(url, wait_until="domcontentloaded", timeout=300000)
    page.wait_for_function(
        "() => window.spike && window.spike.firstRenderMs", timeout=300000, polling=100
    )
    cold_ms = page.evaluate("() => window.spike.firstRenderMs")
    wall_ms = (time.perf_counter() - t_nav) * 1000
    latencies = [page.evaluate("(op) => window.spike.apply(op)", op) for op in ops]
    mismatches = 0
    checked = 0
    for st, expected in zip(states, ref):
        page.evaluate("(s) => window.spike.setState(s)", st)
        got = page.evaluate("() => window.spike.counts()")
        for key, value in expected.items():
            checked += 1
            if got.get(key) != value:
                mismatches += 1
    # Read transfer sizes while the page is still open (sizes() fails after close).
    transfer = summarize_transfers(reqs)
    page.close()
    return {
        "cold_ms": cold_ms,
        "wall_ms": wall_ms,
        "latencies": latencies,
        "checked": checked,
        "mismatches": mismatches,
        "errors": errors[:5],
        "transfer": transfer,
    }


def stats(values: list[float]) -> dict:
    return {"median": round(statistics.median(values), 2), "max": round(max(values), 2)}


def raw_and_gzip(files: list[Path]) -> dict:
    raw = sum(f.stat().st_size for f in files)
    gz = sum(len(gzip.compress(f.read_bytes(), 9)) for f in files)
    return {"raw": raw, "gzip": gz}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sizes", nargs="+", type=int, default=[30000, 100000])
    ap.add_argument("--runs", type=int, default=5)
    args = ap.parse_args()

    WWW.mkdir(parents=True, exist_ok=True)
    for name in ("bitmask.html", "mosaic.html", "facets.js"):
        shutil.copy(HERE / name, WWW / name)
    server, port = start_server()
    base = f"http://127.0.0.1:{port}"
    results: dict = {
        "versions": {"mosaic": MOSAIC_PIN, "released": MOSAIC_RELEASED, "duckdb_py": DUCKDB_PIN}
    }
    defs = bb.facet_defs()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        results["chromium"] = browser.version
        for n in args.sizes:
            ddir = WWW / "data" / f"n{n}"
            t0 = time.perf_counter()
            records, facets = bb.write_dataset(n, ddir)
            labels_by_rec = [set(bb.record_labels(r)) for r in records]
            csv_path, pq_path = ddir / "works.csv", ddir / "works.parquet"
            csv_to_parquet(csv_path, pq_path)
            csv_path.unlink()
            build_s = time.perf_counter() - t0
            states = make_states(defs, n)
            ref = [reference_counts(labels_by_rec, defs, st) for st in states]

            bit_files = [ddir / f for f in ("works_index.json", "facets.json", "facets.bin")]
            res: dict = {
                "bitmask_payload": raw_and_gzip(bit_files),
                "parquet_bytes": pq_path.stat().st_size,
                "build_s": round(build_s, 1),
            }
            for kind in ("bitmask", "mosaic"):
                url = f"{base}/{kind}.html?n={n}"
                runs = []
                for r in range(args.runs):
                    ctx = browser.new_context()
                    reqs: list = []
                    ctx.on("requestfinished", lambda req, acc=reqs: acc.append(req))
                    run = run_page(ctx, url, OPS, states, ref, reqs)
                    ctx.close()
                    runs.append(run)
                    print(
                        f"[{kind} n={n} run {r + 1}] cold={run['cold_ms']:.0f} ms "
                        f"mismatches={run['mismatches']}/{run['checked']} "
                        f"errors={len(run['errors'])}",
                        flush=True,
                    )
                res[kind] = runs
            results[str(n)] = res
        browser.close()
    server.shutdown()

    report = summarize(results, args.sizes, args.runs)
    out = SCRATCH / "results.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(report)
    print(f"results saved to {out}")
    return 0


def _med(values) -> float:
    return statistics.median(list(values))


def summarize(results: dict, sizes: list[int], runs: int) -> str:
    lines = []
    for n in sizes:
        res = results[str(n)]
        bm, mo = res["bitmask"], res["mosaic"]
        lat_bm = [x for run in bm for x in run["latencies"]]
        lat_mo = [x for run in mo for x in run["latencies"]]
        p = res["bitmask_payload"]
        bm_local = _med(r["transfer"]["local_data"] + r["transfer"]["local_html_js"] for r in bm)
        lines.append(f"== N={n} (runs={runs}, budget facet <= {BUDGET_MS[n]} ms)")
        lines.append(
            f"bitmask payload raw={p['raw']} gz={p['gzip']} | transferred median={bm_local:.0f}"
        )
        mo_total = _med(r["transfer"]["total"] for r in mo)
        mo_js = _med(r["transfer"]["cdn_js"] for r in mo)
        mo_wasm = _med(r["transfer"]["cdn_wasm"] for r in mo)
        lines.append(
            f"mosaic transferred median={mo_total:.0f} (parquet={res['parquet_bytes']}, "
            f"cdn_js={mo_js:.0f}, cdn_wasm={mo_wasm:.0f})"
        )
        lines.append(
            f"cold start ms bitmask={stats([r['cold_ms'] for r in bm])} "
            f"mosaic={stats([r['cold_ms'] for r in mo])}"
        )
        lines.append(f"update ms bitmask={stats(lat_bm)} mosaic={stats(lat_mo)}")
        mm_bm = sum(r["mismatches"] for r in bm)
        mm_mo = sum(r["mismatches"] for r in mo)
        checked = sum(r["checked"] for r in bm)
        lines.append(
            f"correctness vs Python: bitmask mismatches={mm_bm}/{checked}, "
            f"mosaic mismatches={mm_mo}/{checked}"
        )
    return chr(10).join(lines)


if __name__ == "__main__":
    sys.exit(main())
