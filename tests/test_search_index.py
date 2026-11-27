"""Contract checks for the header search index (VD-19): site/data/california/search_index.json."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from atlas.build.search_index import (
    TYPES,
    build_search_index,
    parse_glossary,
    parse_institution_types,
    parse_matrix_labels,
    parse_page_groups,
    serialize,
)

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "framework"
CLIENT = ROOT / "site" / "assets" / "site_search.js"
STYLE = ROOT / "site" / "assets" / "site_search.css"
SEARCH_PAGE = FW / "src" / "california" / "search.md"

AUTHORS = [
    {
        "author_id": "A2",
        "name": "Zoe Análisis",
        "primary_affiliations": ["UC Davis"],
        "email": "zoe@example.org",
        "abstract": "Private abstract text.",
    },
    {"author_id": "A1", "name": "Ana Rochman", "primary_affiliations": []},
    {"author_id": "", "name": "No identifier"},
    {"author_id": "A3", "name": ""},
]
INSTITUTIONS = [
    {"inst_id": "I9", "name": "Davis Lab", "ca_flag": True, "atlas_type": "UC", "city": "Davis"},
    {"inst_id": "I8", "name": "Far Away Institute", "ca_flag": False, "atlas_type": "other"},
]
GRANTS = {
    "columns": ["funder", "funder_agency", "funder_type"],
    "rows": [
        ["NSF", "NSF", "federal"],
        ["National Science Foundation", "NSF", "federal"],
        ["CA Ocean Protection Council", "CA Ocean Protection Council", "state"],
    ],
}
LINKOUTS = {
    "entries": [
        {
            "name": "Global Plastic Laws",
            "relation": "law database",
            "root_url": "https://www.globalplasticlaws.org/",
        },
        {"name": "Internal Note", "relation": "note", "root_url": ""},
    ]
}
GLOSSARY_MD = (
    '<dl class="glossary">\n'
    '<dt id="access-tiers"><a class="glossary-term-link" href="#access-tiers">'
    "<strong>Access tiers A&ndash;D</strong></a></dt>\n"
    "<dd>\n<p>Each monitoring source is placed in one tier.</p>\n"
    "<p><small>Source: rules.</small></p>\n</dd>\n"
    "</dl>\n"
)
CONFIG_JS = """
const PAGE_GROUPS = [
  {name: "Explore", pages: [
    {name: "Authors", path: "/california/authors"},
    {name: "Institutions", path: "/california/institutions"},
  ]},
  {name: "Reference", pages: [
    {name: "Glossary", path: "/california/glossary"},
  ]},
];
"""


def build(**overrides):
    sources = {
        "generated_at": "2026-11-16T04:41:04+00:00",
        "pages": [
            ("Authors", "Explore", "california/authors"),
            ("Glossary", "Reference", "california/glossary"),
        ],
        "authors": AUTHORS,
        "institutions": INSTITUTIONS,
        "institution_types": {"UC": "University of California"},
        "topic_labels": {"air": "Air & atmosphere"},
        "matrix_labels": {"air": "Air"},
        "grants": GRANTS,
        "glossary": [("access-tiers", "Access tiers A–D", "Each monitoring source is placed.")],
        "resources": LINKOUTS["entries"],
    }
    sources.update(overrides)
    return build_search_index(**sources)


def by_type(index: dict, name: str) -> list[list]:
    number = index["types"].index(name)
    return [item for item in index["items"] if item[0] == number]


def test_types_and_schema_version_are_fixed() -> None:
    index = build()

    assert index["schema_version"] == 1
    assert (
        index["types"]
        == list(TYPES)
        == [
            "page",
            "expert",
            "institution",
            "topic",
            "funder",
            "term",
            "resource",
        ]
    )
    assert index["generated_at"] == "2026-11-16T04:41:04+00:00"
    assert all(len(item) == 4 for item in index["items"])


def test_build_is_deterministic_whatever_the_input_order() -> None:
    first = serialize(build())
    second = serialize(
        build(authors=list(reversed(AUTHORS)), institutions=list(reversed(INSTITUTIONS)))
    )

    assert first == serialize(build())
    assert first == second


def test_every_type_is_built_with_its_own_source() -> None:
    index = build()

    assert [item[1] for item in by_type(index, "page")] == ["Overview", "Authors", "Glossary"]
    assert [item[1] for item in by_type(index, "expert")] == ["Ana Rochman", "Zoe Análisis"]
    assert [item[1] for item in by_type(index, "institution")] == ["Davis Lab"]
    assert {item[1] for item in by_type(index, "topic")} == {"Air & atmosphere", "Air"}
    assert {item[1] for item in by_type(index, "funder")} == {
        "CA Ocean Protection Council",
        "NSF",
        "National Science Foundation",
    }
    assert [item[1] for item in by_type(index, "term")] == ["Access tiers A–D"]
    assert [item[1] for item in by_type(index, "resource")] == [
        "Global Plastic Laws",
        "Internal Note",
    ]


def test_hrefs_use_the_route_each_page_reads() -> None:
    index = build()
    hrefs = {item[3] for item in index["items"]}

    assert "california/expert.html#author=A2" in hrefs
    assert "california/institution#inst=I9" in hrefs
    assert "california/authors#tag=air" in hrefs
    assert "california/authors#tag=matrix%3Aair" in hrefs
    assert "california/funding#fa=NSF" in hrefs
    assert "california/funding#q=National+Science+Foundation" in hrefs
    assert "california/glossary#access-tiers" in hrefs
    assert "https://www.globalplasticlaws.org/" in hrefs
    assert "california/authors" in hrefs
    assert not any(href.startswith("/") for href in hrefs)


def test_resources_without_a_url_point_at_the_resources_page() -> None:
    index = build(resources=[{"name": "Portal without URL", "relation": "portal", "root_url": ""}])

    assert by_type(index, "resource")[0][3] == "california/resources"


def test_only_california_institutions_are_indexed() -> None:
    index = build()

    labels = [item[1] for item in by_type(index, "institution")]
    assert "Far Away Institute" not in labels
    institution = by_type(index, "institution")[0]
    assert institution[2] == "University of California · Davis"


def test_no_abstract_or_email_text_reaches_the_index() -> None:
    text = serialize(build())

    assert "zoe@example.org" not in text
    assert "Private abstract text" not in text
    assert "email" not in text
    assert "abstract" not in text


def test_experts_without_an_id_or_name_are_skipped() -> None:
    index = build()

    assert "No identifier" not in [item[1] for item in by_type(index, "expert")]
    assert len(by_type(index, "expert")) == 2


def test_parsers_read_the_config_glossary_and_label_tables() -> None:
    assert parse_page_groups(CONFIG_JS) == [
        ("Authors", "Explore", "california/authors"),
        ("Institutions", "Explore", "california/institutions"),
        ("Glossary", "Reference", "california/glossary"),
    ]
    assert parse_glossary(GLOSSARY_MD) == [
        ("access-tiers", "Access tiers A–D", "Each monitoring source is placed in one tier.")
    ]
    assert parse_matrix_labels(
        'const MATRICES = {\n    marine: "Marine",\n    air: "Air",\n  };'
    ) == {
        "marine": "Marine",
        "air": "Air",
    }
    labels_js = (
        "export const INSTITUTION_TYPE_LABELS = Object.freeze({\n"
        '  UC: "University of California",\n'
        '  "nonprofit/NGO": "Nonprofit or NGO"\n});'
    )
    assert parse_institution_types(labels_js) == {
        "UC": "University of California",
        "nonprofit/NGO": "Nonprofit or NGO",
    }


def test_real_nav_pages_exclude_the_results_page() -> None:
    config = (FW / "observablehq.config.js").read_text(encoding="utf-8")
    pages = [path for _, _, path in parse_page_groups(config)]

    assert "california/authors" in pages and "california/glossary" in pages
    assert "california/search" not in pages
    assert "/search" not in (ROOT / "site" / "llms.txt").read_text(encoding="utf-8")
    assert '"/search"' not in (ROOT / "src" / "atlas" / "build" / "seo.py").read_text(
        encoding="utf-8"
    )


def test_results_page_is_unlisted_and_noindex() -> None:
    page = SEARCH_PAGE.read_text(encoding="utf-8")

    assert page.startswith("---\n")
    assert 'head: \'<meta name="robots" content="noindex, nofollow">\'' in page
    assert "data-atlas-search-results" in page
    assert "data-atlas-search-status" in page
    assert "data-atlas-search-page" in page


def test_header_and_hero_forms_are_the_site_search() -> None:
    config = (FW / "observablehq.config.js").read_text(encoding="utf-8")
    index_md = (FW / "src" / "california" / "index.md").read_text(encoding="utf-8")

    assert "data-atlas-site-search" in config
    assert 'action="./search"' in config
    assert 'name="q"' in config
    assert "Show search" in config and "Hide search" in config
    assert "data-atlas-expert-search" not in config
    assert "data-atlas-expert-search" not in index_md
    assert index_md.count("data-atlas-site-search") == 1
    assert "./assets/site_search.js" in config
    assert "./assets/site_search.css" in config


def test_client_has_no_imports_and_implements_the_combobox_contract() -> None:
    script = CLIENT.read_text(encoding="utf-8")

    assert "import " not in script
    assert 'setAttribute("role", "combobox")' in script
    for attribute in ("aria-expanded", "aria-controls", "aria-activedescendant", "aria-selected"):
        assert attribute in script
    assert 'role: "listbox"' in script
    assert "search#" in script
    assert "authors#" in script
    assert "PER_GROUP = 5" in script
    assert '"data/" + REGION + "/search_index.json"' in script
    assert script.isascii()


def test_stylesheet_overrides_only_the_header_search_and_targets_are_large_enough() -> None:
    css = STYLE.read_text(encoding="utf-8")

    assert ".atlas-header__search[data-atlas-site-search]" in css
    assert "min-height: 2.75rem" in css
    assert "@media (min-width: 52.01rem)" in css


def test_build_script_writes_the_committed_index_path() -> None:
    script = (ROOT / "scripts" / "build_search_index.py").read_text(encoding="utf-8")

    assert "--check" in script
    assert "search_index.json" in script


def test_postbuild_restores_site_search_assets_on_pages_with_their_own_head() -> None:
    if shutil.which("node") is None:
        return
    module = (FW / "scripts" / "postbuild.mjs").resolve().as_uri()
    expression = (
        f"const m = await import({json.dumps(module)});"
        'const once = m.fixHtml(\'<html><head><meta name="robots" content="noindex">'
        "<title>Search | CA Plastics Research Atlas</title></head><body></body></html>', "
        "'california/search');"
        "const twice = m.fixHtml(once, 'california/search');"
        "process.stdout.write(JSON.stringify({once, same: once === twice}));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", expression],
        cwd=FW,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    assert data["same"] is True
    assert data["once"].count("site_search.js") == 1
    assert data["once"].count("site_search.css") == 1
