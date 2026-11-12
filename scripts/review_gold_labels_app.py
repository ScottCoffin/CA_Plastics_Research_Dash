"""Owner gold-label review for the S4.3 gold set (one work per screen).

Run from the repository root:

    py -3.14 -m streamlit run scripts/review_gold_labels_app.py

Shows one work at a time from ``curation/splits_v2.csv``, with its title and abstract
(abstract from ``data/processed/normalized/works.parquet``) and the search terms highlighted.
"Save and next" validates the row with the rules of ``atlas.nlp.annotation`` and rewrites
that one row of ``curation/annotations/annotations_SC.csv`` atomically. The sheet is created
on first run if it is missing and is never overwritten. Nothing is sent anywhere.
``-- --sheet PATH`` uses another sheet with the same columns.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas import gold_label_review as gl  # noqa: E402
from atlas import review_highlight as hl  # noqa: E402
from atlas.nlp.annotation import DOMAIN_TAGS  # noqa: E402
from atlas.query import load_query_config  # noqa: E402

SPLITS_CSV = ROOT / "curation" / "splits_v2.csv"
WORKS_PARQUET = ROOT / "data" / "processed" / "normalized" / "works.parquet"
DEFAULT_SHEET = ROOT / "curation" / "annotations" / gl.SHEET_NAME
CA_HELP = (
    "guide_v1 section 3. California land or state waters only; mentions, affiliations and "
    "lab-only work do not count."
)
TIER_HELP_TEXT = "guide_v1 section 2. Shown only when plastic_related is yes."
NEW_LABEL = "__new__"


def _sheet_path() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--sheet", default="")
    args, _ = parser.parse_known_args()
    path = Path(args.sheet) if args.sheet else DEFAULT_SHEET
    return path if path.is_absolute() else ROOT / path


SHEET = _sheet_path()


@st.cache_resource(show_spinner=False)
def _splits() -> list[dict[str, str]]:
    return gl.load_splits(SPLITS_CSV)


@st.cache_resource(show_spinner=False)
def _works() -> dict[str, dict[str, Any]]:
    return gl.load_works(WORKS_PARQUET, [str(row["work_id"]) for row in _splits()])


@st.cache_resource(show_spinner=False)
def _rules() -> list[hl.Rule]:
    return hl.build_rules([load_query_config(ROOT / "config" / "queries.yml")])


@st.cache_resource(show_spinner=False)
def _prior() -> dict[str, dict[str, str]]:
    return gl.load_prior_relevance(
        ROOT / "curation" / "overrides_works.csv", ROOT / "curation" / "work_relevance.csv"
    )


def _key(work_id: str, field: str) -> str:
    return f"{work_id}|{field}"


def _go(delta: int) -> None:
    last = max(st.session_state.get("queue_len", 1) - 1, 0)
    st.session_state.pos = min(max(st.session_state.pos + delta, 0), last)
    st.session_state.search = ""


def _save(work_id: str, status: str) -> None:
    """Callback: validate, write one row, move on. Errors stay on screen, nothing is written."""
    view = st.session_state.view
    before = [row["work_id"] for row in gl.queue(gl.read_rows(SHEET), view)]
    form = {field: st.session_state.get(_key(work_id, field)) for field in gl.FORM_FIELDS}
    if form["study_type"] == NEW_LABEL:
        typed = gl.normalize_label(st.session_state.get(_key(work_id, "study_type_new")) or "")
        if not typed and status == "complete" and form["plastic_related"] == "true":
            st.session_state.flash = ("error", "Not saved: type the new design label first.")
            return
        form["study_type"] = typed
    try:
        gl.save_decision(SHEET, work_id, form, status, gl.split_index(_splits()))
    except (ValueError, KeyError) as error:
        st.session_state.flash = ("error", f"Not saved: {error}")
        return
    after = [row["work_id"] for row in gl.queue(gl.read_rows(SHEET), view)]
    st.session_state.pos = gl.position_after(before, after, work_id, st.session_state.pos)
    st.session_state.search = ""
    label = "adjudication hold" if status == "adjudication_required" else "complete"
    st.session_state.flash = ("success", f"Saved {work_id} as {label}.")


def _skip(work_id: str) -> None:
    view = st.session_state.view
    ids = [row["work_id"] for row in gl.queue(gl.read_rows(SHEET), view)]
    st.session_state.pos = gl.position_after(ids, ids, work_id, st.session_state.pos)
    st.session_state.search = ""


def _defaults(row: dict[str, str], prior: dict[str, str] | None = None) -> dict[str, Any]:
    """Initial widget values for a row; applied only the first time a widget is drawn.

    A prior relevance decision pre-selects plastic_related on an unlabelled row only.
    """
    tags = [tag for tag in row["domain_tags"].split("|") if tag in DOMAIN_TAGS]
    related = row["plastic_related"] or None
    if prior and row["decision_status"] == "":
        related = prior["value"]
    return {
        "plastic_related": related,
        "plastic_tier": row["plastic_tier"] or None,
        "ca_sampled": row["ca_sampled"] or None,
        "study_type": row["study_type"],
        "domain_tags": tags,
        "evidence_snippet": row["evidence_snippet"],
        "evidence_source": row["evidence_source"],
    }


def _design_label(value: str) -> str:
    if value == NEW_LABEL:
        return "+ Create a new design label"
    if not value:
        return "Choose a design"
    return value if value in gl.STUDY_TYPES else f"{value} (new label)"


def _draw_form(
    row: dict[str, str], design_options: list[str], prior: dict[str, str] | None = None
) -> None:
    work_id = row["work_id"]
    init = _defaults(row, prior)

    def widget_key(field: str) -> str:
        return _key(work_id, field)

    st.markdown("**Plastic relevance** (guide_v1 sections 1-2)")
    if prior and row["decision_status"] == "":
        verdict = "relevant" if prior["value"] == "true" else "not relevant"
        st.info(
            f"You already judged this {verdict} on {prior['date']} ({prior['source']}). "
            "Pre-selected; change it if you disagree."
        )
    related = st.radio(
        "Is plastic the primary research subject?",
        ["true", "false"],
        index=["true", "false"].index(init["plastic_related"])
        if init["plastic_related"] in ("true", "false")
        else None,
        format_func=lambda v: "Yes, plastic-related" if v == "true" else "No, not plastic-related",
        horizontal=True,
        key=widget_key("plastic_related"),
    )
    if related == "true":
        tiers = list(gl.TIER_OPTIONS)
        st.radio(
            "Plastic tier",
            tiers,
            index=tiers.index(init["plastic_tier"]) if init["plastic_tier"] in tiers else None,
            format_func=lambda v: f"{v}: {gl.TIER_HELP[v]}",
            key=widget_key("plastic_tier"),
            help=TIER_HELP_TEXT,
        )
        st.multiselect(
            "Domain tags (every supported tag; multi-label, guide_v1 section 4)",
            list(DOMAIN_TAGS),
            default=init["domain_tags"],
            key=widget_key("domain_tags"),
        )

    if related == "false":
        st.info("Not plastic-related: nothing else is needed. Save and next.")
    if related == "true":
        st.markdown("**California sampling** (guide_v1 section 3)")
        samplings = list(gl.SAMPLING_OPTIONS)
        st.radio(
            "ca_sampled",
            samplings,
            index=samplings.index(init["ca_sampled"]) if init["ca_sampled"] in samplings else None,
            format_func=lambda v: f"{v}: {gl.SAMPLING_HELP[v]}",
            key=widget_key("ca_sampled"),
            help=CA_HELP,
        )

        st.markdown("**Design** (guide_v2 section 1)")
        studies = ["", *design_options]
        if init["study_type"] and init["study_type"] not in studies:
            studies.append(init["study_type"])
        studies.append(NEW_LABEL)
        choice = st.selectbox(
            "study_type (one primary design)",
            studies,
            index=studies.index(init["study_type"]),
            format_func=_design_label,
            help="\n\n".join(f"**{k}**: {v}" for k, v in gl.STUDY_TYPES.items()),
            key=widget_key("study_type"),
        )
        if choice == NEW_LABEL:
            typed = st.text_input(
                "New design label (saved as snake_case; offered for later works)",
                key=widget_key("study_type_new"),
                placeholder="e.g. archival_specimen_analysis",
            )
            if typed.strip():
                st.caption(f"Will be saved as `{gl.normalize_label(typed)}`.")

    st.markdown("**Evidence** (the shortest exact excerpt that supports the decision)")
    st.text_area(
        f"Evidence snippet (optional; paste from the title or abstract; up to "
        f"{gl.MAX_SNIPPET_CHARS} characters)",
        value=init["evidence_snippet"],
        key=widget_key("evidence_snippet"),
    )
    sources = ["", *gl.SOURCE_OPTIONS]
    st.selectbox(
        "Evidence source",
        sources,
        index=sources.index(init["evidence_source"]) if init["evidence_source"] in sources else 0,
        format_func=lambda v: v or "(automatic: title if the snippet is in it, else abstract)",
        key=widget_key("evidence_source"),
    )


def main() -> None:
    st.set_page_config(page_title="Atlas gold labels", layout="wide")
    st.markdown("### Gold labels: plastic relevance, CA sampling, design, domains")

    splits = _splits()
    works = _works()
    try:
        created = gl.ensure_sheet(SHEET, splits, works)
        rows = gl.read_rows(SHEET)
    except (ValueError, OSError) as error:
        st.error(f"Cannot open the sheet: {error}")
        return
    if created:
        st.toast(f"Created {SHEET.name} from {SPLITS_CSV.name}.")

    if flash := st.session_state.pop("flash", None):
        kind, message = flash
        (st.success if kind == "success" else st.error)(message)

    with st.sidebar:
        st.caption(f"Annotator `{gl.ANNOTATOR}` · `{gl.GUIDE_VERSION}`")
        st.caption(f"Sheet: `{SHEET.relative_to(ROOT) if SHEET.is_relative_to(ROOT) else SHEET}`")
        done, total = gl.eval_progress(rows)
        st.progress(
            done / total if total else 1.0,
            text=f"Evaluation set: labelled {done} of {total}",
        )
        st.caption(
            "Train (350) and leak-check (80) works are not needed now: train labels come from "
            "active learning, leak-check works wait for S5.7."
        )
        for split, (done, total) in gl.progress(rows).items():
            st.progress(done / total if total else 1.0, text=f"{split}: labelled {done} of {total}")
        view = st.selectbox("Show", gl.VIEWS, key="view")
        st.text_input("Work ID search", key="search", placeholder="W1234567 or 1234567")
        with st.expander("Highlight legend"):
            st.html(hl.legend_html())

    if st.session_state.get("view_seen") != view:
        st.session_state.pos = 0
        st.session_state["view_seen"] = view
    st.session_state.setdefault("pos", 0)

    queue = gl.queue(rows, view)
    st.session_state.queue_len = len(queue)
    found = None
    if st.session_state.get("search", "").strip():
        found = gl.find_work(rows, st.session_state.search)
        if found is None:
            st.warning(f"No work {st.session_state.search.strip()} in the sheet.")
    if found is None:
        if not queue:
            st.success(f"Nothing left in '{view}'.")
            return
        st.session_state.pos = min(st.session_state.pos, len(queue) - 1)
        current = queue[st.session_state.pos]
        position = f"{st.session_state.pos + 1} of {len(queue)} in this view"
    else:
        current = found
        position = "searched work"

    work_id = current["work_id"]
    meta = works.get(work_id, {})
    title = str(meta.get("title") or current["title"] or "")
    abstract = str(meta.get("abstract") or "")
    blocks = hl.record_blocks(title or None, abstract or None, _rules(), empty="No abstract")

    nav = st.columns([1, 2, 1])
    nav[0].button(
        "◀ Previous",
        on_click=_go,
        args=(-1,),
        width="stretch",
        disabled=found is None and st.session_state.pos == 0,
    )
    nav[1].markdown(f"<div style='text-align:center'>{position}</div>", unsafe_allow_html=True)
    nav[2].button(
        "Next ▶",
        on_click=_go,
        args=(1,),
        width="stretch",
        disabled=found is None and st.session_state.pos >= len(queue) - 1,
    )

    st.divider()
    st.html(blocks.title)
    year = meta.get("year") or current["year"]
    byline = gl.author_line(meta.get("authors"))
    journal = str(meta.get("journal") or "").strip()
    link = gl.paper_link(meta, work_id)
    link_label = "DOI" if "doi.org" in link else "OpenAlex (no DOI)"
    st.markdown(
        f"{byline or '_Authors not available_'}  \n"
        f"_{journal or 'Journal not available'}_ · **{year}** · "
        f"[{link_label}: {link.removeprefix('https://')} ↗]({link})"
    )
    st.html(blocks.summary)
    st.html(blocks.abstract)
    st.caption(
        f"**{work_id}** · split "
        f"`{current['split']}` · role `{current['sample_role']}` · status "
        f"`{current['decision_status'] or 'unlabelled'}`"
    )
    if current["decision_status"] in ("complete", "adjudication_required"):
        st.caption("Already recorded: saving again overwrites this row.")

    prior = _prior().get(work_id)
    _draw_form(current, gl.study_type_options(rows), prior)

    st.divider()
    buttons = st.columns(3)
    buttons[0].button(
        "Save and next",
        type="primary",
        width="stretch",
        on_click=_save,
        args=(work_id, "complete"),
    )
    buttons[1].button(
        "Needs adjudication",
        width="stretch",
        on_click=_save,
        args=(work_id, "adjudication_required"),
        help="Clears the labels and keeps the evidence note; the owner decides later.",
    )
    buttons[2].button("Skip", width="stretch", on_click=_skip, args=(work_id,))


if __name__ == "__main__":
    main()
