"""Offline acceptance checks for S10.4 (dependency pins, Dependabot, notifications, rotation notes).

Makes no network calls. Each check takes a repository root so tests can run it on temp copies.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

LOCK = Path("requirements/lock.txt")
PYPROJECT = Path("pyproject.toml")
DEPENDABOT = Path(".github/dependabot.yml")
SECURITY = Path("docs/SECURITY.md")
WORKFLOWS = Path(".github/workflows")
CONSTRAINT = "-c requirements/lock.txt"
REQUIRED_HEADINGS = (
    "## Dependency policy",
    "## Failure notification",
    "## Secret rotation",
    "## Incident response",
)
DEPENDABOT_ECOSYSTEMS = {"pip", "github-actions"}

_PROJECT_INSTALL = re.compile(r"pip install\b.*(\s-e\b|\s\.\[|\s\.(\s|$))")


def normalize(name: str) -> str:
    """Return a PEP 503 normalized distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def pyproject_names(root: Path) -> set[str]:
    """Return normalized names of runtime and dev dependencies from pyproject.toml."""
    data = tomllib.loads((root / PYPROJECT).read_text(encoding="utf-8"))
    project = data["project"]
    specs = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        specs.extend(group)
    names = set()
    for spec in specs:
        match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
        if not match:
            raise ValueError(f"cannot parse dependency: {spec!r}")
        names.add(normalize(match.group(1)))
    return names


def lock_pins(root: Path) -> set[str]:
    """Return normalized names pinned with '==' in requirements/lock.txt."""
    pins = set()
    for line in (root / LOCK).read_text(encoding="utf-8").splitlines():
        match = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)==", line)
        if match:
            pins.add(normalize(match.group(1)))
    return pins


def check_lock(root: Path) -> list[str]:
    """Every pyproject dependency must appear as an exact pin in the lock file."""
    if not (root / LOCK).is_file():
        return [f"missing lock file: {LOCK}"]
    missing = sorted(pyproject_names(root) - lock_pins(root))
    return [f"{LOCK} has no exact pin for: {name}" for name in missing]


def installs_project(line: str) -> bool:
    return bool(_PROJECT_INSTALL.search(line))


def check_workflows(root: Path) -> list[str]:
    """Every workflow line that pip-installs the project must use the lock constraint."""
    errors = []
    for path in sorted((root / WORKFLOWS).glob("*.yml")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "pip install" in line and installs_project(line) and CONSTRAINT not in line:
                errors.append(
                    f"{path.relative_to(root)}:{lineno} installs the project without '{CONSTRAINT}'"
                )
    return errors


def check_dependabot(root: Path) -> list[str]:
    """dependabot.yml must be version 2 and cover exactly the pip and github-actions ecosystems."""
    path = root / DEPENDABOT
    if not path.is_file():
        return [f"missing {DEPENDABOT}"]
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors = []
    if not isinstance(data, dict) or str(data.get("version")) != "2":
        errors.append(f"{DEPENDABOT} must set version: 2")
        return errors
    updates = data.get("updates") or []
    ecosystems = {u.get("package-ecosystem") for u in updates if isinstance(u, dict)}
    if ecosystems != DEPENDABOT_ECOSYSTEMS:
        errors.append(
            f"{DEPENDABOT} ecosystems {sorted(ecosystems)} != {sorted(DEPENDABOT_ECOSYSTEMS)}"
        )
    for update in updates:
        if isinstance(update, dict) and (update.get("schedule") or {}).get("interval") != "weekly":
            errors.append(f"{DEPENDABOT} ecosystem {update.get('package-ecosystem')} is not weekly")
    return errors


def check_security_doc(root: Path) -> list[str]:
    """docs/SECURITY.md must exist and contain the required section headings."""
    path = root / SECURITY
    if not path.is_file():
        return [f"missing {SECURITY}"]
    lines = {line.strip() for line in path.read_text(encoding="utf-8").splitlines()}
    return [f"{SECURITY} missing heading: {h}" for h in REQUIRED_HEADINGS if h not in lines]


def run_all(root: Path = ROOT) -> list[str]:
    return [
        *check_lock(root),
        *check_workflows(root),
        *check_dependabot(root),
        *check_security_doc(root),
    ]


def main() -> int:
    errors = run_all(ROOT)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("S10.4 check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
