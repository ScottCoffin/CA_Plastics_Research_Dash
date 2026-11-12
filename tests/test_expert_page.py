from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "expert.html"
HELPERS = ROOT / "site" / "assets" / "expert_page.js"
FIXTURE = ROOT / "tests" / "fixtures" / "expert_page_author.json"

# Loads site/assets/expert_page.js in a Node VM context (no window, so it exports via `module`)
# and checks the pure helpers against tests/fixtures/expert_page_author.json.
NODE_CHECK = r"""
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = process.argv[2];
const fixture = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const source = fs.readFileSync(path.join(root, "site", "assets", "expert_page.js"), "utf8");
const context = vm.createContext({ URLSearchParams, URL, module: { exports: {} } });
vm.runInContext(source, context, { filename: "expert_page.js" });
const A = context.module.exports;
// Helpers return arrays from the VM realm; compare plain JSON copies.
const plain = (value) => JSON.parse(JSON.stringify(value));
const ids = (list) => list.map((w) => w.work_id.replace(/^W90*/, "W"));
const works = fixture.works;
const tagSet = (...tags) => new Set(tags);

// Author id parsing and validation.
assert.equal(A.parseAuthorParam("#author=A1", ""), "A1");
assert.equal(A.parseAuthorParam("", "?author=A2"), "A2");
assert.equal(A.parseAuthorParam("#foo=1", ""), "");
assert.equal(A.parseAuthorParam("#author=A1", "?author=A2"), "A1", "hash wins over query");
assert.equal(A.parseAuthorParam("#author=%20A3%20", ""), "A3");
assert.equal(A.isValidAuthorId("A9000000001"), true);
assert.equal(A.isValidAuthorId("../x"), false);
assert.equal(A.isValidAuthorId(""), false);

// Text search matches title and journal only (not abstracts), case-insensitively, all terms required.
assert.deepEqual(ids(plain(A.filterWorks(works, {}))), ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]);
assert.deepEqual(ids(plain(A.filterWorks(works, { q: "synthetic" }))), ["W1", "W4"], "abstract text is not searched");
assert.deepEqual(ids(plain(A.filterWorks(works, { q: "SEABIRD  marine" }))), ["W6"]);
assert.deepEqual(ids(plain(A.filterWorks(works, { q: "seabird sediments" }))), [], "every term must match");

// Plastics-only toggle and year range (undated works drop out when a bound is set).
assert.deepEqual(ids(plain(A.filterWorks(works, { plasticOnly: true }))), ["W1", "W2", "W3", "W5", "W6", "W8"]);
assert.deepEqual(ids(plain(A.filterWorks(works, { yearFrom: "2019", yearTo: "2021" }))), ["W4", "W5", "W8"]);
assert.deepEqual(ids(plain(A.filterWorks(works, { yearFrom: 2020 }))), ["W1", "W2", "W3", "W4", "W8"]);
assert.deepEqual(ids(plain(A.filterWorks(works, { yearFrom: "2030" }))), []);

// Topic filter: a work matches a tag found in domain_tags or facet_tags; several tags must all match.
assert.deepEqual(ids(plain(A.filterWorks(works, { tags: tagSet("air") }))), ["W5"]);
assert.deepEqual(ids(plain(A.filterWorks(works, { tags: tagSet("matrix:sediment") }))), ["W1"], "facet tags count");
assert.deepEqual(ids(plain(A.filterWorks(works, { tags: ["soil_and_agriculture"] }))), ["W2"], "array tags accepted");
assert.deepEqual(ids(plain(A.filterWorks(works, { tags: tagSet("matrix:marine", "matrix:biota") }))), ["W6"]);
assert.deepEqual(ids(plain(A.filterWorks(works, { tags: tagSet("matrix:marine", "air") }))), [], "tags combine with AND");
assert.deepEqual(
  ids(plain(A.filterWorks(works, { plasticOnly: true, tags: tagSet("fate_transport_and_sorption") }))),
  ["W2", "W5"],
  "filters compose"
);
assert.deepEqual(ids(plain(A.filterWorks(null, {}))), []);

// Sorting: year desc (undated last), citations desc, title A to Z; stable; input not mutated.
assert.deepEqual(ids(plain(A.sortWorks(works, "year"))), ["W1", "W2", "W3", "W4", "W8", "W5", "W6", "W7"]);
assert.deepEqual(ids(plain(A.sortWorks(works, "citations"))), ["W4", "W3", "W8", "W1", "W5", "W2", "W6", "W7"]);
assert.deepEqual(ids(plain(A.sortWorks(works, "title"))), ["W5", "W4", "W2", "W3", "W1", "W6", "W7", "W8"]);
assert.deepEqual(ids(plain(A.sortWorks(works, "unknown"))), ids(plain(A.sortWorks(works, "year"))), "unknown key falls back to year");
assert.equal(works[0].work_id, "W9000000001", "input array is not reordered");
const ties = [
  { work_id: "Wa", year: 2020, cited_by_count: 5, title: "Same" },
  { work_id: "Wb", year: 2020, cited_by_count: 5, title: "Same" },
  { work_id: "Wc", year: 2020, cited_by_count: 9, title: "Same" }
];
assert.deepEqual(ids(plain(A.sortWorks(ties, "citations"))), ["Wc", "Wa", "Wb"], "ties keep input order");
assert.deepEqual(ids(plain(A.sortWorks(ties, "year"))), ["Wa", "Wb", "Wc"], "ties keep input order");

// M-quotient tooltip and plastics share.
assert.equal(
  A.mQuotientText(fixture.author),
  "h-index divided by years since first publication (first year 2016)"
);
assert.equal(A.mQuotientText({}), "h-index divided by years since first publication (first year unknown)");
assert.equal(A.plasticShare(fixture.author), 38);
assert.equal(A.plasticShare({ cited_by_count: 0, plastic_citations: 3 }), null);

// Year ranges and co-authors.
assert.equal(A.yearRangesText([2021, 2022, 2023, 2024]), "2021–2024");
assert.equal(A.yearRangesText([2018, 2020, 2021, 2022, 2025, 2025]), "2018, 2020–2022, 2025");
assert.equal(A.yearRangesText([]), "");
assert.deepEqual(
  plain(A.coauthorCounts(works, "A9000000001")),
  [
    { author_id: "A9000000002", shared: 4 },
    { author_id: "A9000000003", shared: 2 },
    { author_id: "A9000000004", shared: 2 },
    { author_id: "A9000000005", shared: 1 }
  ],
  "self excluded; most shared first; ties by id"
);

// Links and profile markup: only http(s) URLs, everything escaped.
assert.equal(A.safeHttpUrl("https://example.org/x"), "https://example.org/x");
assert.equal(A.safeHttpUrl("javascript:alert(1)"), "");
assert.equal(A.safeHttpUrl("not a url"), "");
const profile = plain(A.profileHtml(fixture.profile, "Test Expert"));
assert.ok(profile.includes('src="https://example.org/photo/thumb.jpg"'));
assert.ok(profile.includes("Photo: Test Photographer"));
assert.ok(profile.includes('href="https://example.org/photo/source"') && profile.includes("CC BY 4.0"));
assert.ok(profile.includes('href="https://example.org/lab"'));
assert.ok(!profile.includes("javascript:") && !profile.includes("Unsafe link"), "unsafe links are dropped");
assert.ok(profile.includes("test sediments") && profile.includes("polymer fate"));
assert.equal(A.profileHtml(null), "");
assert.equal(A.profileHtml({}), "");
const hostile = plain(A.profileHtml({ bio: "<script>x</script>", keywords: ["<b>k</b>"] }));
assert.ok(hostile.includes("&lt;script&gt;x&lt;/script&gt;") && !hostile.includes("<script>"), "bio is escaped");
assert.ok(hostile.includes("&lt;b&gt;k&lt;/b&gt;"), "keywords are escaped");
assert.equal(A.escapeHtml(`"a" & 'b' <c>`), "&quot;a&quot; &amp; &#39;b&#39; &lt;c&gt;");

// Citation histogram: all years of the fixture; plastics known for 2016 to 2024 only.
const rows = plain(A.citationSeries(fixture.author.citations_by_year));
assert.equal(rows.length, 10);
assert.equal(rows[9].plastic, null);
const svg = A.citationHistogramSvg(rows, { width: 600, height: 240 });
assert.ok(svg.startsWith("<svg"), "returns an SVG string");
assert.ok(svg.includes('role="img"') && svg.includes('aria-label="Citations received per year"'));
assert.ok(svg.includes("<title>Citations received per year</title>"));
assert.ok(svg.includes("<title>2025: 5 citations</title>"), "unknown plastics does not add a plastics note");
assert.equal((svg.match(/fill="#b43c0c"/g) || []).length, 9, "8 plastics bars plus the legend swatch");
assert.ok(svg.includes("Plastics-related (Atlas plastics query)"), "legend when plastics are known");
assert.ok(svg.includes(">2016<") && svg.includes(">2025<"), "year labels");
const allOnly = plain(A.citationHistogramSvg([{ year: 2020, all: 4, plastic: null }, { year: 2021, all: 0, plastic: null }]));
assert.ok(!allOnly.includes("#b43c0c") && !allOnly.includes("Plastics-related"), "all-citation bars only when plastics are unknown");
assert.ok(allOnly.includes("<title>2020: 4 citations</title>"));
assert.equal(A.citationHistogramSvg([]), "", "no rows, no chart");
assert.equal(A.citationHistogramSvg(null), "");
const escapedLabel = plain(A.citationHistogramSvg([{ year: 2020, all: 1 }], { label: "<b>x</b>" }));
assert.ok(escapedLabel.includes("&lt;b&gt;x&lt;/b&gt;") && !escapedLabel.includes("<b>x</b>"));
const sparse = plain(A.citationSeries([{ year: "2019", all: "3", plastic: "1" }, { year: "bad", all: 2 }, { year: 2018, all: NaN, plastic: undefined }]));
assert.deepEqual(sparse, [{ year: 2018, all: 0, plastic: null }, { year: 2019, all: 3, plastic: 1 }], "bad rows are dropped or zeroed");

console.log("Expert page runtime checks passed: parsing, filters, sorting, profile, histogram helpers.");
"""  # noqa: E501

ATTR_RE = re.compile(r"""\b(?:src|href)\s*=\s*["']([^"']*)["']""", re.IGNORECASE)


def test_expert_page_has_no_external_hosts() -> None:
    html = PAGE.read_text(encoding="utf-8")
    refs = ATTR_RE.findall(html)
    assert refs, "the page should link to local assets and back to the atlas"
    external = [
        ref
        for ref in refs
        if re.match(r"^(?:https?:)?//", ref, re.IGNORECASE) or ref.lower().startswith("http:")
    ]
    assert external == [], f"external src/href values are not allowed: {external}"
    assert not re.search(r"url\(\s*['\"]?https?:", html, re.IGNORECASE), "no external CSS url()"
    assert not re.search(r"@import", html), "no CSS @import"


def test_expert_page_loads_topics_and_helpers_in_order() -> None:
    html = PAGE.read_text(encoding="utf-8")
    topics = html.index('<script src="assets/topics.js"></script>')
    helpers = html.index('<script src="assets/expert_page.js"></script>')
    app = html.index('<script id="expert-app">')
    assert topics < helpers < app, "topics.js and expert_page.js must load before the page script"
    assert HELPERS.exists()


def test_expert_page_navigation_and_disclaimer() -> None:
    html = PAGE.read_text(encoding="utf-8")
    assert 'href="index.html#experts"' in html, "back link to the Experts list"
    assert "index.html#experts?author=" in html, "Open in Experts list link"
    assert "Independent project; not an official OEHHA or State product." in html
    assert 'class="skip-link" href="#main-content"' in html
    assert "hashchange" in html, "a new author in the hash re-renders the page"


def test_expert_helpers_have_no_external_hosts() -> None:
    source = HELPERS.read_text(encoding="utf-8")
    assert not re.search(r"https?://", source), "expert_page.js must not embed external hosts"


def test_expert_fixture_matches_the_data_contract() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    author = fixture["author"]
    for key in (
        "author_id",
        "name",
        "orcid",
        "ca_works_count",
        "work_count",
        "cited_by_count",
        "h_index",
        "plastic_citations",
        "plastic_works_count",
        "plastic_basis",
        "institution_ids",
        "primary_affiliations",
        "affiliation_history",
        "citations_by_year",
        "first_pub_year",
        "m_quotient",
        "rising_score",
        "rising_pct",
        "early_career",
    ):
        assert key in author, f"fixture author is missing {key}"
    assert 0 < len(fixture["works"]) <= 20
    for work in fixture["works"]:
        for key in (
            "work_id",
            "title",
            "year",
            "journal",
            "plastic_related",
            "domain_tags",
            "facet_tags",
            "author_ids",
            "author_institution_ids",
        ):
            assert key in work, f"fixture work {work.get('work_id')} is missing {key}"


def test_expert_page_helpers_runtime(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not on PATH; install Node.js 20+ to run the helper checks.")
    script = tmp_path / "expert_page_check.cjs"
    script.write_text(NODE_CHECK, encoding="utf-8")
    subprocess.run([node, str(script), str(ROOT), str(FIXTURE)], cwd=ROOT, check=True)
