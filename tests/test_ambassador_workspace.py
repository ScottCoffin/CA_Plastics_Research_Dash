"""Static checks for the ambassador workspace (AMB-1 front end slice 2b).

The pure helpers run in node (tests/framework_ambassador_workspace_runtime.mjs).
These checks read the sources as text: the sign-up mounts the workspace, the
workspace reuses the sign-up's api() and errorText() (no copy), stream B
addresses items by the region.json item_id, nothing personal is kept in the
browser, and the styles use tokens. Nothing here calls the network.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "framework" / "src" / "components"
WORKSPACE = COMPONENTS / "ambassador_workspace.js"
SIGNUP = COMPONENTS / "ambassador_signup.js"
STYLES = COMPONENTS / "ambassadors.css"
RUNTIME_CHECK = ROOT / "tests" / "framework_ambassador_workspace_runtime.mjs"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sign_up_mounts_the_workspace_and_drops_the_stub() -> None:
    signup = _text(SIGNUP)
    assert 'from "./ambassador_workspace.js"' in signup
    assert "mountWorkspace(body, ambassador, {focus, announce: setStatus})" in signup
    assert "Workspace coming next" not in signup
    assert "Workspace coming next" not in _text(ROOT / "framework" / "src" / "ambassadors.md")


def test_workspace_reuses_the_sign_up_api_and_error_map() -> None:
    signup = _text(SIGNUP)
    workspace = _text(WORKSPACE)
    assert "export async function api(" in signup, "api() is exported for the workspace"
    assert 'from "./ambassador_signup.js"' in workspace
    assert re.search(
        r'import \{[^}]*\bapi\b[^}]*\berrorText\b[^}]*\} from "\./ambassador_signup\.js";',
        workspace,
    )
    # No private copy of the helper or the error map.
    assert "async function api(" not in workspace
    assert "const ERROR_TEXT" not in workspace
    # Every Worker call goes through api(); the only raw fetch reads same-origin public files.
    assert "https://api.plastiverse.live" not in workspace
    assert "apiUrl(" not in workspace
    assert 'fetch(url, {cache: "no-cache"})' in workspace, (
        "the only raw fetch is readJson() for public files"
    )
    assert 'readJson(regionFileUrl(slug, "ambassador_cases.json"))' in workspace
    routes = set(re.findall(r'api\(\s*"(/[^"]*)"', workspace))
    assert routes == {"/cases/answer", "/submissions", "/submissions/mine"}, routes
    assert "`/cases/answers?region=${encodeURIComponent(slug)}`" in workspace


def test_routes_and_bodies_match_the_worker() -> None:
    workspace = _text(WORKSPACE)
    assert 'api("/cases/answer", {method: "POST", body})' in workspace
    assert 'api("/submissions", {method: "POST", body})' in workspace
    # The answer body carries the case id, the answer and (for disagree) the correct value only.
    assert "case_id: caseId" in workspace and "correct_value: value" in workspace
    # Stream B: the confirm stream, one kind per action, addressed by the region.json item_id.
    assert 'stream: "confirm"' in workspace
    assert 'CONFIRM_KINDS = ["confirm", "correct", "not_relevant"]' in workspace
    assert "const payload = {item_id: itemId};" in workspace


def test_stream_b_uses_the_stable_item_id_not_a_list_position() -> None:
    workspace = _text(WORKSPACE)
    assert "item.item_id" in workspace
    assert "item_id: item.item_id" in workspace
    assert "section_id" in workspace
    # The id is never built from a position or a name in the browser.
    assert not re.search(r"item_id:\s*`", workspace)
    assert "`${region}:" not in workspace and "`${slug}:" not in workspace


def test_stream_a_reads_the_public_case_file_and_the_caller_answers() -> None:
    workspace = _text(WORKSPACE)
    assert 'regionFileUrl(slug, "ambassador_cases.json")' in workspace
    assert 'CASES_SCHEMA = "amb-cases-v1"' in workspace
    assert 'regionFileUrl(slug, "region.json")' in workspace
    assert "REGION_SCHEMA" in workspace and 'from "./region_page.js"' in workspace


def test_no_personal_data_is_kept_in_the_browser() -> None:
    for path in (WORKSPACE, SIGNUP):
        text = _text(path)
        assert not re.search(r"(localStorage|sessionStorage)\.", text), path.name
        assert "document.cookie" not in text, path.name
    # The workspace names no browser storage at all and keeps no e-mail or ORCID iD in a URL.
    workspace = _text(WORKSPACE)
    assert "localStorage" not in workspace and "sessionStorage" not in workspace
    assert "orcid" not in workspace.lower()
    assert "email" not in workspace.lower()


def test_highlight_escapes_before_it_marks() -> None:
    workspace = _text(WORKSPACE)
    assert "export function highlightHtml" in workspace
    assert "escapeHtml(part)" in workspace
    assert "`<mark>${escapeHtml(part)}</mark>`" in workspace
    assert (
        'import {escapeHtml, globalDataUrl, regionFileUrl, siteRoot} from "./atlas.js";'
        in workspace
    )


def test_one_heading_per_screen_and_focus_on_navigation() -> None:
    workspace = _text(WORKSPACE)
    assert 'tabindex="-1"' in workspace
    assert 'focus === "heading"' in workspace
    # Stream A keeps the answer on the same case: answering never moves to the next case.
    assert "state.index += action" in workspace
    assert (
        "postAnswer(body" in workspace
        and "state.index"
        not in workspace.split("async function postAnswer")[1].split("async function sendItem")[0]
    )


def test_local_knowledge_invitations_and_settings_open_their_screens() -> None:
    workspace = _text(WORKSPACE)
    # Slice 3: the three later cards open real screens drawn by their own modules.
    assert "Coming next" not in workspace
    for name in (
        "Add local knowledge",
        "Tag local groups",
        "Invite your co-authors",
        "Notification settings",
    ):
        assert name in workspace
    for module, mount in (
        ("ambassador_knowledge.js", "mountKnowledge"),
        ("ambassador_groups.js", "mountGroups"),
        ("ambassador_settings.js", "mountSettings"),
        ("ambassador_invite.js", "mountInvite"),
    ):
        assert f'from "./{module}"' in workspace and f"{mount}(host" in workspace
    assert 'const MODULE_SCREENS = new Set(["C", "D", "settings", "invite"]);' in workspace
    page = _text(ROOT / "framework" / "src" / "ambassadors.md")
    for css in (
        "ambassador_knowledge.css",
        "ambassador_groups.css",
        "ambassador_settings.css",
        "ambassador_invite.css",
    ):
        assert f'href="./components/{css}"' in page


def test_email_links_open_their_screens_and_leave_the_address_bar() -> None:
    workspace = _text(WORKSPACE)
    # The settings link in every mail ends in #notifications; the reminder links to ?region=&case=.
    assert "deepLinkFrom(location.search, location.hash)" in workspace
    assert 'history.replaceState(history.state, "", url.href)' in workspace


def test_the_workspace_has_no_hex_colours_and_the_css_uses_tokens() -> None:
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", _text(WORKSPACE))
    styles = _text(STYLES)
    added = styles[styles.index("Ambassador workspace (AMB-1 front end slice 2b") :]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", added), (
        "workspace styles use the theme tokens only"
    )
    assert "min-height: 44px" in added
    assert "@media (prefers-reduced-motion: reduce)" in added


def test_dashboard_is_two_columns_on_wide_screens_only() -> None:
    workspace = _text(WORKSPACE)
    styles = _text(STYLES)
    added = styles[styles.index("Ambassador workspace (AMB-1 front end slice 2b") :]
    # Tasks come first in the DOM (one column below 1100px); the side column holds map and progress.
    assert 'class="ws-dash"' in workspace and 'class="ws-side"' in workspace
    assert workspace.index('class="ws-tasks"') < workspace.index('class="ws-side"')
    assert 'wrap.classList.toggle("is-dash"' in workspace
    # The two columns start at 1100px; the tablet width (1024px) keeps one column.
    assert "@media (min-width: 1100px)" in added
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr)" in added
    # The dashboard uses the page width (no 1200px cap); the grid itself starts at 1100px.
    assert "max-width: 1200px" not in added
    # The map box reserves the shared frame's aspect ratio inline, so the layout does not shift.
    assert 'style="aspect-ratio: ${w} / ${h}"' in workspace
    assert "export function mapFrame(world)" in workspace
    assert "aspect-ratio: 2 / 1" in added


def test_a_choice_shows_as_pressed_with_a_check_and_a_text_state() -> None:
    workspace = _text(WORKSPACE)
    # Stream B: each chosen button carries aria-pressed and a check mark; the row states the choice.
    for kind in ("confirm", "not_relevant", "correct"):
        assert f'${{pressed("{kind}")}}' in workspace, kind
    assert 'const pressed = (kind) => `aria-pressed="${chosen?.kind === kind}"`;' in workspace
    assert "choiceText(chosen)" in workspace
    assert 'class="ws-state"' in workspace
    # Stream A: the chosen answer is pressed and marked, and its text says what was answered.
    assert 'aria-pressed="${saved?.answer === answer}"' in workspace
    assert "chosenMark(saved?.answer === answer)" in workspace
    assert "Your answer: ${ANSWER_LABELS[saved.answer]}." in workspace
    # The check icon is decorative; the state is text and the check is hidden from assistive tech.
    assert (
        'class="ws-check"' in workspace
        and 'aria-hidden="true"' in workspace.split("const CHECK")[1][:200]
    )
    styles = _text(STYLES)
    added = styles[styles.index("Ambassador workspace (AMB-1 front end slice 2b") :]
    assert '.am .ws .ws-item-actions .btn[aria-pressed="true"]' in added
    assert ".am .ws .ws-state" in added


def test_ambassador_text_uses_the_page_width() -> None:
    # Owner 2026-11-26: no narrow column limits on headings or prose; inputs keep their own widths.
    styles = _text(STYLES)
    for name in (
        "ambassador_knowledge.css",
        "ambassador_settings.css",
        "ambassador_invite.css",
        "ambassador_moderation.css",
    ):
        styles += _text(COMPONENTS / name)
    for old in ("max-width: 18ch", "max-width: 58ch", "max-width: 760px", "max-width: 960px"):
        assert old not in styles, old


def test_progress_summary_is_text_and_a_bar() -> None:
    workspace = _text(WORKSPACE)
    assert "export function progressSummary(streams)" in workspace
    assert "export function timeLeftText(minutes)" in workspace
    assert "Time left: ${estimateText(minutes)}" in workspace
    assert 'class="ws-progress-line"' in workspace
    # Each bar has a text label and the count and share are written out, not only shown as colour.
    assert 'aria-label="Region progress: ' in workspace
    assert "(${row.percent}%)" in workspace


def test_runtime_helpers_pass_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_ambassador_workspace_runtime.mjs")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
