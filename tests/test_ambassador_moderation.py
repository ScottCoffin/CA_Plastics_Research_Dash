"""Static checks for the moderation page (AMB-1 front end slice 2c).

The pure helpers run in node (tests/framework_ambassador_moderation_runtime.mjs). These checks
read the sources as text: the page is unlisted and noindex, every Worker call goes through the
shared api() helper with credentials, submitted text is never written as HTML, links carry
rel="noopener noreferrer nofollow", and no window.confirm is used. Nothing here calls the network.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMPONENTS = SRC / "components"
PAGE = SRC / "ambassador_moderation.md"
MODULE = COMPONENTS / "ambassador_moderation.js"
STYLES = COMPONENTS / "ambassador_moderation.css"
SIGNUP = COMPONENTS / "ambassador_signup.js"
RUNTIME_CHECK = ROOT / "tests" / "framework_ambassador_moderation_runtime.mjs"
CHECK_AT5 = ROOT / "scripts" / "check_at5.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_page_is_unlisted_and_noindex() -> None:
    page = _text(PAGE)
    assert 'head: \'<meta name="robots" content="noindex, nofollow">\'' in page
    assert "title: Moderation" in page
    config = _text(ROOT / "framework" / "observablehq.config.js")
    assert "ambassador_moderation" not in config
    assert "/moderation" not in config


def test_page_mounts_the_module_and_loads_its_styles() -> None:
    page = _text(PAGE)
    assert 'from "./components/ambassador_moderation.js"' in page
    assert 'mountModeration(document.querySelector(".am"))' in page
    assert 'href="./components/ambassador_moderation.css"' in page
    assert 'id="mod-body"' in page and 'id="mod-status"' in page
    assert STYLES.is_file()


def test_page_is_registered_as_a_global_page_for_the_shell_check() -> None:
    assert '"ambassador_moderation.md"' in _text(CHECK_AT5)


def test_every_worker_call_uses_the_shared_api_helper() -> None:
    source = _text(MODULE)
    assert 'import {REGION_NAMES, api, apiUrl, errorText} from "./ambassador_signup.js";' in source
    assert "fetch(" not in source
    assert "XMLHttpRequest" not in source
    paths = re.findall(r'api\((?:"|`)([^"`]+)', source)
    assert set(paths) >= {"/me", "/moderation/decide", "/moderation/leads", "/moderation/suspend"}
    assert "queueUrl(" in source
    assert 'apiUrl("/orcid/start")' in source
    # The helper sends credentials and is exported (one keyword added to ambassador_signup.js).
    assert "export async function api(" in _text(SIGNUP)
    assert 'credentials: "include"' in _text(SIGNUP)


def test_submitted_text_is_never_written_as_html() -> None:
    source = _text(MODULE)
    assert "innerHTML" not in source.replace("body.innerHTML = SHELL;", "")
    assert "insertAdjacentHTML" not in source
    assert "outerHTML" not in source
    # The only innerHTML is the static shell (no request data is in it).
    assert source.count("body.innerHTML = SHELL;") == 1
    assert "document.write" not in source
    for forbidden in ("eval(", "new Function("):
        assert forbidden not in source


def test_submitted_links_are_safe_and_open_in_a_new_tab() -> None:
    source = _text(MODULE)
    assert 'rel: "noopener noreferrer nofollow"' in source
    assert 'target: "_blank"' in source
    assert re.search(r"URL_RE = /\^https\?", source), "only http(s) values become links"


def test_no_native_confirm_dialogs() -> None:
    for path in (MODULE, PAGE):
        text = _text(path)
        assert "window.confirm" not in text
        assert not re.search(r"(?<![\w.])confirm\(", text)
        assert "window.alert" not in text


def test_focus_moves_to_the_item_heading_and_targets_are_large_enough() -> None:
    source = _text(MODULE)
    assert 'tabindex: "-1"' in source
    assert "view.heading.focus()" in source
    styles = _text(STYLES)
    assert "min-height: 44px" in styles


def test_visible_copy_uses_the_required_sentences() -> None:
    source = _text(MODULE)
    assert "This page is for the owner and region leads." in source
    assert "Sign in with ORCID to moderate" in source
    assert "You cannot decide your own submission." in source
    assert "Estimated time: about" in source


def test_styles_use_tokens_only() -> None:
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", _text(STYLES))
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", _text(PAGE).split("<style", 1)[0])


def test_runtime_checks_pass_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_ambassador_moderation_runtime.mjs")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
