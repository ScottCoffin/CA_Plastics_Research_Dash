"""Expert career metrics for the site export (owner request 2026-11-12).

Pure helpers over ``data/processed/author_metrics.parquet`` rows (written by
``scripts/fetch_author_metrics.py``):

* ``citations_by_year``: citations received per year, all works vs. whole-record
  plastics works, for the last ``HISTOGRAM_YEARS`` years. OpenAlex reports a work's
  ``counts_by_year`` only for the last ten years, so the plastics series (summed over
  works) is complete only inside that window; the histogram is clipped to it.
* ``m_quotient``: Hirsch's m = h-index / years since the first publication. The first
  year is the robust first publication year (isolated misattributed early works are
  skipped by the fetch script).
* ``rising_score``: field-normalized citation momentum. For each of the last
  ``RISING_YEARS`` complete years, an expert's plastics citations are divided by all
  exported experts' plastics citations that year (their share of the field), and the
  score is the least-squares slope of that share, in percentage points per year.
  Normalizing by the yearly field total removes the growth of the field itself.
  ``rising_pct`` is the expert's percentile among scored experts.
* ``primary_affiliations``: OpenAlex ``last_known_institutions`` (the author's own),
  falling back to the institution the author used most in their latest Atlas year.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

HISTOGRAM_YEARS = 10
RISING_YEARS = 5
# Experts need this many plastics citations inside the rising window to be scored;
# below it the yearly share is mostly noise.
RISING_MIN_CITATIONS = 10
EARLY_CAREER_YEARS = 10


def _short(value: object) -> str:
    return str(value or "").rsplit("/", 1)[-1]


def _load(value: object) -> list[dict[str, Any]]:
    if not value:
        return []
    try:
        data = json.loads(str(value))
    except ValueError:
        return []
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _year_counts(value: object, field: str = "cited_by_count") -> dict[int, int]:
    out: dict[int, int] = {}
    for item in _load(value):
        try:
            year = int(item["year"])
        except (KeyError, TypeError, ValueError):
            continue
        out[year] = out.get(year, 0) + int(item.get(field) or 0)
    return out


def merge_metric_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Combine the metric rows of one exported expert (merged OpenAlex records)."""
    cites: Counter[int] = Counter()
    plastic: Counter[int] = Counter()
    plastic_covered = False
    first_years: list[int] = []
    last_known: dict[str, dict[str, str]] = {}
    affiliations: dict[str, dict[str, Any]] = {}
    for row in rows:
        cites.update(_year_counts(row.get("counts_by_year_json")))
        if row.get("plastic_counts_by_year_json"):
            plastic_covered = True
            plastic.update(_year_counts(row.get("plastic_counts_by_year_json")))
        if row.get("first_pub_year") is not None:
            first_years.append(int(row["first_pub_year"]))
        for item in _load(row.get("last_known_institutions_json")):
            if _short(item.get("id")):
                last_known.setdefault(_short(item.get("id")), item)
        for item in _load(row.get("affiliations_json")):
            key = _short(item.get("id"))
            if not key:
                continue
            entry = affiliations.setdefault(key, {**item, "id": key, "years": []})
            entry["years"] = sorted(set(entry["years"]) | {int(y) for y in item.get("years") or []})
    return {
        "cites_by_year": dict(cites),
        "plastic_by_year": dict(plastic) if plastic_covered else None,
        "first_pub_year": min(first_years) if first_years else None,
        "last_known": list(last_known.values()),
        "affiliations": list(affiliations.values()),
    }


def citations_by_year(merged: Mapping[str, Any], current_year: int) -> list[dict[str, Any]]:
    """Rows ``{year, all, plastic}`` for the histogram window (plastic null if unknown)."""
    cites = merged.get("cites_by_year") or {}
    plastic = merged.get("plastic_by_year")
    if not cites and not plastic:
        return []
    start = current_year - HISTOGRAM_YEARS + 1
    first = merged.get("first_pub_year")
    if isinstance(first, int):
        start = max(start, first)
    return [
        {
            "year": year,
            "all": int(cites.get(year, 0)),
            "plastic": None if plastic is None else int(plastic.get(year, 0)),
        }
        for year in range(start, current_year + 1)
    ]


def m_quotient(h_index: object, first_pub_year: object, current_year: int) -> float | None:
    if h_index is None or not isinstance(first_pub_year, int):
        return None
    years = max(1, current_year - first_pub_year)
    return round(int(h_index) / years, 2)


def _slope(values: Sequence[float]) -> float:
    n = len(values)
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    den = sum((x - mean_x) ** 2 for x in range(n))
    return sum((x - mean_x) * (y - mean_y) for x, y in enumerate(values)) / den


def rising_scores(
    plastic_by_author: Mapping[str, Mapping[int, int] | None], current_year: int
) -> dict[str, tuple[float, int]]:
    """``{author_id: (score, percentile)}`` for experts with enough plastics citations."""
    years = list(range(current_year - RISING_YEARS, current_year))
    totals = {
        year: sum((series or {}).get(year, 0) for series in plastic_by_author.values())
        for year in years
    }
    scores: dict[str, float] = {}
    for author, series in plastic_by_author.items():
        if not series or sum(series.get(year, 0) for year in years) < RISING_MIN_CITATIONS:
            continue
        shares = [
            100.0 * series.get(year, 0) / totals[year] if totals[year] else 0.0 for year in years
        ]
        scores[author] = round(_slope(shares), 4)
    ordered = sorted(scores.values())
    n = len(ordered)
    out: dict[str, tuple[float, int]] = {}
    for author, score in scores.items():
        below = sum(1 for value in ordered if value < score)
        out[author] = (score, round(100 * below / (n - 1)) if n > 1 else 100)
    return out


def primary_affiliations(
    merged: Mapping[str, Any],
    recent_institution_ids: Iterable[str],
    names: Mapping[str, str],
) -> list[dict[str, str]]:
    """OpenAlex last-known institutions, else the most used institution(s) in the latest
    Atlas year (``recent_institution_ids`` lists one id per authorship, latest year)."""
    last_known = [
        {
            "id": _short(item.get("id")),
            "name": str(item.get("name") or names.get(_short(item.get("id")), "")),
            "country_code": str(item.get("country_code") or ""),
            "source": "openalex_last_known",
        }
        for item in merged.get("last_known") or []
    ]
    if last_known:
        return last_known
    counts = Counter(i for i in recent_institution_ids if i)
    if not counts:
        return []
    top = max(counts.values())
    return [
        {"id": i, "name": names.get(i, i), "country_code": "", "source": "atlas_recent"}
        for i in sorted(i for i, n in counts.items() if n == top)
    ]


def affiliation_history(merged: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The author's own OpenAlex affiliations, most recent first."""
    rows = [
        {
            "id": item["id"],
            "name": str(item.get("name") or ""),
            "country_code": str(item.get("country_code") or ""),
            "years": list(item.get("years") or []),
        }
        for item in merged.get("affiliations") or []
    ]
    return sorted(rows, key=lambda r: (-(max(r["years"]) if r["years"] else 0), r["name"]))
