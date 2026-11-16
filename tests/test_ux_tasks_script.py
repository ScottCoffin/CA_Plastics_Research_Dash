"""Light tests for scripts/ux_tasks.py: import without Playwright, registry, args, failures."""

from __future__ import annotations

import importlib
import inspect
import re
import sys
from pathlib import Path

import pytest

from scripts import ux_tasks


class _FakeDisclosure:
    def __init__(self, open_: bool) -> None:
        self.open = open_
        self.clicks = 0

    def get_attribute(self, name: str) -> str | None:
        assert name == "open"
        return "" if self.open else None

    def click(self) -> None:
        self.clicks += 1
        self.open = not self.open


class _FakeSummary:
    def __init__(self, disclosure: _FakeDisclosure) -> None:
        self.disclosure = disclosure

    def locator(self, selector: str) -> _FakeDisclosure:
        assert selector == "xpath=.."
        return self.disclosure

    def click(self) -> None:
        self.disclosure.click()


class _FakeDisclosurePage:
    def __init__(self, summary: _FakeSummary) -> None:
        self.summary = summary

    def get_by_text(self, pattern: re.Pattern[str]) -> _FakeSummary:
        assert pattern.fullmatch("More filters (7)")
        return self.summary


class _FakeDisclosureRun:
    def __init__(self, open_: bool) -> None:
        self.disclosure = _FakeDisclosure(open_)
        self.page = _FakeDisclosurePage(_FakeSummary(self.disclosure))
        self.clicked: list[str] = []

    def click(self, locator: _FakeSummary, label: str) -> None:
        self.clicked.append(label)
        locator.click()


def test_module_imports_without_playwright(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    module = importlib.reload(ux_tasks)
    assert callable(module.main)


def test_six_tasks_are_registered_in_order() -> None:
    ids = [task_id for task_id, _ in ux_tasks.TASKS]
    assert len(ids) == 6
    assert len(set(ids)) == 6
    assert [task_id.split("_", 1)[0] for task_id in ids] == ["1", "2", "3", "4", "5", "6"]
    assert all(callable(fn) for _, fn in ux_tasks.TASKS)


@pytest.mark.parametrize(("initially_open", "expected_clicks"), [(False, 1), (True, 0)])
def test_open_expert_more_filters_only_toggles_when_collapsed(
    initially_open: bool, expected_clicks: int
) -> None:
    run = _FakeDisclosureRun(initially_open)

    ux_tasks.open_expert_more_filters(run)  # type: ignore[arg-type]

    assert run.disclosure.open is True
    assert run.disclosure.clicks == expected_clicks
    assert run.clicked == (["More filters (7)"] if expected_clicks else [])


def test_expert_visitor_tasks_open_secondary_filters_before_using_them() -> None:
    profile = inspect.getsource(ux_tasks.task_overview_profile)
    export = inspect.getsource(ux_tasks.task_experts_export)

    assert profile.index("open_expert_more_filters(run)") < profile.index(
        'run.select(run.page.get_by_label("CA basis")'
    )
    assert export.index("open_expert_more_filters(run)") < export.index(
        'run.fill(run.page.get_by_label("From year")'
    )


def test_argparse_defaults() -> None:
    args = ux_tasks.parse_args([])
    assert args.base == "http://127.0.0.1:8780/CA_Plastics_Research_Dash/"
    assert args.out == "scratch/ux18"
    assert args.headed is False


def test_argparse_overrides() -> None:
    args = ux_tasks.parse_args(["--base", "http://example.test/x/", "--out", "o", "--headed"])
    assert args.base == "http://example.test/x/"
    assert args.out == "o"
    assert args.headed is True


def test_run_check_raises_on_false_condition() -> None:
    run = ux_tasks.Run("t", None, "http://x/", Path("."))
    run.check(True, "unused")
    with pytest.raises(AssertionError, match="boom"):
        run.check(False, "boom")


def test_run_step_enforces_deadline() -> None:
    run = ux_tasks.Run("t", None, "http://x/", Path("."))
    run.deadline = 0.0
    with pytest.raises(TimeoutError):
        run.step("too late")


class _FakePage:
    def set_default_timeout(self, _ms: int) -> None:
        return None

    def screenshot(self, path: str) -> None:
        Path(path).write_bytes(b"")

    def wait_for_load_state(self, _state: str) -> None:
        return None

    def goto(self, _url: str) -> None:
        return None


class _FakeContext:
    def new_page(self) -> _FakePage:
        return _FakePage()

    def close(self) -> None:
        return None


class _FakeBrowser:
    def new_context(self, **_kwargs: object) -> _FakeContext:
        return _FakeContext()


def test_run_task_captures_failure_and_keeps_steps(tmp_path: Path) -> None:
    def failing(run: ux_tasks.Run) -> None:
        run.goto("app/")
        run.last_element = "Missing control"
        run.check(False, "control not found")

    result = ux_tasks.run_task(_FakeBrowser(), "http://x/", tmp_path, "9_fake", failing)
    assert result["task"] == "9_fake"
    assert result["passed"] is False
    assert result["steps"] == ["open app/"]
    assert result["last_element"] == "Missing control"
    assert "AssertionError" in result["note"]
    assert (tmp_path / "9_fake.png").exists()


def test_run_task_passes_and_records_note(tmp_path: Path) -> None:
    def passing(run: ux_tasks.Run) -> None:
        run.step("look")
        run.note = "finding"

    result = ux_tasks.run_task(_FakeBrowser(), "http://x/", tmp_path, "8_fake", passing)
    assert result == {
        "task": "8_fake",
        "passed": True,
        "steps": ["look"],
        "last_element": "",
        "note": "finding",
    }
