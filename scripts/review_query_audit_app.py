"""Local Streamlit app for labelling the AT-1 query audit sample.

Run from the repository root:

    py -3.14 -m streamlit run scripts/review_query_audit_app.py

Each click writes straight to docs/QUERY_AUDIT_REVIEW.csv (atomic save). A label
applies to the work, so duplicate rows of the same work_id are labelled together.
Nothing is sent anywhere; the app only reads and writes that CSV.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas import review_highlight as hl  # noqa: E402
from atlas.query import load_query_config  # noqa: E402
from atlas.query_audit_review import (  # noqa: E402
    LABELS,
    REVIEW_CSV,
    load_review,
    save_review,
    set_label,
)


@st.cache_resource(show_spinner=False)
def _highlight_rules() -> list[hl.Rule]:
    """Search terms that admitted a record (see atlas.review_highlight)."""
    return hl.build_rules(
        load_query_config(ROOT / "config" / name)
        for name in ("queries.yml", "queries_v3.yml", "queries_v2.yml")
        if (ROOT / "config" / name).exists()
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
    """``-- --csv PATH`` (e.g. the v3 repeat audit), else ATLAS_REVIEW_CSV, else the default."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--csv", default="")
    args, _ = parser.parse_known_args()
    chosen = args.csv or os.environ.get("ATLAS_REVIEW_CSV") or str(REVIEW_CSV)
    path = Path(chosen)
    return path if path.is_absolute() else ROOT / path


CSV_PATH = _csv_path()
BADGE = {
    "relevant": ("#0f766e", "#ecfdf5"),
    "not_relevant": ("#b91c1c", "#fef2f2"),
    "unsure": ("#a16207", "#fffbeb"),
    "": ("#475569", "#f8fafc"),
}


def _badge(label: str) -> str:
    fg, bg = BADGE.get(label, BADGE[""])
    text = LABELS.get(label, "Unlabeled")
    return (
        f'<span style="display:inline-block;padding:0.2rem 0.55rem;border-radius:0.35rem;'
        f'border:1px solid {fg};background:{bg};color:{fg};font-weight:700;">{text}</span>'
    )


def _record(work_id: str, label: str, reviewer: str, noise: str) -> None:
    table = load_review(CSV_PATH)  # reload so edits made elsewhere are not lost
    set_label(table, work_id, label, reviewer, noise)
    save_review(table, CSV_PATH)
    revisiting = st.session_state.get("focus_work") == work_id
    st.session_state.focus_work = None
    if label:
        history = st.session_state.setdefault("history", [])
        if not history or history[-1] != work_id:
            history.append(work_id)
    # In the Unlabeled view the labelled work leaves the list, so the next work
    # slides into the current position; advancing there would skip one. A
    # revisited work (Back to last reviewed) returns to the queue position.
    still_shown = st.session_state.get("status") != "Unlabeled"
    if label and still_shown and not revisiting and st.session_state.get("auto_advance", True):
        st.session_state.position += 1
    st.rerun()


def _go(delta: int) -> None:
    st.session_state.focus_work = None
    st.session_state.position += delta
    st.rerun()


def main() -> None:
    st.set_page_config(page_title="Atlas query audit review", layout="wide")
    st.markdown("### AT-1 query audit: is this work about plastic pollution?")
    table = load_review(CSV_PATH)
    works = table.works()
    by_id = {str(work["work_id"]): work for work in works}
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("focus_work", None)

    with st.sidebar:
        reviewer = st.text_input("Your initials (required)", value=st.session_state.get("rev", ""))
        st.session_state.rev = reviewer
        st.session_state.auto_advance = st.checkbox("Advance after labelling", value=True)
        status = st.selectbox("Show", ["Unlabeled", "All", *LABELS.values()], index=0)
        st.session_state.status = status
        search = st.text_input("Search title / abstract / institution").strip().lower()
        counts = table.label_counts()
        st.divider()
        done = len(works) - counts["unlabeled"]
        st.metric("Labelled works", f"{done} / {len(works)}")
        st.progress(done / len(works) if works else 1.0)
        for key, text in LABELS.items():
            st.write(f"{text}: **{counts[key]}**")
        st.caption(f"Saving to {CSV_PATH}")

    def keep(work: dict) -> bool:
        label = str(work.get("review_label") or "")
        if status == "Unlabeled" and label:
            return False
        if status in LABELS.values() and LABELS.get(label) != status:
            return False
        if search:
            hay = " ".join(str(work.get(k) or "") for k in ("title", "abstract_excerpt", "work_id"))
            hay += " " + " ".join(work["institutions"])
            return search in hay.lower()
        return True

    shown = [work for work in works if keep(work)]
    signature = f"{status}|{search}"
    if st.session_state.get("signature") != signature:
        st.session_state.signature = signature
        st.session_state.position = 0
    st.session_state.setdefault("position", 0)
    focus = st.session_state.focus_work
    if focus not in by_id:
        focus = st.session_state.focus_work = None
    if not shown and focus is None:
        st.success("Nothing left in this view. Switch 'Show' to All to revisit labels.")
        if st.session_state.history and st.button("↩ Back to last reviewed"):
            st.session_state.focus_work = st.session_state.history.pop()
            st.rerun()
        return
    if shown:
        st.session_state.position = min(max(st.session_state.position, 0), len(shown) - 1)
    position = st.session_state.position
    work = by_id[focus] if focus else shown[position]
    work_id = str(work["work_id"])
    label = str(work.get("review_label") or "")

    # Fixed control band: everything above the variable-length title and abstract,
    # so the buttons sit in the same place for every work.
    nav = st.columns([1, 1.3, 1.7, 1])
    at_start = focus is None and position == 0
    if nav[0].button("◀ Previous", use_container_width=True, disabled=at_start):
        _go(0 if focus else -1)
    if nav[1].button(
        "↩ Back to last reviewed",
        use_container_width=True,
        disabled=not st.session_state.history,
        help="Reopen the work you labelled most recently (repeat to step further back).",
    ):
        st.session_state.focus_work = st.session_state.history.pop()
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

    buttons = st.columns(4)
    noise_key = f"noise_{work_id}"
    for column, key in zip(buttons[:3], LABELS, strict=True):
        text = f"✓ {LABELS[key]}" if key == label else LABELS[key]
        if column.button(
            text,
            key=f"label_{key}",
            use_container_width=True,
            type="primary" if key == label else "secondary",
        ):
            if not reviewer.strip():
                st.error("Enter your initials in the sidebar first.")
            else:
                _record(work_id, key, reviewer, st.session_state.get(noise_key, ""))
    if buttons[3].button(
        "Clear label", key="label_clear", use_container_width=True, disabled=not label
    ):
        _record(work_id, "", reviewer, "")
    st.text_input(
        "Noise terms (optional): words that pulled in an off-topic work, e.g. plasticity",
        value=str(work.get("noise_terms") or ""),
        key=noise_key,
    )
    st.divider()

    abstract_html = _show_record(
        work.get("title"),
        work.get("abstract_excerpt"),
        empty="No abstract excerpt in the sample.",
    )
    st.markdown(f"Current label: {_badge(label)}", unsafe_allow_html=True)
    meta = [
        f"**Published:** {work.get('publication_date') or 'unknown'}",
        f"**Institution stratum:** {'; '.join(work['institutions'])}",
    ]
    st.markdown("  \n".join(meta))
    links = st.columns(3)
    if work.get("doi_url"):
        links[0].link_button("Open DOI", str(work["doi_url"]), use_container_width=True)
    if work.get("work_url"):
        links[1].link_button("Open in OpenAlex", str(work["work_url"]), use_container_width=True)
    st.markdown("**Abstract excerpt**")
    st.html(abstract_html)

    with st.expander("All fields"):
        st.json({k: v for k, v in work.items() if k != "abstract_excerpt"})


if __name__ == "__main__":
    main()
