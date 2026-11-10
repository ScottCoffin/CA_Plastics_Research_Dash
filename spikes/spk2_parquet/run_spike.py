"""SPK-2 orchestrator: write Parquet per DuckDB writer, then read it per DuckDB-Wasm version.

Steps:
1. Run write_fixture.py once per pinned writer version via uv (no project, no global installs).
2. Serve the repo root with a Range-aware static server (DuckDB-Wasm reads Parquet by byte range).
3. Open page.html in headless Chromium once per DuckDB-Wasm version and run every check.
4. Write raw results to scratch/spk2/results.json and print a matrix.

Usage (from the repo root):
    py -3.14 spikes/spk2_parquet/run_spike.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "scratch", "spk2")
WRITER = os.path.join(HERE, "write_fixture.py")
WRITER_VERSIONS = ["1.1.1", "2.0.0"]
WASM_VERSIONS = ["1.29.0", "1.32.0"]
OPTIONS = ["zstd_default", "zstd_rg10k", "snappy"]


class RangeHandler(SimpleHTTPRequestHandler):
    """Static handler that also answers HTTP Range requests with 206 responses."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):  # keep console clean
        pass

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path):
            return super().send_head()
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
        if not m:
            return super().send_head()
        size = os.path.getsize(path)
        if m.group(1):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
        else:
            start = max(0, size - int(m.group(2)))
            end = size - 1
        end = min(end, size - 1)
        length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command != "HEAD":
            with open(path, "rb") as fh:
                fh.seek(start)
                self.wfile.write(fh.read(length))
        return None


def write_fixtures() -> dict:
    """Run the writer for each pinned DuckDB version and return its metadata."""
    meta = {}
    for ver in WRITER_VERSIONS:
        out_dir = os.path.join(OUT, f"duckdb-{ver}")
        shutil.rmtree(out_dir, ignore_errors=True)
        cmd = [
            "uv",
            "run",
            "--no-project",
            "--with",
            f"duckdb=={ver}",
            "python",
            WRITER,
            "--out",
            out_dir,
        ]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            raise SystemExit(f"writer duckdb=={ver} failed:\n{proc.stderr[-2000:]}")
        with open(os.path.join(out_dir, "expected.json"), encoding="utf-8") as fh:
            meta[ver] = json.load(fh)
        print(f"wrote duckdb {ver}: {proc.stdout.strip()}")
    return meta


def run_browser(files: list[dict], meta: dict, port: int) -> dict:
    """Open the page once per Wasm version and run every file through it."""
    results = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for wasm in WASM_VERSIONS:
            page = browser.new_page()
            console = []
            page.on(
                "console", lambda msg: console.append(msg.text) if msg.type == "error" else None
            )
            page.goto(f"http://127.0.0.1:{port}/spikes/spk2_parquet/page.html?ver={wasm}")
            page.wait_for_function("window.ready === true", timeout=180_000)
            status = page.evaluate("window.status_")
            entry = {"status": status, "files": [], "console_errors": console}
            if status.get("error") is None:
                for f in files:
                    expected = meta[f["writer"]]["expected"]
                    url = f"http://127.0.0.1:{port}/scratch/spk2/duckdb-{f['writer']}/{f['opt']}.parquet"
                    res = page.evaluate(
                        "([url, name, expected]) => "
                        "window.runFile(window.state, url, name, expected)",
                        [url, f"{f['writer']}_{f['opt']}.parquet", expected],
                    )
                    res.update({"writer": f["writer"], "opt": f["opt"]})
                    entry["files"].append(res)
            results[wasm] = entry
            page.close()
        browser.close()
    return results


def print_matrix(results: dict, files: list[dict], meta: dict) -> None:
    print("\nFile sizes (bytes) and writer-side expected count:")
    for f in files:
        size = meta[f["writer"]]["file_sizes_bytes"][f["opt"]]
        print(f"  duckdb {f['writer']:6s} {f['opt']:12s} {size:>10d}")
    print("\nPass/fail per wasm version (checks passed / total; load ms = total per file):")
    for wasm, entry in results.items():
        st = entry["status"]
        if st.get("error"):
            print(f"  wasm {wasm}: INIT FAILED: {st['error']}")
            continue
        print(f"  wasm {wasm} (engine {st.get('duckdbVersion')}, init {st.get('initMs')} ms)")
        for r in entry["files"]:
            passed = sum(1 for c in r["checks"] if c["pass"])
            total = len(r["checks"])
            failed = [c for c in r["checks"] if not c["pass"]]
            line = (
                f"    {r['writer']:6s} {r['opt']:12s} {passed:2d}/{total}  "
                f"load {r['load_ms_total']} ms"
            )
            print(line)
            for c in failed:
                detail = (
                    c["error"] if c["error"] else f"got={c['got']!r} expected={c['expected']!r}"
                )
                print(f"      FAIL {c['check']}: {detail}")
        if entry["console_errors"]:
            print(
                f"    console errors: {len(entry['console_errors'])} "
                f"(first: {entry['console_errors'][0][:200]})"
            )


def main() -> None:
    t0 = time.time()
    meta = write_fixtures()
    files = [{"writer": w, "opt": o} for w in WRITER_VERSIONS for o in OPTIONS]

    server = ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        results = run_browser(files, meta, port)
    finally:
        server.shutdown()

    os.makedirs(OUT, exist_ok=True)
    raw = {"writers": meta, "wasm": results}
    with open(os.path.join(OUT, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(raw, fh, ensure_ascii=False, indent=2)
    print_matrix(results, files, meta)
    print(f"\nRaw results: {os.path.join(OUT, 'results.json')} ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    sys.exit(main())
