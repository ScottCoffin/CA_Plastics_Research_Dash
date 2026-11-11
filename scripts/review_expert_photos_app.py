"""Owner review of licensed Wikidata expert photos (S9.5).

Run from the repository root:

    py -3.14 -m streamlit run scripts/review_expert_photos_app.py

Shows one photo at a time from ``curation/expert_photo_review.csv`` (regenerate it
with ``py -3.14 scripts/build_photo_review.py``; decisions are kept). The thumbnail
loads in your browser straight from Wikimedia Commons; nothing is downloaded into
the repository. Click Approve (same person, fine to show with the credit) or Reject;
the app writes ``owner_decision`` and ``owner_notes`` to the CSV at once.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.csv_review import load_sheet, set_fields  # noqa: E402

CSV_PATH = ROOT / "curation" / "expert_photo_review.csv"
REQUIRED = ("wikidata_label", "commons_page_url", "thumb_url", "owner_decision", "owner_notes")
VIEWS = ("Pending", "All", "Approved", "Rejected")


def _sheet():
    return load_sheet(CSV_PATH, key="author_id", required=REQUIRED)


def _decide(key: str, decision: str, note: str, view: str, pos: int) -> None:
    set_fields(_sheet(), key, {"owner_decision": decision, "owner_notes": note})
    if view != "Pending":
        st.session_state.pos = pos + 1
    st.rerun()


def main() -> None:
    st.set_page_config(page_title="Atlas expert photos", layout="wide")
    st.markdown("### Expert photos: is this the same person, and may we show it?")
    if not CSV_PATH.exists():
        st.error("No review sheet yet. Run: py -3.14 scripts/build_photo_review.py")
        return
    rows = _sheet().rows
    done = sum(1 for r in rows if r["owner_decision"].strip())

    with st.sidebar:
        st.progress(done / len(rows) if rows else 1.0, text=f"Reviewed {done} of {len(rows)}")
        view = st.selectbox("Show", VIEWS, index=0)
        st.caption(
            "Approve only if the photo shows this expert. The site will show the "
            "licence and credit under the photo."
        )

    decided = {"Approved": "approve", "Rejected": "reject"}
    if view == "Pending":
        queue = [r for r in rows if not r["owner_decision"].strip()]
    elif view in decided:
        queue = [r for r in rows if r["owner_decision"] == decided[view]]
    else:
        queue = list(rows)
    if not queue:
        st.success("Nothing left in this view. Tell the agent: photos reviewed.")
        return

    st.session_state.setdefault("pos", 0)
    pos = min(st.session_state.pos, len(queue) - 1)
    row = queue[pos]
    key = row["author_id"]

    nav = st.columns([1, 2, 1])
    if nav[0].button("◀ Previous", width="stretch", disabled=pos == 0):
        st.session_state.pos = pos - 1
        st.rerun()
    nav[1].markdown(
        f"<div style='text-align:center'>{pos + 1} of {len(queue)}</div>", unsafe_allow_html=True
    )
    if nav[2].button("Next ▶", width="stretch", disabled=pos >= len(queue) - 1):
        st.session_state.pos = pos + 1
        st.rerun()
    st.divider()

    left, right = st.columns([1, 2])
    with left:
        if row["thumb_url"]:
            st.image(row["thumb_url"], width="stretch")
        else:
            st.info("No thumbnail URL; open the Commons page.")
    with right:
        st.subheader(row["wikidata_label"] or key)
        st.markdown(
            f"Licence: **{row.get('license_short') or 'unknown'}**  \n"
            f"Credit: {row.get('credit') or '(none given)'}  \n"
            f"Current decision: **{row['owner_decision'] or 'pending'}**"
        )
        links = st.columns(3)
        if row.get("atlas_profile_url"):
            links[0].link_button("Atlas profile", row["atlas_profile_url"], width="stretch")
        if row.get("wikidata_url"):
            links[1].link_button("Wikidata", row["wikidata_url"], width="stretch")
        if row.get("commons_page_url"):
            links[2].link_button("Commons page", row["commons_page_url"], width="stretch")
        note = st.text_input("Note (optional)", value=row["owner_notes"], key=f"note_{key}")
        buttons = st.columns(3)
        if buttons[0].button(
            "✓ Approve",
            width="stretch",
            type="primary" if row["owner_decision"] == "approve" else "secondary",
        ):
            _decide(key, "approve", note, view, pos)
        if buttons[1].button(
            "✗ Reject",
            width="stretch",
            type="primary" if row["owner_decision"] == "reject" else "secondary",
        ):
            _decide(key, "reject", note, view, pos)
        if row["owner_decision"] and buttons[2].button("Clear", width="stretch"):
            _decide(key, "", note, view, pos)


if __name__ == "__main__":
    main()
