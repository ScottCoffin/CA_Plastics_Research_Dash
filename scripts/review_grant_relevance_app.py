"""Local Streamlit app for owner review of Haiku's grant relevance suggestions (S11.3).

Run from the repository root:

    py -3.14 -m streamlit run scripts/review_grant_relevance_app.py

Pass ``-- --csv PATH`` to review a different copy of the CSV. Each decision writes
straight to curation/grant_relevance.csv (atomic save). Grant details are read
from the local data/interim/grants/grants_merged.parquet when it exists and are
only displayed here; abstracts are never printed or committed. Nothing is sent
anywhere. After review, run ``py -3.14 scripts/build_grants_export.py`` to
refresh site/data/grants.json.

Haiku's suggestion is kept in ``assist_plastic_related``. Confirm and Not
plastic-related set ``plastic_related`` to the owner's choice, and ``owner_review``
records whether it matches Haiku. Reset to pending restores Haiku's value. Unsure
sets ``owner_review`` to ``unsure`` and puts ``plastic_related`` back to Haiku's value,
so the export uses Haiku's value for skipped grants.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas import review_highlight as hl  # noqa: E402
from atlas.grant_relevance_review import (  # noqa: E402
    GRANTS_PARQUET,
    REVIEW_CSV,
    VIEWS,
    format_amount,
    format_years,
    haiku_value,
    in_view,
    load_grant_details,
    load_grant_reviews,
    merged_view,
    record_decision,
    reset_to_pending,
    save_grant_reviews,
    select_view,
)
from atlas.ingest.grants.ca_sea_grant import KEYWORDS as CA_SEA_GRANT_KEYWORDS  # noqa: E402
from atlas.ingest.grants.faast import KEYWORDS as FAAST_KEYWORDS  # noqa: E402
from atlas.ingest.grants.normalize import (  # noqa: E402
    STRONG_ABSTRACT_RE,
    grant_plastic_decision,
)
from atlas.ingest.grants.usaspending import USASPENDING_TERMS  # noqa: E402
from atlas.query import load_query_config  # noqa: E402


@st.cache_resource(show_spinner=False)
def _highlight_rules() -> list[hl.Rule]:
    """Search terms that admitted a record (see atlas.review_highlight)."""
    return hl.build_rules(
        [load_query_config(ROOT / "config" / "queries.yml")],
        extra=[
            hl.regex_rule("core", "strong abstract term", STRONG_ABSTRACT_RE),
            *hl.keyword_rules((*CA_SEA_GRANT_KEYWORDS, *FAAST_KEYWORDS, *USASPENDING_TERMS)),
        ],
    )


def _show_record(title: object, abstract: object, *, empty: str) -> str:
    """Title and abstract with the admitting search terms highlighted."""
    blocks = hl.record_blocks(
        str(title) if title else None,
        str(abstract) if abstract else None,
        _highlight_rules(),
        empty=empty,
    )
    st.html(blocks.title)
    st.html(blocks.summary)
    with st.expander("Highlight legend"):
        st.html(hl.legend_html())
    return blocks.abstract


def _csv_path() -> Path:
    """``-- --csv PATH`` (a copy of the CSV), else the committed curation file."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--csv", default="")
    args, _ = parser.parse_known_args()
    path = Path(args.csv or str(REVIEW_CSV))
    return path if path.is_absolute() else ROOT / path


CSV_PATH = _csv_path()
GRANTS_PATH = ROOT / GRANTS_PARQUET
OWNER_STATES = {
    "pending": "Pending",
    "confirmed": "Owner confirmed Haiku",
    "changed": "Owner changed Haiku",
    "unsure": "Owner unsure (skipped)",
}
POSITIVE = ("#0f766e", "#ecfdf5")
NEGATIVE = ("#b91c1c", "#fef2f2")
CAUTION = ("#a16207", "#fffbeb")
NEUTRAL = ("#475569", "#f8fafc")


def _badge(text: str, colours: tuple[str, str]) -> str:
    fg, bg = colours
    return (
        f'<span style="display:inline-block;padding:0.2rem 0.55rem;border-radius:0.35rem;'
        f'border:1px solid {fg};background:{bg};color:{fg};font-weight:700;">{text}</span>'
    )


def _suggestion_badge(item: dict[str, Any]) -> str:
    suggested = bool(item["haiku"])
    text = (
        f"Haiku: {'plastic-related' if suggested else 'not plastic-related'}"
        f" ({item['confidence']} confidence)"
    )
    if item["confidence"] == "low":
        colours = CAUTION
    else:
        colours = POSITIVE if suggested else NEGATIVE
    return _badge(text, colours)


def _record(
    grant_key: str,
    item: dict[str, Any],
    plastic_related: bool | None,
    reviewer: str,
    note: str,
    view: str,
    search: str,
) -> None:
    table = load_grant_reviews(CSV_PATH)  # reload so edits made elsewhere are not lost
    record_decision(table, grant_key, plastic_related, reviewer, note)
    save_grant_reviews(table, CSV_PATH)
    current = next(row for row in table.rows if row["grant_key"] == grant_key)
    revisiting = st.session_state.get("focus_key") == grant_key
    st.session_state.focus_key = None
    history = st.session_state.setdefault("history", [])
    if not history or history[-1] != grant_key:
        history.append(grant_key)
    # A decision that moves the grant out of the current view lets the next grant slide
    # into this position, so advancing would skip one. A revisited grant returns to the queue.
    still_shown = in_view({**item, **current}, view, search)
    if still_shown and not revisiting and st.session_state.get("auto_advance", True):
        st.session_state.position += 1
    st.rerun()


def _reset(grant_key: str) -> None:
    table = load_grant_reviews(CSV_PATH)
    reset_to_pending(table, grant_key)
    save_grant_reviews(table, CSV_PATH)
    st.session_state.focus_key = None
    st.rerun()


def _go(delta: int) -> None:
    st.session_state.focus_key = None
    st.session_state.position += delta
    st.rerun()


def _facts(item: dict[str, Any]) -> str:
    funder = " / ".join(part for part in (item.get("funder"), item.get("program")) if part)
    years = format_years(item.get("start"), item.get("end"))
    amount = format_amount(item.get("amount"), item.get("currency"))
    rows = {
        "Funder / program": funder,
        "Organisation": item.get("org"),
        "PIs": item.get("pi_names"),
        "Years": years,
        "Amount": amount,
    }
    return "  \n".join(f"**{label}:** {value or 'unknown'}" for label, value in rows.items())


def main() -> None:
    st.set_page_config(page_title="Atlas grant relevance review", layout="wide")
    st.markdown("### Grant relevance: is this grant about plastic pollution?")
    table = load_grant_reviews(CSV_PATH)
    details = load_grant_details(GRANTS_PATH)
    try:
        query_config = load_query_config(ROOT / "config" / "queries.yml")
    except Exception:  # noqa: BLE001 - the app still works without the rule view
        query_config = None
    items: list[dict[str, Any]] = []
    for item in merged_view(table.rows, details):
        basis = ""
        if query_config is not None:
            _value, basis = grant_plastic_decision(
                item.get("title"), item.get("abstract"), query_config, owner_reviewed=frozenset()
            )
        items.append({**item, "haiku": haiku_value(item), "rule_basis": basis})
    by_key = {str(item["grant_key"]): item for item in items}
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("focus_key", None)
    st.session_state.setdefault("position", 0)

    with st.sidebar:
        reviewer = st.text_input("Your initials (required)", value=st.session_state.get("rev", ""))
        st.session_state.rev = reviewer
        st.session_state.auto_advance = st.checkbox("Advance after deciding", value=True)
        view = st.selectbox("Show", VIEWS, index=0)
        search = st.text_input("Search title / abstract / org / PI / grant key").strip()
        counts = table.counts()
        total = len(table.rows)
        reviewed = counts["confirmed"] + counts["changed"]
        low_pending = sum(1 for item in items if in_view(item, "Low confidence pending"))
        st.divider()
        st.metric("Owner-reviewed", f"{reviewed} / {total}")
        st.progress(reviewed / total if total else 1.0)
        st.write(f"Pending: **{counts['pending']}** (low confidence: **{low_pending}**)")
        st.write(f"Owner confirmed: **{counts['confirmed']}**")
        st.write(f"Owner changed: **{counts['changed']}**")
        st.write(f"Owner unsure: **{counts['unsure']}**")
        st.caption(f"Saving to {CSV_PATH}")
        if details:
            st.caption(f"Grant details: {len(details)} loaded")
        else:
            st.caption("Grant details file missing: showing CSV fields only.")

    shown = select_view(items, view, search)
    signature = f"{view}|{search}"
    if st.session_state.get("signature") != signature:
        st.session_state.signature = signature
        st.session_state.position = 0
    focus = st.session_state.focus_key
    if focus not in by_key:
        focus = st.session_state.focus_key = None
    if not shown and focus is None:
        st.success("Nothing left in this view. Switch 'Show' to All to revisit decisions.")
        if st.session_state.history and st.button("↩ Back to last reviewed"):
            st.session_state.focus_key = st.session_state.history.pop()
            st.rerun()
        return
    if shown:
        st.session_state.position = min(max(st.session_state.position, 0), len(shown) - 1)
    position = st.session_state.position
    item = by_key[focus] if focus else shown[position]
    grant_key = str(item["grant_key"])
    state = str(item["owner_review"])

    # Fixed control band: everything above the variable-length text, so the buttons
    # sit in the same place for every grant.
    nav = st.columns([1, 1.3, 1.7, 1])
    at_start = focus is None and position == 0
    if nav[0].button("◀ Previous", use_container_width=True, disabled=at_start):
        _go(0 if focus else -1)
    if nav[1].button(
        "↩ Back to last reviewed",
        use_container_width=True,
        disabled=not st.session_state.history,
        help="Reopen the grant you decided most recently (repeat to step further back).",
    ):
        st.session_state.focus_key = st.session_state.history.pop()
        st.rerun()
    nav[2].markdown(
        "Revisiting a reviewed grant"
        if focus
        else f"Grant **{position + 1}** of **{len(shown)}** in this view"
    )
    if nav[3].button(
        "Next ▶", use_container_width=True, disabled=focus is None and position >= len(shown) - 1
    ):
        _go(0 if focus else 1)

    owner_badge = _badge(OWNER_STATES.get(state, state), NEUTRAL)
    st.markdown(f"{_suggestion_badge(item)} &nbsp; {owner_badge}", unsafe_allow_html=True)
    if item.get("reason"):
        st.caption(f"Haiku's reason: {item['reason']}")
    st.caption(
        "Unsure (skip) leaves the export on Haiku's value for this grant; "
        "Reset to pending restores Haiku's value."
    )

    note = st.text_input("Owner note (optional)", key=f"note_{grant_key}")
    buttons = st.columns(4)
    recorded = state in ("confirmed", "changed")
    decisions = (
        ("decide_true", "Plastic-related ✓", True, recorded and item["plastic_related"] == "true"),
        (
            "decide_false",
            "Not plastic-related ✗",
            False,
            recorded and item["plastic_related"] == "false",
        ),
        ("decide_unsure", "Unsure (skip)", None, state == "unsure"),
    )
    for column, (key, text, value, current) in zip(buttons[:3], decisions, strict=True):
        if column.button(
            text,
            key=key,
            use_container_width=True,
            type="primary" if current else "secondary",
        ):
            if not reviewer.strip():
                st.error("Enter your initials in the sidebar first.")
            else:
                _record(grant_key, item, value, reviewer, note, view, search)
    if buttons[3].button(
        "Reset to pending",
        key="reset_pending",
        use_container_width=True,
        disabled=state == "pending",
        help="Return this grant to the pending queue. The current plastic-related value is kept.",
    ):
        _reset(grant_key)
    st.divider()

    abstract_html = _show_record(
        item.get("title"),
        item.get("abstract"),
        empty="No abstract in the grant details file.",
    )
    if item.get("rule_basis") in ("title", "abstract_strong_term"):
        st.caption(
            "Rule: plastic-related by "
            + ("title match" if item["rule_basis"] == "title" else "strong abstract term")
            + " unless you decide otherwise."
        )
    st.markdown(_facts(item))
    if item.get("url"):
        st.link_button("Open grant page", str(item["url"]))
    st.markdown("**Abstract**")
    st.html(abstract_html)

    with st.expander("All fields"):
        st.json(
            {
                key: "" if value is None else str(value)
                for key, value in item.items()
                if key not in ("abstract", "haiku")
            }
        )


if __name__ == "__main__":
    main()
