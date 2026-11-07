"""Measure the committed S3.1 fixture in headless Chromium for S3.6."""

from __future__ import annotations

import json
import statistics
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TRIAL_TERMS = ["Alice", "Bob", "Carol", "Dana"] * 5
EXPECTED_NAMES = {
    "Alice": "Alice California",
    "Bob": "Bob Oregon",
    "Carol": "Carol Davis",
    "Dana": "Dana Field",
}
COLD_LOAD_TRIALS = 5


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        pass


def main() -> None:
    handler = partial(QuietHandler, directory=str(ROOT / "site"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = None
            initial_trials = []
            contexts = []
            for _ in range(COLD_LOAD_TRIALS):
                context = browser.new_context()
                contexts.append(context)
                page = context.new_page()
                page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded")
                page.locator("#load-status").filter(has_text="Data loaded").wait_for()
                page.locator("#expert-rows .virtual-row").first.wait_for()
                initial = page.evaluate(
                    """() => {
                      const fcp = performance.getEntriesByType('paint')
                        .find((entry) => entry.name === 'first-contentful-paint');
                      return {
                        fcp_ms: fcp ? fcp.startTime : null,
                        meaningful_ms: performance.now(),
                        status: document.querySelector('#load-status').textContent,
                        visible_expert_rows: document.querySelectorAll(
                          '#expert-rows .virtual-row'
                        ).length,
                        expert_count: document.querySelector('#expert-count').textContent
                      };
                    }"""
                )
                if initial["status"] != "Data loaded" or initial["visible_expert_rows"] < 1:
                    raise RuntimeError(f"Fixture did not render: {initial}")
                initial_trials.append(initial)

            results = []
            for term in TRIAL_TERMS:
                result = page.evaluate(
                    """({ term, expectedName }) => new Promise((resolve) => {
                      const input = document.querySelector('#expert-search');
                      const start = performance.now();
                      input.value = term;
                      input.dispatchEvent(new Event('input', { bubbles: true }));
                      requestAnimationFrame(() => resolve({
                        ms: performance.now() - start,
                        term,
                        rows: document.querySelectorAll('#expert-rows .virtual-row').length,
                        count: document.querySelector('#expert-count').textContent,
                        name: document.querySelector('#expert-rows .expert-link')?.textContent,
                        expected_name: expectedName
                      }));
                    })""",
                    {"term": term, "expectedName": EXPECTED_NAMES[term]},
                )
                results.append(result)
            for context in contexts:
                context.close()

            durations = [result["ms"] for result in results]
            fcp_values = [result["fcp_ms"] for result in initial_trials]
            meaningful_values = [result["meaningful_ms"] for result in initial_trials]
            print(
                json.dumps(
                    {
                        "browser": browser.version,
                        "fixture_authors": 4,
                        "cold_load_trials": COLD_LOAD_TRIALS,
                        "fcp_ms_median": statistics.median(fcp_values),
                        "fcp_ms_max": max(fcp_values),
                        "meaningful_ms_median": statistics.median(meaningful_values),
                        "meaningful_ms_max": max(meaningful_values),
                        "meaningful_render_definition": "Data loaded status and an expert row",
                        "filter_trials": len(results),
                        "filter_ms_median": statistics.median(durations),
                        "filter_ms_max": max(durations),
                        "filter_trials_with_expected_single_match": sum(
                            result["rows"] == 1
                            and result["count"] == "1 expert shown"
                            and result["name"] == result["expected_name"]
                            for result in results
                        ),
                    },
                    indent=2,
                )
            )
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
