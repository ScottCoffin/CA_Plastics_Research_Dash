"""Global gold-sampling frame rules (BQ-G3): blocks, theme groups, rule score and strata.

Everything here is label-blind. The rule score is a transparent proxy for the v3.1 rule engine
(no trained classifier exists); the frame never reads gold labels. Title and abstract text is used
only in memory and is never returned by the public helpers except through their boolean or
numeric results.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import random
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from atlas.nlp.labels import _ordered_terms, _qualified_terms, _term_pattern

MODEL_VERSION = "rules-v3.1-proxy"
GLOBAL_FRAME_SEED = 42043
SCORE_FULL_POINTS = 4
BAND_LOW_MAX = 0.34
BAND_HIGH_MIN = 0.67

BLOCK_REGISTRY = "registry_region"
BLOCK_GLOBAL_EN = "global_english"
BLOCK_GLOBAL_NON_EN = "global_non_english"
BLOCKS = (BLOCK_REGISTRY, BLOCK_GLOBAL_EN, BLOCK_GLOBAL_NON_EN)

THEME_LENS = "lens-candidate"
THEME_LIFECYCLE = "lifecycle-and-society"
THEME_POLLUTION = "pollution-core"
THEME_OTHER = "other"
THEME_GROUPS = (THEME_LENS, THEME_LIFECYCLE, THEME_POLLUTION, THEME_OTHER)

BANDS = ("low", "medium", "high")
BAND_ALL = "all"

LIFECYCLE_GROUP = "lifecycle_and_society"
FRAME_COLUMNS = ("work_id", "doi", "block", "theme_group", "score", "band", "stratum", "rand_key")


class TermSet:
    """Terms compiled once: a combined gate regex answers 'any hit?' in one search.

    Per-term patterns are only run on texts the gate accepts, so most works cost one search.
    """

    def __init__(self, terms: Iterable[str]) -> None:
        unique = tuple(dict.fromkeys(term for term in terms if term))
        self.patterns = tuple(_term_pattern(term) for term in unique)
        self.gate: re.Pattern[str] | None = (
            re.compile("|".join(f"(?:{p.pattern})" for p in self.patterns), re.IGNORECASE)
            if self.patterns
            else None
        )

    def any(self, text: str) -> bool:
        return self.gate is not None and self.gate.search(text) is not None

    def count(self, text: str) -> int:
        if not self.any(text):
            return 0
        return sum(1 for pattern in self.patterns if pattern.search(text))


@dataclass(frozen=True)
class ScoreRules:
    """Rule-score vocabulary from config/queries.yml (v3.1 active query)."""

    core: TermSet
    qualified: tuple[tuple[re.Pattern[str], TermSet], ...]
    tier_2: TermSet
    exclusions: TermSet


@dataclass(frozen=True)
class ThemeRules:
    """Theme-group vocabulary: lens phrases, lifecycle terms with anchors, pollution-core terms."""

    lens: TermSet
    lifecycle_co_term: TermSet
    lifecycle_title_only: TermSet
    anchors: TermSet
    pollution_core: TermSet


@dataclass(frozen=True)
class FrameWork:
    """One frame row; carries identifiers and the frozen score, never text."""

    work_id: str
    doi: str
    block: str
    theme_group: str
    score: float
    band: str
    rand_key: float = 0.0


def load_score_rules(queries: Mapping[str, Any]) -> ScoreRules:
    """Rule-score vocabulary from the active query config (core, qualified, tier-2, exclusions)."""
    qualified = tuple(
        (_term_pattern(term), TermSet(contexts)) for term, contexts in _qualified_terms(queries)
    )
    return ScoreRules(
        core=TermSet(_ordered_terms(queries, "core_terms")),
        qualified=qualified,
        tier_2=TermSet(_ordered_terms(queries, "tier_2_terms")),
        exclusions=TermSet(_ordered_terms(queries, "exclusions")),
    )


def load_theme_rules(
    v32: Mapping[str, Any],
    register: Mapping[str, Any],
    pollution_core: Mapping[str, Any],
) -> ThemeRules:
    """Theme patterns from the v3.2 candidate (lens theme, anchors), the register, and core v0."""
    themes = v32.get("themes") or {}
    lens_block = themes.get("waste_colonialism_lens") or {}
    lifecycle_rows = [
        row for row in register.get("terms") or [] if row.get("group") == LIFECYCLE_GROUP
    ]
    return ThemeRules(
        lens=TermSet(_ordered_terms(lens_block, "terms")),
        lifecycle_co_term=TermSet(
            row["term"] for row in lifecycle_rows if row.get("handling") == "co_term"
        ),
        lifecycle_title_only=TermSet(
            row["term"] for row in lifecycle_rows if row.get("handling") == "title_only"
        ),
        anchors=TermSet(_ordered_terms(v32, "anchor_phrases")),
        pollution_core=TermSet(_ordered_terms(pollution_core, "core_terms")),
    )


def normalize_doi(value: object) -> str:
    """Lower-case DOI without a resolver prefix; empty when absent."""
    text = str(value or "").strip().lower()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ):
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def assign_block(work_id: str, language: str | None, registry_ids: set[str]) -> str:
    """Registry block when the regions table matched the work; else English or non-English."""
    if work_id in registry_ids:
        return BLOCK_REGISTRY
    return BLOCK_GLOBAL_EN if (language or "").strip() == "en" else BLOCK_GLOBAL_NON_EN


def rule_points(title: str, abstract: str, rules: ScoreRules) -> int:
    """Integer rule points: core hit 2 in title + 1 in abstract; qualified and tier-2 hits 1 each.

    Any exclusion match in title or abstract returns 0 (exclusions override inclusions).
    """
    text = f"{title} {abstract}"
    if rules.exclusions.any(text):
        return 0
    points = 2 * rules.core.count(title) + rules.core.count(abstract)
    for term, contexts in rules.qualified:
        if term.search(text) and contexts.any(text):
            points += 1
    return points + rules.tier_2.count(text)


def rule_score(points: int) -> float:
    """Map points to [0, 1]: linear up to SCORE_FULL_POINTS, rounded to four decimals."""
    return round(min(1.0, max(0, points) / SCORE_FULL_POINTS), 4)


def band_for(score: float) -> str:
    if score < BAND_LOW_MAX:
        return "low"
    if score >= BAND_HIGH_MIN:
        return "high"
    return "medium"


def assign_theme(title: str, abstract: str, rules: ThemeRules) -> str:
    """Lens, then lifecycle-and-society (needs an anchor), then pollution-core, else other."""
    text = f"{title} {abstract}"
    if rules.lens.any(text):
        return THEME_LENS
    if rules.anchors.any(text) and (
        rules.lifecycle_co_term.any(text) or rules.lifecycle_title_only.any(title)
    ):
        return THEME_LIFECYCLE
    if rules.pollution_core.any(text):
        return THEME_POLLUTION
    return THEME_OTHER


def frame_theme_group(block: str, theme: str) -> str:
    """Theme used for strata: outside global English the lens stratum is merged into lifecycle."""
    if block != BLOCK_GLOBAL_EN and theme == THEME_LENS:
        return THEME_LIFECYCLE
    return theme


def stratum_id(block: str, theme_group: str, band: str) -> str:
    """Stable stratum id ``block|theme|band``; blocks outside global English use band ``all``."""
    if block != BLOCK_GLOBAL_EN:
        band = BAND_ALL
    elif theme_group == THEME_LENS:
        band = BAND_ALL
    return f"{block}|{theme_group}|{band}"


def all_strata() -> tuple[str, ...]:
    """The 16 frozen strata (A3 section 4.4 round-0 design, ADR-GOLD-GLOBAL-SAMPLER-2026-11-25)."""
    ids = [
        stratum_id(BLOCK_GLOBAL_EN, theme, band)
        for theme in (THEME_POLLUTION, THEME_LIFECYCLE, THEME_OTHER)
        for band in BANDS
    ]
    ids.append(stratum_id(BLOCK_GLOBAL_EN, THEME_LENS, BAND_ALL))
    for block in (BLOCK_REGISTRY, BLOCK_GLOBAL_NON_EN):
        ids.extend(
            stratum_id(block, theme, BAND_ALL)
            for theme in (THEME_POLLUTION, THEME_LIFECYCLE, THEME_OTHER)
        )
    return tuple(ids)


def gzip_bytes(data: bytes) -> bytes:
    """Deterministic gzip: mtime 0 and no stored file name."""
    return gzip.compress(data, compresslevel=9, mtime=0)


def rand_keys(work_ids: Sequence[str], seed: int = GLOBAL_FRAME_SEED) -> dict[str, float]:
    """One uniform key per work, drawn in sorted work_id order from a seeded generator."""
    rng = random.Random(seed)
    return {work_id: round(rng.random(), 16) for work_id in sorted(set(work_ids))}


def score_snapshot_sha256(pairs: Iterable[tuple[str, float]]) -> str:
    """sha256 over the sorted (work_id, score) list, one ``work_id<TAB>score`` line each."""
    digest = hashlib.sha256()
    for work_id, score in sorted(pairs):
        digest.update(f"{work_id}\t{score:.4f}\n".encode())
    return digest.hexdigest()


def guide_example_ids(guides: Sequence[Mapping[str, str]]) -> tuple[set[str], set[str]]:
    """Guide-example work_ids and normalized DOIs (role=guide_example rows only)."""
    rows = [row for row in guides if (row.get("role") or "").strip() == "guide_example"]
    ids = {(row.get("work_id") or "").strip() for row in rows} - {""}
    dois = {normalize_doi(row.get("doi")) for row in rows} - {""}
    return ids, dois


def is_guide_example(work_id: str, doi: object, ids: set[str], dois: set[str]) -> bool:
    return work_id in ids or (normalize_doi(doi) != "" and normalize_doi(doi) in dois)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a YAML mapping in {path}")
    return payload


def render_frame_csv(rows: Sequence[FrameWork]) -> bytes:
    """Committed frame CSV: identifiers, block, theme, score, band, stratum and rand key only."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(FRAME_COLUMNS)
    for row in sorted(rows, key=lambda item: item.work_id):
        writer.writerow(
            [
                row.work_id,
                row.doi,
                row.block,
                row.theme_group,
                f"{row.score:.4f}",
                row.band,
                stratum_id(row.block, row.theme_group, row.band),
                f"{row.rand_key:.16f}",
            ]
        )
    return buffer.getvalue().encode("utf-8")
