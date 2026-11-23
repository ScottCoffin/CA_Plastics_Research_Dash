"""Owner triage of the PubMed records that the Atlas corpus misses (BQ-S9 part D).

Fetch each case's title and abstract once (the cache stays in the gitignored data/interim/):

    py -3.14 scripts/fetch_pubmed_miss_text.py

Review in the browser, one case per screen:

    py -3.14 -m streamlit run scripts/review_pubmed_misses_app.py

A click on a failure class writes triage_class, reviewer initials and the UTC time to that PMID's
row in ``curation/pubmed_miss_triage_v1.csv`` at once, then moves to the next case. "Other" writes
the note with no class; a class is assigned later. No other row changes. Rebuild the coverage
JSON with ``py -3.14 scripts/build_pubmed_coverage_json.py``. ``-- --csv PATH`` and ``-- --text
PATH`` review other copies. Nothing is sent anywhere.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas import review_highlight as hl  # noqa: E402
from atlas.csv_review import load_sheet, set_fields  # noqa: E402
from atlas.query import load_query_config  # noqa: E402

SHEET_PATH = ROOT / "curation" / "pubmed_miss_triage_v1.csv"
TEXT_PATH = ROOT / "data" / "interim" / "pubmed" / "miss_text.json"
TAXONOMY_PATH = ROOT / "config" / "failure_taxonomy.yml"
QUERIES_PATH = ROOT / "config" / "queries.yml"
KEY = "pmid"
SHEET_COLUMNS = (
    "doi",
    "pub_year",
    "reference_sets",
    "in_normalized_corpus",
    "atlas_work_id",
    "triage_class",
    "note",
    "reviewer",
    "reviewed_at",
)
DIRECTION_GROUPS = (
    ("false_negative", "Wrongly out of the Atlas (false negative)"),
    ("either", "Either direction"),
    ("false_positive", "Wrongly in the Atlas (false positive)"),
    ("not_an_error", "Not an Atlas error (right to leave out)"),
)
REFERENCE_NOTES = {
    "r1": "MeSH-indexed microplastics records, California affiliation (narrow)",
    "r2": "title and abstract plastics terms, California affiliation (broad)",
}
VIEWS = ("Pending", "All")
OTHER_LABEL = "Other (write a note)"
HELP = (
    "Read the title and abstract. Highlighted words are the search terms that let a record into "
    "the Atlas search. Pick the failure class that best explains this record (hover a button for "
    "its definition). A click saves at once and moves on. Choose Show: All to change an earlier "
    "decision. Other needs a note and is saved without a class."
)
OTHER_HELP = (
    "No class fits. Write a note first. The note is saved with no class, and a class is "
    "assigned to this case later, before the coverage JSON counts it."
)


class FailureClass(NamedTuple):
    id: str
    label: str
    direction: str
    definition: str


def load_classes(path: Path = TAXONOMY_PATH) -> list[FailureClass]:
    """Failure classes in file order, read from config/failure_taxonomy.yml."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    known = dict(DIRECTION_GROUPS)
    classes: list[FailureClass] = []
    for item in data["classes"]:
        direction = str(item.get("direction", ""))
        if direction not in known:
            raise ValueError(f"{path.name}: class {item.get('id')} has direction {direction!r}")
        classes.append(
            FailureClass(
                str(item["id"]),
                str(item["label"]),
                direction,
                " ".join(str(item.get("definition", "")).split()),
            )
        )
    ids = [cls.id for cls in classes]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path.name} has duplicate class ids")
    return classes


def read_rows(path: Path) -> list[dict[str, str]]:
    """Triage rows in sheet order (read-only; the sheet keeps its header and row order)."""
    return load_sheet(path, key=KEY, required=SHEET_COLUMNS).rows


def read_texts(path: Path) -> dict[str, dict[str, str]]:
    """Title and abstract per PMID from the cache written by fetch_pubmed_miss_text.py."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(pmid): {
            "title": str(record.get("title") or ""),
            "abstract": str(record.get("abstract") or ""),
        }
        for pmid, record in payload.get("records", {}).items()
    }


def is_decided(row: Mapping[str, str]) -> bool:
    """Decided once a class, or an "Other" note with a timestamp, has been saved."""
    return bool(row["triage_class"].strip() or row["reviewed_at"].strip())


def record_decision(
    path: Path,
    pmid: str,
    triage_class: str,
    note: str,
    reviewer: str,
    *,
    class_ids: Collection[str] | None = None,
    reviewed_at: str | None = None,
) -> None:
    """Save one case's triage fields (triage_class, note, reviewer, reviewed_at) and nothing else.

    ``triage_class`` is a failure-taxonomy id, or "" for Other, which needs a note.
    """
    who = reviewer.strip()
    if not who:
        raise ValueError("Enter your reviewer initials first.")
    known = {cls.id for cls in load_classes()} if class_ids is None else set(class_ids)
    if triage_class and triage_class not in known:
        raise ValueError(f"{triage_class!r} is not a class in failure_taxonomy.yml")
    if not triage_class and not note.strip():
        raise ValueError("Write a note before choosing Other.")
    sheet = load_sheet(path, key=KEY, required=SHEET_COLUMNS)
    try:
        sheet.find(pmid)
    except KeyError:
        raise ValueError(f"PMID {pmid} is not in {path.name}") from None
    stamp = reviewed_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    set_fields(
        sheet,
        pmid,
        {
            "triage_class": triage_class,
            "note": note.strip(),
            "reviewer": who,
            "reviewed_at": stamp,
        },
    )


def _options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--csv", default="")
    parser.add_argument("--text", default="")
    args, _ = parser.parse_known_args()
    return args


def _resolve(value: str, default: Path) -> Path:
    path = Path(value) if value else default
    return path if path.is_absolute() else ROOT / path


def _shown(path: Path) -> Path:
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


@st.cache_resource(show_spinner=False)
def _rules() -> list[hl.Rule]:
    """Search terms that admitted a record (config/queries.yml, see atlas.review_highlight)."""
    return hl.build_rules([load_query_config(QUERIES_PATH)])


def _reference_line(row: Mapping[str, str]) -> str:
    sets = [name for name in row["reference_sets"].split(";") if name]
    if not sets:
        return "none"
    return "; ".join(f"{name}: {REFERENCE_NOTES.get(name, 'unknown set')}" for name in sets)


def _atlas_line(row: Mapping[str, str]) -> str:
    if row["in_normalized_corpus"] == "true":
        return (
            "In the Atlas normalized corpus but not among the published works "
            f"(atlas_work_id `{row['atlas_work_id']}`)."
        )
    return "Not in the Atlas normalized corpus (no PMID or DOI match)."


def _status(row: Mapping[str, str], labels: Mapping[str, str]) -> str:
    """The owner's saved decision for this case, or an empty string while pending."""
    if not is_decided(row):
        return ""
    text = labels.get(row["triage_class"], row["triage_class"]) if row["triage_class"] else "Other"
    note = f" Note: {row['note']}" if row["note"] else ""
    return f"Your decision: **{text}** ({row['reviewer']}, {row['reviewed_at']}).{note}"


def _decide(
    path: Path,
    pmid: str,
    triage_class: str,
    note: str,
    who: str,
    codes: Sequence[str],
    pos: int,
    labels: Mapping[str, str],
) -> None:
    """Save at once, then move to the next case in the view."""
    try:
        record_decision(path, pmid, triage_class, note, who)
    except ValueError as error:
        st.error(str(error))
        return
    label = labels.get(triage_class, triage_class) if triage_class else "Other"
    st.session_state.just_saved = f"Saved {pmid}: {label}."
    if pos + 1 < len(codes):
        st.session_state.pmid = codes[pos + 1]
    st.rerun()


def _class_panel(
    classes: Sequence[FailureClass],
    *,
    row: Mapping[str, str],
    note: str,
    who: str,
    codes: Sequence[str],
    pos: int,
    path: Path,
    labels: Mapping[str, str],
) -> None:
    pmid = row["pmid"]
    ready = bool(who)
    for direction, heading in DIRECTION_GROUPS:
        members = [cls for cls in classes if cls.direction == direction]
        if not members:
            continue
        st.markdown(f"*{heading}*")
        for start in range(0, len(members), 3):
            for column, cls in zip(st.columns(3), members[start : start + 3]):
                if column.button(
                    cls.label,
                    key=f"cls_{pmid}_{cls.id}",
                    help=cls.definition,
                    width="stretch",
                    disabled=not ready,
                ):
                    _decide(path, pmid, cls.id, note, who, codes, pos, labels)
    st.markdown("*None of the classes fits*")
    other_column = st.columns(3)[0]
    if other_column.button(
        OTHER_LABEL,
        key=f"other_{pmid}",
        help=OTHER_HELP,
        width="stretch",
        disabled=not ready,
    ):
        _decide(path, pmid, "", note, who, codes, pos, labels)


def main() -> None:
    options = _options()
    sheet_path = _resolve(options.csv, SHEET_PATH)
    text_path = _resolve(options.text, TEXT_PATH)
    st.set_page_config(page_title="Atlas PubMed misses", layout="wide")
    st.markdown("### PubMed misses: which failure class fits?")
    if not sheet_path.exists():
        st.error(f"No triage sheet at `{_shown(sheet_path)}`.")
        return
    if not text_path.exists():
        st.error(
            f"No title and abstract cache at `{_shown(text_path)}`. Fetch it once with "
            "`py -3.14 scripts/fetch_pubmed_miss_text.py`."
        )
        return

    classes = load_classes(TAXONOMY_PATH)
    labels = {cls.id: cls.label for cls in classes}
    rows = read_rows(sheet_path)
    texts = read_texts(text_path)
    decided = [row for row in rows if is_decided(row)]

    with st.sidebar:
        who = st.text_input(
            "Reviewer initials (required)", key="reviewer", placeholder="e.g. SC"
        ).strip()
        share = len(decided) / len(rows) if rows else 0.0
        st.progress(
            share,
            text=f"{len(rows) - len(decided)} pending ({len(decided)} of {len(rows)} decided)",
        )
        view = st.selectbox("Show", VIEWS, index=0)
        st.caption(f"Sheet: `{_shown(sheet_path)}`")
        if not who:
            st.warning("Enter your initials to enable the decision buttons.")
        if rows and len(decided) == len(rows):
            st.success(
                f"All {len(rows)} cases have a decision. Rebuild with "
                "`py -3.14 scripts/build_pubmed_coverage_json.py`."
            )

    # The pinned case stays on screen after a decision in Pending, so it does not vanish.
    current = st.session_state.get("pmid")
    if view == "Pending":
        queue = [row for row in rows if not is_decided(row) or row["pmid"] == current]
    else:
        queue = rows
    if not queue:
        st.success("Nothing pending. Choose Show: All to revisit a decision.")
        return
    codes = [row["pmid"] for row in queue]
    pos = codes.index(current) if current in codes else 0
    row = queue[pos]
    pmid = row["pmid"]
    st.session_state.pmid = pmid

    if message := st.session_state.pop("just_saved", None):
        st.toast(message)
    nav = st.columns([1, 2, 1])
    if nav[0].button("◀ Previous", key="prev", width="stretch", disabled=pos == 0):
        st.session_state.pmid = codes[pos - 1]
        st.rerun()
    nav[1].markdown(
        f"<div style='text-align:center'>{pos + 1} of {len(queue)} in this view</div>",
        unsafe_allow_html=True,
    )
    if nav[2].button("Next ▶", key="next", width="stretch", disabled=pos >= len(queue) - 1):
        st.session_state.pmid = codes[pos + 1]
        st.rerun()

    st.divider()
    st.caption(HELP)
    st.subheader(f"PMID {pmid}")
    doi = row["doi"].strip()
    links = st.columns(3)
    links[0].link_button("Open in PubMed", f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
    if doi:
        links[1].link_button("Open DOI", f"https://doi.org/{doi}")
    st.markdown(
        f"**Year:** {row['pub_year'] or 'unknown'} · **Reference sets:** {_reference_line(row)}"
    )
    st.markdown(_atlas_line(row))

    text = texts.get(pmid)
    if text is None:
        st.warning(
            "No title or abstract cached for this PMID. Rerun "
            "`py -3.14 scripts/fetch_pubmed_miss_text.py`."
        )
    blocks = hl.record_blocks(
        text["title"] if text else None,
        text["abstract"] if text else None,
        _rules(),
        empty="No abstract in the PubMed record: judge from the title.",
    )
    st.html(blocks.title)
    st.html(blocks.summary)
    st.html(hl.legend_html())
    st.html(blocks.abstract)

    st.divider()
    st.markdown("**Decision**")
    if status := _status(row, labels):
        st.info(status)
    note = st.text_input(
        "Note (required for Other; optional otherwise)", value=row["note"], key=f"note_{pmid}"
    )
    _class_panel(
        classes,
        row=row,
        note=note,
        who=who,
        codes=codes,
        pos=pos,
        path=sheet_path,
        labels=labels,
    )


if __name__ == "__main__":
    main()
