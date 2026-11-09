"""Validate the offline Add-on A1 acceptance scaffold."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_DIR = ROOT / "tests" / "acceptance" / "add_on_a1"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "add_on_a1"
EXPECTED_STUBS = {
    "test_query_regression.py",
    "test_stale_cache.py",
    "test_landing_first_load.py",
    "test_facet_latency.py",
    "test_parquet_compatibility.py",
    "test_weights.py",
    "test_no_abstracts.py",
    "test_r_gate.py",
    "test_release.py",
    "test_licence_audit.py",
    "test_base_spec_regression.py",
}
EXPECTED_PLACEHOLDERS = {
    Path("query/.gitkeep"),
    Path("analytics/.gitkeep"),
    Path("serving/.gitkeep"),
    Path("release/.gitkeep"),
}
MAX_FIXTURE_ROWS = 200


def fail(message: str) -> None:
    print(f"Add-on A1 scaffold check failed: {message}", file=sys.stderr)
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
    if actual != EXPECTED_STUBS or unexpected_entries:
        missing = sorted(EXPECTED_STUBS - actual)
        unexpected = sorted(actual - EXPECTED_STUBS)
        fail(
            "acceptance stub set differs; "
            f"missing={missing}, unexpected={unexpected}, "
            f"unexpected entries={unexpected_entries}"
        )

    for name in sorted(EXPECTED_STUBS):
        path = ACCEPTANCE_DIR / name
        if path.stat().st_size != 0:
            fail(f"acceptance stub must be empty and contain no network-capable code: {name}")


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

    if not git_ignores("release/a1-release.zip"):
        fail("release/ output is not ignored by Git")
    if not git_ignores("tests/fixtures/add_on_a1/local.large.parquet"):
        fail("a .large.parquet file is not ignored by Git")
    slim_fixture = "tests/fixtures/add_on_a1/slim_fixture.parquet"
    if git_ignores(slim_fixture):
        fail("slim Parquet fixtures must remain visible to Git")

    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "tests/fixtures"],
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
        if is_slim_parquet:
            if git_ignores(relative_path):
                fail(f"committed slim fixture is ignored by Git: {relative_path}")


def main() -> int:
    check_stubs()
    check_fixtures()
    check_ignore_rules()
    print("Add-on A1 scaffold check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
