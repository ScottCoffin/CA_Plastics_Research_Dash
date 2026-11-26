"""Static checks for the ORCID-first sign-up on /ambassadors (AMB-1 front end slice 2a).

The pure helpers run in node (tests/framework_ambassador_signup_runtime.mjs). These checks read the
sources as text: the page mounts the module, every Worker call uses credentials and the single API
constant, no email is stored in the browser, and Turnstile loads only on the email step.
Nothing here calls the network.
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
PAGE = SRC / "ambassadors.md"
MODULE = COMPONENTS / "ambassador_signup.js"
STYLES = COMPONENTS / "ambassadors.css"
RUNTIME_CHECK = ROOT / "tests" / "framework_ambassador_signup_runtime.mjs"
API_HOST = "api.plastiverse.live"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _module_calls(name: str) -> list[str]:
    """Each `name(` call (not its definition) in the module, as the text that follows it."""
    return re.findall(rf"(?<!function ){re.escape(name)}\(([^)]*)\)", _text(MODULE))


def test_page_mounts_the_sign_up_module_and_has_its_panel() -> None:
    page = _text(PAGE)
    assert 'from "./components/ambassador_signup.js"' in page
    assert 'mountSignup(document.querySelector(".am"))' in page
    assert 'id="amb-signup"' in page and 'id="amb-signup-body"' in page
    assert 'id="amb-signup-status"' in page and 'role="status"' in page


def test_sign_in_opens_soon_is_gone_everywhere() -> None:
    for path in (PAGE, MODULE, COMPONENTS / "ambassadors.js"):
        assert "Sign-in opens soon" not in _text(path), path.name


def test_orcid_links_point_at_the_worker_start_route() -> None:
    page = _text(PAGE)
    links = re.findall(r"<a [^>]*data-orcid-start[^>]*>", page)
    assert len(links) >= 3, "hero, sign-in line and the how-it-works section"
    for link in links:
        assert 'href="https://api.plastiverse.live/orcid/start"' in link, link
    assert "Sign up with ORCID" in page
    assert "Already an ambassador? " in page


def test_single_api_constant_and_every_fetch_is_credentialed() -> None:
    text = _text(MODULE)
    assert text.count(f"https://{API_HOST}") == 1, "the API base is one constant"
    assert re.search(r'export const API_BASE = "https://api\.plastiverse\.live";', text)
    fetches = re.findall(r"\bfetch\(([A-Za-z]+)\(", text)
    # Worker calls go through api(); the only other fetch is a same-origin allowlist file
    # (no credentials).
    assert fetches and set(fetches) <= {"apiUrl", "regionFileUrl"}, fetches
    api_block = re.search(r"async function api\(.*?\n\}\n", text, re.S)
    assert api_block is not None
    assert 'credentials: "include"' in api_block.group(0)
    assert "fetch(apiUrl(path)" in api_block.group(0)
    assert "fetch(regionFileUrl(" in text
    assert text.count("fetch(regionFileUrl(") == 1
    assert (
        "credentials"
        not in text.split("async function loadDomains")[1].split("function loadTurnstile")[0]
    )


def test_no_email_or_session_is_kept_in_the_browser_or_url() -> None:
    text = _text(MODULE)
    assert not re.search(r"(localStorage|sessionStorage)\.", text)
    assert "document.cookie" not in text
    # The query state is cleaned from the URL after it is read, before anything is shown.
    assert 'history.replaceState(history.state, "", stripQuery(location.href))' in text
    # The email goes in the request body only, never in a query string.
    assert re.search(
        r'api\("/signup/email", \{method: "POST", body: \{email, turnstileToken: flow\.token\}\}\)',
        text,
    )


def test_turnstile_loads_only_on_the_email_step() -> None:
    text = _text(MODULE)
    script = "https://challenges.cloudflare.com/turnstile/v0/api.js"
    assert text.count(script) == 1
    assert script not in _text(PAGE)
    # mountTurnstile is called from stepEmail only, and stepEmail is reached only via renderStep(4).
    step_email = re.search(r"async function stepEmail\(\) \{(.*?)\n\}\n", text, re.S)
    assert step_email is not None and "await mountTurnstile();" in step_email.group(1)
    assert len(_module_calls("mountTurnstile")) == 1
    assert len(_module_calls("loadTurnstile")) == 1  # called only by mountTurnstile
    assert "renderStep(4)" in text and text.count("return stepEmail()") == 1
    # The key is public and set; the PENDING fallback stays in code.
    assert re.search(r'export const TURNSTILE_SITE_KEY = "0x[A-Za-z0-9_-]+";', text)
    assert 'PENDING = "PENDING-OWNER"' in text
    assert "Email confirmation opens soon." in text


def test_no_raw_error_codes_are_shown_to_the_user() -> None:
    text = _text(MODULE)
    # Error codes are mapped through errorText(); the code itself is never written into the DOM.
    assert "errorText(" in text
    assert "${esc(response.error)}" not in text and "${response.error}" not in text
    assert "body.innerHTML = html" in text and "esc(" in text


def test_module_has_no_hex_colours_and_the_css_uses_tokens() -> None:
    styles = _text(STYLES)
    added = styles[styles.index("ORCID-first sign-up") :]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", added), "sign-up styles use the theme tokens only"
    assert "var(--pv-ink)" in added


def test_sign_up_fields_have_labels_and_targets_are_24px_or_more() -> None:
    page_module = _text(MODULE)
    for field in ("signup-email", "prop-name", "prop-url", "profile-name"):
        assert f'for="{field}"' in page_module or f'id="{field}"' in page_module, field
    styles = _text(STYLES)
    assert "width: 24px; height: 24px" in styles and "min-height: 44px" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles


def test_runtime_helpers_pass_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_ambassador_signup_runtime.mjs")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
