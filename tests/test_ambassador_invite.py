"""Static checks for the co-author invite screen (AMB-1 front end slice 3c).

The pure helpers run in node (tests/framework_ambassador_invite_runtime.mjs).
These checks read the sources as text: the only Worker route is POST /invitations,
no email field or address prompt exists, nothing is kept in browser storage,
index.json is fetched only inside the mount flow, and the styles use tokens and
stay scoped. Nothing here calls the network.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "framework" / "src" / "components"
INVITE = COMPONENTS / "ambassador_invite.js"
STYLES = COMPONENTS / "ambassador_invite.css"
RUNTIME_CHECK = ROOT / "tests" / "framework_ambassador_invite_runtime.mjs"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(text: str) -> str:
    """Source text without line and block comments (rough, for user-visible text checks)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def test_invite_module_exports_helpers_and_mount() -> None:
    invite = _text(INVITE)
    for name in (
        "export function coAuthors(",
        "export function eligibleRegions(",
        "export function coAuthorRows(",
        "export function eligibilityText(",
        "export function copyText(",
        "export function parseMailto(",
        "export function mountInvite(host, ctx)",
    ):
        assert name in invite, name


def test_only_worker_route_is_invitations() -> None:
    invite = _text(INVITE)
    routes = re.findall(r"api\(\s*[\"'`]([^\"'`]*)[\"'`]", invite)
    assert routes == ["/invitations"]
    assert '"/invitations", {method: "POST", body: {}}' in invite
    assert "https://api.plastiverse.live" not in invite
    assert "https://api.plastiverse.live" not in _text(STYLES)


def test_no_email_field_or_address_prompt() -> None:
    invite = _text(INVITE)
    assert 'type="email"' not in invite
    assert "type='email'" not in invite
    assert "<input" not in invite
    assert "<select" not in invite


def test_no_browser_storage() -> None:
    invite = _text(INVITE)
    assert "localStorage" not in invite
    assert "sessionStorage" not in invite
    assert "indexedDB" not in invite
    assert "document.cookie" not in invite


def test_index_json_is_fetched_only_inside_mount_flow() -> None:
    invite = _text(INVITE)
    assert invite.count('"index.json"') == 1
    mount_at = invite.index("export function mountInvite(")
    assert invite.index('"index.json"') > mount_at
    # The author file and the eligible lists are also read only from the mount flow.
    assert invite.index("authors/${authorId}.json") > mount_at
    assert invite.index('"ambassador_institutions.json"') > mount_at


def test_user_visible_text_is_plain_language() -> None:
    code = _code(_text(INVITE))
    # Only string and template literals reach the screen; identifiers such as author_id are fine.
    literals = [
        m.group(1) or m.group(2) or ""
        for m in re.finditer(r'"((?:[^"\\\n]|\\.)*)"|`([^`]*)`', code)
    ]
    shown = " ".join(literals)
    assert literals, "no text literals found"
    for term in ("AMB-1", "author_id", "stream"):
        assert term not in shown, term


def test_copy_fallback_and_status_text() -> None:
    invite = _text(INVITE)
    assert "Select the text and copy it." in invite
    assert 'role="status"' in invite
    assert "readOnly = true" in invite
    assert "navigator.clipboard.writeText" in invite
    assert "Back to your tasks" in invite
    assert 'data-ws-action="home"' in invite
    assert "data-ws-action=" not in re.sub(r'data-ws-action="home"', "", invite)
    assert '<h2 tabindex="-1">Invite your co-authors</h2>' in invite


def test_styles_use_tokens_and_scoped_selectors() -> None:
    css = re.sub(r"/\*.*?\*/", "", _text(STYLES), flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "hex colours are not allowed"
    assert "var(--pv-ink)" in css
    for selector_block in re.findall(r"([^{}]+)\{", css):
        selector_block = selector_block.strip()
        if selector_block.startswith("@"):
            continue
        for selector in selector_block.split(","):
            assert selector.strip().startswith(".am .iv-"), selector.strip()


def test_styles_stack_rows_and_keep_buttons_tall() -> None:
    css = _text(STYLES)
    assert ".am .iv-row { display: grid;" in css
    assert "@media (min-width: 640px)" in css
    assert "min-height: 44px" in css


def test_runtime_helpers_pass_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_ambassador_invite_runtime.mjs")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
