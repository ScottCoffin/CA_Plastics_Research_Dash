"""Candidate plastic-v3.2 query rendering for BQ-S2 (A3 sections 5.1, 5.2, 5.8 and 5.9).

The candidate is never the active query. It renders per-theme count requests, the v3.1 baseline,
and the combined expression. Every expression is wrapped so that it is fully parenthesised, and
every request URL is checked against the same limit that scripts/fetch_trend_global.py uses.
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from atlas.ingest.openalex import OPENALEX_BASE
from atlas.query import _term, load_query_config, render_query, type_filters

# Same limit and URL pattern as scripts/fetch_trend_global.py (MAX_URL_CHARS, build_url).
MAX_URL_CHARS = 8000
TITLE_FIELD = "title.search"
OPERATORS = frozenset({"AND", "OR", "NOT"})
_FIELD_PREFIX = re.compile(r"^[a-z_.]+:(?=\()")
_TOKEN = re.compile(r'\s*(?:(?P<open>\()|(?P<close>\))|"(?P<phrase>[^"]*)"|(?P<word>[^\s()"]+))')


class UrlTooLongError(ValueError):
    """Raised when a request URL is longer than MAX_URL_CHARS."""


class ExpressionError(ValueError):
    """Raised when a boolean expression cannot be tokenized."""


def _strip_field(expression: str) -> str:
    """Drop a leading ``field.name:`` prefix so that the boolean itself is checked."""

    text = expression.strip()
    return _FIELD_PREFIX.sub("", text, count=1)


def _tokens(expression: str) -> list[tuple[str, str]]:
    """Tokenize a boolean expression into ``(, ), OP, TERM`` tokens; quoted phrases stay whole."""

    text = _strip_field(expression)
    if not text:
        raise ExpressionError("empty expression")
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if match is None:
            raise ExpressionError(f"cannot tokenize at position {pos}")
        pos = match.end()
        if match.group("open"):
            tokens.append(("(", "("))
        elif match.group("close"):
            tokens.append((")", ")"))
        elif match.group("phrase") is not None:
            if not match.group("phrase").strip():
                raise ExpressionError("empty quoted phrase")
            tokens.append(("TERM", match.group("phrase")))
        else:
            word = match.group("word")
            tokens.append(("OP", word) if word in OPERATORS else ("TERM", word))
    return tokens


def operator_count(expression: str) -> int:
    """Number of boolean operators (AND, OR, NOT) outside quoted phrases."""

    return sum(1 for kind, _ in _tokens(expression) if kind == "OP")


def _check_sequence(tokens: list[tuple[str, str]], pos: int) -> tuple[bool, int, set[str]]:
    """Check operands joined by a single operator kind; stops before an unmatched ')'."""

    operators: set[str] = set()
    expect_operand = True
    while pos < len(tokens):
        kind, value = tokens[pos]
        if expect_operand:
            if kind == "TERM":
                pos += 1
            elif kind == "(":
                ok, pos = _check_group(tokens, pos)
                if not ok:
                    return False, pos, operators
            else:
                return False, pos, operators
            expect_operand = False
            continue
        if kind == ")":
            break
        if kind != "OP":
            return False, pos, operators
        operators.add(value)
        pos += 1
        expect_operand = True
    if expect_operand:
        return False, pos, operators
    return len(operators) <= 1, pos, operators


def _check_group(tokens: list[tuple[str, str]], pos: int) -> tuple[bool, int]:
    """Check one parenthesised group starting at ``tokens[pos]`` (an opening parenthesis)."""

    ok, pos, _ = _check_sequence(tokens, pos + 1)
    if not ok or pos >= len(tokens) or tokens[pos][0] != ")":
        return False, pos
    return True, pos + 1


def is_fully_parenthesised(expression: str) -> bool:
    """True when every AND/OR/NOT group is wrapped in its own parentheses.

    Rules: one operator kind per parenthesised group (``a OR b AND c`` is rejected); operands and
    operators strictly alternate; the top level is a single operand, never a bare operator group
    (``(a) NOT (b)`` is rejected, ``((a) NOT (b))`` is accepted); parentheses balance.
    """

    try:
        tokens = _tokens(expression)
    except ExpressionError:
        return False
    ok, pos, operators = _check_sequence(tokens, 0)
    if not ok or pos != len(tokens):
        return False
    return not operators


def check_url_length(url: str) -> str:
    """Return the URL, or raise UrlTooLongError when it is over MAX_URL_CHARS."""

    if len(url) > MAX_URL_CHARS:
        raise UrlTooLongError(f"request URL is {len(url)} characters; limit is {MAX_URL_CHARS}")
    return url


def works_url(expression: str, *, field: str, config: Mapping[str, Any]) -> str:
    """Count-request URL for one expression: per_page=1 plus the configured type exclusions."""

    filters = [f"{field}:{expression}", *type_filters(config)]
    params = {"filter": ",".join(filters), "per_page": 1}
    return f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


def wrapped(config: Mapping[str, Any], *, include_exclusions: bool = True) -> str:
    """render_query output wrapped once more, so the whole expression is one parenthesised group."""

    return f"({render_query(config, include_exclusions=include_exclusions)})"


def factored_expression(config: Mapping[str, Any], *, include_exclusions: bool = True) -> str:
    """Like render_query, but qualified terms that share an identical any_context list are grouped.

    ``(t1 AND (c)) OR (t2 AND (c))`` becomes ``((t1 OR t2) AND (c))``: the same boolean function
    with fewer operators and characters. Groups keep the order of their first term.
    """

    groups: dict[tuple[str, ...], list[str]] = {}
    for qualified in config["qualified_terms"]:
        contexts = tuple(qualified["any_context"])
        if not contexts:
            raise ValueError(f"qualified term has no context: {qualified['term']!r}")
        groups.setdefault(contexts, []).append(_term(qualified["term"]))
    positive = [_term(term) for term in config["core_terms"]]
    for contexts, names in groups.items():
        context_text = " OR ".join(_term(context) for context in contexts)
        if len(names) == 1:
            positive.append(f"({names[0]} AND ({context_text}))")
        else:
            positive.append(f"(({' OR '.join(names)}) AND ({context_text}))")
    expression = f"({' OR '.join(positive)})"
    if include_exclusions:
        exclusions = [_term(term) for term in config["exclusions"]]
        if exclusions:
            expression += f" NOT ({' OR '.join(exclusions)})"
    return expression


def factored_wrapped(config: Mapping[str, Any], *, include_exclusions: bool = True) -> str:
    """factored_expression, wrapped once more so the whole expression is one group."""

    return f"({factored_expression(config, include_exclusions=include_exclusions)})"


def theme_config(config: Mapping[str, Any], theme: str, *, title: bool = False) -> dict[str, Any]:
    """Sub-config holding one theme's added rows (title_and_abstract or title.search rows)."""

    themes = config["themes"]
    if theme not in themes:
        raise KeyError(f"unknown theme {theme!r}")
    if title:
        names = list(themes[theme].get("title_only", []))
        rows = [r for r in config.get("title_only_terms", []) if r["term"] in names]
        key = "title_only_terms"
    else:
        names = list(themes[theme].get("terms", []))
        rows = [
            r for r in config["qualified_terms"] if r.get("theme") == theme and r["term"] in names
        ]
        key = "qualified_terms"
    if len(rows) != len(names):
        raise ValueError(f"theme {theme!r} names terms with no matching {key} row")
    return {
        "core_terms": [],
        "qualified_terms": rows,
        "exclusions": list(config["exclusions"]),
    }


def base_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """The v3.1 terms copied into the candidate (rows without register_term)."""

    return {
        "core_terms": list(config["core_terms"]),
        "qualified_terms": [q for q in config["qualified_terms"] if "register_term" not in q],
        "exclusions": list(config["exclusions"]),
    }


def validate_candidate(config: Mapping[str, Any]) -> None:
    """Structural checks that the tests and the count script rely on."""

    if config.get("status") != "candidate":
        raise ValueError("candidate config must have status: candidate")
    if config.get("promotion", {}).get("status") != "not promoted":
        raise ValueError("candidate must not be promoted")
    themed = {(r["theme"], r["term"]) for r in config["qualified_terms"] if "register_term" in r}
    for theme, block in config["themes"].items():
        for name in block.get("terms", []):
            if (theme, name) not in themed:
                raise ValueError(f"theme {theme!r} lists {name!r} with no qualified row")
    for row in config.get("title_only_terms", []):
        if row["term"] not in config["themes"].get(row["theme"], {}).get("title_only", []):
            raise ValueError(f"title_only row {row['term']!r} missing from its theme block")
    for row in config["qualified_terms"]:
        if (
            "register_term" in row
            and "context_source" not in row
            and row["any_context"] != config["anchor_phrases"]
        ):
            raise ValueError(f"added row {row['term']!r} lacks the anchor context")


def load_candidate(path: str) -> dict[str, Any]:
    """Load and validate the candidate configuration."""

    config = load_query_config(path)
    validate_candidate(config)
    return config


@dataclass(frozen=True)
class CountRequest:
    """One count request: a label, the boolean it counts, and its full URL."""

    label: str
    kind: str
    field: str
    expression: str
    url: str

    @property
    def length(self) -> int:
        return len(self.url)

    @property
    def operators(self) -> int:
        return operator_count(self.expression)


def _request(
    label: str, kind: str, field: str, expression: str, config: Mapping[str, Any]
) -> CountRequest:
    url = works_url(expression, field=field, config=config)
    return CountRequest(label=label, kind=kind, field=field, expression=expression, url=url)


@dataclass(frozen=True)
class Plan:
    """All count requests for BQ-S2, plus the incremental requests the URL limit dropped."""

    v31: CountRequest
    combined_length: int
    base: CountRequest | None
    combined: CountRequest | None
    themes: tuple[CountRequest, ...]
    titles: tuple[CountRequest, ...]
    incremental: tuple[CountRequest, ...]
    skipped_incremental: tuple[tuple[str, int], ...]

    def requests(self) -> list[CountRequest]:
        """Every request that will be sent in live mode, in a fixed order."""

        found = [self.v31]
        found += [r for r in (self.base, self.combined) if r is not None]
        found += list(self.themes) + list(self.titles) + list(self.incremental)
        return found


def plan(config: Mapping[str, Any], v31: Mapping[str, Any]) -> Plan:
    """Render every request. The combined expression is split by theme when it is too long."""

    v31_request = _request("v31", "v31", v31["openalex"]["field"], wrapped(v31), v31)
    v31_expression = wrapped(v31)
    field = config["openalex"]["field"]

    full = _request("combined", "combined", field, factored_wrapped(config), config)
    if full.length <= MAX_URL_CHARS:
        base = None
        combined: CountRequest | None = full
    else:
        base = _request(
            "base (v3.1 terms, candidate exclusions)",
            "base",
            field,
            factored_wrapped(base_config(config)),
            config,
        )
        check_url_length(base.url)
        combined = None

    themes: list[CountRequest] = []
    incremental: list[CountRequest] = []
    skipped: list[tuple[str, int]] = []
    for theme, block in config["themes"].items():
        if block.get("terms"):
            sub = theme_config(config, theme)
            request = _request(f"theme:{theme}", "theme", field, factored_wrapped(sub), config)
            check_url_length(request.url)
            themes.append(request)
            inc_expression = f"({factored_wrapped(sub)} NOT {v31_expression})"
            inc = _request(f"incremental:{theme}", "incremental", field, inc_expression, config)
            if inc.length <= MAX_URL_CHARS:
                incremental.append(inc)
            else:
                skipped.append((theme, inc.length))
    titles: list[CountRequest] = []
    for theme, block in config["themes"].items():
        if block.get("title_only"):
            sub = theme_config(config, theme, title=True)
            request = _request(
                f"title:{theme}", "title", TITLE_FIELD, factored_wrapped(sub), config
            )
            check_url_length(request.url)
            titles.append(request)
    return Plan(
        v31=v31_request,
        combined_length=full.length,
        base=base,
        combined=combined,
        themes=tuple(themes),
        titles=tuple(titles),
        incremental=tuple(incremental),
        skipped_incremental=tuple(skipped),
    )
