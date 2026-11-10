"""SPK-3 shell bench (Observable Framework vs single-file) plus SPK-2(a).

Run from the repo root:  py -3.14 spikes/spk3_shell/run_bench.py
Needs: framework/node_modules (npm install done), `uv` on PATH (DuckDB 1.1.1
writer), Playwright Chromium. Generated data, builds, logs and results go to
scratch/spk3/ (gitignored). Everything is served from localhost; no network.
"""

from __future__ import annotations

import argparse
import gzip
import http.server
import json
import shutil
import statistics
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / "scratch" / "spk3"
DATA = SCRATCH / "data"
PARQUET_OUT = SCRATCH / "parquet"
FW = HERE / "framework"
DIST = FW / "dist"
SINGLE = HERE / "single"
DATASETS = ["syn30k", "syn100k", "fixture"]
MIB = 1024 * 1024
BUDGET_LANDING_GZ = 3 * MIB
BUDGET_TTI_MS = 2000
BUDGET_LAT_MS = {"syn30k": 50, "syn100k": 150}
LOAD_RUNS = 3
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".wasm": "application/wasm",
    ".svg": "image/svg+xml",
    ".parquet": "application/octet-stream",
}
# Six facets, one virtualized table, one bar chart, one map placeholder.
# Each step changes state; latency is measured from the input event to the
# next render (window-visible #status data-seq increment).
TOGGLES = [
    {"f": "domain", "op": "flip", "i": 0},
    {"f": "domain", "op": "flip", "i": 1},
    {"f": "facet", "op": "flip", "i": 2},
    {"f": "yf", "op": "set", "v": "2010"},
    {"f": "domain", "op": "flip", "i": 0},
    {"f": "inst", "op": "set", "v": "academic"},
    {"f": "ca", "op": "set", "v": "led"},
    {"f": "oa", "op": "flip", "i": 0},
    {"f": "yt", "op": "set", "v": "2020"},
    {"f": "facet", "op": "flip", "i": 0},
    {"f": "domain", "op": "flip", "i": 3},
    {"f": "oa", "op": "flip", "i": 0},
    {"f": "inst", "op": "set", "v": "any"},
    {"f": "ca", "op": "set", "v": "any"},
    {"f": "yf", "op": "set", "v": "2000"},
    {"f": "yt", "op": "set", "v": "2026"},
    {"f": "facet", "op": "flip", "i": 0},
    {"f": "domain", "op": "flip", "i": 1},
    {"f": "facet", "op": "flip", "i": 4},
    {"f": "domain", "op": "flip", "i": 5},
]
ACT_JS = """(act) => new Promise((resolve) => {
  const seqOf = () => {
    const s = document.querySelector("#status");
    return s ? Number(s.dataset.seq) : -1;
  };
  const before = seqOf();
  const wrap = document.querySelector(`[data-facet="${act.f}"]`);
  const el = act.op === "flip"
    ? wrap.querySelectorAll('input[type="checkbox"]')[act.i]
    : wrap.querySelector("input, select");
  const t0 = performance.now();
  if (act.op === "flip") el.checked = !el.checked;
  else el.value = act.v;
  let timer = null;
  const obs = new MutationObserver(check);
  function done(v) { obs.disconnect(); clearTimeout(timer); resolve(v); }
  function check() { if (seqOf() > before) done(performance.now() - t0); }
  obs.observe(document.body, {
    subtree: true, childList: true, attributes: true, characterData: true,
  });
  timer = setTimeout(() => done(-1), 5000);
  el.dispatchEvent(new Event("input", { bubbles: true }));
  check();
})"""

_CACHE: dict[Path, tuple[str, bytes]] = {}


def resolve(url_path: str) -> Path | None:
    path = urllib.parse.unquote(urllib.parse.urlsplit(url_path).path)
    if path.startswith("/single/"):
        base, rel = SINGLE, path[len("/single/") :]
    elif path.startswith("/data/"):
        base, rel = DATA, path[len("/data/") :]
    else:
        base, rel = DIST, path[1:]
    rel = rel or "index.html"
    for cand in (base / rel, base / (rel + ".html"), base / rel / "index.html"):
        if cand.is_file():
            return cand
    return None


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keep bench output quiet
        return

    def do_GET(self):  # noqa: N802 - http.server naming
        self._serve(head_only=False)

    def do_HEAD(self):  # noqa: N802 - DuckDB-wasm sizes attachments with HEAD
        self._serve(head_only=True)

    def _serve(self, head_only: bool) -> None:
        f = resolve(self.path)
        if f is None:
            self.send_error(404)
            return
        ctype = MIME.get(f.suffix, "application/octet-stream")
        rng = self.headers.get("Range", "")
        if rng.startswith("bytes="):
            # Range reads (DuckDB-wasm over FileAttachment) are served raw, unencoded.
            raw = f.read_bytes()
            first, _, last = rng[len("bytes=") :].partition("-")
            start = int(first) if first else max(0, len(raw) - int(last))
            end = min(int(last) if (first and last) else len(raw) - 1, len(raw) - 1)
            body = raw[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(raw)}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
            return
        if f not in _CACHE:
            _CACHE[f] = (ctype, gzip.compress(f.read_bytes(), 6))
        ctype, body = _CACHE[f]
        # Full responses are gzip-encoded so CDP encodedDataLength is the wire size.
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)


def run_logged(cmd, log: Path, cwd: Path, shell: bool = False) -> None:
    with log.open("w", encoding="utf-8") as fh:
        subprocess.run(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, check=True, shell=shell)


def prepare_parquet() -> None:
    """Run the SPK-2 writer (read-only reuse) and stage its fixture for FileAttachment."""
    writer = REPO / "spikes" / "spk2_parquet" / "write_fixture.py"
    run_logged(
        [
            "uv",
            "run",
            "--no-project",
            "--with",
            "duckdb==1.1.1",
            "python",
            str(writer),
            "--out",
            str(PARQUET_OUT),
        ],
        SCRATCH / "parquet_writer.log",
        REPO,
    )
    (FW / "src" / "data").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        PARQUET_OUT / "zstd_default.parquet", FW / "src" / "data" / "zstd_default.parquet"
    )
    shutil.copyfile(PARQUET_OUT / "expected.json", DATA / "parquet_expected.json")


def build_framework() -> float:
    times = []
    for i in range(2):
        t0 = time.perf_counter()
        run_logged("npm run build", SCRATCH / f"build{i}.log", FW, shell=True)
        times.append(time.perf_counter() - t0)
    return statistics.median(times)


def dist_stats() -> dict:
    files = [p for p in DIST.rglob("*") if p.is_file()]
    parquet = [p for p in files if "_file" in p.relative_to(DIST).parts]
    duck = [p for p in files if p not in parquet and "duckdb" in p.name.lower()]
    shell = [p for p in files if p not in parquet and p not in duck]

    def size(ps):
        return sum(p.stat().st_size for p in ps)

    return {
        "dist_bytes": size(files),
        "dist_files": len(files),
        "shell_bytes": size(shell),
        "shell_files": len(shell),
        "duckdb_bytes": size(duck),
        "parquet_attach_bytes": size(parquet),
    }


def loc(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def wire_sizes(req_url: dict, enc: dict) -> dict:
    def total(pred):
        return sum(
            v for k, v in enc.items() if pred(urllib.parse.urlsplit(req_url.get(k, "")).path)
        )

    all_bytes = total(lambda p: True)
    data = total(lambda p: p.startswith("/data/"))
    return {
        "total": all_bytes,
        "data": data,
        "shell": all_bytes - data,
        "wasm": total(lambda p: p.endswith(".wasm")),
    }


def open_page(browser, url: str):
    ctx = browser.new_context()
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    req_url: dict[str, str] = {}
    enc: dict[str, int] = {}
    cdp.on(
        "Network.requestWillBeSent",
        lambda e: req_url.__setitem__(e["requestId"], e["request"]["url"]),
    )
    cdp.on(
        "Network.loadingFinished",
        lambda e: enc.__setitem__(e["requestId"], int(e.get("encodedDataLength", 0))),
    )
    page.goto(url, wait_until="load", timeout=120_000)
    return ctx, page, req_url, enc


def measure_app(browser, app: str, ds: str, port: int) -> dict:
    base = f"http://127.0.0.1:{port}"
    url = f"{base}/single/?ds={ds}" if app == "single" else f"{base}/?ds={ds}"
    ttis, lats, first = [], [], None
    for _ in range(LOAD_RUNS):
        ctx, page, req_url, enc = open_page(browser, url)
        try:
            page.wait_for_function("window.__ttiMs !== undefined", timeout=120_000)
            tti = float(page.evaluate("window.__ttiMs"))
            page.wait_for_load_state("networkidle", timeout=120_000)
            if first is None:
                first = wire_sizes(req_url, enc)
            ttis.append(tti)
            lats.extend(float(page.evaluate(ACT_JS, act)) for act in TOGGLES)
        finally:
            ctx.close()
    ok = [x for x in lats if x >= 0]
    return {
        "app": app,
        "ds": ds,
        "tti_ms": statistics.median(ttis),
        "lat_med_ms": statistics.median(ok) if ok else None,
        "lat_max_ms": max(ok) if ok else None,
        "lat_timeouts": len(lats) - len(ok),
        "lat_n": len(ok),
        **first,
    }


def measure_parquet(browser, port: int) -> dict:
    ctx, page, req_url, enc = open_page(browser, f"http://127.0.0.1:{port}/parquet")
    try:
        page.wait_for_function("window.__spk2Done === true", timeout=120_000)
        page.wait_for_load_state("networkidle", timeout=120_000)
        spk2 = page.evaluate("window.__spk2")
        return {"checks": spk2, "wire": wire_sizes(req_url, enc)}
    finally:
        ctx.close()


def fmt_bytes(b) -> str:
    return f"{b / MIB:.2f}" if b is not None else "n/a"


def verdict(ok: bool | None) -> str:
    return "n/a" if ok is None else ("PASS" if ok else "FAIL")


def report(rows: list[dict], parquet: dict, build_s: float, dist: dict, locs: dict) -> None:
    print(
        "app       dataset  shell_gz_MiB data_gz_MiB total_gz_MiB  wasm_KiB  TTI_ms  "
        "lat_med  lat_max  n_lat  landing  tti  facet"
    )
    for r in rows:
        budget = BUDGET_LAT_MS.get(r["ds"])
        lat_ok = None if budget is None or r["lat_med_ms"] is None else r["lat_med_ms"] <= budget
        landing_ok = r["total"] <= BUDGET_LANDING_GZ
        print(
            f"{r['app']:<9} {r['ds']:<8} {fmt_bytes(r['shell']):>13} {fmt_bytes(r['data']):>13} "
            f"{fmt_bytes(r['total']):>13} {r['wasm'] / 1024:>9.1f} {r['tti_ms']:>7.0f} "
            f"{r['lat_med_ms'] or float('nan'):>8.1f} {r['lat_max_ms'] or float('nan'):>8.1f} "
            f"{r['lat_n']:>5}  {verdict(landing_ok):<7}  "
            f"{verdict(r['tti_ms'] <= BUDGET_TTI_MS):<4} {verdict(lat_ok)}"
        )
    print(f"framework build median: {build_s:.2f} s")
    print(f"dist: {dist}")
    print(f"LOC: {locs}")
    print("SPK-2(a) checks:")
    for k, c in parquet["checks"].items():
        if isinstance(c, dict):
            print(f"  {k}: got={c['got']} want={c['want']} -> {verdict(c['pass'])}")
    print(
        f"  parquet page wire: total={fmt_bytes(parquet['wire']['total'])} MiB "
        f"wasm={parquet['wire']['wasm'] / 1024:.1f} KiB (page session only)"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true", help="reuse existing framework/dist")
    args = parser.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    subprocess.run([sys.executable, str(HERE / "gen_data.py"), "--out", str(DATA)], check=True)
    shutil.copyfile(REPO / "site" / "data" / "index.json", DATA / "fixture.json")
    prepare_parquet()
    build_s = float("nan") if args.skip_build else build_framework()
    dist = dist_stats()
    locs = {
        "single/index.html": loc(SINGLE / "index.html"),
        "framework/src/index.md": loc(FW / "src" / "index.md"),
        "framework/observablehq.config.js": loc(FW / "observablehq.config.js"),
        "framework/src/parquet.md (SPK-2 only)": loc(FW / "src" / "parquet.md"),
    }

    from playwright.sync_api import sync_playwright

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for app in ("single", "framework"):
                for ds in DATASETS:
                    rows.append(measure_app(browser, app, ds, port))
                    print(f"done {app} {ds}", file=sys.stderr)
            parquet = measure_parquet(browser, port)
        finally:
            browser.close()
    srv.shutdown()

    report(rows, parquet, build_s, dist, locs)
    out = {
        "build_median_s": build_s,
        "dist": dist,
        "loc": locs,
        "rows": rows,
        "parquet": {"checks": parquet["checks"], "wire": parquet["wire"]},
    }
    (SCRATCH / "results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
