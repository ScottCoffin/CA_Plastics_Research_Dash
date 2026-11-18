"""Validate the Add-on A3 plan registration: spec file, BQ task order, decisions and questions."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "docs" / "add_on_spec_3.md"
TODO_PATH = ROOT / ".agent" / "TODO.md"
QUESTIONS_PATH = ROOT / ".agent" / "QUESTIONS.md"
DECISIONS_PATH = ROOT / ".agent" / "DECISIONS.md"

# BQ task IDs in the order they first appear in TODO.md (Add-on A3 plan).
BQ_TASK_IDS = (
    "BQ-0 BQ-S8 BQ-R1 BQ-G0 BQ-G7 BQ-G1 BQ-G2 BQ-S1 BQ-S9 BQ-S4 "
    "BQ-V.0 BQ-V.2 BQ-G3 BQ-G4 BQ-G5 BQ-G6 BQ-S5 BQ-R2 BQ-2.1 BQ-2.2 "
    "BQ-2.3 BQ-2.4 BQ-3.1 BQ-3.2 BQ-3.3 BQ-3.4 BQ-V.1 BQ-S2 BQ-S6 BQ-S3 "
    "BQ-S7 BQ-1.1 BQ-1.2 BQ-1.3 BQ-1.4 BQ-1.5 BQ-1.6 BQ-S9b BQ-S10 BQ-4.1 "
    "BQ-4.2 BQ-4.3 BQ-4.4 BQ-V.3 BQ-V.4 BQ-V.5 BQ-V.6 BQ-6.1 BQ-6.2 BQ-6.3 "
    "BQ-6.4 BQ-9"
).split()
DECISION_IDS = [f"A3-D{n}" for n in range(25)]
CONSTRAINT_IDS = [f"A3-C{n}" for n in range(1, 15)]
QUESTION_IDS = [f"A3-Q{n}" for n in range(1, 16)]
DECISION_HEADINGS = (
    "## ADR-A3-INTEGRATION-2026-11-18",
    "## ADR-GOLD-GLOBAL-2026-11-18",
    "## ADR-A3-PUBMED-2026-11-18",
)

TASK_LINE_PATTERN = re.compile(r"^- \[[ x]\] \*\*(BQ-[^*\s]+)\*\*")
BOLD_BQ_ID_PATTERN = re.compile(r"\*\*(BQ-[^*\s]+)\*\*")
BQ_DEPENDENCY_PATTERN = re.compile(r"BQ-(?:[A-Z]\.?)?\d+(?:\.\d+)?b?")


def fail(message: str) -> None:
    print(f"Add-on A3 scaffold check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    if not path.is_file():
        fail(f"missing plan file: {display(path)}")
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
    todo_text = "\n".join(todo_lines)

    for task_id in BQ_TASK_IDS:
        token = f"**{task_id}**"
        count = todo_text.count(token)
        if count != 1:
            fail(f"TODO.md must contain {token} exactly once, found {count}")

    # Line index where each BQ id first appears as a bold **ID** token.
    definition_line: dict[str, int] = {}
    for index, line in enumerate(todo_lines):
        for match in BOLD_BQ_ID_PATTERN.finditer(line):
            definition_line.setdefault(match.group(1), index)

    for earlier, later in zip(BQ_TASK_IDS, BQ_TASK_IDS[1:]):
        if definition_line[earlier] >= definition_line[later]:
            fail(f"{later} must first appear after {earlier} in TODO.md")

    for index, line in enumerate(todo_lines):
        task = TASK_LINE_PATTERN.match(line)
        if task is None:
            continue
        for dependency in BQ_DEPENDENCY_PATTERN.findall(dependency_text(line)):
            dep_index = definition_line.get(dependency)
            if dep_index is None:
                fail(f"{task.group(1)} depends on {dependency}, which is not defined in TODO.md")
            if dep_index >= index:
                fail(f"{task.group(1)} depends on {dependency}, which is not earlier in TODO.md")


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


def main() -> int:
    check_spec()
    check_todo()
    check_decisions()
    check_questions()
    print("Add-on A3 scaffold check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
