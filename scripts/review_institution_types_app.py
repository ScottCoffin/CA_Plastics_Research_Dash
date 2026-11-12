"""Owner review of institution types for new top-100 entrants (AT2-REVIEW).

Run from the repository root:

    py -3.14 -m streamlit run scripts/review_institution_types_app.py

Shows one institution at a time from
``data/processed/institution_review_needs_v31.csv`` with its proposed Atlas type.
Click the correct type (or "Accept proposed"); the app writes ``owner_atlas_type``,
``owner_reviewed_at`` (UTC date) and ``owner_notes`` to the CSV at once. Nothing is
sent anywhere. ``-- --csv PATH`` reviews another sheet with the same columns.

"Add a new type" saves a label typed by the owner. Labels already used in the sheet
appear as buttons for later rows. A label outside ``ATLAS_TYPES`` is flagged in the
sidebar, because the pipeline rejects it until the vocabulary is extended.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.csv_review import load_sheet, set_fields, today_utc  # noqa: E402
from atlas.ingest.institutions import ATLAS_TYPES  # noqa: E402

DEFAULT_CSV = ROOT / "data" / "processed" / "institution_review_needs_v31.csv"
TYPES: dict[str, str] = {
    "UC": "University of California campus or unit",
    "CSU": "California State University campus",
    "private": "Private university or college",
    "community-college": "California community college",
    "other-public": "Other public college or public body not listed elsewhere",
    "nonprofit/NGO": "Nonprofit, NGO, independent research institute",
    "company": "Company or consultancy",
    "state-agency": "California state agency",
    "federal": "Federal agency or lab",
    "local-agency": "City, county, district or regional agency",
    "JPA": "Joint powers authority (e.g. SCCWRP)",
    "utility": "Water, power or other utility (e.g. Metropolitan Water District)",
    "intergovernmental-organization": "Treaty body or intergovernmental commission (e.g. IATTC)",
}
VIEWS = ("Pending", "All", "Reviewed")


def _csv_path() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--csv", default="")
    args, _ = parser.parse_known_args()
    path = Path(args.csv) if args.csv else DEFAULT_CSV
    return path if path.is_absolute() else ROOT / path


CSV_PATH = _csv_path()
REQUIRED = (
    "display_name",
    "proposed_atlas_type",
    "owner_atlas_type",
    "owner_reviewed_at",
    "owner_notes",
)


def _decide(key: str, atlas_type: str, note: str) -> None:
    sheet = load_sheet(CSV_PATH, key="openalex_id", required=REQUIRED)
    set_fields(
        sheet,
        key,
        {"owner_atlas_type": atlas_type, "owner_reviewed_at": today_utc(), "owner_notes": note},
    )
    st.session_state.just_saved = f"Saved {atlas_type}."


def _advance(view: str, pos: int) -> None:
    """Pending drops the decided row by itself; other views step forward."""
    if view != "Pending":
        st.session_state.pos = pos + 1
    st.rerun()


def _custom_types(rows: list[dict[str, str]]) -> list[str]:
    """Owner labels in the sheet that are not one of the built-in buttons."""
    return sorted({r["owner_atlas_type"].strip() for r in rows} - set(TYPES) - {""})


def _clear(key: str) -> None:
    sheet = load_sheet(CSV_PATH, key="openalex_id", required=REQUIRED)
    set_fields(sheet, key, {"owner_atlas_type": "", "owner_reviewed_at": ""})


def main() -> None:
    st.set_page_config(page_title="Atlas institution types", layout="wide")
    st.markdown("### Institution types: what kind of organization is this?")
    sheet = load_sheet(CSV_PATH, key="openalex_id", required=REQUIRED)
    rows = sheet.rows
    done = sum(1 for r in rows if r["owner_atlas_type"].strip())

    with st.sidebar:
        st.caption(
            f"Sheet: `{CSV_PATH.relative_to(ROOT) if CSV_PATH.is_relative_to(ROOT) else CSV_PATH}`"
        )
        st.progress(done / len(rows) if rows else 1.0, text=f"Reviewed {done} of {len(rows)}")
        view = st.selectbox("Show", VIEWS, index=0)
        with st.expander("Type definitions"):
            for name, text in TYPES.items():
                st.markdown(f"**{name}**: {text}")
        custom = _custom_types(rows)
        if unknown := [name for name in custom if name not in ATLAS_TYPES]:
            st.warning(
                "New types not yet in the pipeline vocabulary: "
                + ", ".join(f"`{name}`" for name in unknown)
                + ". Tell the agent to add them before the next build."
            )

    if view == "Pending":
        queue = [r for r in rows if not r["owner_atlas_type"].strip()]
    elif view == "Reviewed":
        queue = [r for r in rows if r["owner_atlas_type"].strip()]
    else:
        queue = list(rows)
    if not queue:
        st.success("Nothing left in this view. Tell the agent: AT2-REVIEW done.")
        return

    st.session_state.setdefault("pos", 0)
    pos = min(st.session_state.pos, len(queue) - 1)
    row = queue[pos]
    key = row["openalex_id"]

    if msg := st.session_state.pop("just_saved", None):
        st.toast(msg)

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
    st.subheader(row["display_name"] or key)
    facts = []
    if row.get("review_rank"):
        facts.append(f"Rank **{row['review_rank']}** by plastic works")
    if row.get("plastic_work_count"):
        facts.append(f"**{row['plastic_work_count']}** plastic-related works")
    facts.append(f"Proposed type: **{row['proposed_atlas_type'] or '(none)'}**")
    if row["owner_atlas_type"]:
        facts.append(f"Your type: **{row['owner_atlas_type']}** ({row['owner_reviewed_at']})")
    st.markdown(" · ".join(facts))
    links = st.columns(3)
    links[0].link_button("Open in OpenAlex", f"https://openalex.org/{key}", width="stretch")
    links[1].link_button(
        "Search the web",
        "https://duckduckgo.com/?q=" + (row["display_name"] or key).replace(" ", "+"),
        width="stretch",
    )

    note = st.text_input(
        "Note (optional, e.g. 'community college, closest fit')",
        value=row["owner_notes"],
        key=f"note_{key}",
    )
    proposed = row["proposed_atlas_type"].strip()
    if proposed in TYPES and st.button(
        f"✓ Accept proposed: {proposed}", type="primary", width="stretch"
    ):
        _decide(key, proposed, note)
        _advance(view, pos)

    st.markdown("**Or choose the type:**")
    cols = st.columns(4)
    for index, name in enumerate(TYPES):
        current = row["owner_atlas_type"] == name
        if cols[index % 4].button(
            name,
            key=f"type_{name}",
            help=TYPES[name],
            width="stretch",
            type="primary" if current else "secondary",
        ):
            _decide(key, name, note)
            _advance(view, pos)
    if custom:
        st.markdown("**Your added types:**")
        extra = st.columns(4)
        for index, name in enumerate(custom):
            if extra[index % 4].button(
                name,
                key=f"custom_{name}",
                width="stretch",
                type="primary" if row["owner_atlas_type"] == name else "secondary",
            ):
                _decide(key, name, note)
                _advance(view, pos)
    with st.form(f"new_type_{key}", clear_on_submit=True, border=False):
        new_cols = st.columns([3, 1], vertical_alignment="bottom")
        new_type = new_cols[0].text_input(
            "Add a new type", placeholder="e.g. tribal-government", key=f"new_{key}"
        )
        if new_cols[1].form_submit_button("Save new type", width="stretch"):
            label = " ".join(new_type.split())
            if not label:
                st.error("Type a label first.")
            elif "," in label:
                st.error("Labels cannot contain commas.")
            else:
                existing = {t.lower(): t for t in [*TYPES, *custom]}
                _decide(key, existing.get(label.lower(), label), note)
                _advance(view, pos)
    if row["owner_atlas_type"] and st.button("Clear my decision"):
        _clear(key)
        st.rerun()


if __name__ == "__main__":
    main()
