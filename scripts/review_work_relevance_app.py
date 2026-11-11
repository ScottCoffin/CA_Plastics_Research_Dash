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
import random
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas import review_highlight as hl  # noqa: E402
from atlas.nlp import active_relevance as al  # noqa: E402
from atlas.query import load_query_config  # noqa: E402
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
    record_owner_decision,
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


SMART_VIEW = "Smart queue (active learning)"
RETRAIN_EVERY = 20
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
    if item.get("haiku") is None:
        return _badge("No Haiku call for this work", NEUTRAL)
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


# --------------------------------------------------------------- smart queue (S5.1-AL)

REASON_TEXT = {
    "uncertain": "Uncertain: the model is close to 50/50, so your label teaches it the most.",
    "disagreement": "Disagreement: the model and Haiku disagree, and the model is fairly sure.",
    "audit": (
        "Audit: a random check of a work the model is confident about. "
        "Your answer measures how accurate the auto-labels are."
    ),
}


@st.cache_resource(show_spinner=False)
def _highlight_rules() -> list[hl.Rule]:
    """Search terms that admitted a record (see atlas.review_highlight)."""
    return hl.build_rules([load_query_config(ROOT / "config" / "queries.yml")])


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


def _ml_available() -> str:
    """Empty string when scikit-learn and sentence-transformers import; else the reason."""
    try:
        import sentence_transformers  # noqa: F401
        import sklearn  # noqa: F401
    except ImportError as error:
        return f"{error}. Install the extra: py -3.14 -m pip install -e .[ml]"
    return ""


@st.cache_resource(show_spinner="Loading the embedding model (first run downloads it)...")
def _embedder(model_name: str) -> al.Embedder:
    return al.sentence_transformer_embedder(model_name)


@st.cache_data(show_spinner=False)
def _texts(works_path: str) -> dict[str, str]:
    return al.work_texts(load_work_details(Path(works_path)))


def _retrain() -> None:
    """Embed (cached), train, rescore, refill the queue, log the trend point."""
    table = load_work_reviews(CSV_PATH)
    state = al.load_state(ROOT / al.STATE_PATH)
    with st.spinner("Training on your labels..."):
        result = al.run_active_learning(
            texts=_texts(str(WORKS_PATH)),
            review_rows=table.rows,
            audit_labels=al.load_audit_labels([ROOT / p for p in al.AUDIT_CSVS]),
            test_ids=al.load_test_ids(ROOT / al.SPLITS_CSV),
            embedder=_embedder(al.DEFAULT_MODEL),
            model_name=al.DEFAULT_MODEL,
            cache_dir=ROOT / al.EMBEDDING_DIR,
            batch_size=al.BATCH_SIZE,
            seed=random.randrange(1_000_000),
            skipped=frozenset(state.get("skipped", [])),
        )
    summary = al.audit_summary(state, result.confident_auto)
    al.append_trend(state, result.model.metrics, summary)
    al.save_state(al.state_snapshot(result, state), ROOT / al.STATE_PATH)
    st.session_state.al_result = result
    st.session_state.al_queue = list(result.queue)
    st.session_state.al_since_retrain = 0


def _accuracy_bar(summary: al.AuditSummary) -> str:
    low, span = 0.80, 0.20  # axis 80% to 100% so a 95% target is readable

    def at(value: float) -> float:
        return 100 * min(max((value - low) / span, 0.0), 1.0)

    colour = POSITIVE[0] if summary.ready_to_accept else CAUTION[0]
    parts = [
        '<div style="position:relative;height:16px;background:#e2e8f0;border-radius:8px;'
        'margin:0.4rem 0 1.4rem 0;">'
    ]
    if summary.accuracy is not None:
        parts.append(
            f'<div style="position:absolute;left:{at(summary.lower)}%;'
            f"width:{max(at(summary.upper) - at(summary.lower), 0.8)}%;top:0;bottom:0;"
            f'background:{colour};opacity:0.35;border-radius:8px;"></div>'
            f'<div style="position:absolute;left:calc({at(summary.accuracy)}% - 3px);width:6px;'
            f'top:-3px;bottom:-3px;background:{colour};border-radius:3px;"></div>'
        )
    parts.append(
        f'<div style="position:absolute;left:{at(summary.target)}%;width:2px;top:-6px;'
        f'bottom:-6px;background:#0f172a;"></div>'
        f'<div style="position:absolute;left:calc({at(summary.target)}% - 40px);top:20px;'
        f'font-size:0.75rem;color:#0f172a;white-space:nowrap;">'
        f"target {summary.target:.0%}</div>"
        '<div style="position:absolute;left:0;top:20px;font-size:0.75rem;color:#64748b;">80%</div>'
        '<div style="position:absolute;right:0;top:20px;font-size:0.75rem;color:#64748b;">'
        "100%</div></div>"
    )
    return "".join(parts)


def _more_audits_text(summary: al.AuditSummary) -> str:
    if summary.n == 0:
        floor = al.MIN_AUDIT_ITEMS + (al.audits_needed(30, 30, summary.target) or 0)
        return f"At least {floor} audits with no errors are needed."
    if summary.more_audits_needed is None:
        return (
            "The audit accuracy so far is at or below the target, so more audits alone "
            "will not reach it; label the model's mistakes to improve it."
        )
    if summary.more_audits_needed == 0:
        return "Enough audits for the target."
    return (
        f"About {summary.more_audits_needed} more audits are expected to reach the target "
        "if the current accuracy holds."
    )


def _audit_round_control(
    result: al.ActiveResult, summary: al.AuditSummary, state: dict[str, Any]
) -> None:
    """Switch the queue to a batch of random audits of confident auto-labels."""
    trend = state.get("trend", [])
    if al.is_stable(trend):
        st.info("CV and trend look stable - an audit round will tighten the estimate fastest.")
    left = summary.more_audits_needed
    expected = (
        "" if left is None or left == 0 else f" About {left} more audits are expected to be needed."
    )
    if st.button(
        f"Start audit round ({al.BATCH_SIZE} random audits of confident auto-labels)",
        type="primary" if al.is_stable(trend) else "secondary",
        help="Stratified across predicted classes in proportion. The normal mixed queue "
        "returns after this batch." + expected,
        key="audit_round",
    ):
        st.session_state.al_queue = al.select_audit_round(
            result.scores, al.BATCH_SIZE, seed=random.randrange(1_000_000)
        )
        st.session_state.al_since_retrain = 0
        st.rerun()
    if expected:
        st.caption(expected.strip())


def _accuracy_panel(
    result: al.ActiveResult, summary: al.AuditSummary, state: dict[str, Any]
) -> None:
    """Top-of-page accuracy indicator: audit accuracy, status, errors left, trend."""
    metrics = result.model.metrics
    st.markdown("##### Estimated auto-label accuracy")
    if summary.accuracy is None:
        st.markdown("**No audit results yet.** Audit items appear in about 15% of each batch.")
    else:
        st.markdown(
            f"### {summary.accuracy:.1%} "
            f"<span style='font-size:1rem;font-weight:400;'>(95% CI "
            f"{summary.lower:.1%} to {summary.upper:.1%})</span>",
            unsafe_allow_html=True,
        )
    st.markdown(_accuracy_bar(summary), unsafe_allow_html=True)
    if summary.ready_to_accept:
        st.success(
            "Target reached - you can accept the model labels, "
            "or keep tagging to tighten the interval."
        )
    else:
        st.warning("Below target - keep tagging.")
    _audit_round_control(result, summary, state)
    cols = st.columns(3)
    cols[0].metric("Audited items", f"{summary.n} ({summary.correct} correct)")
    cols[0].caption(_more_audits_text(summary))
    if summary.errors_remaining is None:
        cols[1].metric("Wrong auto-labels remaining", "unknown")
    else:
        cols[1].metric(
            "Wrong auto-labels remaining",
            f"about {summary.errors_remaining:.0f} of {summary.confident_auto}",
        )
        cols[1].caption(f"Upper bound (95% CI) about {summary.errors_upper:.0f}.")
    cols[2].metric(
        "Model fit (5-fold CV; not audit accuracy)",
        f"AUC {metrics['cv_roc_auc']:.2f} / acc {metrics['cv_accuracy']:.0%}",
    )
    cols[2].caption(
        "Measured on your existing labels only. It does not say how accurate the "
        "auto-labels on unreviewed works are; the audit figure does."
    )
    trend = state.get("trend", [])
    with st.expander(f"Trend after each retrain ({len(trend)} points)"):
        points = [p for p in trend if p.get("audit_accuracy") is not None]
        if len(points) >= 2:
            import pandas as pd

            frame = pd.DataFrame(points).set_index("audit_n")[["audit_accuracy", "audit_lower"]]
            st.line_chart(frame)
        st.dataframe(
            [
                {
                    "retrained": p["at"][:16].replace("T", " "),
                    "labels": p["n_labels"],
                    "audits": p["audit_n"],
                    "audit accuracy": p["audit_accuracy"],
                    "CI lower": p["audit_lower"],
                    "CV accuracy": p["cv_accuracy"],
                    "CV AUC": p["cv_roc_auc"],
                }
                for p in reversed(trend[-12:])
            ],
            use_container_width=True,
            hide_index=True,
        )


def _smart_record(pick: dict[str, Any], value: bool | None, reviewer: str, note: str) -> None:
    table = load_work_reviews(CSV_PATH)  # reload so edits made elsewhere are not lost
    state = al.load_state(ROOT / al.STATE_PATH)
    known = any(row["work_id"] == pick["work_id"] for row in table.rows)
    if value is None and not known:
        # No Haiku row to fall back on: remember the skip in the state file, not the CSV.
        state.setdefault("skipped", []).append(pick["work_id"])
    else:
        if known:
            record_decision(table, pick["work_id"], value, reviewer, note)
        else:
            record_owner_decision(table, pick["work_id"], value, reviewer, note)
        save_work_reviews(table, CSV_PATH)
    al.record_audit(state, pick, value)
    al.save_state(state, ROOT / al.STATE_PATH)
    st.session_state.al_queue = [
        q for q in st.session_state.al_queue if q["work_id"] != pick["work_id"]
    ]
    st.session_state.al_since_retrain += 1
    if st.session_state.al_since_retrain >= RETRAIN_EVERY or not st.session_state.al_queue:
        _retrain()
    st.rerun()


def _sidebar_metrics(result: al.ActiveResult, summary: al.AuditSummary) -> None:
    metrics = result.model.metrics
    with st.sidebar:
        st.divider()
        st.markdown("**Smart queue**")
        st.write(
            f"Human labels: **{metrics['n_labels']}** "
            f"({metrics['n_relevant']} relevant, {metrics['n_not_relevant']} not)"
        )
        st.write(
            f"CV AUC **{metrics['cv_roc_auc']:.2f}**, accuracy **{metrics['cv_accuracy']:.0%}**"
        )
        if summary.accuracy is None:
            st.write("Audit accuracy: none yet")
        else:
            st.write(
                f"Audit accuracy **{summary.accuracy:.1%}** "
                f"(CI {summary.lower:.1%} to {summary.upper:.1%}, n={summary.n})"
            )
        if summary.errors_remaining is not None:
            st.write(f"Est. wrong auto-labels left: **{summary.errors_remaining:.0f}**")
        st.write(f"ready_to_accept: **{summary.ready_to_accept}**")
        st.caption(
            f"Retrains every {RETRAIN_EVERY} decisions "
            f"({st.session_state.al_since_retrain} so far)."
        )
        if st.button("Retrain model", use_container_width=True):
            _retrain()
            st.rerun()


def _accept_panel(result: al.ActiveResult, summary: al.AuditSummary, state: dict[str, Any]) -> None:
    with st.expander("Accept model labels for remaining works"):
        st.caption(
            f"Writes the model's confident calls (p at most 0.1 or at least 0.9; "
            f"{summary.confident_auto} works now) to {al.MODEL_CSV}. In the export they rank "
            "above Haiku and below every owner decision and AT-1 label. "
            "Works you decided are never touched."
        )
        confirm = st.checkbox("I accept the model's labels for the works I did not review")
        if st.button(
            "Accept model labels",
            disabled=not (summary.ready_to_accept and confirm),
            help="Enabled once the accuracy target is reached and this box is ticked.",
        ):
            table = load_work_reviews(CSV_PATH)
            written = al.accept_model_labels(result, state, table.rows, ROOT / al.MODEL_CSV)
            st.success(
                f"Wrote {written} rows to {al.MODEL_CSV}. "
                "Run scripts/build_export_site.py to refresh the site."
            )


def _smart_view(
    items: list[dict[str, Any]], details: dict[str, dict[str, Any]], reviewer: str
) -> None:
    by_key = {str(item["work_id"]): item for item in items}
    for work_id, detail in details.items():  # corpus works with no Haiku row
        by_key.setdefault(
            work_id,
            {**detail, "work_id": work_id, "haiku": None, "confidence": "", "reason": ""},
        )
    if "al_result" not in st.session_state:
        try:
            _retrain()
        except al.InsufficientLabels as error:
            st.error(f"Cannot train yet: {error}")
            return
    result: al.ActiveResult = st.session_state.al_result
    state = al.load_state(ROOT / al.STATE_PATH)
    summary = al.audit_summary(state, result.confident_auto)
    _sidebar_metrics(result, summary)
    _accuracy_panel(result, summary, state)
    _accept_panel(result, summary, state)
    st.divider()

    queue = [q for q in st.session_state.al_queue if q["work_id"] in by_key]
    if not queue:
        st.success("Queue empty. Press Retrain model for a new batch.")
        return
    pick = queue[0]
    item = by_key[pick["work_id"]]
    st.markdown(f"**{len(queue)}** left in this batch.")
    model_says = "plastic-related" if pick["model_pred"] else "not plastic-related"
    model_badge = _badge(f"Model: {model_says} (p = {pick['p_relevant']:.2f})", NEUTRAL)
    st.markdown(f"{model_badge} &nbsp; {_suggestion_badge(item)}", unsafe_allow_html=True)
    st.info(REASON_TEXT[pick["reason"]])
    if item.get("reason"):
        st.caption(f"Haiku's reason: {item['reason']}")
    work_id = str(item["work_id"])
    note = st.text_input("Owner note (optional)", key=f"note_{work_id}")
    decisions = (
        ("smart_true", "Plastic-related ✓", True),
        ("smart_false", "Not plastic-related ✗", False),
        ("smart_unsure", "Unsure (skip)", None),
    )
    for column, (key, text, value) in zip(st.columns(3), decisions, strict=True):
        if column.button(text, key=key, use_container_width=True):
            if not reviewer.strip():
                st.error("Enter your initials in the sidebar first.")
            else:
                _smart_record(pick, value, reviewer, note)
    st.divider()
    abstract_html = _show_record(
        item.get("title"),
        item.get("abstract"),
        empty="No abstract in OpenAlex for this work.",
    )
    st.markdown(_facts(item))
    links = st.columns(2)
    if item.get("doi"):
        links[0].link_button("Open DOI", str(item["doi"]), use_container_width=True)
    if item.get("url"):
        links[1].link_button("Open in OpenAlex", str(item["url"]), use_container_width=True)
    st.markdown("**Abstract**")
    st.html(abstract_html)


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
        ml_problem = _ml_available()
        if ml_problem:
            st.warning(f"Smart queue unavailable: {ml_problem}")
        views = VIEWS if ml_problem else (SMART_VIEW, *VIEWS)
        view = st.selectbox("Show", views, index=0)
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

    if view == SMART_VIEW:
        _smart_view(items, details, reviewer)
        return

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

    abstract_html = _show_record(
        item.get("title"),
        item.get("abstract"),
        empty="No abstract in OpenAlex for this work.",
    )
    st.markdown(_facts(item))
    links = st.columns(2)
    if item.get("doi"):
        links[0].link_button("Open DOI", str(item["doi"]), use_container_width=True)
    if item.get("url"):
        links[1].link_button("Open in OpenAlex", str(item["url"]), use_container_width=True)
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
