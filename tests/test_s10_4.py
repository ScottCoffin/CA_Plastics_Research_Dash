"""Tests for the S10.4 offline checker (scripts/check_s10_4.py)."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("check_s10_4", REPO / "scripts" / "check_s10_4.py")
checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(checker)

FILES = [
    "pyproject.toml",
    "requirements/lock.txt",
    ".github/dependabot.yml",
    "docs/SECURITY.md",
]


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    """Copy the files the checker reads into a temp root so tests can break them safely."""
    for rel in FILES:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, target)
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    for path in (REPO / ".github" / "workflows").glob("*.yml"):
        shutil.copy2(path, workflows / path.name)
    return tmp_path


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"expected one match for {old!r} in {path.name}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_real_repo_passes_all_checks() -> None:
    assert checker.run_all(REPO) == []


def test_main_reports_pass(capsys: pytest.CaptureFixture[str]) -> None:
    assert checker.main() == 0
    assert "S10.4 check passed." in capsys.readouterr().out


def test_normalize_handles_pep503_names() -> None:
    assert checker.normalize("PyYAML") == "pyyaml"
    assert checker.normalize("pdfminer.six") == "pdfminer-six"
    assert checker.normalize("pre_commit") == "pre-commit"


def test_pyproject_names_include_dev_extras() -> None:
    names = checker.pyproject_names(REPO)
    assert {"pyyaml", "pdfminer-six", "pre-commit", "pytest", "ruff"} <= names


def test_lock_missing_pin_is_reported(repo_copy: Path) -> None:
    lock = repo_copy / "requirements" / "lock.txt"
    kept = [
        line
        for line in lock.read_text(encoding="utf-8").splitlines()
        if not line.lower().startswith("pyyaml==")
    ]
    lock.write_text("\n".join(kept) + "\n", encoding="utf-8")
    errors = checker.check_lock(repo_copy)
    assert any("pyyaml" in e for e in errors)


def test_missing_lock_file_is_reported(repo_copy: Path) -> None:
    (repo_copy / "requirements" / "lock.txt").unlink()
    assert checker.check_lock(repo_copy)


def test_workflow_without_constraint_is_reported(repo_copy: Path) -> None:
    ci = repo_copy / ".github" / "workflows" / "ci.yml"
    _replace(ci, "pip install -c requirements/lock.txt -e", "pip install -e")
    errors = checker.check_workflows(repo_copy)
    assert len(errors) == 1
    assert "ci.yml" in errors[0]


def test_build_deploy_pyarrow_line_is_not_a_project_install(repo_copy: Path) -> None:
    assert checker.check_workflows(repo_copy) == []


def test_dependabot_wrong_version_is_reported(repo_copy: Path) -> None:
    path = repo_copy / ".github" / "dependabot.yml"
    _replace(path, "version: 2", "version: 1")
    assert checker.check_dependabot(repo_copy)


def test_dependabot_extra_npm_ecosystem_is_reported(repo_copy: Path) -> None:
    path = repo_copy / ".github" / "dependabot.yml"
    path.write_text(
        path.read_text(encoding="utf-8")
        + '  - package-ecosystem: "npm"\n    directory: "/"\n'
        + '    schedule:\n      interval: "weekly"\n',
        encoding="utf-8",
    )
    assert any("ecosystems" in e for e in checker.check_dependabot(repo_copy))


def test_dependabot_missing_file_is_reported(repo_copy: Path) -> None:
    (repo_copy / ".github" / "dependabot.yml").unlink()
    assert checker.check_dependabot(repo_copy)


def test_security_doc_missing_heading_is_reported(repo_copy: Path) -> None:
    path = repo_copy / "docs" / "SECURITY.md"
    _replace(path, "## Incident response", "## Response")
    errors = checker.check_security_doc(repo_copy)
    assert len(errors) == 1
    assert "missing heading: ## Incident response" in errors[0]


def test_main_fails_on_broken_copy(repo_copy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo_copy / "docs" / "SECURITY.md").unlink()
    monkeypatch.setattr(checker, "ROOT", repo_copy)
    assert checker.main() == 1
