"""Validate the Add-on A4 plan registration: spec, CG task order, decisions, questions, ignores."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "docs" / "BFFP.md"
TODO_PATH = ROOT / ".agent" / "TODO.md"
QUESTIONS_PATH = ROOT / ".agent" / "QUESTIONS.md"
DECISIONS_PATH = ROOT / ".agent" / "DECISIONS.md"
GITIGNORE_PATH = ROOT / ".gitignore"

# CG task IDs in the order they must appear in TODO.md (Add-on A4 plan).
CG_TASK_IDS = (
    "CG-0 CG-1 CG-2 CG-3 CG-4 CG-5 CG-6 CG-7 CG-8 CG-9 CG-10 CG-11 CG-12 CG-12b "
    "CG-13 CG-14 CG-15 CG-16 CG-X1 CG-X2"
).split()
DECISION_IDS = [f"A4-D{n}" for n in range(25)]
CONSTRAINT_IDS = [f"A4-C{n}" for n in range(1, 12)]
QUESTION_IDS = [f"A4-Q{n}" for n in range(1, 10)]
DECISION_HEADINGS = ("## ADR-A4-INTEGRATION-2026-11-26",)
GITIGNORE_LINES = (
    "data/raw/bffp/",
    "data/interim/bffp/",
    "**/roster_manifest.local.json",
    "**/roster_quarantine.csv",
)

TASK_LINE_PATTERN = re.compile(r"^- \[[ x]\] \*\*(CG-[^*\s]+)\*\*")
# Whole IDs only: CG-1 must not match inside CG-10, and CG-12b / CG-X1 are matched whole.
CG_DEPENDENCY_PATTERN = re.compile(r"CG-(?:X\d+|\d+b?)\b")


def fail(message: str) -> None:
    print(f"Add-on A4 scaffold check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    if not path.is_file():
        fail(f"missing file: {display(path)}")
    return path.read_text(encoding="utf-8")


def dependency_text(line: str) -> str:
    """Return the text after 'Depends:' up to the next '. ' (or the end of the line)."""
    start = line.find("Depends:")
    if start == -1:
        return ""
    clause = line[start + len("Depends:") :]
    end = clause.find(". ")
    return clause if end == -1 else clause[:end]


def check_spec() -> None:
    if not SPEC_PATH.is_file():
        fail(f"missing plan file: {display(SPEC_PATH)}")


def check_todo() -> None:
    todo_lines = read_text(TODO_PATH).splitlines()

    task_ids: list[str] = []
    task_line: dict[str, int] = {}
    for index, line in enumerate(todo_lines):
        match = TASK_LINE_PATTERN.match(line)
        if match is None:
            continue
        task_ids.append(match.group(1))
        task_line.setdefault(match.group(1), index)

    for task_id in CG_TASK_IDS:
        count = task_ids.count(task_id)
        if count != 1:
            fail(f"TODO.md must have exactly one task line for {task_id}, found {count}")

    if task_ids != list(CG_TASK_IDS):
        fail("CG task lines in TODO.md are out of order or include unexpected IDs")

    for index, line in enumerate(todo_lines):
        match = TASK_LINE_PATTERN.match(line)
        if match is None:
            continue
        for dependency in CG_DEPENDENCY_PATTERN.findall(dependency_text(line)):
            dep_index = task_line.get(dependency)
            if dep_index is None:
                fail(f"{match.group(1)} depends on {dependency}, which is not defined in TODO.md")
            if dep_index >= index:
                fail(f"{match.group(1)} depends on {dependency}, which is not earlier in TODO.md")


def check_decisions() -> None:
    decision_lines = read_text(DECISIONS_PATH).splitlines()
    for decision_id in DECISION_IDS + CONSTRAINT_IDS:
        prefix = f"| {decision_id} |"
        count = sum(line.startswith(prefix) for line in decision_lines)
        if count != 1:
            fail(f"DECISIONS.md must have one row starting {prefix!r}, found {count}")
    for heading in DECISION_HEADINGS:
        # ADR headings carry a title or status after the ID, e.g. "## ID: title".
        if not any(
            line == heading or line.startswith((f"{heading}:", f"{heading} "))
            for line in decision_lines
        ):
            fail(f"DECISIONS.md must contain the heading {heading!r}")


def check_questions() -> None:
    question_lines = read_text(QUESTIONS_PATH).splitlines()
    for question_id in QUESTION_IDS:
        prefix = f"| {question_id} |"
        count = sum(line.startswith(prefix) for line in question_lines)
        if count != 1:
            fail(f"QUESTIONS.md must have one row starting {prefix!r}, found {count}")


def check_gitignore() -> None:
    ignore_lines = {line.strip() for line in read_text(GITIGNORE_PATH).splitlines()}
    for entry in GITIGNORE_LINES:
        if entry not in ignore_lines:
            fail(f".gitignore must contain the line {entry!r}")


def main() -> int:
    check_spec()
    check_todo()
    check_decisions()
    check_questions()
    check_gitignore()
    print("Add-on A4 scaffold check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
