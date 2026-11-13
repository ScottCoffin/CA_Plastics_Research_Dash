"""Naive-user Playwright checks for six UX-18 tasks on the Framework build (/app/).

Each task navigates by visible text, role and label only. A task records its steps, the last
element it touched, and a finding. A failed control lookup is itself a finding.

    py -3.14 scripts/ux_tasks.py --base http://127.0.0.1:8780/CA_Plastics_Research_Dash/ \
        [--out scratch/ux18] [--headed]

Writes <out>/<task>.png per task and <out>/results.json. Exit code 1 if any task fails.
Playwright is imported inside main() so that importing this module needs no browser stack.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

TASK_TIMEOUT_S = 20
VIEWPORT = {"width": 1280, "height": 900}


class Run:
    """Per-task recorder: steps, last element touched, finding note and deadline."""

    def __init__(self, task_id: str, page: Any, base: str, out: Path) -> None:
        self.task_id = task_id
        self.page = page
        self.base = base
        self.out = out
        self.steps: list[str] = []
        self.last_element = ""
        self.note = ""
        self.deadline = time.monotonic() + TASK_TIMEOUT_S

    def step(self, text: str) -> None:
        if time.monotonic() > self.deadline:
            raise TimeoutError(f"task exceeded {TASK_TIMEOUT_S} s")
        self.steps.append(text)

    def goto(self, path: str) -> None:
        self.step(f"open {path}")
        self.page.goto(self.base + path)
        self.page.wait_for_load_state("networkidle")

    def click(self, locator: Any, label: str) -> None:
        self.last_element = label
        self.step(f"click '{label}'")
        locator.click()

    def fill(self, locator: Any, label: str, value: str) -> None:
        self.last_element = label
        self.step(f"fill '{label}' with '{value}'")
        locator.fill(value)

    def select(self, locator: Any, label: str, option: str) -> None:
        self.last_element = label
        self.step(f"select '{option}' in '{label}'")
        locator.select_option(label=option)

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)


def task_overview_profile(run: Run) -> None:
    """1. Overview -> CA-led author -> profile."""
    run.goto("app/")
    run.check(
        run.page.get_by_role("heading", name="CA Plastics Research Atlas").is_visible(),
        "no Overview heading",
    )
    run.last_element = "Overview page text"
    run.step("look for a CA-led author list on the Overview")
    on_overview = run.page.get_by_text("CA-led").count()
    run.click(
        run.page.get_by_role("link", name="Find a California researcher"),
        "Find a California researcher",
    )
    run.select(run.page.get_by_label("CA basis"), "CA basis", "CA-led")
    first = run.page.get_by_role("list", name="Experts").get_by_role("button").first
    run.click(first, "first expert name")
    drawer = run.page.get_by_role("dialog")
    run.check(drawer.is_visible(), "profile drawer did not open")
    run.step("read profile heading")
    lead = (
        "Overview lists CA-led authors." if on_overview else "Overview has no CA-led author list."
    )
    run.note = f"{lead} Reached a profile via Experts ({drawer.locator('h2').first.inner_text()})."


def task_experts_export(run: Run) -> None:
    """2. Experts: topic + year range, export CSV, row count matches shown count."""
    run.goto("app/experts")
    tag = run.page.get_by_label("Domain or matrix tag")
    run.select(tag, "Domain or matrix tag", tag.locator("option").nth(1).inner_text())
    run.fill(run.page.get_by_label("From year"), "From year", "2015")
    run.fill(run.page.get_by_label("To year"), "To year", "2024")
    run.page.wait_for_timeout(300)
    shown_text = run.page.get_by_text(re.compile(r"^\d+ experts? shown$")).inner_text()
    shown = int(re.match(r"\d+", shown_text).group())
    run.step(f"read count '{shown_text}'")
    run.last_element = "Export filtered CSV"
    with run.page.expect_download() as info:
        run.click(run.page.get_by_role("button", name="Export filtered CSV"), "Export filtered CSV")
    path = run.out / "experts.csv"
    info.value.save_as(path)
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    data_rows = len(rows) - 1
    run.note = f"Shown {shown}, CSV data rows {data_rows}, header has {len(rows[0])} columns."
    run.check(data_rows == shown, f"shown {shown} != CSV rows {data_rows}")


def task_institution_tier(run: Run) -> None:
    """3. Institutions: explain from the page why two institutions share a tier."""
    run.goto("app/institutions")
    shown_notes = [
        n for n in run.page.get_by_text("cannot be reliably ordered").all() if n.is_visible()
    ]
    run.check(bool(shown_notes), "no visible tier explanation text")
    explanation = shown_notes[0].inner_text()
    run.step("read tier explanation")
    groups = run.page.locator("details.tier-group").filter(has_text=re.compile(r"\d+ institutions"))
    target = None
    for index in range(groups.count()):
        group = groups.nth(index)
        if re.search(r"·\s*([2-9]|\d{2,}) institutions", group.locator("summary").inner_text()):
            target = group
            break
    run.check(target is not None, "no tier holds two or more institutions")
    summary = target.locator("summary")
    if target.get_attribute("open") is None:  # tiers 1-2 start open; clicking would close them
        run.click(summary, summary.inner_text())
    buttons = [button.inner_text() for button in target.get_by_role("button").all()]
    names = [text for text in buttons if text and not text.startswith("Tier")][:2]
    run.check(len(names) == 2, "fewer than two named institutions in the tier")
    run.step(f"read names {names}")
    run.last_element = names[1]
    run.note = (
        f"Page says: '{explanation[:160]}'. Tier group '{summary.inner_text()}' "
        f"contains {names[0]} and {names[1]}."
    )


def task_monitoring_csv(run: Run) -> None:
    """4. Monitoring: filter to one matrix and download the CSV."""
    run.goto("app/monitoring")
    matrix = run.page.get_by_label("Sample matrix")
    option = matrix.locator("option").nth(1).inner_text()
    run.select(matrix, "Sample matrix", option)
    details = run.page.get_by_text("Sample observations", exact=True)
    if not run.page.get_by_role("button", name="Download observations (CSV)").is_visible():
        run.click(details, "Sample observations")
    button = run.page.get_by_role("button", name="Download observations (CSV)")
    with run.page.expect_download() as info:
        run.click(button, "Download observations (CSV)")
    path = run.out / "monitoring.csv"
    info.value.save_as(path)
    text = path.read_text(encoding="utf-8")
    rows = list(csv.reader(line for line in text.splitlines() if not line.startswith("#")))
    data = rows[1:]
    matching = sum(any(option in cell for cell in row) for row in data)
    run.note = f"Matrix '{option}': CSV has {len(data)} data rows, {matching} mention the matrix."
    run.check(len(data) > 0, "CSV has no data rows")
    run.check(matching == len(data), f"{len(data) - matching} rows lack the selected matrix")


def task_funding_basis(run: Run) -> None:
    """5. Funding: California-led awards, then the amount basis for NIH awards."""
    run.goto("app/funding")
    run.select(run.page.get_by_label("Led from California"), "Led from California", "Yes")
    agency = run.page.get_by_label("Funder agency")
    labels = agency.locator("option").all_inner_texts()
    nih = next((text for text in labels if re.search(r"NIH|Institutes of Health", text)), None)
    run.check(nih is not None, "no NIH option under Funder agency")
    run.select(agency, "Funder agency", nih)
    run.page.wait_for_timeout(300)
    table = run.page.locator("table").filter(has_text="Per-source subtotals")
    row = table.get_by_role("row").filter(has_text="NIH RePORTER")
    run.check(row.count() > 0, "no NIH RePORTER row in the per-source subtotals")
    cells = row.first.get_by_role("cell").all_inner_texts()
    run.last_element = "NIH RePORTER subtotal row"
    run.step("read NIH RePORTER subtotal row")
    run.note = f"NIH RePORTER amount basis: '{cells[-1]}' (reported amount {cells[-2]})."


def task_index_to_app(run: Run) -> None:
    """6. From index.html, reach /app/."""
    run.goto("index.html")
    link = run.page.get_by_role("link", name=re.compile("newer version of this atlas", re.I))
    run.check(link.count() > 0, "no link to the Framework app on index.html")
    run.check(link.first.is_visible(), "app link on index.html is not visible")
    run.click(link.first, "A newer version of this atlas is available.")
    run.page.wait_for_load_state("networkidle")
    run.check(run.page.url.rstrip("/").endswith("/app"), f"landed on {run.page.url}")
    run.check(
        run.page.get_by_role("heading", name="CA Plastics Research Atlas").is_visible(),
        "no app heading",
    )
    run.note = f"Reached {run.page.url} via the index.html banner link."


TASKS: list[tuple[str, Callable[[Run], None]]] = [
    ("1_overview_profile", task_overview_profile),
    ("2_experts_export", task_experts_export),
    ("3_institution_tier", task_institution_tier),
    ("4_monitoring_csv", task_monitoring_csv),
    ("5_funding_basis", task_funding_basis),
    ("6_index_to_app", task_index_to_app),
]


def run_task(browser: Any, base: str, out: Path, task_id: str, fn: Callable[[Run], None]) -> dict:
    """Run one task in a fresh context so a failure cannot leak state into the next task."""
    context = browser.new_context(viewport=VIEWPORT, accept_downloads=True)
    page = context.new_page()
    page.set_default_timeout(TASK_TIMEOUT_S * 1000)
    run = Run(task_id, page, base, out)
    passed = False
    try:
        fn(run)
        passed = True
    except Exception as exc:  # one failed task must not stop the others
        run.note = (
            run.note + " " if run.note else ""
        ) + f"FAIL {type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
    try:
        page.screenshot(path=str(out / f"{task_id}.png"))
    except Exception:
        pass
    context.close()
    return {
        "task": task_id,
        "passed": passed,
        "steps": run.steps,
        "last_element": run.last_element,
        "note": run.note,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", default="http://127.0.0.1:8780/CA_Plastics_Research_Dash/")
    parser.add_argument("--out", default="scratch/ux18")
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    from playwright.sync_api import sync_playwright

    base = args.base.rstrip("/") + "/"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        for task_id, fn in TASKS:
            result = run_task(browser, base, out, task_id, fn)
            results.append(result)
            status = "PASS" if result["passed"] else "FAIL"
            print(
                f"{task_id}: {status} steps={len(result['steps'])} "
                f"last={result['last_element'] or '-'} | {result['note'][:200]}"
            )
        browser.close()
    (out / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
