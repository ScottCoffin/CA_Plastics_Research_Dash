"""Owner QC of the community groups roster: likely duplicates and suspect names (CG-ROSTER-QC).

Review in the browser, one case per screen:

    py -3.14 -m streamlit run scripts/review_group_roster_app.py

Two queues, chosen in the sidebar:

- Likely duplicates: pairs from data/interim/bffp/dupe_review.csv (local) and pairs in the
  published roster whose websites share an exact host (social, shared and link-shortener hosts
  and broken URLs are left out). "Same, keep A" or "Same, keep B" writes a ``same`` row to
  curation/group_merges.csv; "Different groups" writes a ``different`` row.
- Suspect names: a name with "??", a web address as the name, a bare domain, or a short
  (3 characters or fewer) name in one case. "Name is OK" is remembered in a local state file;
  "Save corrected name" appends a row to curation/group_name_corrections.csv.

Every click saves at once. Cases already decided leave the queue, so reopening the app resumes
at the next open case; "Skip" moves a case to the end of its queue. Nothing is published here.
After review, rebuild with ``py -3.14 scripts/build_groups_roster.py`` (offline, no --fetch) and
then ``py -3.14 scripts/build_groups.py``.

Other files (for tests or a copy): ``-- --roster PATH --dupes PATH --merges PATH
--corrections PATH --state PATH``.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.groups import admission  # noqa: E402

ROSTER_PATH = ROOT / "site" / "data" / "global" / "groups" / "roster.json"
DUPES_PATH = ROOT / "data" / "interim" / "bffp" / "dupe_review.csv"
MERGES_PATH = ROOT / "curation" / "group_merges.csv"
CORRECTIONS_PATH = ROOT / "curation" / "group_name_corrections.csv"
STATE_PATH = ROOT / "data" / "interim" / "bffp" / "group_roster_review_state.json"
QUEUES = ("Likely duplicates", "Suspect names")
URL_START_RE = re.compile(r"^(?:https?://|www\.)", re.IGNORECASE)
DOMAIN_RE = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


def _options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    for flag in ("roster", "dupes", "merges", "corrections", "state"):
        parser.add_argument(f"--{flag}", default="")
    args, _ = parser.parse_known_args()
    return args


def _resolve(value: str, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _paths() -> dict[str, Path]:
    options = _options()
    return {
        "roster": _resolve(options.roster, ROSTER_PATH),
        "dupes": _resolve(options.dupes, DUPES_PATH),
        "merges": _resolve(options.merges, MERGES_PATH),
        "corrections": _resolve(options.corrections, CORRECTIONS_PATH),
        "state": _resolve(options.state, STATE_PATH),
    }


def read_roster(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["records"]


def read_dupes(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_state(path: Path) -> dict[str, list[str]]:
    """Local memory of "Name is OK" ids and skipped case keys. A missing file is empty."""
    if not path.exists():
        return {"name_ok": [], "skipped": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"name_ok": list(data.get("name_ok", [])), "skipped": list(data.get("skipped", []))}


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(text.encode("utf-8"))
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def _csv_text(header: list[str], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_merge(path: Path, keep_id: str, drop_id: str, decision: str, when: str) -> None:
    """Save one duplicate decision; an earlier row for the same pair is replaced."""
    pair = frozenset((keep_id, drop_id))
    rows = [
        row
        for row in admission.read_merges(path)
        if frozenset((row["group_id_keep"], row["group_id_drop"])) != pair
    ]
    rows.append(
        {
            "group_id_keep": keep_id,
            "group_id_drop": drop_id,
            "decided_at": when,
            "decision": decision,
        }
    )
    _write_atomic(path, _csv_text(admission.MERGE_HEADER, rows))


def record_correction(path: Path, group_id: str, name: str, when: str) -> None:
    """Append a corrected display name; the build keeps the last row per group_id."""
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            rows = [dict(row) for row in csv.DictReader(handle)]
    rows.append({"group_id": group_id, "name": name, "submitted_at": when})
    _write_atomic(path, _csv_text(admission.NAME_CORRECTION_HEADER, rows))


def write_state(path: Path, state: dict[str, list[str]]) -> None:
    _write_atomic(path, json.dumps(state, indent=2, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def duplicate_candidates(
    records: list[dict[str, Any]], dupes: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Every likely-duplicate pair (local review list plus same-host pairs), decided or not."""
    by_id = {record["group_id"]: record for record in records}
    found: dict[frozenset[str], dict[str, Any]] = {}

    def add(first_id: str, second_id: str, reason: str) -> None:
        first, second = by_id.get(first_id), by_id.get(second_id)
        if first is None or second is None or first_id == second_id:
            return
        pair = frozenset((first_id, second_id))
        if pair not in found:
            found[pair] = {"kind": "dup", "a": first, "b": second, "reason": reason}

    for row in dupes:
        first_id, second_id = row.get("group_id_a", ""), row.get("group_id_b", "")
        first, second = by_id.get(first_id), by_id.get(second_id)
        if first is None or second is None:
            continue
        shared_domain = row.get("reason") == "same registrable domain"
        if shared_domain and (
            admission.excluded_host(first.get("url")) or admission.excluded_host(second.get("url"))
        ):
            continue
        add(first_id, second_id, row.get("reason", ""))
    for pair in admission.same_host_pairs(records):
        add(pair["group_id_a"], pair["group_id_b"], pair["reason"])
    cases = list(found.values())
    for case in cases:
        case["key"] = "dup:" + "|".join(sorted((case["a"]["group_id"], case["b"]["group_id"])))
    return cases


def suspect_reasons(name: str) -> list[str]:
    text = name.strip()
    reasons: list[str] = []
    if "??" in text:
        reasons.append('the name contains "??"')
    if "�" in text:
        reasons.append("the name has a broken character (�)")
    if "`" in text:
        reasons.append("the name uses a backtick (`) as an apostrophe")
    if "://" in text or URL_START_RE.match(text):
        reasons.append("a web address is used as the name")
    elif DOMAIN_RE.fullmatch(text):
        reasons.append("the name is only a domain")
    short = len(text) <= 3 and any(ch.isalpha() for ch in text)
    if short and (text == text.lower() or text == text.upper()):
        reasons.append("a short name in one case")
    return reasons


def suspect_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = []
    for record in records:
        reasons = suspect_reasons(record["name"])
        if reasons:
            key = "name:" + record["group_id"]
            cases.append({"kind": "name", "key": key, "record": record, "reasons": reasons})
    return cases


def is_done(
    case: dict[str, Any], merges: list[dict[str, str]], corrected: set[str], ok: set[str]
) -> bool:
    """A pair is done once decided; a name is done once it is OK or has a correction."""
    if case["kind"] == "dup":
        pair = frozenset((case["a"]["group_id"], case["b"]["group_id"]))
        return any(frozenset((m["group_id_keep"], m["group_id_drop"])) == pair for m in merges)
    group_id = case["record"]["group_id"]
    return group_id in corrected or group_id in ok


def pending_cases(
    cases: list[dict[str, Any]], done: set[str], skipped: list[str]
) -> list[dict[str, Any]]:
    """Open cases in order, with skipped ones last. Decided cases are left out."""
    open_cases = [c for c in cases if c["key"] not in done]
    return [c for c in open_cases if c["key"] not in skipped] + [
        c for c in open_cases if c["key"] in skipped
    ]


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------


def _show_record(label: str, record: dict[str, Any]) -> None:
    st.markdown(f"**{label}: {record['name']}**")
    alternates = record.get("name_alt") or []
    country = record.get("country") or "country unknown"
    detail = f"{country} · id `{record['group_id']}`"
    if alternates:
        detail += " · other names: " + "; ".join(alternates)
    st.caption(detail)
    if record.get("url"):
        st.link_button(f"Open {label} website", record["url"], width="stretch")
    else:
        st.caption("No website on record.")


def _remember(message: str) -> None:
    st.session_state.just_saved = message


def _duplicate_screen(case: dict[str, Any], paths: dict[str, Path], when: str) -> None:
    st.subheader("Are these the same organisation?")
    st.caption(f"Why this pair is here: {case['reason']}.")
    left, right = st.columns(2)
    with left:
        _show_record("A", case["a"])
    with right:
        _show_record("B", case["b"])
    a_id, b_id = case["a"]["group_id"], case["b"]["group_id"]
    buttons = st.columns(4)
    if buttons[0].button("Same, keep A", type="primary", width="stretch", key="same_a"):
        record_merge(paths["merges"], a_id, b_id, "same", when)
        _remember("Saved: same organisation, keeping A.")
        st.rerun()
    if buttons[1].button("Same, keep B", type="primary", width="stretch", key="same_b"):
        record_merge(paths["merges"], b_id, a_id, "same", when)
        _remember("Saved: same organisation, keeping B.")
        st.rerun()
    if buttons[2].button("Different groups", width="stretch", key="different"):
        record_merge(paths["merges"], a_id, b_id, "different", when)
        _remember("Saved: different groups.")
        st.rerun()
    if buttons[3].button("Skip", width="stretch", key="skip_pair"):
        _skip(paths, case["key"])


def _name_screen(case: dict[str, Any], paths: dict[str, Path], when: str) -> None:
    record = case["record"]
    st.subheader(record["name"])
    st.caption("Why this name is here: " + "; ".join(case["reasons"]) + ".")
    _show_record("Group", record)
    if st.button("Name is OK", type="primary", width="stretch", key="name_ok"):
        state = read_state(paths["state"])
        state["name_ok"] = sorted(set(state["name_ok"]) | {record["group_id"]})
        write_state(paths["state"], state)
        _remember("Saved: name is OK.")
        st.rerun()
    corrected = st.text_input("Corrected name", value=record["name"], key="corrected_name")
    if st.button("Save corrected name", width="stretch", key="save_name"):
        text = admission.normalise_text(corrected)
        if not text or text == record["name"]:
            st.error("Type a different name, or use Name is OK.")
        else:
            record_correction(paths["corrections"], record["group_id"], text, when)
            _remember("Saved: corrected name. It applies at the next rebuild.")
            st.rerun()
    if st.button("Skip", width="stretch", key="skip_name"):
        _skip(paths, case["key"])


def _skip(paths: dict[str, Path], key: str) -> None:
    state = read_state(paths["state"])
    state["skipped"] = sorted(set(state["skipped"]) | {key})
    write_state(paths["state"], state)
    st.rerun()


def main() -> None:
    paths = _paths()
    st.set_page_config(page_title="Atlas community groups: roster QC", layout="wide")
    st.markdown("### Community groups roster: duplicates and names")
    if not paths["roster"].exists():
        st.error(f"No roster at `{paths['roster']}`. Build it first with build_groups_roster.py.")
        return
    try:
        records = read_roster(paths["roster"])
        merges = admission.read_merges(paths["merges"])
        corrections = admission.read_name_corrections(paths["corrections"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        st.error(f"Could not read the review files: {exc}")
        return
    state = read_state(paths["state"])
    ok = set(state["name_ok"])

    with st.sidebar:
        queue = st.radio("Queue", QUEUES, key="queue")
        st.caption("Rebuild after review: build_groups_roster.py, then build_groups.py.")

    if queue == QUEUES[0]:
        candidates = duplicate_candidates(records, read_dupes(paths["dupes"]))
    else:
        candidates = suspect_candidates(records)
    done_keys = {c["key"] for c in candidates if is_done(c, merges, set(corrections), ok)}
    pending = pending_cases(candidates, done_keys, state["skipped"])
    total = len(candidates)
    with st.sidebar:
        st.progress(
            len(done_keys) / total if total else 1.0, text=f"Decided {len(done_keys)} of {total}"
        )
    if msg := st.session_state.pop("just_saved", None):
        st.toast(msg)
    if not pending:
        st.success("Nothing left to review in this queue.")
        return
    when = _now()
    st.caption(f"{len(pending)} case(s) left in this queue.")
    if queue == QUEUES[0]:
        _duplicate_screen(pending[0], paths, when)
    else:
        _name_screen(pending[0], paths, when)


if __name__ == "__main__":
    main()
