"""Loader and validator for the OPC Solutions track (Add-on A2 §7 Part A, EM-17).

The 22 recommended early actions are hand-curated in config/opc_early_actions.yml. The topic
keys an Atlas link may name are read from site/assets/topics.js. The owner's review of the
Global Plastic Laws mapping is kept in curation/opc_mapping_review.csv and applied by
``apply_review``. This module makes no network calls.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml

from atlas.csv_review import ReviewSheet, load_sheet, save_sheet

DISCLAIMER = (
    "The Global Plastic Laws Database is an educational and research resource and should not "
    "be regarded as fully comprehensive or completely up to date for legal purposes."
)
ACTION_COUNT = 22
MAPPING_STATUSES = frozenset({"draft", "owner_reviewed"})
TOP_LEVEL_KEYS = ("source", "mapping_status", "gpl", "objectives", "actions")
ACTION_KEYS = (
    "code",
    "objective",
    "group",
    "summary",
    "deadline_as_stated",
    "deadline_year",
    "pdf_page",
    "gpl_topics",
    "atlas",
)
CODE = re.compile(r"^2A\.([123])\.\d$")
DEADLINE_PREFIXES = ("by ", "beginning in ", "adopted or reissued after ")
DEADLINE_YEARS = range(2022, 2031)
SUMMARY_MAX_LENGTH = 200
# Summaries paraphrase what the Strategy asks for; they must not claim implementation or effect.
FORBIDDEN_SUMMARY_TERMS = ("enforced", "implemented", "effective in reducing", "is effective")
TOPIC_KEY = re.compile(r"^[ \t]+([a-z_]+): \{", re.MULTILINE)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "config" / "opc_early_actions.yml"
TOPICS_PATH = ROOT / "site" / "assets" / "topics.js"
REVIEW_PATH = ROOT / "curation" / "opc_mapping_review.csv"
REVIEW_COLUMNS = ("code", "decision", "owner_gpl_topics", "note", "reviewer", "reviewed_at")
REVIEW_DECISIONS = frozenset({"accept", "change", "none"})


class OpcActionsError(ValueError):
    """Raised when the curated OPC early actions fail validation."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _non_empty_str(value: Any, where: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise OpcActionsError(f"{where} must be a non-empty string")


def _https(value: Any, where: str) -> None:
    if not isinstance(value, str) or not value.startswith("https://"):
        raise OpcActionsError(f"{where} must be an https URL, got {value!r}")


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OpcActionsError(f"{where} must be a mapping")
    return value


def topic_keys(path: Path | str = TOPICS_PATH) -> frozenset[str]:
    """Return the topic keys defined in the TOPICS object of site/assets/topics.js."""
    keys = frozenset(TOPIC_KEY.findall(Path(path).read_text(encoding="utf-8")))
    if not keys:
        raise OpcActionsError(f"no topic keys found in {path}")
    return keys


def _check_action(
    action: Any,
    index: int,
    objectives: frozenset[int],
    slugs: frozenset[str],
    topics: frozenset[str],
) -> str:
    if not isinstance(action, dict):
        raise OpcActionsError(f"action {index}: must be a mapping")
    code = str(action.get("code", f"action {index}"))
    missing = [key for key in ACTION_KEYS if key not in action]
    if missing:
        raise OpcActionsError(f"{code}: missing keys {missing}")
    match = CODE.match(action["code"]) if isinstance(action["code"], str) else None
    if match is None:
        raise OpcActionsError(f"{code}: code must match 2A.N.N with N from 1 to 3")
    objective = action["objective"]
    if not _is_int(objective) or objective not in objectives:
        raise OpcActionsError(f"{code}: objective {objective!r} is not in objectives")
    if int(match.group(1)) != objective:
        raise OpcActionsError(f"{code}: code and objective disagree")
    _non_empty_str(action["group"], f"{code}: group")
    summary = action["summary"]
    _non_empty_str(summary, f"{code}: summary")
    if len(summary) > SUMMARY_MAX_LENGTH:
        raise OpcActionsError(f"{code}: summary must be {SUMMARY_MAX_LENGTH} characters or fewer")
    lowered = summary.lower()
    if any(term in lowered for term in FORBIDDEN_SUMMARY_TERMS):
        raise OpcActionsError(f"{code}: summary must not claim implementation or effect")
    deadline = action["deadline_as_stated"]
    if not isinstance(deadline, str) or not deadline.startswith(DEADLINE_PREFIXES):
        raise OpcActionsError(
            f"{code}: deadline_as_stated must start with 'by ', 'beginning in ' "
            "or 'adopted or reissued after '"
        )
    year = action["deadline_year"]
    if not _is_int(year) or year not in DEADLINE_YEARS:
        raise OpcActionsError(f"{code}: deadline_year must be an integer from 2022 to 2030")
    years = re.findall(r"\d{4}", deadline)
    if not years or int(years[-1]) != year:
        raise OpcActionsError(f"{code}: deadline_year {year} does not match deadline_as_stated")
    page = action["pdf_page"]
    if not _is_int(page) or page < 1:
        raise OpcActionsError(f"{code}: pdf_page must be a positive integer")
    used = action["gpl_topics"]
    if not isinstance(used, list) or not all(isinstance(slug, str) for slug in used):
        raise OpcActionsError(f"{code}: gpl_topics must be a list of slugs")
    unknown = [slug for slug in used if slug not in slugs]
    if unknown:
        raise OpcActionsError(f"{code}: gpl_topics {unknown} not in gpl.topics")
    if len(set(used)) != len(used):
        raise OpcActionsError(f"{code}: gpl_topics repeats a slug")
    atlas = _mapping(action["atlas"], f"{code}: atlas")
    if set(atlas) == {"q"}:
        _non_empty_str(atlas["q"], f"{code}: atlas.q")
    elif set(atlas) == {"topic"}:
        topic = atlas["topic"]
        if not isinstance(topic, str) or topic not in topics:
            raise OpcActionsError(f"{code}: atlas.topic {topic!r} is not in site/assets/topics.js")
    else:
        raise OpcActionsError(f"{code}: atlas must have exactly one of q or topic")
    return code


def validate_actions(data: Any, topics: frozenset[str] | None = None) -> dict[str, Any]:
    """Validate an already-parsed OPC actions mapping and return it.

    ``topics`` is the set of topic keys an Atlas link may name. It defaults to the keys in
    site/assets/topics.js.
    """
    if not isinstance(data, dict):
        raise OpcActionsError("actions file must be a mapping")
    missing = [key for key in TOP_LEVEL_KEYS if key not in data]
    if missing:
        raise OpcActionsError(f"missing top-level keys {missing}")
    if data["mapping_status"] not in MAPPING_STATUSES:
        raise OpcActionsError(f"mapping_status must be one of {sorted(MAPPING_STATUSES)}")
    source = _mapping(data["source"], "source")
    for key in ("label", "adopted"):
        _non_empty_str(source.get(key), f"source.{key}")
    _https(source.get("url"), "source.url")
    gpl = _mapping(data["gpl"], "gpl")
    for key in ("name", "steward"):
        _non_empty_str(gpl.get(key), f"gpl.{key}")
    _https(gpl.get("base_url"), "gpl.base_url")
    _https(gpl.get("california_search_url"), "gpl.california_search_url")
    if gpl.get("disclaimer") != DISCLAIMER:
        raise OpcActionsError("gpl.disclaimer must equal the required sentence exactly")
    slugs = _mapping(gpl.get("topics"), "gpl.topics")
    if not slugs:
        raise OpcActionsError("gpl.topics must not be empty")
    for slug, name in slugs.items():
        _non_empty_str(name, f"gpl.topics.{slug}")
    objectives = data["objectives"]
    if not isinstance(objectives, list) or not objectives:
        raise OpcActionsError("objectives must be a non-empty list")
    ids: list[int] = []
    for index, objective in enumerate(objectives):
        if not isinstance(objective, dict) or not _is_int(objective.get("id")):
            raise OpcActionsError(f"objective {index}: id must be an integer")
        _non_empty_str(objective.get("name"), f"objective {objective['id']}: name")
        ids.append(objective["id"])
    if len(set(ids)) != len(ids):
        raise OpcActionsError("objective ids must be unique")
    actions = data["actions"]
    if not isinstance(actions, list) or len(actions) != ACTION_COUNT:
        found = len(actions) if isinstance(actions, list) else actions
        raise OpcActionsError(
            f"actions must list exactly {ACTION_COUNT} early actions, got {found}"
        )
    atlas_topics = topic_keys() if topics is None else topics
    codes: set[str] = set()
    for index, action in enumerate(actions):
        code = _check_action(action, index, frozenset(ids), frozenset(slugs), atlas_topics)
        if code in codes:
            raise OpcActionsError(f"duplicate code {code}")
        codes.add(code)
    return data


def load_actions(
    path: Path | str = DEFAULT_PATH, topics_path: Path | str = TOPICS_PATH
) -> dict[str, Any]:
    """Load and validate the curated OPC early actions YAML."""
    with Path(path).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return validate_actions(data, topic_keys(topics_path))


# Owner review of the mapping to Global Plastic Laws topics (EM-17b).


def review_topics(text: str) -> list[str]:
    """Split an ``owner_gpl_topics`` cell (slugs joined by ";") into a list of slugs."""
    return [part.strip() for part in text.split(";") if part.strip()]


def read_review(path: Path | str = REVIEW_PATH) -> list[dict[str, str]]:
    """Return the owner's review rows, one per action code, from the CSV sheet."""
    return load_sheet(Path(path), key="code", required=REVIEW_COLUMNS).rows


def blank_review_rows(data: dict[str, Any]) -> list[dict[str, str]]:
    """One empty review row per action, in YAML order."""
    return [
        {"code": action["code"], **{column: "" for column in REVIEW_COLUMNS[1:]}}
        for action in data["actions"]
    ]


def init_review_sheet(path: Path | str = REVIEW_PATH, data: dict[str, Any] | None = None) -> None:
    """Write a blank review sheet. Refuses to replace a sheet that holds any owner input."""
    target = Path(path)
    if target.exists():
        for row in read_review(target):
            if any(value.strip() for column, value in row.items() if column != "code"):
                raise OpcActionsError(f"{target} already holds owner input; not overwritten")
    curated = load_actions() if data is None else data
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = blank_review_rows(curated)
    save_sheet(ReviewSheet(target, list(REVIEW_COLUMNS), rows, "\n", "code"))


def apply_review(data: dict[str, Any], sheet_rows: Iterable[Mapping[str, str]]) -> dict[str, Any]:
    """Return a copy of ``data`` with the owner's topic decisions applied.

    ``sheet_rows`` are rows of curation/opc_mapping_review.csv. ``accept`` keeps the draft
    topics, ``change`` takes ``owner_gpl_topics`` and ``none`` leaves no topic. A blank
    decision keeps the draft. ``mapping_status`` is ``owner_reviewed`` only when every action
    has a decision, and ``draft`` otherwise.
    """
    actions = {action["code"]: action for action in data["actions"]}
    known = frozenset(data["gpl"]["topics"])
    seen: set[str] = set()
    decided: dict[str, tuple[str, list[str]]] = {}
    for row in sheet_rows:
        code = (row.get("code") or "").strip()
        if code not in actions:
            raise OpcActionsError(f"review sheet: unknown action code {code!r}")
        if code in seen:
            raise OpcActionsError(f"review sheet: {code} is listed more than once")
        seen.add(code)
        decision = (row.get("decision") or "").strip()
        if decision and decision not in REVIEW_DECISIONS:
            raise OpcActionsError(f"{code}: decision must be blank, accept, change or none")
        topics = review_topics(row.get("owner_gpl_topics") or "")
        unknown = [slug for slug in topics if slug not in known]
        if unknown:
            raise OpcActionsError(f"{code}: owner_gpl_topics {unknown} not in gpl.topics")
        if len(set(topics)) != len(topics):
            raise OpcActionsError(f"{code}: owner_gpl_topics repeats a slug")
        if decision == "change" and not topics:
            raise OpcActionsError(f"{code}: decision change needs at least one topic")
        if decision != "change" and topics:
            raise OpcActionsError(f"{code}: owner_gpl_topics is only used with decision change")
        if decision:
            decided[code] = (decision, topics)
    result = copy.deepcopy(data)
    for action in result["actions"]:
        choice = decided.get(action["code"])
        if choice and choice[0] != "accept":
            action["gpl_topics"] = choice[1]
    result["mapping_status"] = "owner_reviewed" if len(decided) == len(actions) else "draft"
    return result
