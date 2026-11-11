"""Owner rules 2026-11-11: micro-nano plastics always relevant; shared abstracts ignored;
plastisphere title seeds and exclusions."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas.ingest.abstract_qc import misattached_abstract_ids
from atlas.ingest.grants.normalize import STRONG_ABSTRACT_RE
from atlas.nlp.labels import _taxonomy_tags, always_relevant
from atlas.query import load_query_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_query_config(ROOT / "config" / "queries.yml")

VARIANTS = [
    "micro-nano plastics",
    "Micro-Nanoplastics",
    "micro/nano plastics",
    "micro(nano)plastics",
    "Micro(Nano)plastics",
    "micro- and nanoplastics",
    "micro and nano plastics",
    "micro-and nano-plastics",
    "micronanoplastics",
    "micro‐nanoplastics",  # Unicode hyphen
]


@pytest.mark.parametrize("text", VARIANTS)
def test_micro_nano_variants_always_relevant(text: str) -> None:
    assert always_relevant(f"Effects of {text} on fish", CONFIG)
    assert STRONG_ABSTRACT_RE.search(text)


@pytest.mark.parametrize(
    "text", ["micronutrients and nanoparticles", "microbial nano-scale plastic-like", ""]
)
def test_non_matches(text: str) -> None:
    assert not always_relevant(text, CONFIG)


LONG = "Micro-nano plastics originating from the prevalent usage of plastics " * 5


def test_misattached_flags_unrelated_works_sharing_one_abstract() -> None:
    works = [
        {
            "work_id": "W1",
            "doi": "10.1073/pnas.48.11.1913",
            "title": "A new formalism",
            "abstract": LONG,
        },
        {
            "work_id": "W2",
            "doi": "https://doi.org/10.1073/pnas.0913578107",
            "title": "The Maya Forest",
            "abstract": LONG.upper(),
        },
        {
            "work_id": "W3",
            "doi": None,
            "title": "Optoretinography is coming of age",
            "abstract": "  " + LONG,
        },
        {"work_id": "W4", "doi": "10.1/x", "title": "Unique", "abstract": "unique abstract " * 20},
    ]
    assert misattached_abstract_ids(works) == {"W1", "W2", "W3"}
    assert misattached_abstract_ids(works[:2]) == frozenset()


def test_misattached_spares_preprint_versions_book_chapters_and_series() -> None:
    versions = [
        {"work_id": f"V{i}", "doi": doi, "title": None, "abstract": LONG}
        for i, doi in enumerate(
            [
                "10.7287/peerj.preprints.2697v1",
                "10.7287/peerj.preprints.2697/v2",
                "10.7287/peerj.preprints.2697v3",
            ]
        )
    ]
    chapters = [
        {"work_id": f"C{i}", "doi": doi, "title": title, "abstract": LONG + "book"}
        for i, (doi, title) in enumerate(
            [
                ("10.2166/9781789060034", "Microplastics in Water and Wastewater"),
                ("10.2166/9781789060034_0063", "Method development for microplastic analysis"),
                ("10.2166/9781789060034_0109", "Evaluating wastewater effluent as a source"),
            ]
        )
    ]
    series = [
        {
            "work_id": f"S{i}",
            "doi": None,
            "title": f"Kelp Wrack: Hopping with Life in {c}",
            "abstract": LONG + "kelp",
        }
        for i, c in enumerate(["Santa Barbara", "Los Angeles", "San Diego", "Ventura"])
    ]
    assert misattached_abstract_ids(versions + chapters + series) == frozenset()


TAXONOMY = {
    "domain_tags": [
        {
            "id": "plastisphere",
            "seed_concepts": ["plastisphere"],
            "title_seed_concepts": ["biofilm"],
            "exclude_concepts": ["biofilm reactor"],
        }
    ]
}


def test_title_seeds_and_exclusions() -> None:
    def tags(text: str, title: str | None) -> list[str]:
        return _taxonomy_tags(text, [], TAXONOMY, title=title)[0]

    abstract_only = "Microplastics. Biofilms were removed with acid before counting."
    assert tags(abstract_only, "Counting microplastics") == []
    assert tags("Biofilm on microplastics", "Biofilm on microplastics") == ["plastisphere"]
    assert tags("The plastisphere of lakes", "Lakes") == ["plastisphere"]
    assert tags("Moving biofilm reactor upgrades", "Biofilm reactor upgrades") == []
    # Without a separate title, title seeds fall back to the whole text (grant callers).
    assert tags("Biofilm on microplastics", None) == ["plastisphere"]


def test_peerj_supplement_records_share_their_preprint_abstract() -> None:
    supp = [
        {"work_id": f"P{i}", "doi": doi, "title": None, "abstract": LONG}
        for i, doi in enumerate(
            [
                "10.7287/peerj.preprints.2697v1/supp-1",
                "10.7287/peerj.preprints.2697/supp-2",
                "10.7287/peerj.preprints.2697v1/supp-3",
                "10.7287/peerj.preprints.2697",
            ]
        )
    ]
    assert misattached_abstract_ids(supp) == frozenset()
