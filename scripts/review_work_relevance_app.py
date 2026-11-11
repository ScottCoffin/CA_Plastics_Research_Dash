"""Local Streamlit app for owner review of Haiku's work relevance calls (v3.1 corpus, S11.3).

Run from the repository root:

    py -3.14 -m streamlit run scripts/review_work_relevance_app.py

Pass ``-- --csv PATH`` to review a different copy of the CSV. Each decision writes
straight to curation/work_relevance.csv (atomic save). Work details are read
from the local data/interim/works_raw.parquet and only displayed here. Nothing
is sent anywhere. After review, run ``py -3.14 scripts/build_export_site.py`` to
refresh site/data (the daily ingest also re-exports with the committed CSV).

Haiku's suggestion is kept in ``assist_plastic_related``. Confirm and Not
plastic-related set ``plastic_related`` to the owner's choice, and ``owner_review``
records whether it matches Haiku. Reset to pending restores Haiku's value. Unsure
sets ``owner_review`` to ``unsure`` and puts ``plastic_related`` back to Haiku's value,
so the export uses Haiku's value for skipped works.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.work_relevance_review import (  # noqa: E402
    REVIEW_CSV,
    VIEWS,
    WORKS_PARQUET,
    haiku_value,
    in_view,
    load_work_details,
    load_work_reviews,
    merged_view,
    record_decision,
    reset_to_pending,
    save_work_reviews,
    select_view,
)


def _csv_path() -> Path:
    """``-- --csv PATH`` (a copy of the CSV), else the committed curation file."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--csv", default="")
    args, _ = parser.parse_known_args()
    path = Path(args.csv or str(REVIEW_CSV))
    return path if path.is_absolute() else ROOT / path


CSV_PATH = _csv_path()
WORKS_PATH = ROOT / WORKS_PARQUET
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
    work_id: str,
    item: dict[str, Any],
    plastic_related: bool | None,
    reviewer: str,
    note: str,
    view: str,
    search: str,
) -> None:
    table = load_work_reviews(CSV_PATH)  # reload so edits made elsewhere are not lost
    record_decision(table, work_id, plastic_related, reviewer, note)
    save_work_reviews(table, CSV_PATH)
    current = next(row for row in table.rows if row["work_id"] == work_id)
    revisiting = st.session_state.get("focus_key") == work_id
    st.session_state.focus_key = None
    history = st.session_state.setdefault("history", [])
    if not history or history[-1] != work_id:
        history.append(work_id)
    # A decision that moves the work out of the current view lets the next work slide
    # into this position, so advancing would skip one. A revisited work returns to the queue.
    still_shown = in_view({**item, **current}, view, search)
    if still_shown and not revisiting and st.session_state.get("auto_advance", True):
        st.session_state.position += 1
    st.rerun()


def _reset(work_id: str) -> None:
    table = load_work_reviews(CSV_PATH)
    reset_to_pending(table, work_id)
    save_work_reviews(table, CSV_PATH)
    st.session_state.focus_key = None
    st.rerun()


def _go(delta: int) -> None:
    st.session_state.focus_key = None
    st.session_state.position += delta
    st.rerun()


def _facts(item: dict[str, Any]) -> str:
    rows = {
        "Year / type": " · ".join(str(v) for v in (item.get("year"), item.get("type")) if v),
        "Journal": item.get("journal"),
        "Authors": item.get("authors"),
        "Institutions": item.get("institutions"),
        "Cited by": item.get("cited_by_count"),
    }
    return "  \n".join(f"**{label}:** {value or 'unknown'}" for label, value in rows.items())


def main() -> None:
    st.set_page_config(page_title="Atlas work relevance review", layout="wide")
    st.markdown("### Work relevance (v3.1): is plastic a central subject of this work?")
    table = load_work_reviews(CSV_PATH)
    details = load_work_details(WORKS_PATH)
    items: list[dict[str, Any]] = []
    for item in merged_view(table.rows, details):
        items.append({**item, "haiku": haiku_value(item)})
    by_key = {str(item["work_id"]): item for item in items}
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("focus_key", None)
    st.session_state.setdefault("position", 0)

    with st.sidebar:
        reviewer = st.text_input("Your initials (required)", value=st.session_state.get("rev", ""))
        st.session_state.rev = reviewer
        st.session_state.auto_advance = st.checkbox("Advance after deciding", value=True)
        view = st.selectbox("Show", VIEWS, index=0)
        search = st.text_input("Search title / abstract / authors / institutions / work ID").strip()
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
            st.caption(f"Work details: {len(details)} loaded")
        else:
            st.caption("Works file missing: showing CSV fields only.")

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
    work_id = str(item["work_id"])
    state = str(item["owner_review"])

    # Fixed control band: everything above the variable-length text, so the buttons
    # sit in the same place for every work.
    nav = st.columns([1, 1.3, 1.7, 1])
    at_start = focus is None and position == 0
    if nav[0].button("◀ Previous", use_container_width=True, disabled=at_start):
        _go(0 if focus else -1)
    if nav[1].button(
        "↩ Back to last reviewed",
        use_container_width=True,
        disabled=not st.session_state.history,
        help="Reopen the work you decided most recently (repeat to step further back).",
    ):
        st.session_state.focus_key = st.session_state.history.pop()
        st.rerun()
    nav[2].markdown(
        "Revisiting a reviewed work"
        if focus
        else f"Work **{position + 1}** of **{len(shown)}** in this view"
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
        "Unsure (skip) leaves the export on Haiku's value for this work; "
        "Reset to pending restores Haiku's value."
    )

    note = st.text_input("Owner note (optional)", key=f"note_{work_id}")
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
                _record(work_id, item, value, reviewer, note, view, search)
    if buttons[3].button(
        "Reset to pending",
        key="reset_pending",
        use_container_width=True,
        disabled=state == "pending",
        help="Return this work to the pending queue. The current plastic-related value is kept.",
    ):
        _reset(work_id)
    st.divider()

    st.subheader(item.get("title") or "(no title)")
    st.markdown(_facts(item))
    links = st.columns(2)
    if item.get("doi"):
        links[0].link_button("Open DOI", str(item["doi"]), use_container_width=True)
    if item.get("url"):
        links[1].link_button("Open in OpenAlex", str(item["url"]), use_container_width=True)
    st.markdown("**Abstract**")
    st.write(item.get("abstract") or "_No abstract in OpenAlex for this work._")

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
