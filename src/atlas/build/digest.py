"""Weekly email digest of newly added California plastics papers (MAIL-1).

The digest lists the plastic-related works in ``site/data/works_detail.json`` whose
``first_seen`` falls in one Monday-to-Sunday week (UTC) and whose ``pub_date`` is recent
(``digest.max_age_days``, default 60). ``first_seen`` is the fetch time of the raw snapshot, so a
full re-ingest resets it for old papers; the publication-date window keeps those out. Abstracts
come from
``site/data/work_text/abstracts.json``. The module renders an email-safe HTML body (table
layout, inline CSS, Plane Poster colours) and a plain-text copy for previews.

``send_digest`` posts the HTML to the Buttondown API: it creates a draft, then publishes it.
The API key is passed in by the script, which reads ``BUTTONDOWN_API_KEY`` from the
environment. Nothing here prints or logs the key. Stdlib plus PyYAML.
"""

from __future__ import annotations

import html
import http.client
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = ROOT / "config" / "notifications.yml"
# A work counts as new only when published within this many days of the week's end.
DEFAULT_MAX_AGE_DAYS = 60
DEFAULT_WORKS = ROOT / "site" / "data" / "works_detail.json"
DEFAULT_ABSTRACTS = ROOT / "site" / "data" / "work_text" / "abstracts.json"

BUTTONDOWN_API = "https://api.buttondown.com/v1"
API_KEY_ENV = "BUTTONDOWN_API_KEY"
USER_AGENT = "ca-plastics-research-atlas-digest"
TIMEOUT_SECONDS = 30
# Buttondown reads this first-line comment as "render the body as HTML" (fancy editor mode).
EDITOR_MODE = "<!-- buttondown-editor-mode: fancy -->"
# Buttondown merge tag for the unsubscribe link. Not found in the Buttondown API docs read on
# 2026-11-17; verify with a test send before the first live send (docs/api_notes/buttondown.md).
UNSUBSCRIBE_TAG = "{{ unsubscribe_url }}"
OPENALEX_WORK = "https://openalex.org/"
ABSTRACT_MAX_CHARS = 700
AUTHORS_SHOWN = 3
WORK_ID = re.compile(r"W[0-9]+")
Opener = Callable[..., Any]

# Plane Poster tokens (framework/src/design/tokens.css).
PAPER = "#ece7dc"
SURFACE = "#f6f3ec"
INK = "#141311"
TEXT = "#1f1d1a"
MUTED = "#4b463e"
INDIGO = "#23305e"
VERMILION = "#e2452b"
GOLD = "#e3a92b"
ON_BRAND_MUTED = "#cfcabd"
FONT = "Archivo, 'Helvetica Neue', Arial, sans-serif"

# Topic labels and hues, copied from framework/src/components/shared/topics.js. The test suite
# checks this table against that file.
TOPIC_STYLE: dict[str, tuple[str, str]] = {
    "occurrence_and_monitoring": ("Occurrence & monitoring", "#2a78d6"),
    "fate_transport_and_sorption": ("Fate & transport", "#eb6834"),
    "soil_and_agriculture": ("Soil & agriculture", "#1baf7a"),
    "analytical_methods": ("Analytical methods", "#eda100"),
    "ecotoxicology_and_trophic_transfer": ("Ecotoxicology & food webs", "#e87ba4"),
    "wastewater_and_treatment": ("Wastewater & treatment", "#008300"),
    "human_exposure_and_health_risk": ("Human exposure & health", "#6250d6"),
    "air": ("Air & atmosphere", "#e34948"),
    "risk_assessment": ("Risk assessment", "#6250d6"),
    "plastisphere": ("Plastisphere", "#e87ba4"),
    "plastic_associated_chemicals": ("Plastic-associated chemicals", "#6f7b82"),
}


class DigestError(RuntimeError):
    """A configuration, data or API problem that stops the digest. Messages never hold the key."""


@dataclass(frozen=True)
class DigestSettings:
    site_url: str
    max_works: int
    subject_template: str
    sender_name: str
    ntfy_url: str = ""
    max_age_days: int = DEFAULT_MAX_AGE_DAYS


@dataclass(frozen=True)
class Topic:
    label: str
    colour: str


@dataclass(frozen=True)
class WorkCard:
    title: str
    url: str
    authors: str
    journal: str
    year: str
    topics: tuple[Topic, ...]
    rule: str
    abstract: str


@dataclass(frozen=True)
class Digest:
    week_start: date
    week_end: date
    total: int
    cards: tuple[WorkCard, ...]

    @property
    def hidden(self) -> int:
        return self.total - len(self.cards)


# Dates and windows -----------------------------------------------------------------------


def last_sunday(today: date) -> date:
    """The most recent Sunday on or before ``today`` (a Sunday returns itself)."""
    return today - timedelta(days=(today.weekday() + 1) % 7)


def parse_week_ending(text: str) -> date:
    """Parse ``YYYY-MM-DD``; raise ValueError unless it is a Sunday."""
    day = date.fromisoformat(text.strip())
    if day.weekday() != 6:
        raise ValueError("week ending must be a Sunday (YYYY-MM-DD)")
    return day


def week_window(week_ending: date) -> tuple[datetime, datetime]:
    """Monday 00:00 UTC through Sunday 23:59:59.999999 UTC, as [start, end) datetimes."""
    start = datetime.combine(week_ending - timedelta(days=6), time(0), tzinfo=UTC)
    end = datetime.combine(week_ending + timedelta(days=1), time(0), tzinfo=UTC)
    return start, end


def parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO timestamp as UTC. Naive values are read as UTC; bad values give None."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def week_label(start: date, end: date) -> str:
    """'9–15 November 2026', or the same with the months and years that differ."""
    if start.year == end.year and start.month == end.month:
        return f"{start.day}–{end.day} {end:%B %Y}"
    if start.year == end.year:
        return f"{start.day} {start:%B} – {end.day} {end:%B %Y}"
    return f"{start.day} {start:%B %Y} – {end.day} {end:%B %Y}"


# Selection -------------------------------------------------------------------------------


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def _year(row: Mapping[str, Any]) -> int:
    year = row.get("year")
    return year if isinstance(year, int) and not isinstance(year, bool) else 0


def parse_pub_date(value: Any) -> date | None:
    """``YYYY-MM-DD`` (or a longer ISO string) as a date; None when missing or unreadable."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def select_new_works(
    rows: Sequence[Mapping[str, Any]],
    start: datetime,
    end: datetime,
    *,
    max_age_days: int | None = None,
) -> list[Mapping[str, Any]]:
    """Plastic-related works with ``start <= first_seen < end``, newest first.

    With ``max_age_days``, a work must also have a ``pub_date`` no more than that many days
    before the window's end; rows without a readable ``pub_date`` are then left out. This stops a
    re-ingest, which resets ``first_seen``, from listing old papers as new.

    Ties on ``first_seen`` break by year (newest first), then title and work_id, so the order is
    stable. Rows without a usable ``first_seen`` or a ``work_id`` are left out.
    """
    cutoff = end.date() - timedelta(days=max_age_days) if max_age_days is not None else None
    fresh: list[tuple[datetime, Mapping[str, Any]]] = []
    for row in rows:
        if row.get("plastic_related") is not True or not row.get("work_id"):
            continue
        if cutoff is not None:
            published = parse_pub_date(row.get("pub_date"))
            if published is None or published < cutoff:
                continue
        seen = parse_timestamp(row.get("first_seen"))
        if seen is not None and start <= seen < end:
            fresh.append((seen, row))
    fresh.sort(
        key=lambda pair: (
            -pair[0].timestamp(),
            -_year(pair[1]),
            _clean(pair[1].get("title")).casefold(),
            str(pair[1]["work_id"]),
        )
    )
    return [row for _, row in fresh]


# Cards -----------------------------------------------------------------------------------


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return cut + "…"


def _authors(value: Any) -> str:
    """First three names, then 'et al.' when there are more."""
    if not isinstance(value, list):
        return ""
    names = [_clean(name) for name in value if _clean(name)]
    if not names:
        return ""
    return ", ".join(names[:AUTHORS_SHOWN]) + (" et al." if len(names) > AUTHORS_SHOWN else "")


def _topics(value: Any) -> tuple[Topic, ...]:
    tags = [str(tag) for tag in value] if isinstance(value, list) else []
    topics = []
    for tag in tags:
        if tag in TOPIC_STYLE:
            label, colour = TOPIC_STYLE[tag]
        else:
            label, colour = tag.replace("_", " ").replace(":", " ").strip(), INK
        topics.append(Topic(label=label, colour=colour))
    return tuple(topics)


def _work_url(row: Mapping[str, Any], work_id: str, fallback: str) -> str:
    """The DOI when there is one, else the OpenAlex work page, else the site."""
    doi = _clean(row.get("doi"))
    if doi.startswith("https://"):
        return doi
    if WORK_ID.fullmatch(work_id):
        return OPENALEX_WORK + work_id
    return fallback


def _card(row: Mapping[str, Any], abstracts: Mapping[str, str], fallback_url: str) -> WorkCard:
    work_id = _clean(row.get("work_id"))
    topics = _topics(row.get("domain_tags"))
    year = _year(row)
    abstract = _clean(abstracts.get(work_id))
    return WorkCard(
        title=_clean(row.get("title")) or "Untitled work",
        url=_work_url(row, work_id, fallback_url),
        authors=_authors(row.get("authors")),
        journal=_clean(row.get("journal")),
        year=str(year) if year else "",
        topics=topics,
        # The thin top rule takes the first topic's hue; untagged works get the plane ink.
        rule=topics[0].colour if topics else INK,
        abstract=_shorten(abstract, ABSTRACT_MAX_CHARS) if abstract else "",
    )


def build_digest(
    works: Sequence[Mapping[str, Any]],
    abstracts: Mapping[str, str],
    *,
    week_ending: date,
    max_works: int,
    site_url: str,
    max_age_days: int | None = None,
) -> Digest:
    """Select the week's new works and build at most ``max_works`` cards from them."""
    start, end = week_window(week_ending)
    fresh = select_new_works(works, start, end, max_age_days=max_age_days)
    cards = tuple(_card(row, abstracts, site_url) for row in fresh[:max_works])
    return Digest(week_start=start.date(), week_end=week_ending, total=len(fresh), cards=cards)


# Settings and data files -----------------------------------------------------------------


def _ntfy_url(data: Mapping[str, Any]) -> str:
    block = data.get("ntfy")
    if not isinstance(block, dict):
        return ""
    server = str(block.get("server", "")).strip().rstrip("/")
    topic = str(block.get("topic", "")).strip()
    return f"{server}/{topic}" if server.startswith("https://") and topic else ""


def load_settings(path: Path = DEFAULT_CONFIG) -> DigestSettings:
    """Read the ``digest`` block of config/notifications.yml; raise DigestError when unusable."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise DigestError(f"notification config unreadable: {exc}") from None
    block = data.get("digest") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        raise DigestError("config has no digest block")
    site_url = str(block.get("site_url", "")).strip().rstrip("/")
    if not site_url.startswith("https://"):
        raise DigestError("digest.site_url must be an https URL")
    max_works = block.get("max_works")
    if not isinstance(max_works, int) or isinstance(max_works, bool) or max_works < 1:
        raise DigestError("digest.max_works must be a whole number of at least 1")
    subject = str(block.get("subject_template", "")).strip()
    try:
        subject.format(start="x")
    except (KeyError, IndexError, ValueError):
        raise DigestError("digest.subject_template may use only the {start} field") from None
    if "{start}" not in subject:
        raise DigestError("digest.subject_template must contain {start}")
    sender = str(block.get("sender_name", "")).strip()
    if not sender:
        raise DigestError("digest.sender_name is empty")
    max_age_days = block.get("max_age_days", DEFAULT_MAX_AGE_DAYS)
    if not isinstance(max_age_days, int) or isinstance(max_age_days, bool) or max_age_days < 7:
        raise DigestError("digest.max_age_days must be a whole number of at least 7")
    return DigestSettings(
        site_url=site_url,
        max_works=max_works,
        subject_template=subject,
        sender_name=sender,
        ntfy_url=_ntfy_url(data),
        max_age_days=max_age_days,
    )


def load_works(path: Path = DEFAULT_WORKS) -> list[dict[str, Any]]:
    """The ``works`` rows of works_detail.json; raise DigestError when unreadable."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DigestError(f"works file unreadable ({path.name}): {exc}") from None
    rows = payload.get("works") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise DigestError(f"works file has no works list ({path.name})")
    return [row for row in rows if isinstance(row, dict)]


def load_abstracts(path: Path = DEFAULT_ABSTRACTS) -> dict[str, str]:
    """work_id to abstract text from work_text/abstracts.json; raise DigestError when unreadable."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DigestError(f"abstracts file unreadable ({path.name}): {exc}") from None
    block = payload.get("abstracts") if isinstance(payload, dict) else None
    if not isinstance(block, dict):
        raise DigestError(f"abstracts file has no abstracts map ({path.name})")
    return {str(key): value for key, value in block.items() if isinstance(value, str)}


def feed_url(settings: DigestSettings) -> str:
    return f"{settings.site_url}/feed.xml"


def subject_line(settings: DigestSettings, digest: Digest) -> str:
    start = digest.week_start
    return settings.subject_template.format(start=f"{start.day} {start:%B %Y}")


def _phrase(total: int) -> str:
    """The noun phrase after the count: 'new plastic-related California papers'."""
    return "new plastic-related California " + ("paper" if total == 1 else "papers")


def _headline(total: int) -> str:
    return f"{total:,} {_phrase(total)}"


def _e(text: Any) -> str:
    return html.escape(str(text), quote=True)


# HTML rendering --------------------------------------------------------------------------


def _type(size: int, *, weight: int = 400, colour: str = INK, extra: str = "") -> str:
    return (
        f"font-family:{FONT};font-size:{size}px;font-weight:{weight};"
        f"color:{colour};line-height:1.45;{extra}"
    )


def _mark() -> str:
    """The four-plane square mark as an inline table: indigo, gold over vermilion, ink."""

    def cell(colour: str, height: int) -> str:
        style = f"width:15px;height:{height}px;background:{colour};font-size:1px;line-height:1px;"
        return f'<td width="15" height="{height}" bgcolor="{colour}" style="{style}">&nbsp;</td>'

    return (
        '<table role="presentation" width="30" cellpadding="0" cellspacing="0" border="0" '
        'style="width:30px;border-collapse:collapse;">'
        f"<tr>{cell(INDIGO, 13)}{cell(GOLD, 13)}</tr>"
        f"<tr>{cell(VERMILION, 17)}{cell(INK, 17)}</tr></table>"
    )


def _header(settings: DigestSettings, digest: Digest) -> str:
    label = week_label(digest.week_start, digest.week_end)
    name_style = _type(17, weight=800)
    week_style = _type(14, colour=MUTED)
    return (
        '<tr><td style="padding:22px 0 14px 0;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td valign="middle" width="30" style="width:30px;padding-right:12px;">{_mark()}</td>'
        f'<td valign="middle" style="{name_style}">{_e(settings.sender_name)}'
        f'<br><span style="{week_style}">Week of {_e(label)}</span></td>'
        "</tr></table></td></tr>"
        f'<tr><td style="border-top:2px solid {INK};font-size:0;line-height:0;">&nbsp;</td></tr>'
    )


def _count_block(digest: Digest) -> str:
    label_style = _type(
        12,
        weight=700,
        colour=ON_BRAND_MUTED,
        extra="text-transform:uppercase;letter-spacing:0.12em;",
    )
    number_style = (
        f"font-family:{FONT};font-size:88px;font-weight:800;line-height:1;"
        f"letter-spacing:-0.02em;color:{SURFACE};"
    )
    line_style = _type(18, weight=700, colour=SURFACE, extra="margin-top:10px;")
    if digest.hidden:
        note = f"The {len(digest.cards)} most recent are listed below."
    else:
        note = "All of them are listed below."
    note_style = _type(14, colour=ON_BRAND_MUTED, extra="margin-top:6px;")
    return (
        f'<tr><td bgcolor="{INDIGO}" style="background:{INDIGO};padding:26px 26px 24px 26px;">'
        f'<div style="{label_style}">New this week</div>'
        f'<div style="{number_style}">{digest.total:,}</div>'
        f'<div style="{line_style}">{_e(_phrase(digest.total))}</div>'
        f'<div style="{note_style}">{_e(note)}</div>'
        "</td></tr>"
    )


def _card_html(card: WorkCard) -> str:
    title_style = _type(18, weight=700, extra="text-decoration:underline;")
    meta_style = _type(14, colour=MUTED, extra="margin-top:6px;")
    chip_style = _type(13, colour=MUTED, extra="margin-top:10px;")
    abstract_style = _type(15, colour=TEXT, extra="margin-top:12px;")
    parts = [
        f'<a href="{_e(card.url)}" style="{title_style}">{_e(card.title)}</a>',
    ]
    author_line = " · ".join(text for text in (card.authors, card.journal, card.year) if text)
    if author_line:
        parts.append(f'<div style="{meta_style}">{_e(author_line)}</div>')
    if card.topics:
        chips = "&nbsp;&nbsp;".join(
            f'<span style="color:{topic.colour};">&#9632;</span>&nbsp;{_e(topic.label)}'
            for topic in card.topics
        )
        parts.append(f'<div style="{chip_style}">{chips}</div>')
    if card.abstract:
        parts.append(f'<div style="{abstract_style}">{_e(card.abstract)}</div>')
    body = "".join(parts)
    return (
        '<tr><td style="padding:0 0 14px 0;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;">'
        f'<tr><td style="background:{SURFACE};border-top:3px solid {card.rule};'
        f'padding:16px 20px 18px 20px;">{body}</td></tr></table></td></tr>'
    )


def _button(url: str, label: str) -> str:
    link_style = _type(16, weight=700, colour=SURFACE, extra="text-decoration:none;")
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td bgcolor="{INDIGO}" style="background:{INDIGO};padding:14px 22px;">'
        f'<a href="{_e(url)}" style="{link_style}">{_e(label)}</a></td></tr></table>'
    )


def _footer(settings: DigestSettings) -> str:
    link_style = f"color:{INK};"
    links = [
        f'<a href="{_e(settings.site_url)}" style="{link_style}">Atlas</a>',
        f'<a href="{_e(feed_url(settings))}" style="{link_style}">Feed</a>',
    ]
    if settings.ntfy_url:
        links.append(f'<a href="{_e(settings.ntfy_url)}" style="{link_style}">Phone alerts</a>')
    return (
        '<tr><td style="border-top:2px solid '
        f'{INK};padding:18px 0 0 0;{_type(13, colour=MUTED)}">'
        f'<strong style="color:{INK};">Created by Scott Coffin.</strong><br>'
        + " &nbsp;·&nbsp; ".join(links)
        + "<br><br>You get this digest because you subscribed. "
        + f'<a href="{UNSUBSCRIBE_TAG}" style="{link_style}">Unsubscribe</a>.'
        + "</td></tr>"
    )


def render_html(digest: Digest, settings: DigestSettings) -> str:
    """The digest as a standalone HTML document (table layout, inline CSS, 640 px wide)."""
    label = week_label(digest.week_start, digest.week_end)
    preheader = f"{_headline(digest.total)}, week of {label}."
    rows = [
        _header(settings, digest),
        _count_block(digest),
        '<tr><td style="height:24px;"></td></tr>',
    ]
    heading_style = _type(22, weight=800, extra="padding:0 0 12px 0;")
    rows.append(f'<tr><td style="{heading_style}">New papers</td></tr>')
    if digest.cards:
        rows.extend(_card_html(card) for card in digest.cards)
    else:
        empty_style = _type(15, colour=MUTED)
        rows.append(f'<tr><td style="{empty_style}">No new papers were added this week.</td></tr>')
    if digest.hidden:
        more_style = _type(15, extra="padding:4px 0 22px 0;")
        more_link = f'<a href="{_e(settings.site_url)}" style="color:{INDIGO};font-weight:700;">'
        rows.append(
            f'<tr><td style="{more_style}">and {digest.hidden:,} more on the site. '
            f"{more_link}See them all</a>.</td></tr>"
        )
    button = _button(settings.site_url, "Open the Atlas")
    rows.append(f'<tr><td style="padding:8px 0 28px 0;">{button}</td></tr>')
    rows.append(_footer(settings))
    title = _e(subject_line(settings, digest))
    preheader_style = (
        f"display:none;max-height:0;overflow:hidden;mso-hide:all;opacity:0;color:{PAPER};"
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light">\n'
        f"<title>{title}</title>\n</head>\n"
        f'<body style="margin:0;padding:0;background:{PAPER};">\n'
        f'<div style="{preheader_style}">{_e(preheader)}</div>\n'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'bgcolor="{PAPER}" style="background:{PAPER};">\n'
        '<tr><td align="center" style="padding:8px 12px 32px 12px;">\n'
        '<table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" '
        'style="width:100%;max-width:640px;">\n'
        + "\n".join(rows)
        + "\n</table>\n</td></tr>\n</table>\n</body>\n</html>\n"
    )


# Plain text ------------------------------------------------------------------------------


def render_text(digest: Digest, settings: DigestSettings) -> str:
    """The plain-text copy of the digest. Used for previews; the API takes one HTML body."""
    lines = [
        settings.sender_name,
        f"Week of {week_label(digest.week_start, digest.week_end)}",
        "",
        _headline(digest.total) + ".",
        "",
    ]
    if not digest.cards:
        lines += ["No new papers were added this week.", ""]
    for number, card in enumerate(digest.cards, start=1):
        lines.append(f"{number}. {card.title}")
        for text in (
            card.authors,
            " · ".join(part for part in (card.journal, card.year) if part),
        ):
            if text:
                lines.append(f"   {text}")
        if card.topics:
            lines.append("   Topics: " + ", ".join(topic.label for topic in card.topics))
        lines.append(f"   {card.url}")
        if card.abstract:
            lines.append(f"   {card.abstract}")
        lines.append("")
    if digest.hidden:
        lines += [f"and {digest.hidden:,} more on the site: {settings.site_url}", ""]
    lines.append(f"Open the Atlas: {settings.site_url}")
    lines.append(f"Feed: {feed_url(settings)}")
    if settings.ntfy_url:
        lines.append(f"Phone alerts: {settings.ntfy_url}")
    lines += ["", "Created by Scott Coffin.", f"Unsubscribe: {UNSUBSCRIBE_TAG}", ""]
    return "\n".join(lines)


# Buttondown ------------------------------------------------------------------------------


def idempotency_key(week_ending: date) -> str:
    """One key per digest week, so a repeated run cannot create a second draft."""
    return f"atlas-digest-{week_ending.isoformat()}"


def email_payload(subject: str, html_body: str) -> dict[str, str]:
    """The POST /v1/emails body. ``naked`` uses our HTML as the whole email."""
    return {"subject": subject, "body": EDITOR_MODE + html_body, "template": "naked"}


def _error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError, AttributeError):
        return ""
    detail = body.get("detail") if isinstance(body, dict) else None
    return f": {str(detail)[:200]}" if detail else ""


def _post_json(
    url: str,
    api_key: str,
    payload: Mapping[str, Any],
    extra_headers: Mapping[str, str],
    opener: Opener | None,
) -> Any:
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        **extra_headers,
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=TIMEOUT_SECONDS) as response:
            status = int(getattr(response, "status", 200))
            raw = response.read()
    except urllib.error.HTTPError as exc:  # HTTPError is an OSError, so it comes first
        raise DigestError(f"Buttondown returned HTTP {exc.code}{_error_detail(exc)}") from None
    except (OSError, http.client.HTTPException) as exc:
        raise DigestError(f"Buttondown request failed ({type(exc).__name__})") from None
    if not 200 <= status < 300:
        raise DigestError(f"Buttondown returned HTTP {status}")
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except ValueError:
        return {}


def send_digest(
    *,
    api_key: str,
    subject: str,
    html_body: str,
    idempotency: str,
    opener: Opener | None = None,
) -> str:
    """Create the email as a draft, then publish it to subscribers; return the email id.

    A failed publish raises DigestError and names the draft id, so the owner can publish it
    from the Buttondown app.
    """
    created = _post_json(
        f"{BUTTONDOWN_API}/emails",
        api_key,
        email_payload(subject, html_body),
        {"X-Idempotency-Key": idempotency},
        opener,
    )
    email_id = created.get("id") if isinstance(created, dict) else None
    if not isinstance(email_id, str) or not email_id:
        raise DigestError("Buttondown did not return an email id")
    try:
        _post_json(f"{BUTTONDOWN_API}/emails/{email_id}/publish", api_key, {}, {}, opener)
    except DigestError as exc:
        raise DigestError(f"draft {email_id} was created but not published ({exc})") from None
    return email_id
