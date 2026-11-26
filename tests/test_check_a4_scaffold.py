"""Offline tests for scripts/check_a4_scaffold.py (Add-on A4 plan registration)."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "check_a4_scaffold", ROOT / "scripts" / "check_a4_scaffold.py"
)
assert _SPEC and _SPEC.loader
check_a4_scaffold = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_a4_scaffold)

# Real plan files, captured before any test monkeypatches the module constants.
REAL_PATHS = {
    name: getattr(check_a4_scaffold, name)
    for name in ("TODO_PATH", "QUESTIONS_PATH", "DECISIONS_PATH", "GITIGNORE_PATH")
}


@pytest.fixture
def plan_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Point the script at copies of the real plan files under tmp_path."""
    spec = tmp_path / "BFFP.md"
    spec.write_text("# BFFP\n", encoding="utf-8")
    monkeypatch.setattr(check_a4_scaffold, "SPEC_PATH", spec)
    copies: dict[str, Path] = {}
    for name, source in REAL_PATHS.items():
        copy = tmp_path / source.name
        copy.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        monkeypatch.setattr(check_a4_scaffold, name, copy)
        copies[name] = copy
    return copies


def _expect_failure(capsys: pytest.CaptureFixture[str], fragment: str) -> None:
    with pytest.raises(SystemExit) as excinfo:
        check_a4_scaffold.main()
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Add-on A4 scaffold check failed" in err
    assert fragment in err


def _task_index(lines: list[str], task_id: str) -> int:
    pattern = re.compile(rf"^- \[[ x]\] \*\*{re.escape(task_id)}\*\*")
    matches = [index for index, line in enumerate(lines) if pattern.match(line)]
    assert len(matches) == 1
    return matches[0]


def _replace_on_task(path: Path, task_id: str, old: str, new: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    index = _task_index(lines, task_id)
    assert old in lines[index]
    lines[index] = lines[index].replace(old, new, 1)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _drop_line(path: Path, line_prefix: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not line.startswith(line_prefix)]
    assert len(kept) == len(lines) - 1
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def test_real_plan_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_a4_scaffold.main() == 0
    assert "Add-on A4 scaffold check passed." in capsys.readouterr().out


def test_missing_spec_fails(
    plan_copy: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(check_a4_scaffold, "SPEC_PATH", tmp_path / "absent.md")
    _expect_failure(capsys, "missing plan file")


def test_missing_task_id_fails(
    plan_copy: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _drop_line(plan_copy["TODO_PATH"], "- [ ] **CG-5**")
    _expect_failure(capsys, "exactly one task line for CG-5, found 0")


def test_duplicated_task_id_fails(
    plan_copy: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    todo = plan_copy["TODO_PATH"]
    todo.write_text(
        todo.read_text(encoding="utf-8") + "\n- [ ] **CG-0** Duplicate row.\n", encoding="utf-8"
    )
    _expect_failure(capsys, "exactly one task line for CG-0, found 2")


def test_out_of_order_tasks_fail(
    plan_copy: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    todo = plan_copy["TODO_PATH"]
    lines = todo.read_text(encoding="utf-8").splitlines()
    first, second = _task_index(lines, "CG-1"), _task_index(lines, "CG-2")
    lines[first], lines[second] = lines[second], lines[first]
    todo.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _expect_failure(capsys, "out of order")


def test_dependency_listed_after_dependent_fails(
    plan_copy: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    # CG-4 depends on CG-0; pointing it at CG-9 (defined later) must fail.
    _replace_on_task(plan_copy["TODO_PATH"], "CG-4", "Depends: CG-0.", "Depends: CG-9.")
    _expect_failure(capsys, "CG-4 depends on CG-9, which is not earlier")


def test_dependency_on_double_digit_id_is_matched_whole(
    plan_copy: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    # CG-7 depends on CG-6; pointing it at CG-10 must report CG-10 whole, not CG-1 plus a 0.
    _replace_on_task(plan_copy["TODO_PATH"], "CG-7", "Depends: CG-6.", "Depends: CG-10.")
    _expect_failure(capsys, "CG-7 depends on CG-10, which is not earlier")


def test_missing_questions_row_fails(
    plan_copy: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _drop_line(plan_copy["QUESTIONS_PATH"], "| A4-Q7 |")
    _expect_failure(capsys, "| A4-Q7 |")


def test_missing_decision_row_fails(
    plan_copy: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _drop_line(plan_copy["DECISIONS_PATH"], "| A4-C11 |")
    _expect_failure(capsys, "| A4-C11 |")


def test_missing_gitignore_line_fails(
    plan_copy: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _drop_line(plan_copy["GITIGNORE_PATH"], "**/roster_quarantine.csv")
    _expect_failure(capsys, "**/roster_quarantine.csv")
