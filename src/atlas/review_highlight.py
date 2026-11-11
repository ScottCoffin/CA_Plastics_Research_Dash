"""Highlight the search terms that admitted a record, for the Streamlit review apps.

The review apps show a title and an abstract and ask a human whether the record is
about plastic. This module marks the terms that let the record through the search
filters so the reviewer can see at a glance *why* it is in the queue:

* ``core``: a ``core_terms`` entry of the query config (or a grant strong term).
* ``qualified``: a ``qualified_terms`` entry whose context also occurs in the record.
* ``context``: the context word that qualified it (marked only when the term occurs).
* ``tier_2``: a chemicals-in-plastics ``tier_2_terms`` entry.
* ``keyword``: a grant-source search keyword (for example bare ``plastic`` or ``debris``).
* ``exclusion``: an ``exclusions`` entry; a hit means the record should usually be out.
* ``stem``: any other ``plastic*`` word. OpenAlex stems search terms, so ``plasticity``
  or ``plastics`` can admit a work on their own; these are the usual noise hits.

Matching follows ``atlas.nlp.labels``: case-insensitive, whole words, spaces match any
run of whitespace or hyphens, and an optional plural ``s``/``es``. Text is HTML-escaped
before any markup is added, so the output is safe for ``st.html``.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# Lower number wins when two matches overlap.
PRIORITY: dict[str, int] = {
    "exclusion": 0,
    "core": 1,
    "qualified": 2,
    "tier_2": 3,
    "context": 4,
    "keyword": 5,
    "stem": 6,
}

STYLES: dict[str, str] = {
    "core": "background:#fde047;color:#111827;",
    "qualified": "background:#fdba74;color:#111827;",
    "context": "background:#fef3c7;color:#111827;",
    "tier_2": "background:#93c5fd;color:#111827;",
    "keyword": "background:#bbf7d0;color:#111827;",
    "exclusion": "background:#fca5a5;color:#7f1d1d;text-decoration:line-through;",
    "stem": "background:transparent;color:inherit;border-bottom:2px dashed #9ca3af;",
}

DESCRIPTIONS: dict[str, str] = {
    "core": "core search term",
    "qualified": "qualified term (context present)",
    "context": "qualifying context",
    "tier_2": "chemicals-in-plastics term",
    "keyword": "grant search keyword",
    "exclusion": "exclusion term",
    "stem": "other plastic* word (OpenAlex stem match)",
}

STEM_PATTERN = re.compile(r"(?<!\w)\w*plastic\w*", re.IGNORECASE)
_MARK_BASE = "padding:0 2px;border-radius:3px;"


@dataclass(frozen=True)
class Rule:
    """One highlightable term."""

    kind: str
    label: str
    pattern: re.Pattern[str]
    requires: tuple[re.Pattern[str], ...] = ()


@dataclass(frozen=True)
class Hit:
    start: int
    end: int
    kind: str
    label: str


def term_pattern(term: str) -> re.Pattern[str]:
    """Whole-word, case-insensitive pattern; spaces/hyphens interchangeable; plural ok."""

    value = term.strip()
    parts = [re.escape(part) for part in re.split(r"[\s-]+", value) if part]
    body = r"[\s\-]+".join(parts)
    plural = r"(?:e?s)?" if value[-1:].casefold() not in {"s", "x", "z"} else ""
    return re.compile(rf"(?<!\w){body}{plural}(?!\w)", re.IGNORECASE)


def _strings(values: object) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    return [str(value).strip() for value in values if str(value or "").strip()]


def rules_from_query_config(config: Mapping[str, Any]) -> list[Rule]:
    """Rules for one ``config/queries*.yml`` mapping."""

    rules = [Rule("core", term, term_pattern(term)) for term in _strings(config.get("core_terms"))]
    for entry in config.get("qualified_terms") or []:
        if not isinstance(entry, Mapping):
            continue
        term = str(entry.get("term") or "").strip()
        contexts = _strings(entry.get("any_context"))
        if not term or not contexts:
            continue
        term_re = term_pattern(term)
        context_res = tuple(term_pattern(context) for context in contexts)
        rules.append(Rule("qualified", term, term_re, requires=context_res))
        for context, context_re in zip(contexts, context_res, strict=True):
            rules.append(
                Rule("context", f"{context} (for {term})", context_re, requires=(term_re,))
            )
    rules += [Rule("tier_2", t, term_pattern(t)) for t in _strings(config.get("tier_2_terms"))]
    rules += [Rule("exclusion", t, term_pattern(t)) for t in _strings(config.get("exclusions"))]
    return rules


def keyword_rules(keywords: Iterable[str], *, kind: str = "keyword") -> list[Rule]:
    return [Rule(kind, k.strip(), term_pattern(k)) for k in keywords if k and k.strip()]


def regex_rule(kind: str, label: str, pattern: re.Pattern[str]) -> Rule:
    return Rule(kind, label, pattern)


def build_rules(
    configs: Iterable[Mapping[str, Any]] = (),
    *,
    extra: Iterable[Rule] = (),
    include_stem: bool = True,
) -> list[Rule]:
    """Union of rules from several query configs plus extras, de-duplicated by label."""

    seen: set[tuple[str, str]] = set()
    out: list[Rule] = []
    candidates: list[Rule] = []
    for config in configs:
        candidates += rules_from_query_config(config)
    candidates += list(extra)
    if include_stem:
        candidates.append(Rule("stem", "plastic*", STEM_PATTERN))
    for rule in candidates:
        key = (rule.kind, rule.label.casefold())
        if key not in seen:
            seen.add(key)
            out.append(rule)
    return out


def active_rules(rules: Sequence[Rule], *texts: str | None) -> list[Rule]:
    """Drop qualified terms/contexts whose partner does not occur in the record."""

    combined = " ".join(text for text in texts if text)
    return [r for r in rules if not r.requires or any(p.search(combined) for p in r.requires)]


def find_hits(text: str, rules: Sequence[Rule]) -> list[Hit]:
    """Non-overlapping hits; higher-priority kinds, then longer matches, win."""

    if not text:
        return []
    candidates = [
        Hit(m.start(), m.end(), rule.kind, rule.label)
        for rule in rules
        for m in rule.pattern.finditer(text)
        if m.end() > m.start()
    ]
    candidates.sort(key=lambda h: (PRIORITY.get(h.kind, 99), -(h.end - h.start), h.start))
    taken: list[Hit] = []
    for hit in candidates:
        if all(hit.end <= t.start or hit.start >= t.end for t in taken):
            taken.append(hit)
    return sorted(taken, key=lambda h: h.start)


def highlight_html(text: str | None, rules: Sequence[Rule]) -> str:
    """HTML-escaped ``text`` with each hit wrapped in a styled ``<mark>``."""

    if not text:
        return ""
    parts: list[str] = []
    cursor = 0
    for hit in find_hits(text, rules):
        parts.append(html.escape(text[cursor : hit.start]))
        style = _MARK_BASE + STYLES.get(hit.kind, "")
        tip = html.escape(f"{DESCRIPTIONS.get(hit.kind, hit.kind)}: {hit.label}", quote=True)
        parts.append(
            f'<mark style="{style}" title="{tip}">{html.escape(text[hit.start : hit.end])}</mark>'
        )
        cursor = hit.end
    parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def hit_summary(rules: Sequence[Rule], *texts: str | None) -> list[tuple[str, str, int]]:
    """``(kind, label, count)`` for every matched rule, in priority then count order."""

    counts: Counter[tuple[str, str]] = Counter()
    for text in texts:
        for hit in find_hits(text or "", rules):
            label = text[hit.start : hit.end].casefold() if hit.kind == "stem" else hit.label
            counts[(hit.kind, label)] += 1
    rows = [(kind, label, n) for (kind, label), n in counts.items()]
    rows.sort(key=lambda r: (PRIORITY.get(r[0], 99), -r[2], r[1]))
    return rows


def summary_html(rows: Sequence[tuple[str, str, int]]) -> str:
    """A compact 'Matched terms' line; says so when nothing matched."""

    if not rows:
        return (
            '<div style="font-size:0.85rem;opacity:0.8">Matched search terms: '
            "<em>none in title or abstract</em> (admitted by another field, a stem, "
            "or an author/institution route)</div>"
        )
    chips = []
    for kind, label, count in rows:
        style = _MARK_BASE + STYLES.get(kind, "")
        tip = html.escape(DESCRIPTIONS.get(kind, kind), quote=True)
        suffix = f" &times;{count}" if count > 1 else ""
        chips.append(f'<mark style="{style}" title="{tip}">{html.escape(label)}{suffix}</mark>')
    return (
        '<div style="font-size:0.85rem;line-height:1.9">Matched search terms: '
        + " ".join(chips)
        + "</div>"
    )


def legend_html(kinds: Iterable[str] = tuple(PRIORITY)) -> str:
    items = [
        f'<mark style="{_MARK_BASE}{STYLES[k]}">{html.escape(DESCRIPTIONS[k])}</mark>'
        for k in kinds
        if k in STYLES
    ]
    return '<div style="font-size:0.8rem;line-height:1.9">' + " ".join(items) + "</div>"


def title_block(title: str | None, rules: Sequence[Rule]) -> str:
    body = highlight_html(title, rules) if title else "(no title)"
    style = "font-size:1.45rem;font-weight:600;line-height:1.35;margin:0.2rem 0"
    return f'<div style="{style}">{body}</div>'


@dataclass(frozen=True)
class RecordBlocks:
    title: str
    summary: str
    abstract: str


def record_blocks(
    title: str | None, abstract: str | None, rules: Sequence[Rule], *, empty: str
) -> RecordBlocks:
    """Title, matched-terms line and abstract HTML for one record (qualifiers resolved)."""

    title_text = str(title) if title else ""
    abstract_text = str(abstract) if abstract else ""
    live = active_rules(rules, title_text, abstract_text)
    return RecordBlocks(
        title=title_block(title_text, live),
        summary=summary_html(hit_summary(live, title_text, abstract_text)),
        abstract=abstract_block(abstract_text, live, empty),
    )


def abstract_block(abstract: str | None, rules: Sequence[Rule], empty: str) -> str:
    if not abstract:
        return f'<div style="font-style:italic;opacity:0.8">{html.escape(empty)}</div>'
    return (
        '<div style="line-height:1.65;white-space:pre-wrap">'
        + highlight_html(abstract, rules)
        + "</div>"
    )
