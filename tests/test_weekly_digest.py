"""MAIL-1: the weekly Buttondown digest of new California plastics papers.

Every test uses synthetic rows and a fake opener. No test touches the network or the real key.
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import urllib.error
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from atlas.build.digest import (
    ABSTRACT_MAX_CHARS,
    API_KEY_ENV,
    EDITOR_MODE,
    INK,
    TOPIC_STYLE,
    UNSUBSCRIBE_TAG,
    DigestError,
    DigestSettings,
    build_digest,
    email_payload,
    feed_url,
    last_sunday,
    load_settings,
    parse_week_ending,
    render_html,
    render_text,
    select_new_works,
    send_digest,
    subject_line,
    week_label,
    week_window,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_weekly_digest.py"
CONFIG = ROOT / "config" / "notifications.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "weekly_digest.yml"
TOPICS_JS = ROOT / "framework" / "src" / "components" / "shared" / "topics.js"

SITE = "https://plastiverse.live/california"
WEEK_ENDING = date(2026, 11, 15)  # a Sunday; the window is 9 to 15 November 2026 (UTC)
KEY = "sk-test-SECRET-9876"
SETTINGS = DigestSettings(
    site_url=SITE,
    max_works=40,
    subject_template="California plastics research, week of {start}",
    sender_name="Plastiverse · California",
    ntfy_url="https://ntfy.sh/plastiverse-california",
)


def _load_script():
    spec = importlib.util.spec_from_file_location("build_weekly_digest", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCRIPT_MODULE = _load_script()


def work(work_id: str = "W1", first_seen: str = "2026-11-11T12:00:00+00:00", **extra: Any):
    row: dict[str, Any] = {
        "work_id": work_id,
        "title": f"Paper {work_id}",
        "authors": ["Ada Lovelace", "Grace Hopper"],
        "journal": "Environmental Science",
        "year": 2025,
        "doi": f"https://doi.org/10.1000/{work_id.lower()}",
        "domain_tags": ["fate_transport_and_sorption"],
        "plastic_related": True,
        "first_seen": first_seen,
    }
    row.update(extra)
    return row


def _digest(rows, abstracts=None, week_ending=WEEK_ENDING, max_works=40):
    return build_digest(
        rows,
        abstracts or {},
        week_ending=week_ending,
        max_works=max_works,
        site_url=SITE,
    )


class FakeResponse:
    def __init__(self, payload: Any = None, status: int = 200):
        self.status = status
        self._raw = b"" if payload is None else json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


class FakeOpener:
    """Records each request and returns the scripted responses in order."""

    def __init__(self, *responses: Any):
        self.requests: list[Any] = []
        self._responses = list(responses)

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        item = self._responses.pop(0) if self._responses else FakeResponse({})
        if isinstance(item, BaseException):
            raise item
        return item


def _headers(request) -> dict[str, str]:
    return {name.lower(): value for name, value in request.header_items()}


def _write_inputs(tmp_path: Path, rows: list[dict[str, Any]], abstracts=None):
    works = tmp_path / "works_detail.json"
    works.write_text(json.dumps({"schema_version": "test", "works": rows}), encoding="utf-8")
    abstract_file = tmp_path / "abstracts.json"
    abstract_file.write_text(json.dumps({"abstracts": abstracts or {}}), encoding="utf-8")
    return works, abstract_file


def _cli(works: Path, abstracts: Path, *extra: str) -> list[str]:
    return [
        "--week-ending",
        "2026-11-15",
        "--works",
        str(works),
        "--abstracts",
        str(abstracts),
        "--config",
        str(CONFIG),
        *extra,
    ]


# Dates and windows -----------------------------------------------------------------------


def test_week_window_runs_monday_0000_utc_to_next_monday_0000_utc():
    start, end = week_window(WEEK_ENDING)
    assert start == datetime(2026, 11, 9, tzinfo=UTC)
    assert end == datetime(2026, 11, 16, tzinfo=UTC)


def test_default_week_is_the_most_recent_sunday():
    assert last_sunday(date(2026, 11, 16)) == date(2026, 11, 15)  # Monday: last Sunday
    assert last_sunday(date(2026, 11, 15)) == date(2026, 11, 15)  # Sunday: itself
    assert last_sunday(date(2026, 11, 14)) == date(2026, 11, 8)  # Saturday


def test_week_ending_must_be_a_sunday():
    assert parse_week_ending("2026-11-15") == WEEK_ENDING
    with pytest.raises(ValueError, match="Sunday"):
        parse_week_ending("2026-11-16")


def test_week_label_handles_month_and_year_breaks():
    assert week_label(date(2026, 11, 9), date(2026, 11, 15)) == "9–15 November 2026"
    assert week_label(date(2026, 11, 30), date(2026, 12, 6)) == "30 November – 6 December 2026"
    assert week_label(date(2026, 12, 28), date(2027, 1, 3)) == ("28 December 2026 – 3 January 2027")


# Selection -------------------------------------------------------------------------------


def test_selection_follows_utc_boundaries_and_skips_unusable_rows():
    rows = [
        work("A", "2026-11-09T00:00:00+00:00"),  # Monday 00:00 UTC: in
        work("B", "2026-11-15T23:59:59.999999+00:00"),  # Sunday 23:59:59.999999 UTC: in
        work("C", "2026-11-16T00:00:00+00:00"),  # next Monday: out
        work("D", "2026-11-08T23:59:59+00:00"),  # previous Sunday: out
        work("E", "2026-11-16T00:30:00+01:00"),  # 2026-11-15 23:30 UTC: in
        work("F", "2026-11-15T20:00:00-05:00"),  # 2026-11-16 01:00 UTC: out
        work("G", "2026-11-12T10:00:00Z"),  # Z suffix: in
        work("H", "2026-11-10T08:00:00"),  # naive timestamps read as UTC: in
        work("I", "2026-11-12T10:00:00+00:00", plastic_related=False),  # not plastic: out
        work(
            "J",
            "",
        ),  # no first_seen: out
        work("K", "not a timestamp"),  # unreadable first_seen: out
        work("", "2026-11-12T10:00:00+00:00"),  # no work_id: out
    ]
    start, end = week_window(WEEK_ENDING)
    ids = [row["work_id"] for row in select_new_works(rows, start, end)]
    # Newest first: B and E are the latest, then G, H, A.
    assert ids == ["B", "E", "G", "H", "A"]


def test_ties_on_first_seen_order_by_year_then_title():
    stamp = "2026-11-11T12:00:00+00:00"
    rows = [
        work("OLD", stamp, year=2019, title="Aardvark"),
        work("NEW_Z", stamp, year=2024, title="Zebra"),
        work("NEW_A", stamp, year=2024, title="Apple"),
    ]
    start, end = week_window(WEEK_ENDING)
    ids = [row["work_id"] for row in select_new_works(rows, start, end)]
    assert ids == ["NEW_A", "NEW_Z", "OLD"]


def test_cap_lists_max_works_and_counts_the_rest():
    rows = [work(f"W{i:03d}", f"2026-11-1{i % 5 + 1}T09:00:00+00:00") for i in range(45)]
    digest = _digest(rows)
    assert digest.total == 45
    assert len(digest.cards) == 40
    assert digest.hidden == 5
    html_body = render_html(digest, SETTINGS)
    text_body = render_text(digest, SETTINGS)
    assert "and 5 more on the site." in html_body
    assert "and 5 more on the site: " + SITE in text_body
    assert "45 new plastic-related California papers" in html_body


def test_no_more_line_when_everything_fits():
    digest = _digest([work("W1"), work("W2")])
    assert digest.hidden == 0
    assert "more on the site" not in render_html(digest, SETTINGS)
    assert "more on the site" not in render_text(digest, SETTINGS)


def test_singular_headline_for_one_paper():
    digest = _digest([work("W1")])
    assert "1 new plastic-related California paper" in render_html(digest, SETTINGS)


# Cards -----------------------------------------------------------------------------------


def test_html_escapes_titles_and_abstracts():
    rows = [work("W1", title="<img src=x onerror=alert(1)> & Co")]
    abstracts = {"W1": 'Says "quoted" <b>bold</b> & more.'}
    html_body = render_html(_digest(rows, abstracts), SETTINGS)
    assert "&lt;img src=x onerror=alert(1)&gt; &amp; Co" in html_body
    assert "<img src=x" not in html_body
    assert "&quot;quoted&quot; &lt;b&gt;bold&lt;/b&gt; &amp; more." in html_body
    assert "<b>bold</b>" not in html_body


def test_missing_abstract_is_omitted_without_error():
    rows = [work("W1", title="Paper with no summary")]
    digest = _digest(rows, {})
    html_body = render_html(digest, SETTINGS)
    text_body = render_text(digest, SETTINGS)
    assert "Paper with no summary" in html_body
    assert "Paper with no summary" in text_body
    assert digest.cards[0].abstract == ""
    assert "abstract" not in text_body.lower()


def test_long_abstracts_are_shortened_at_a_word_boundary():
    long_text = " ".join(["plastic"] * 400)
    digest = _digest([work("W1")], {"W1": long_text})
    shortened = digest.cards[0].abstract
    assert shortened.endswith("…")
    assert len(shortened) <= ABSTRACT_MAX_CHARS + 1
    assert not shortened[:-1].endswith("plasti")  # cut at a space, not inside a word


def test_authors_show_three_then_et_al():
    four = work("W1", authors=["A One", "B Two", "C Three", "D Four"])
    three = work("W2", authors=["A One", "B Two", "C Three"])
    digest = _digest([four, three])
    by_id = {card.title: card.authors for card in digest.cards}
    assert by_id["Paper W1"] == "A One, B Two, C Three et al."
    assert by_id["Paper W2"] == "A One, B Two, C Three"


def test_link_prefers_doi_then_openalex_page():
    with_doi = work("W1")
    no_doi = work("W2", doi="")
    bad_doi = work("W3", doi="http://doi.org/10.1000/x")
    urls = {card.title: card.url for card in _digest([with_doi, no_doi, bad_doi]).cards}
    assert urls["Paper W1"] == "https://doi.org/10.1000/w1"
    assert urls["Paper W2"] == "https://openalex.org/W2"
    assert urls["Paper W3"] == "https://openalex.org/W3"


def test_rule_takes_the_first_topic_colour():
    rows = [
        work("W1", domain_tags=["air", "occurrence_and_monitoring"]),
        work("W2", domain_tags=[]),
    ]
    cards = {card.title: card for card in _digest(rows).cards}
    assert cards["Paper W1"].rule == TOPIC_STYLE["air"][1]
    assert cards["Paper W2"].rule == INK


def test_html_is_light_only_with_no_tracking_or_scripts():
    html_body = render_html(_digest([work("W1")], {"W1": "Short abstract."}), SETTINGS)
    assert '<meta name="color-scheme" content="light">' in html_body
    assert "prefers-color-scheme" not in html_body
    assert "<script" not in html_body.lower()
    assert "<img" not in html_body.lower()  # no tracking pixel, no image mark
    assert "max-width:640px" in html_body
    assert "Archivo, 'Helvetica Neue', Arial, sans-serif" in html_body
    for colour in ("#ece7dc", "#f6f3ec", "#141311", "#4b463e", "#23305e", "#e2452b", "#e3a92b"):
        assert colour in html_body


def test_links_unsubscribe_placeholder_and_footer_credit():
    digest = _digest([work("W1")])
    html_body = render_html(digest, SETTINGS)
    text_body = render_text(digest, SETTINGS)
    assert UNSUBSCRIBE_TAG in html_body
    assert UNSUBSCRIBE_TAG in text_body
    assert "Created by Scott Coffin." in html_body
    assert f'href="{SITE}"' in html_body
    assert f'href="{feed_url(SETTINGS)}"' in html_body
    assert feed_url(SETTINGS) == SITE + "/feed.xml"
    assert "https://ntfy.sh/plastiverse-california" in html_body


def test_empty_week_renders_a_placeholder_line():
    digest = _digest([])
    assert "No new papers were added this week." in render_html(digest, SETTINGS)
    assert "No new papers were added this week." in render_text(digest, SETTINGS)


def test_subject_names_the_monday_of_the_week():
    assert subject_line(SETTINGS, _digest([work("W1")])) == (
        "California plastics research, week of 9 November 2026"
    )


def test_email_payload_marks_html_and_uses_the_naked_template():
    payload = email_payload("Subject", "<p>Hi</p>")
    assert payload["body"] == EDITOR_MODE + "<p>Hi</p>"
    assert payload["template"] == "naked"
    assert payload["subject"] == "Subject"


# Buttondown send -------------------------------------------------------------------------


def test_send_creates_a_draft_then_publishes_it():
    opener = FakeOpener(FakeResponse({"id": "em_123"}), FakeResponse({"id": "em_123"}))
    email_id = send_digest(
        api_key=KEY,
        subject="Subject line",
        html_body="<p>Body</p>",
        idempotency="atlas-digest-2026-11-15",
        opener=opener,
    )
    assert email_id == "em_123"
    create, publish = opener.requests
    assert create.get_method() == "POST"
    assert create.full_url == "https://api.buttondown.com/v1/emails"
    assert _headers(create)["authorization"] == f"Token {KEY}"
    assert _headers(create)["x-idempotency-key"] == "atlas-digest-2026-11-15"
    sent = json.loads(create.data.decode("utf-8"))
    assert sent["subject"] == "Subject line"
    assert sent["body"].startswith(EDITOR_MODE)
    assert sent["body"].endswith("<p>Body</p>")
    assert sent["template"] == "naked"
    assert publish.get_method() == "POST"
    assert publish.full_url == "https://api.buttondown.com/v1/emails/em_123/publish"
    assert _headers(publish)["authorization"] == f"Token {KEY}"


def test_failed_publish_names_the_draft_and_never_the_key():
    http_error = urllib.error.HTTPError(
        "https://api.buttondown.com/v1/emails/em_9/publish",
        500,
        "Server Error",
        {},
        io.BytesIO(b'{"detail": "boom"}'),
    )
    opener = FakeOpener(FakeResponse({"id": "em_9"}), http_error)
    with pytest.raises(DigestError) as caught:
        send_digest(
            api_key=KEY,
            subject="S",
            html_body="<p>x</p>",
            idempotency="k",
            opener=opener,
        )
    message = str(caught.value)
    assert "em_9" in message and "not published" in message
    assert "HTTP 500" in message
    assert KEY not in message


def test_unauthorised_create_reports_status_only():
    error = urllib.error.HTTPError(
        "https://api.buttondown.com/v1/emails", 401, "Unauthorized", {}, io.BytesIO(b"")
    )
    with pytest.raises(DigestError, match="HTTP 401") as caught:
        send_digest(
            api_key=KEY,
            subject="S",
            html_body="<p>x</p>",
            idempotency="k",
            opener=FakeOpener(error),
        )
    assert KEY not in str(caught.value)


def test_missing_key_makes_no_request(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    works, abstracts = _write_inputs(tmp_path, [work("W1")])
    opener = FakeOpener()
    code = SCRIPT_MODULE.main(_cli(works, abstracts, "--send"), opener=opener)
    out = capsys.readouterr().out
    assert code == 0
    assert opener.requests == []
    assert f"{API_KEY_ENV} is not set; digest not sent (no-op)." in out


def test_zero_new_works_skips_the_send_and_logs_it(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(API_KEY_ENV, KEY)
    works, abstracts = _write_inputs(tmp_path, [work("W1", "2026-10-01T00:00:00+00:00")])
    opener = FakeOpener()
    code = SCRIPT_MODULE.main(_cli(works, abstracts, "--send"), opener=opener)
    out = capsys.readouterr().out
    assert code == 0
    assert opener.requests == []
    assert "No new plastic-related works this week; digest not sent." in out


def test_send_prints_success_without_the_key(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(API_KEY_ENV, KEY)
    works, abstracts = _write_inputs(tmp_path, [work("W1"), work("W2")], {"W1": "Abstract."})
    opener = FakeOpener(FakeResponse({"id": "em_77"}), FakeResponse({}))
    code = SCRIPT_MODULE.main(_cli(works, abstracts, "--send"), opener=opener)
    captured = capsys.readouterr()
    assert code == 0
    assert "Sent digest email em_77: 2 new works, 2 listed." in captured.out
    assert len(opener.requests) == 2
    assert KEY not in captured.out + captured.err


def test_send_failure_exits_one_and_hides_the_key(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(API_KEY_ENV, KEY)
    works, abstracts = _write_inputs(tmp_path, [work("W1")])
    error = urllib.error.HTTPError(
        "https://api.buttondown.com/v1/emails", 401, "Unauthorized", {}, io.BytesIO(b"")
    )
    code = SCRIPT_MODULE.main(_cli(works, abstracts, "--send"), opener=FakeOpener(error))
    captured = capsys.readouterr()
    assert code == 1
    assert "digest not sent" in captured.err
    assert KEY not in captured.out + captured.err


def test_dry_run_prints_the_request_without_the_key_or_a_send(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(API_KEY_ENV, KEY)
    works, abstracts = _write_inputs(tmp_path, [work("W1")])
    opener = FakeOpener()
    code = SCRIPT_MODULE.main(_cli(works, abstracts, "--dry-run"), opener=opener)
    out = capsys.readouterr().out
    assert code == 0
    assert opener.requests == []
    assert f"Authorization: Token <{API_KEY_ENV}>" in out
    assert "X-Idempotency-Key: atlas-digest-2026-11-15" in out
    assert KEY not in out


def test_dry_run_needs_no_key(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    works, abstracts = _write_inputs(tmp_path, [work("W1")])
    assert SCRIPT_MODULE.main(_cli(works, abstracts, "--dry-run")) == 0
    assert "Dry run: nothing was sent" in capsys.readouterr().out


def test_out_writes_html_and_text_previews(tmp_path, capsys):
    works, abstracts = _write_inputs(tmp_path, [work("W1")], {"W1": "An abstract."})
    out_dir = tmp_path / "preview"
    assert SCRIPT_MODULE.main(_cli(works, abstracts, "--out", str(out_dir))) == 0
    html_body = (out_dir / "digest.html").read_text(encoding="utf-8")
    text_body = (out_dir / "digest.txt").read_text(encoding="utf-8")
    assert html_body.startswith("<!DOCTYPE html>")
    assert "An abstract." in html_body
    assert "Created by Scott Coffin." in text_body


# Settings and workflow -------------------------------------------------------------------


def test_config_digest_block_is_loaded():
    settings = load_settings(CONFIG)
    assert settings.site_url == "https://plastiverse.live/california"
    assert settings.max_works == 40
    assert settings.sender_name == "Plastiverse · California"
    assert settings.ntfy_url == "https://ntfy.sh/plastiverse-california"
    assert "{start}" in settings.subject_template


@pytest.mark.parametrize(
    "block",
    [
        "site_url: http://example.org\nmax_works: 40\nsubject_template: 'x {start}'\n"
        "sender_name: S",
        "site_url: https://example.org\nmax_works: 0\nsubject_template: 'x {start}'\n"
        "sender_name: S",
        "site_url: https://example.org\nmax_works: 40\nsubject_template: 'x {other}'\n"
        "sender_name: S",
        "site_url: https://example.org\nmax_works: 40\nsubject_template: 'no field'\n"
        "sender_name: S",
    ],
)
def test_bad_digest_settings_are_rejected(tmp_path, block):
    config = tmp_path / "notifications.yml"
    config.write_text("digest:\n  " + block.replace("\n", "\n  ") + "\n", encoding="utf-8")
    with pytest.raises(DigestError):
        load_settings(config)


def test_topic_table_matches_the_site_palette():
    text = TOPICS_JS.read_text(encoding="utf-8")
    site = {
        key: (label, colour)
        for key, label, colour in re.findall(
            r'(\w+):\s*\{\s*label:\s*"([^"]+)",\s*color:\s*"(#[0-9a-fA-F]{6})"', text
        )
    }
    assert set(TOPIC_STYLE) <= set(site)
    for key, (label, colour) in TOPIC_STYLE.items():
        assert (site[key][0], site[key][1].lower()) == (label, colour), key


def test_workflow_schedules_monday_and_sends_only_with_the_secret():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = data.get(True) or data.get("on")  # PyYAML reads the bare key "on" as True
    crons = [entry["cron"] for entry in triggers["schedule"]]
    assert crons == ["0 14 * * 1"]
    assert "week_ending" in triggers["workflow_dispatch"]["inputs"]
    steps = data["jobs"]["digest"]["steps"]
    gate = next(step for step in steps if step.get("id") == "secret")
    assert "secrets.BUTTONDOWN_API_KEY" in gate["env"]["BUTTONDOWN_API_KEY"]
    send = next(step for step in steps if step.get("name") == "Send the digest")
    assert send["if"] == "steps.secret.outputs.ready == 'true'"
    assert "--send" in send["run"]
    assert data["permissions"] == {"contents": "read"}
    setup = next(step for step in steps if step.get("name") == "Set up Python")
    assert setup["with"]["python-version"] == "3.11"
