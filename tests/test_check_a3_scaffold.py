"""Offline tests for scripts/check_a3_scaffold.py (Add-on A3 plan registration)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "check_a3_scaffold", ROOT / "scripts" / "check_a3_scaffold.py"
)
assert _SPEC and _SPEC.loader
check_a3_scaffold = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_a3_scaffold)

# Real plan files, captured before any test monkeypatches the module constants.
REAL_PATHS = {
    name: getattr(check_a3_scaffold, name)
    for name in ("TODO_PATH", "QUESTIONS_PATH", "DECISIONS_PATH")
}


@pytest.fixture
def plan_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Point the script at copies of the real plan files under tmp_path."""
    spec = tmp_path / "add_on_spec_3.md"
    spec.write_text("# Add-on A3\n", encoding="utf-8")
    monkeypatch.setattr(check_a3_scaffold, "SPEC_PATH", spec)
    copies: dict[str, Path] = {}
    for name, source in REAL_PATHS.items():
        copy = tmp_path / source.name
        copy.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        monkeypatch.setattr(check_a3_scaffold, name, copy)
        copies[name] = copy
    return copies


def _expect_failure(capsys: pytest.CaptureFixture[str], fragment: str) -> None:
    with pytest.raises(SystemExit) as excinfo:
        check_a3_scaffold.main()
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Add-on A3 scaffold check failed" in err
    assert fragment in err


def _replace_on_line(path: Path, line_prefix: str, old: str, new: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    matches = [index for index, line in enumerate(lines) if line.startswith(line_prefix)]
    assert len(matches) == 1
    assert old in lines[matches[0]]
    lines[matches[0]] = lines[matches[0]].replace(old, new, 1)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _drop_line(path: Path, line_prefix: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not line.startswith(line_prefix)]
    assert len(kept) == len(lines) - 1
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def test_real_plan_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert check_a3_scaffold.main() == 0
    assert "Add-on A3 scaffold check passed." in capsys.readouterr().out


def test_duplicated_bq_id_fails(
    plan_copy: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    todo = plan_copy["TODO_PATH"]
    todo.write_text(
        todo.read_text(encoding="utf-8") + "\n- [ ] **BQ-0** Duplicate row.\n", encoding="utf-8"
    )
    _expect_failure(capsys, "**BQ-0** exactly once, found 2")


def test_dependency_listed_after_dependent_fails(
    plan_copy: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    # BQ-G1 depends on BQ-0; pointing it at BQ-4.4 (defined much later) must fail.
    _replace_on_line(
        plan_copy["TODO_PATH"], "- [ ] **BQ-G1**", "Depends: BQ-0.", "Depends: BQ-4.4."
    )
    _expect_failure(capsys, "BQ-G1 depends on BQ-4.4, which is not earlier")


def test_missing_questions_row_fails(
    plan_copy: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _drop_line(plan_copy["QUESTIONS_PATH"], "| A3-Q7 |")
    _expect_failure(capsys, "| A3-Q7 |")
