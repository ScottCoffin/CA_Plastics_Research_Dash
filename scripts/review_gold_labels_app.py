"""Owner gold-label review for the S4.3 gold set (one work per screen).

Run from the repository root:

    py -3.14 -m streamlit run scripts/review_gold_labels_app.py

Global adaptive block (BQ-G4), after ``scripts/bq_gold_sampler.py round0``:

    py -3.14 -m streamlit run scripts/review_gold_labels_app.py -- --global

It shows the drawn works of ``curation/gold_global_draws_v1.csv`` and saves to
``curation/annotations/annotations_global_SC.csv``. Titles and abstracts come from the local
works parquet and OpenAlex pages and are never saved. The score and score band are not shown.

Shows one work at a time from ``curation/splits_v2.csv``, with its title and abstract
(abstract from ``data/processed/normalized/works.parquet``) and the search terms highlighted.
"Save and next" validates the row with the rules of ``atlas.nlp.annotation`` and rewrites
that one row of ``curation/annotations/annotations_SC.csv`` atomically. The sheet is created
on first run if it is missing and is never overwritten. Nothing is sent anywhere.
``-- --sheet PATH`` uses another sheet with the same columns.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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
DEFAULT_GLOBAL_SHEET = ROOT / "curation" / "annotations" / gl.GLOBAL_SHEET_NAME
DEFAULT_LEDGER = ROOT / "curation" / "gold_global_draws_v1.csv"
GLOBAL_WORKS_PARQUET = ROOT / "data" / "processed" / "global" / "works.parquet"
GLOBAL_PAGES = ROOT / "data" / "raw" / "openalex_global" / "pages"
CA_HELP = (
    "guide_v1 section 3. California land or state waters only; mentions, affiliations and "
    "lab-only work do not count."
)
TIER_HELP_TEXT = "guide_v1 section 2. Shown only when plastic_related is yes."
CENTRALITY_HELP_TEXT = "guide_v3 section 5. Shown only for the lifecycle_and_society tier."
ORIGIN_HELP_TEXT = "guide_v3 section 5.6. Leave blank unless the work states the origin."
LENS_HELP_TEXT = "\n\n".join([gl.LENS_RULE, *(f"**{k}**: {v}" for k, v in gl.LENS_HELP.items())])
NEW_LABEL = "__new__"


def _options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--sheet", default="")
    parser.add_argument("--global", dest="global_block", action="store_true")
    parser.add_argument("--ledger", default="")
    parser.add_argument("--works", default="")
    parser.add_argument("--pages", default="")
    args, _ = parser.parse_known_args()
    return args


def _root_path(text: str, default: Path) -> Path:
    if not text:
        return default
    path = Path(text)
    return path if path.is_absolute() else ROOT / path


OPTIONS = _options()
GLOBAL = bool(OPTIONS.global_block)
GUIDE_VERSION = gl.GLOBAL_GUIDE_VERSION if GLOBAL else gl.GUIDE_VERSION
LEDGER = _root_path(OPTIONS.ledger, DEFAULT_LEDGER)
GLOBAL_WORKS = _root_path(OPTIONS.works, GLOBAL_WORKS_PARQUET)
PAGES = _root_path(OPTIONS.pages, GLOBAL_PAGES)
SHEET = _root_path(OPTIONS.sheet, DEFAULT_GLOBAL_SHEET if GLOBAL else DEFAULT_SHEET)


def _ledger_draws() -> list[dict[str, str]]:
    """Drawn works from the draw ledger (read only here)."""
    if not LEDGER.exists():
        return []
    with LEDGER.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _opaque(stratum: str) -> str:
    """A stratum label that does not reveal the score band to the labeller."""
    return "Stratum " + hashlib.sha1(stratum.encode("utf-8")).hexdigest()[:6]


@st.cache_resource(show_spinner=False)
def _splits() -> list[dict[str, str]]:
    if GLOBAL:
        return [
            {"work_id": wid, **meta} for wid, meta in gl.global_split_index(_ledger_draws()).items()
        ]
    return gl.load_splits(SPLITS_CSV)


@st.cache_resource(show_spinner=False)
def _works() -> dict[str, dict[str, Any]]:
    ids = [str(row["work_id"]) for row in _splits()]
    if not GLOBAL:
        return gl.load_works(WORKS_PARQUET, ids)
    works = gl.load_works(GLOBAL_WORKS, ids, fallbacks=(), authorships=None)
    abstracts = gl.load_global_abstracts(PAGES, set(ids))
    for work_id in ids:
        record = works.setdefault(work_id, {"work_id": work_id})
        record["abstract"] = abstracts.get(work_id, "")
    return works


def _queue(rows: list[dict[str, str]], view: str) -> list[dict[str, str]]:
    return gl.global_queue(rows, view) if GLOBAL else gl.queue(rows, view)


@st.cache_resource(show_spinner=False)
def _rules() -> list[hl.Rule]:
    return hl.build_rules([load_query_config(ROOT / "config" / "queries.yml")])


@st.cache_resource(show_spinner=False)
def _prior() -> dict[str, dict[str, str]]:
    if GLOBAL:
        return {}  # the global block is label-blind: no earlier relevance decision is shown
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
    before = [row["work_id"] for row in _queue(gl.read_rows(SHEET), view)]
    form = {field: st.session_state.get(_key(work_id, field)) for field in gl.FORM_FIELDS}
    if form["study_type"] == NEW_LABEL:
        typed = gl.normalize_label(st.session_state.get(_key(work_id, "study_type_new")) or "")
        if not typed and status == "complete" and form["plastic_related"] == "true":
            st.session_state.flash = ("error", "Not saved: type the new design label first.")
            return
        form["study_type"] = typed
    try:
        gl.save_decision(
            SHEET, work_id, form, status, gl.split_index(_splits()), guide_version=GUIDE_VERSION
        )
    except (ValueError, KeyError) as error:
        st.session_state.flash = ("error", f"Not saved: {error}")
        return
    after = [row["work_id"] for row in _queue(gl.read_rows(SHEET), view)]
    st.session_state.pos = gl.position_after(before, after, work_id, st.session_state.pos)
    st.session_state.search = ""
    label = "adjudication hold" if status == "adjudication_required" else "complete"
    st.session_state.flash = ("success", f"Saved {work_id} as {label}.")


def _skip(work_id: str) -> None:
    view = st.session_state.view
    ids = [row["work_id"] for row in _queue(gl.read_rows(SHEET), view)]
    st.session_state.pos = gl.position_after(ids, ids, work_id, st.session_state.pos)
    st.session_state.search = ""


def _defaults(row: dict[str, str], prior: dict[str, str] | None = None) -> dict[str, Any]:
    """Initial widget values for a row; applied only the first time a widget is drawn.

    A prior relevance decision pre-selects plastic_related on an unlabelled row only.
    """
    tags = [tag for tag in row["domain_tags"].split("|") if tag in DOMAIN_TAGS]
    lenses = [lens for lens in row["analytic_lens"].split("|") if lens in gl.LENS_OPTIONS]
    related = row["plastic_related"] or None
    if prior and row["decision_status"] == "":
        related = prior["value"]
    return {
        "plastic_related": related,
        "plastic_tier": row["plastic_tier"] or None,
        "plastics_centrality": row["plastics_centrality"] or "not_assessed",
        "ca_sampled": row["ca_sampled"] or None,
        "study_type": row["study_type"],
        "domain_tags": tags,
        "analytic_lens": lenses,
        "lens_evidence": row["lens_evidence"],
        "origin": row["origin"] or None,
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
        tier = st.radio(
            "Plastic tier",
            tiers,
            index=tiers.index(init["plastic_tier"]) if init["plastic_tier"] in tiers else None,
            format_func=lambda v: f"{v}: {gl.TIER_HELP[v]}",
            key=widget_key("plastic_tier"),
            help=TIER_HELP_TEXT,
        )
        if tier == "lifecycle_and_society":
            centres = list(gl.CENTRALITY_OPTIONS)
            value = init["plastics_centrality"]
            st.radio(
                "plastics_centrality (scope gate for this tier)",
                centres,
                index=centres.index(value if value in centres else "not_assessed"),
                format_func=lambda v: f"{v}: {gl.CENTRALITY_HELP[v]}",
                key=widget_key("plastics_centrality"),
                help=CENTRALITY_HELP_TEXT,
            )
        st.multiselect(
            "Domain tags (one list; experimental tags marked; multi-label, guide_v1 section 4)",
            list(DOMAIN_TAGS),
            default=init["domain_tags"],
            format_func=gl.tag_label,
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

        st.markdown("**Framing** (guide_v3 sections 5-6; both optional)")
        lenses = st.multiselect(
            "analytic_lens (only when the work itself uses the frame)",
            list(gl.LENS_OPTIONS),
            default=init["analytic_lens"],
            format_func=lambda v: v,
            help=LENS_HELP_TEXT,
            key=widget_key("analytic_lens"),
        )
        if lenses:
            evidence = st.text_area(
                "lens_evidence (required with a lens: the exact excerpt that shows the frame)",
                value=init["lens_evidence"],
                key=widget_key("lens_evidence"),
            )
            if message := gl.lens_error(lenses, evidence):
                st.warning(message)
        origins = list(gl.ORIGIN_OPTIONS)
        st.radio(
            "origin (only when the work states it)",
            origins,
            index=origins.index(init["origin"]) if init["origin"] in origins else None,
            format_func=lambda v: f"{v}: {gl.ORIGIN_HELP[v]}",
            key=widget_key("origin"),
            help=ORIGIN_HELP_TEXT,
        )

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


def _open_rows(works: dict[str, dict[str, Any]]) -> tuple[list[dict[str, str]], bool]:
    """(sheet rows, created). The global sheet gains rows for newly drawn works; old rows stay."""
    if GLOBAL:
        created = not SHEET.exists()
        gl.sync_global_sheet(SHEET, _ledger_draws())
        return gl.read_rows(SHEET), created
    created = gl.ensure_sheet(SHEET, _splits(), works)
    return gl.read_rows(SHEET), created


def main() -> None:
    st.set_page_config(page_title="Atlas gold labels", layout="wide")
    if GLOBAL:
        st.markdown("### Global gold labels (BQ-G4): relevance, CA sampling, design, domains")
    else:
        st.markdown("### Gold labels: plastic relevance, CA sampling, design, domains")

    works = _works()
    try:
        rows, created = _open_rows(works)
    except (ValueError, OSError, KeyError) as error:
        st.error(f"Cannot open the sheet: {error}")
        return
    if created:
        st.toast(f"Created {SHEET.name}.")

    if flash := st.session_state.pop("flash", None):
        kind, message = flash
        (st.success if kind == "success" else st.error)(message)

    with st.sidebar:
        st.caption(f"Annotator `{gl.ANNOTATOR}` · `{GUIDE_VERSION}`")
        st.caption(f"Sheet: `{SHEET.relative_to(ROOT) if SHEET.is_relative_to(ROOT) else SHEET}`")
        if GLOBAL:
            done = sum(1 for row in rows if row["decision_status"] == "complete")
            st.progress(
                done / len(rows) if rows else 1.0,
                text=f"Drawn works labelled {done} of {len(rows)}",
            )
            for stratum, (stratum_done, total) in gl.global_progress(rows).items():
                st.progress(
                    stratum_done / total,
                    text=f"{_opaque(stratum)}: labelled {stratum_done} of {total}",
                )
            views = gl.global_round_views(rows)
            view = st.selectbox("Show (round)", views, key="view")
        else:
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
                st.progress(
                    done / total if total else 1.0, text=f"{split}: labelled {done} of {total}"
                )
            view = st.selectbox("Show", gl.VIEWS, key="view")
        st.text_input("Work ID search", key="search", placeholder="W1234567 or 1234567")
        with st.expander("Highlight legend"):
            st.html(hl.legend_html())

    if st.session_state.get("view_seen") != view:
        st.session_state.pos = 0
        st.session_state["view_seen"] = view
    st.session_state.setdefault("pos", 0)

    queue = _queue(rows, view)
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
    if GLOBAL:
        st.caption(
            f"**{work_id}** · round {current['round']} · status "
            f"`{current['decision_status'] or 'unlabelled'}`"
        )
    else:
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
