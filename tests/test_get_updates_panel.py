"""NOTIFY-AB: the About page has a Get updates section, and the footer links to it."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = ROOT / "framework"
ABOUT = (FRAMEWORK / "src" / "about.md").read_text(encoding="utf-8")
CSS = (FRAMEWORK / "src" / "components" / "about.css").read_text(encoding="utf-8")
CONFIG = (FRAMEWORK / "observablehq.config.js").read_text(encoding="utf-8")


def test_get_updates_section_sits_between_the_lede_and_the_screening_steps() -> None:
    start = ABOUT.index('<section class="about-section get-updates" aria-labelledby="get-updates">')
    assert ABOUT.index('aria-labelledby="what-the-atlas-is"') < start
    assert start < ABOUT.index('aria-labelledby="how-works-are-screened"')
    assert "## Get updates" in ABOUT[start:]


def test_feed_panel_shows_the_address_with_a_copy_button_and_fallback() -> None:
    assert "https://plastiverse.live/feed.xml" in ABOUT
    assert "navigator.clipboard.writeText(FEED_URL)" in ABOUT
    assert 'status.textContent = "Copied"' in ABOUT
    assert 'status.dataset.state = "copied"' in ABOUT
    # Fallback: select the address text so it can be copied from the keyboard.
    assert "range.selectNodeContents(panel.querySelector" in ABOUT
    assert 'status.dataset.state = "fallback"' in ABOUT
    for reader in ("Feedly", "Inoreader", "NetNewsWire", "Thunderbird", "Slack", "Microsoft Teams"):
        assert reader in ABOUT


def test_phone_alert_panel_names_the_topic_and_both_links() -> None:
    assert "Install the free ntfy app for Android or iOS." in ABOUT
    assert "add the topic <code>plastiverse-california</code>" in ABOUT
    assert 'href="https://ntfy.sh/plastiverse-california"' in ABOUT
    assert 'href="https://ntfy.sh"' in ABOUT


def test_weekly_digest_placeholder_is_present() -> None:
    assert '<p class="about-soon">A weekly email digest is coming soon.</p>' in ABOUT


def test_footer_links_to_get_updates_and_keeps_the_existing_links() -> None:
    assert '<li><a href="./about#get-updates">Get updates</a></li>' in CONFIG
    for link in (
        '<li><a href="./about">About</a></li>',
        '<li><a href="./glossary">Glossary</a></li>',
        '<li><a href="./about#how-to-cite">How to cite</a></li>',
        "Report a correction",
    ):
        assert link in CONFIG, link


def test_get_updates_controls_are_at_least_40px_and_use_tokens_only() -> None:
    block = CSS[CSS.index("NOTIFY-AB") :]
    assert "#observablehq-main .get-updates .atlas-btn" in block
    assert "min-height: 2.5rem;" in block  # 40px at the default root size
    assert "min-height: 2.5rem;" in block.split("#observablehq-main .get-updates__address", 1)[1]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block)
