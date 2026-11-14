from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CHECK = ROOT / "tests" / "framework_institution_runtime.mjs"
COMPONENTS = ROOT / "framework" / "src" / "components"
PAGE = ROOT / "framework" / "src" / "institution.md"
CONFIG = ROOT / "framework" / "observablehq.config.js"
INSTITUTIONS_JS = COMPONENTS / "institutions.js"
DETAIL_JS = COMPONENTS / "institution.js"
MODEL_JS = COMPONENTS / "institution_model.js"

# Internal project vocabulary must not reach visible text (scripts/check_public_text.py).
INTERNAL_IDS = re.compile(r"\b(?:S\d+\.\d+|EM-\d+|UX-\d+|TODO)\b")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_page_is_top_level_and_not_in_the_sidebar() -> None:
    assert PAGE.is_file(), "institution.md must sit at the top level of framework/src/"
    assert not re.search(r'path:\s*"/institution"', _read(CONFIG)), "reached from links only"


def test_page_markup_and_mount() -> None:
    markup, _, script = _read(PAGE).partition("```js")
    assert 'id="institution-root"' in markup
    assert "${" not in markup, "no template literal in the HTML block"
    assert "mountInstitution();" in script
    assert "./components/institution.css" in markup
    assert "./components/ev_table.css" in markup
    component = _read(DETAIL_JS)
    # Publications reuse the shared works table (imported read-only).
    assert 'import {mountWorksTable} from "./ev_table.js";' in component
    model = _read(MODEL_JS)
    assert "ev_table" not in model, "the model stays DOM-free"
    assert "document." not in model, "the model stays DOM-free"


def test_institution_links_point_at_the_detail_page() -> None:
    text = _read(INSTITUTIONS_JS)
    assert "function institutionPageUrl" in text
    assert 'institutionPageUrl(institutionId, "publications")' in text
    assert 'institutionPageUrl(institution.inst_id, "experts")' in text
    assert "openInstitution(name.dataset.institutionId)" in text
    assert "sem.html" not in text, "classic links moved to the detail page"
    # The View experts buttons keep the Experts page.
    assert "openInstitutionExperts(button.dataset.institutionId)" in text
    assert "openInstitutionExperts(expertButton.dataset.institutionId)" in text


def test_copy_has_no_internal_ids() -> None:
    for path in [PAGE, DETAIL_JS, MODEL_JS]:
        lines = _read(path).splitlines()
        if path.suffix == ".js":
            lines = [line for line in lines if not line.lstrip().startswith("//")]
        hits = [line for line in lines if INTERNAL_IDS.search(line)]
        assert not hits, f"{path.name} shows internal vocabulary: {hits[:2]}"


def test_framework_institution_runtime_regressions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for tests/framework_institution_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    # Shared helpers are gitignored copies of site/assets; create them as `npm run build` does.
    sync = ROOT / "framework" / "scripts" / "sync_shared.mjs"
    subprocess.run([node, str(sync)], cwd=ROOT, check=True, capture_output=True)
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)
