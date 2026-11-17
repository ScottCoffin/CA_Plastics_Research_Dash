"""Owner review of the OPC Solutions early actions: which Global Plastic Laws topics fit (EM-17b).

Create the blank sheet once (refused if the sheet already holds owner input):

    py -3.14 scripts/review_opc_mapping_app.py --init

Review in the browser, one action per screen:

    py -3.14 -m streamlit run scripts/review_opc_mapping_app.py

Each click writes ``curation/opc_mapping_review.csv`` at once: decision, owner_gpl_topics
(slugs joined by ";"), note, reviewer initials and the UTC time. When all 22 actions have a
decision, publish with ``py -3.14 scripts/build_opc_actions_json.py``. Nothing is sent anywhere.
``-- --csv PATH`` reviews another sheet with the same columns.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas import opc_actions  # noqa: E402
from atlas.csv_review import load_sheet, set_fields  # noqa: E402

HELP = (
    "Each action is linked to the Global Plastic Laws topic page a California reader should open "
    "to find related laws. Mapping OK if the draft topics point to the right page; No topic fits "
    "if none of the nine does; or pick the topics that fit. No legal judgement is needed."
)
VIEWS = ("Pending", "All")
LABELS = {"accept": "Mapping OK", "none": "No topic fits", "change": "Topics changed"}


def _options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--csv", default="")
    parser.add_argument("--init", action="store_true")
    args, _ = parser.parse_known_args()
    return args


def _sheet_path() -> Path:
    value = _options().csv
    path = Path(value) if value else opc_actions.REVIEW_PATH
    return path if path.is_absolute() else ROOT / path


def _record(path: Path, code: str, decision: str, topics: list[str], note: str, who: str) -> None:
    """Save one decision at once, with the reviewer's initials and the UTC time."""
    sheet = load_sheet(path, key="code", required=opc_actions.REVIEW_COLUMNS)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    set_fields(
        sheet,
        code,
        {
            "decision": decision,
            "owner_gpl_topics": ";".join(topics),
            "note": note.strip(),
            "reviewer": who,
            "reviewed_at": stamp,
        },
    )
    st.session_state.just_saved = f"Saved {code}: {LABELS[decision]}."


def _status(row: dict[str, str], names: dict[str, str]) -> str:
    """The owner's earlier decision for this action, or an empty string when still pending."""
    if not row["decision"]:
        return ""
    if row["decision"] == "change":
        slugs = opc_actions.review_topics(row["owner_gpl_topics"])
        text = "Changed to " + ", ".join(names.get(slug, slug) for slug in slugs)
    else:
        text = LABELS[row["decision"]]
    note = f" Note: {row['note']}" if row["note"] else ""
    return f"Your decision: **{text}** ({row['reviewer']}, {row['reviewed_at']}).{note}"


def _advance(codes: list[str], pos: int, advance: bool) -> None:
    """Move to the next action in the view when asked; otherwise stay on this one."""
    if advance and pos + 1 < len(codes):
        st.session_state.code = codes[pos + 1]
    st.rerun()


def main() -> None:
    path = _sheet_path()
    st.set_page_config(page_title="Atlas OPC mapping", layout="wide")
    st.markdown("### OPC early actions: which Global Plastic Laws topic page fits?")
    shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    if not path.exists():
        st.error(
            f"No review sheet at `{shown}`. Create it once with "
            "`py -3.14 scripts/review_opc_mapping_app.py --init`."
        )
        return

    data = opc_actions.load_actions()
    actions = data["actions"]
    names: dict[str, str] = data["gpl"]["topics"]
    objectives = {o["id"]: o["name"] for o in data["objectives"]}
    by_code = {row["code"]: row for row in opc_actions.read_review(path)}
    missing = [a["code"] for a in actions if a["code"] not in by_code]
    if missing:
        st.error(f"The sheet has no row for {', '.join(missing)}. Add the row(s) by hand.")
        return
    done = [a["code"] for a in actions if by_code[a["code"]]["decision"]]

    with st.sidebar:
        who = st.text_input("Reviewer initials (required)", key="reviewer", placeholder="e.g. SC")
        who = who.strip()
        st.progress(len(done) / len(actions), text=f"Decided {len(done)} of {len(actions)}")
        view = st.selectbox("Show", VIEWS, index=0)
        st.caption(f"Sheet: `{shown}`")
        if not who:
            st.warning("Enter your initials to enable the decision buttons.")
        if len(done) == len(actions):
            st.success(
                f"All {len(actions)} actions have a decision. Publish with "
                "`py -3.14 scripts/build_opc_actions_json.py`."
            )

    # The pinned action stays on screen after a decision in Pending, so it does not vanish.
    current = st.session_state.get("code")
    if view == "Pending":
        queue = [a for a in actions if a["code"] not in done or a["code"] == current]
    else:
        queue = list(actions)
    if not queue:
        st.success("Nothing pending. Choose Show: All to revisit a decision.")
        return
    codes = [a["code"] for a in queue]
    pos = codes.index(current) if current in codes else 0
    action = queue[pos]
    code = action["code"]
    st.session_state.code = code

    if msg := st.session_state.pop("just_saved", None):
        st.toast(msg)

    nav = st.columns([1, 2, 1])
    if nav[0].button("◀ Previous", key="prev", width="stretch", disabled=pos == 0):
        st.session_state.code = codes[pos - 1]
        st.rerun()
    nav[1].markdown(
        f"<div style='text-align:center'>{pos + 1} of {len(queue)} in this view</div>",
        unsafe_allow_html=True,
    )
    if nav[2].button("Next ▶", key="next", width="stretch", disabled=pos >= len(queue) - 1):
        st.session_state.code = codes[pos + 1]
        st.rerun()

    st.divider()
    st.caption(HELP)
    st.subheader(f"{code} · {objectives[action['objective']]}")
    st.markdown(
        f"**{action['group']}** · Strategy PDF page {action['pdf_page']} · "
        f"Deadline: **{action['deadline_as_stated']}**"
    )
    st.markdown(f"> {action['summary']}")
    search = action["atlas"]
    term = f'search "{search["q"]}"' if "q" in search else f"topic `{search['topic']}`"
    st.markdown(f"**In the Atlas:** {term}")
    draft = [names[slug] for slug in action["gpl_topics"]]
    st.markdown("**Draft topics:** " + (", ".join(draft) if draft else "none"))

    row = by_code[code]
    if status := _status(row, names):
        st.info(status)

    note = st.text_input("Note (optional)", value=row["note"], key=f"note_{code}")
    advance = st.checkbox("Advance after deciding", value=True, key="advance")
    ready = bool(who)
    buttons = st.columns(2)
    if buttons[0].button(
        "Mapping OK ✓", type="primary", width="stretch", disabled=not ready, key=f"accept_{code}"
    ):
        _record(path, code, "accept", [], note, who)
        _advance(codes, pos, advance)
    if buttons[1].button("No topic fits", width="stretch", disabled=not ready, key=f"none_{code}"):
        _record(path, code, "none", [], note, who)
        _advance(codes, pos, advance)

    st.markdown("**Or choose the topics that fit:**")
    if row["decision"] == "change":
        current_slugs = opc_actions.review_topics(row["owner_gpl_topics"])
    else:
        current_slugs = action["gpl_topics"]
    picked = st.multiselect(
        "Global Plastic Laws topics",
        list(names.values()),
        default=[names[slug] for slug in current_slugs if slug in names],
        key=f"topics_{code}",
    )
    if st.button("Save changed topics", width="stretch", disabled=not ready, key=f"change_{code}"):
        chosen = [slug for slug, name in names.items() if name in picked]
        if chosen:
            _record(path, code, "change", chosen, note, who)
            _advance(codes, pos, advance)
        else:
            st.error("Pick at least one topic, or use No topic fits.")


def _init() -> int:
    path = _sheet_path()
    try:
        opc_actions.init_review_sheet(path)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    if _options().init:
        raise SystemExit(_init())
    main()
