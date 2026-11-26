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


def test_unlisted_institution_is_on_the_institutions_step_and_skips_regions() -> None:
    text = _text(MODULE)
    assert "My institution isn't listed" in text
    assert "data-unlisted-area" in text and 'id="signup-unlisted"' in text
    # Highlighted only when no eligible institution is ticked.
    assert 'class="unlisted${noEligible ? " is-key" : ""}"' in text
    # Region is a select, not radio buttons (the region-choice UI is checkboxes or a select).
    assert 'type="radio"' not in text
    # The unlisted institution skips the regions step through the same claims sender.
    assert 'return sendClaims(form, "signup-institutions");' in text
    assert text.count('api("/signup/claims"') == 1


def test_pending_review_route_makes_no_session_call_and_untrusted_domain_is_plain_text() -> None:
    text = _text(MODULE)
    assert '"pending_review"' in text and "showPendingReview()" in text
    pending = re.search(r"function showPendingReview\(\) \{(.*?)\n\}\n", text, re.S)
    assert pending is not None
    assert "api(" not in pending.group(1)
    assert "Thanks, your email is confirmed." in pending.group(1)
    assert "untrusted_domain:" in text
    assert "pending_email_proposal" in text


def test_trusted_suffix_check_has_no_region_names_and_reads_the_region_file() -> None:
    text = _text(MODULE)
    assert "trusted_email_suffixes" in text
    # The hint is built from the data; the suffixes are not hard-coded in the module.
    for suffix in ("ca.gov", "ca.us"):
        assert f'"{suffix}"' not in text


def test_runtime_helpers_pass_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_ambassador_signup_runtime.mjs")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_sign_up_reports_its_regions_to_the_map_on_the_page_root() -> None:
    """Owner 2026-11-26: the map highlights the suggested and chosen regions while the sign-up runs.

    The sign-up dispatches amb:regions on the page root (no network call); the map listens for it.
    The clear runs when the flow ends or is cancelled, so the highlight does not outlive it.
    """
    signup = _text(COMPONENTS / "ambassador_signup.js")
    landing = _text(COMPONENTS / "ambassadors.js")
    assert 'export const REGIONS_EVENT = "amb:regions"' in signup
    assert 'SIGNUP_REGIONS_EVENT = "amb:regions"' in landing
    assert (
        "pageRoot?.dispatchEvent(new CustomEvent(REGIONS_EVENT, {bubbles: true, detail}))" in signup
    )
    assert "publishRegions();" in signup and "signupRegionState({" in signup
    # Ticks and regions update the map on change, not only when a step is drawn.
    assert (
        'event.target.name === "institution"' in signup
        and 'event.target.name === "region"' in signup
    )
    # Every terminal screen and the landing reset: showLanding, showInbox, showMessage (failed,
    # signed out), showProposalsSent, showPendingReview and showAccount.
    assert signup.count("clearRegions();") == 6
    for name in (
        "showLanding",
        "showInbox",
        "showMessage",
        "showProposalsSent",
        "showPendingReview",
        "showAccount",
    ):
        body = signup.split(f"function {name}(", 1)[1].split("\n}", 1)[0]
        assert "clearRegions();" in body, name
    # The unlisted proposal's region is part of the suggestion (the regions step is skipped for it).
    assert "unlisted?.region" in signup
    # The sign-up does not scroll the page for the map.
    helper = signup.split("export function signupRegionState", 1)[1][:400]
    assert "scrollIntoView" not in helper


def test_map_highlight_is_announced_and_reduces_motion() -> None:
    landing = _text(COMPONENTS / "ambassadors.js")
    page = _text(PAGE)
    css = _text(COMPONENTS / "ambassador_signup_map.css")
    assert 'id="amb-sig-list" aria-live="polite"' in landing
    assert 'id="amb-sig-key" hidden' in landing
    assert "Suggested: " in landing and "Chosen: " in landing
    assert "Dashed outline" in landing and "Solid outline and deeper fill" in landing
    # The map reads the event in its listener, which is attached before the first await.
    listener = landing.split("root.addEventListener(SIGNUP_REGIONS_EVENT", 1)[1][:200]
    assert "paintSignupRegions" in listener
    body = landing.split("// ---- sign-up highlight (owner 2026-11-26)", 1)[1].split(
        "// ---- selection", 1
    )[0]
    # No animated zoom: the view changes at once; nothing scrolls or animates in the highlight code.
    for banned in ("requestAnimationFrame", "scrollIntoView", "animate(", "setTimeout"):
        assert banned not in body, banned
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "transition: none" in css
    assert 'href="./components/ambassador_signup_map.css"' in page
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
