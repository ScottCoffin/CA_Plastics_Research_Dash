"""Static checks for the notification settings screen (AMB-1 front end slice 3b).

The pure helpers run in node (tests/framework_ambassador_settings_runtime.mjs).
These checks read the sources as text: the only Worker route is
GET/POST /me/notifications, the switches are role="switch" checkboxes, there
is no Ambassador badge toggle, no browser storage, no hard-coded API origin,
and the styles use tokens only. Nothing here calls the network.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "framework" / "src" / "components"
SETTINGS = COMPONENTS / "ambassador_settings.js"
STYLES = COMPONENTS / "ambassador_settings.css"
RUNTIME_CHECK = ROOT / "tests" / "framework_ambassador_settings_runtime.mjs"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_only_the_notifications_route_is_called() -> None:
    source = _text(SETTINGS)
    routes = set(re.findall(r'api\(\s*"(/[^"]*)"', source))
    assert routes == {"/me/notifications"}, routes
    assert 'ctx.api("/me/notifications", {method: "POST", body})' in source
    assert 'ctx.api("/me/notifications");' in source
    assert "https://api.plastiverse.live" not in source
    assert "fetch(" not in source


def test_each_switch_saves_on_change_with_one_key() -> None:
    source = _text(SETTINGS)
    assert "host.onchange" in source
    assert "const body = prefsBody(input.dataset.nsKey, input.checked);" in source
    assert "Save settings" not in source
    assert 'role="switch"' in source
    assert 'data-ns-key="${key}"' in source
    assert 'PREF_KEYS = ["reminders", "product_news"]' in source


def test_mount_contract_and_crumb_action() -> None:
    source = _text(SETTINGS)
    assert "export function mountSettings(host, ctx)" in source
    assert 'data-ws-action="home"' in source
    assert "Back to your tasks" in source
    assert '<h2 tabindex="-1">Notification settings</h2>' in source
    assert "Sign-in links are always sent and cannot be switched off." in source
    # The workspace owns data-ws-action; this screen uses its own data-ns-* attributes only.
    assert 'data-ws-action="' not in source.replace('data-ws-action="home"', "")
    assert "ctx.errorText(" in source and "ctx.say(" in source
    assert 'className = "ws-error"' in source or '"ws-error"' in source


def test_reminder_copy_matches_the_design() -> None:
    source = _text(SETTINGS)
    assert "Send me a reminder when I have open tasks" in source
    assert (
        "Sent only while tasks are open. Reminders pause after three unanswered "
        "reminders until you come back." in source
    )
    assert "every two weeks. This is fixed." in source
    assert "Send me occasional news about new regions and features" in source
    assert "News about Plastiverse" in source


def test_no_ambassador_badge_toggle() -> None:
    source = _text(SETTINGS)
    assert "badge" not in source.lower()
    assert "Hide my" not in source


def test_user_visible_text_has_no_internal_names() -> None:
    # Only comments may carry internal names; every string literal (the copy) must be plain.
    lines = _text(SETTINGS).splitlines()
    code = "\n".join(line for line in lines if not line.lstrip().startswith("//"))
    strings = re.findall(r'"[^"\n]*"|`[^`]*`', code)
    keys = {
        '"reminders"',
        '"product_news"',
    }  # the Worker keys, used in code and data attributes only
    for literal in strings:
        copy = re.sub(r"\$\{[^}]*\}", "", literal)  # drop the code inside ${...}
        if literal in keys:
            continue
        for word in ("AMB-1", "stream", "product_news"):
            assert word not in copy, literal


def test_no_browser_storage_or_cookies() -> None:
    source = _text(SETTINGS)
    assert "localStorage" not in source and "sessionStorage" not in source
    assert "document.cookie" not in source
    assert "indexedDB" not in source


def test_styles_use_tokens_and_are_scoped() -> None:
    styles = _text(STYLES)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", styles), "no hex colours"
    for token in ("--pv-ink", "--pv-ink-2", "--pv-paper", "--pv-coral-ink"):
        assert f"var({token})" in styles, token
    code = re.sub(r"/\*.*?\*/", "", styles, flags=re.DOTALL)
    for selector in re.findall(r"^\s*([^\s@}{][^{]*)\{", code, flags=re.MULTILINE):
        for part in selector.split(","):
            part = part.strip()
            if part:
                assert part.startswith(".am .ns-"), part
    assert "min-height: 44px" in styles
    assert "input:focus-visible + .ns-track" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles


def test_switch_shows_state_as_text_as_well_as_position() -> None:
    source = _text(SETTINGS)
    assert "onOff" in source and '"On" : "Off"' in source
    assert 'class="ns-state"' in source or "ns-state" in source
    assert '"Saving…"' in source


def test_runtime_helpers_pass_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        raise AssertionError("Node.js is required for the settings runtime check")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
