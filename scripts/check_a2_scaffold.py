"""Validate the offline Add-on A2 acceptance scaffold and plan registration."""

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_DIR = ROOT / "tests" / "acceptance" / "add_on_a2"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "add_on_a2"
TODO_PATH = ROOT / ".agent" / "TODO.md"
QUESTIONS_PATH = ROOT / ".agent" / "QUESTIONS.md"
DECISIONS_PATH = ROOT / ".agent" / "DECISIONS.md"

# Stub file name -> (EAT id, owning EM task ids), per Add-on A2 section 9.
EXPECTED_STUBS = {
    "test_eat01_fixture_cells_non_additive.py": ("EAT-1", ("EM-8",)),
    "test_eat02_roster_rows_sourced.py": ("EAT-2", ("EM-1",)),
    "test_eat03_concordance.py": ("EAT-3", ("EM-11",)),
    "test_eat04_flow_matches_at10.py": ("EAT-4", ("EM-6",)),
    "test_eat05_counts_only_duckdb.py": ("EAT-5", ("EM-5", "EM-8")),
    "test_eat06_human_label_override.py": ("EAT-6", ("EM-4",)),
    "test_eat07_link_checker.py": ("EAT-7", ("EM-16",)),
    "test_eat08_no_minderoo.py": ("EAT-8", ("EM-14", "EM-16")),
    "test_eat09_no_linkonly_ingest.py": ("EAT-9", ("EM-16",)),
    "test_eat10_ledger_roster.py": ("EAT-10", ("EM-1",)),
    "test_eat11_group_headers_once.py": ("EAT-11", ("EM-11",)),
    "test_eat12_regional_layer.py": ("EAT-12", ("EM-2",)),
}
# Stubs that EM-1 replaced with real offline tests. Only these may hold test functions.
IMPLEMENTED_STUBS = {
    "test_eat02_roster_rows_sourced.py",
    "test_eat10_ledger_roster.py",
    "test_eat12_regional_layer.py",
}
EXPECTED_PLACEHOLDERS = {
    Path("ledger/.gitkeep"),
    Path("taxonomy/.gitkeep"),
    Path("regions/.gitkeep"),
    Path("evidence_map/.gitkeep"),
    Path("linkouts/.gitkeep"),
}
MAX_FIXTURE_ROWS = 200
EM_TASK_IDS = range(1, 19)
QUESTION_IDS = [f"A2-D{n}" for n in range(1, 12)] + [f"A2-INT-{n}" for n in range(1, 4)]
DECISION_IDS = [f"A2-C{n}" for n in range(1, 16)]


def fail(message: str) -> None:
    print(f"Add-on A2 scaffold check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def git_ignores(relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", "--", relative_path],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        fail(f"git check-ignore failed for {relative_path}: {result.stderr.strip()}")
    return result.returncode == 0


def read_text(path: Path) -> str:
    if not path.is_file():
        fail(f"missing plan file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def is_placeholder_stub(path: Path) -> bool:
    """Accept only a docstring, `import pytest`, and one module-level pytest.skip."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    skip_calls = 0
    for index, node in enumerate(tree.body):
        if index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                continue
        if isinstance(node, ast.Import) and [alias.name for alias in node.names] == ["pytest"]:
            continue
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "pytest"
            and node.value.func.attr == "skip"
            and any(
                keyword.arg == "allow_module_level"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.value.keywords
            )
        ):
            skip_calls += 1
            continue
        return False
    return skip_calls == 1


def has_test_function(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        isinstance(node, ast.FunctionDef) and node.name.startswith("test_") for node in tree.body
    )


def check_stubs() -> None:
    if not ACCEPTANCE_DIR.is_dir():
        fail(f"missing acceptance directory: {ACCEPTANCE_DIR.relative_to(ROOT)}")

    entries = list(ACCEPTANCE_DIR.iterdir())
    actual = {path.name for path in entries if path.is_file()}
    unexpected_entries = sorted(
        path.name
        for path in entries
        if not path.is_file()
        and not (path.is_dir() and not path.is_symlink() and path.name == "__pycache__")
    )
    if actual != set(EXPECTED_STUBS) or unexpected_entries:
        missing = sorted(set(EXPECTED_STUBS) - actual)
        unexpected = sorted(actual - set(EXPECTED_STUBS))
        fail(
            "acceptance stub set differs; "
            f"missing={missing}, unexpected={unexpected}, "
            f"unexpected entries={unexpected_entries}"
        )

    for name, (eat_id, owners) in sorted(EXPECTED_STUBS.items()):
        path = ACCEPTANCE_DIR / name
        if name in IMPLEMENTED_STUBS:
            if not has_test_function(path):
                fail(f"implemented acceptance test must define a test function: {name}")
        elif not is_placeholder_stub(path):
            fail(f"acceptance stub must be a docstring-only placeholder that skips: {name}")
        docstring = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
        if not re.search(rf"\b{re.escape(eat_id)}\b", docstring):
            fail(f"acceptance stub docstring does not name {eat_id}: {name}")
        for owner in owners:
            if not re.search(rf"\b{re.escape(owner)}\b", docstring):
                fail(f"acceptance stub docstring does not name owning task {owner}: {name}")


def check_fixtures() -> None:
    if not FIXTURE_DIR.is_dir():
        fail(f"missing fixture directory: {FIXTURE_DIR.relative_to(ROOT)}")

    for relative_path in sorted(EXPECTED_PLACEHOLDERS):
        path = FIXTURE_DIR / relative_path
        if not path.is_file():
            fail(f"missing fixture placeholder: {path.relative_to(ROOT)}")
        if path.stat().st_size != 0:
            fail(f"fixture placeholder must have zero rows: {path.relative_to(ROOT)}")

    for path in sorted(item for item in FIXTURE_DIR.rglob("*") if item.is_file()):
        row_count = len(path.read_bytes().splitlines())
        if row_count > MAX_FIXTURE_ROWS:
            fail(
                f"fixture exceeds {MAX_FIXTURE_ROWS} newline-delimited rows: "
                f"{path.relative_to(ROOT)} has {row_count}"
            )


def check_ignore_rules() -> None:
    ignore_path = ROOT / ".gitignore"
    lines = ignore_path.read_text(encoding="utf-8").splitlines()
    rules = [line.strip() for line in lines]
    if "release/" not in rules:
        fail(".gitignore must ignore release/ output")
    if "*.large.parquet" not in rules:
        fail(".gitignore must ignore only large Parquet files by the .large.parquet suffix")

    rule_index = rules.index("*.large.parquet")
    if rule_index == 0:
        fail("the large Parquet ignore rule needs a suffix explanation comment")
    comment = rules[rule_index - 1].lower()
    has_suffix_comment = ".large.parquet" in comment and "suffix" in comment
    if not comment.startswith("#") or not has_suffix_comment:
        fail("the large Parquet ignore rule needs a comment explaining its suffix")

    if not git_ignores("release/a2-release.zip"):
        fail("release/ output is not ignored by Git")
    if not git_ignores("tests/fixtures/add_on_a2/local.large.parquet"):
        fail("a .large.parquet file is not ignored by Git")
    slim_fixture = "tests/fixtures/add_on_a2/slim_fixture.parquet"
    if git_ignores(slim_fixture):
        fail("slim Parquet fixtures must remain visible to Git")

    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "tests/fixtures/add_on_a2"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if tracked.returncode != 0:
        fail("git ls-files could not inspect tracked fixtures")
    for raw_path in tracked.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative_path = raw_path.decode("utf-8", errors="surrogateescape")
        lower_path = relative_path.lower()
        is_slim_parquet = lower_path.endswith(".parquet") and not lower_path.endswith(
            ".large.parquet"
        )
        if is_slim_parquet and git_ignores(relative_path):
            fail(f"committed slim fixture is ignored by Git: {relative_path}")


def check_plan() -> None:
    todo_lines = read_text(TODO_PATH).splitlines()
    todo_text = "\n".join(todo_lines)

    for number in EM_TASK_IDS:
        count = todo_text.count(f"**EM-{number}**")
        if count != 1:
            fail(f"TODO.md must contain **EM-{number}** exactly once, found {count}")

    # Line index of each EM task definition, used for dependency-order checks.
    definition_line: dict[int, int] = {}
    for index, line in enumerate(todo_lines):
        match = re.match(r"^- \[.\] \*\*EM-(\d+)\*\*", line)
        if match:
            definition_line[int(match.group(1))] = index

    for number, index in sorted(definition_line.items(), key=lambda item: item[1]):
        depends = re.search(r"Depends:(.*?)(?:\. DoD|$)", todo_lines[index])
        if depends is None:
            continue
        for dependency in re.findall(r"\bEM-(\d+)\b", depends.group(1)):
            dep_number = int(dependency)
            dep_index = definition_line.get(dep_number)
            if dep_index is None:
                fail(f"EM-{number} depends on EM-{dep_number}, which is not defined in TODO.md")
            if dep_index >= index:
                fail(f"EM-{number} depends on EM-{dep_number}, which is not earlier in TODO.md")

    questions_text = read_text(QUESTIONS_PATH)
    question_lines = questions_text.splitlines()
    for question_id in QUESTION_IDS:
        prefix = f"| {question_id} |"
        count = sum(line.startswith(prefix) for line in question_lines)
        if count != 1:
            fail(f"QUESTIONS.md must have one row starting {prefix!r}, found {count}")

    decision_lines = read_text(DECISIONS_PATH).splitlines()
    for decision_id in DECISION_IDS:
        prefix = f"| {decision_id} |"
        count = sum(line.startswith(prefix) for line in decision_lines)
        if count != 1:
            fail(f"DECISIONS.md must have one row starting {prefix!r}, found {count}")


def main() -> int:
    check_stubs()
    check_fixtures()
    check_ignore_rules()
    check_plan()
    print("Add-on A2 scaffold check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
