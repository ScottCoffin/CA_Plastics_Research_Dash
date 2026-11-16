"""VD-10 display labels: coverage of the vocabularies, the Node runtime, and the call sites."""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "framework" / "src" / "components"
LABELS = COMPONENTS / "shared" / "labels.js"
RUNTIME_CHECK = ROOT / "tests" / "framework_labels_runtime.mjs"
INSTITUTIONS_PY = ROOT / "src" / "atlas" / "ingest" / "institutions.py"
NORMALIZE_PY = ROOT / "src" / "atlas" / "ingest" / "normalize.py"
QUERIES_V3 = ROOT / "config" / "queries_v3.yml"
SYNC = ROOT / "framework" / "scripts" / "sync_shared.mjs"

# Pages that show a type, sector or work type as text and therefore import the shared labels.
CALL_SITES = [
    "network_model.js",
    "evidence.js",
    "experts.js",
    "institutions.js",
    "institution.js",
    "funding.js",
]

# Raw slugs must not be interpolated as displayed text (value= attributes stay raw).
RAW_TEXT_PATTERNS = {
    "institutions.js": ["escapeHtml(institution.atlas_type", ">${escapeHtml(type)}</button>"],
    "institution.js": ["escapeHtml(institution.atlas_type"],
    "funding.js": ["escapeHtml(row.institution_type)"],
    "experts.js": [">${escapeHtml(type)}</option>"],
}

# The F10 slugs named in the VD-10 brief: institution types and work types.
F10_INSTITUTION_SLUGS = [
    "community-college",
    "intergovernmental-organization",
    "local-agency",
    "nonprofit/NGO",
]
F10_WORK_SLUGS = ["book-chapter", "conference-abstract"]


def _module_assignment(path: Path, name: str) -> ast.expr:
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    raise AssertionError(f"{name} not found in {path.name}")


def _atlas_types() -> set[str]:
    value = _module_assignment(INSTITUTIONS_PY, "ATLAS_TYPES")
    assert isinstance(value, ast.Call) and isinstance(value.args[0], ast.Set)
    return {elt.value for elt in value.args[0].elts if isinstance(elt, ast.Constant)}


def _code_work_types() -> set[str]:
    rank = _module_assignment(NORMALIZE_PY, "_TYPE_RANK")
    assert isinstance(rank, ast.Dict)
    types = {key.value for key in rank.keys if isinstance(key, ast.Constant)}
    excluded = yaml.safe_load(QUERIES_V3.read_text(encoding="utf-8"))["exclude_types"]
    types.update(excluded)
    types.update(F10_WORK_SLUGS)
    types.add("unknown")  # bundle bucket for works without a type
    return types


def _label_keys(export_name: str) -> set[str]:
    text = LABELS.read_text(encoding="utf-8")
    block = re.search(rf"export const {export_name} = Object\.freeze\(\{{(.*?)\n\}}\);", text, re.S)
    assert block, f"{export_name} missing from labels.js"
    keys = set()
    for line in block.group(1).splitlines():
        match = re.match(r'\s*(?:"([^"]+)"|([A-Za-z_]\w*))\s*:', line)
        if match:
            keys.add(match.group(1) or match.group(2))
    return keys


def test_institution_labels_cover_atlas_types() -> None:
    keys = _label_keys("INSTITUTION_TYPE_LABELS")
    missing = sorted((_atlas_types() | {"other"}) - keys)
    assert not missing, f"no display label for: {missing}"
    assert set(F10_INSTITUTION_SLUGS) <= keys


def test_work_labels_cover_code_work_types() -> None:
    keys = _label_keys("WORK_TYPE_LABELS")
    missing = sorted(_code_work_types() - keys)
    assert not missing, f"no display label for work types: {missing}"
    assert set(F10_WORK_SLUGS) <= keys


def test_labels_module_has_no_dependencies() -> None:
    text = LABELS.read_text(encoding="utf-8")
    assert not re.search(r"^\s*import\b", text, re.M)
    assert "document." not in text and "window." not in text


def test_labels_runtime_checks() -> None:
    node = shutil.which("node")
    if node is None:
        raise AssertionError(
            "Node.js is required for tests/framework_labels_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)


def test_call_sites_import_shared_labels() -> None:
    for name in CALL_SITES:
        text = (COMPONENTS / name).read_text(encoding="utf-8")
        assert 'from "./shared/labels.js";' in text, name
    for name, patterns in RAW_TEXT_PATTERNS.items():
        text = (COMPONENTS / name).read_text(encoding="utf-8")
        for pattern in patterns:
            assert pattern not in text, f"{name} still shows a raw slug: {pattern}"


def test_labels_file_is_not_copied_by_sync() -> None:
    # labels.js is a hand-maintained module in the gitignored shared folder; sync must not touch it.
    assert "labels.js" not in SYNC.read_text(encoding="utf-8")
