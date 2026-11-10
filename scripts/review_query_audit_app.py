"""Local Streamlit app for labelling the AT-1 query audit sample.

Run from the repository root:

    py -3.14 -m streamlit run scripts/review_query_audit_app.py

Each click writes straight to docs/QUERY_AUDIT_REVIEW.csv (atomic save). A label
applies to the work, so duplicate rows of the same work_id are labelled together.
Nothing is sent anywhere; the app only reads and writes that CSV.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.query_audit_review import (  # noqa: E402
    LABELS,
    REVIEW_CSV,
    load_review,
    save_review,
    set_label,
)

# ATLAS_REVIEW_CSV points the app at a copy (used for smoke tests).
CSV_PATH = Path(os.environ.get("ATLAS_REVIEW_CSV") or ROOT / REVIEW_CSV)
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
    # In the Unlabeled view the labelled work leaves the list, so the next work
    # slides into the current position; advancing there would skip one.
    still_shown = st.session_state.get("status") != "Unlabeled"
    if label and still_shown and st.session_state.get("auto_advance", True):
        st.session_state.position += 1
    st.rerun()


def main() -> None:
    st.set_page_config(page_title="Atlas query audit review", layout="wide")
    st.title("AT-1 query audit: is this work about plastic pollution?")
    table = load_review(CSV_PATH)
    works = table.works()

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
    if not shown:
        st.success("Nothing left in this view. Switch 'Show' to All to revisit labels.")
        return
    st.session_state.position = min(max(st.session_state.position, 0), len(shown) - 1)
    position = st.session_state.position
    work = shown[position]

    left, mid, right = st.columns([1, 2, 1])
    if left.button("◀ Previous", use_container_width=True, disabled=position == 0):
        st.session_state.position -= 1
        st.rerun()
    mid.write(f"Work **{position + 1}** of **{len(shown)}** in this view")
    if right.button("Next ▶", use_container_width=True, disabled=position >= len(shown) - 1):
        st.session_state.position += 1
        st.rerun()

    label = str(work.get("review_label") or "")
    st.subheader(work.get("title") or "(no title)")
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
    st.write(work.get("abstract_excerpt") or "_No abstract excerpt in the sample._")

    noise = st.text_input(
        "Noise terms (optional): words that pulled in an off-topic work, e.g. plasticity",
        value=str(work.get("noise_terms") or ""),
        key=f"noise_{work['work_id']}",
    )
    buttons = st.columns(4)
    for column, key in zip(buttons[:3], LABELS, strict=True):
        text = f"{LABELS[key]} (current)" if key == label else LABELS[key]
        if column.button(
            text, use_container_width=True, type="primary" if key == "relevant" else "secondary"
        ):
            if not reviewer.strip():
                st.error("Enter your initials in the sidebar first.")
            else:
                _record(str(work["work_id"]), key, reviewer, noise)
    if buttons[3].button("Clear label", use_container_width=True, disabled=not label):
        _record(str(work["work_id"]), "", reviewer, "")

    with st.expander("All fields"):
        st.json({k: v for k, v in work.items() if k != "abstract_excerpt"})


if __name__ == "__main__":
    main()
