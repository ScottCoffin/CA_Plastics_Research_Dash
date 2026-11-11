from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "sem.html"

# Runs the SEM page's pure helpers in a Node VM context that loads the real
# site/assets/topics.js and the <script id="sem-app"> block from sem.html.
NODE_CHECK = r"""
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = process.argv[2];
const html = fs.readFileSync(path.join(root, "site", "sem.html"), "utf8");
const block = html.match(/<script id="sem-app">([\s\S]*?)<\/script>/);
assert.ok(block, "sem.html must include the <script id=\"sem-app\"> logic block");
const context = vm.createContext({ URLSearchParams });
vm.runInContext(fs.readFileSync(path.join(root, "site", "assets", "topics.js"), "utf8"), context, { filename: "topics.js" });
vm.runInContext(block[1], context, { filename: "sem-app.js" });

context.works = [
  { work_id: "W1", title: "Microplastics in marine fish", year: 2019, domain_tags: ["occurrence_and_monitoring", "ecotoxicology_and_trophic_transfer"], facet_tags: ["matrix:marine"], plastic_related: true, cited_by_count: 10, is_oa: true, author_names: ["Ann Lee", "Bo Chen"], abstract: "fish sampling", doi: "https://doi.org/10.1/a", journal: "J A", pub_date: "2019-05-01" },
  { work_id: "W2", title: "River survey", year: 2019, domain_tags: ["occurrence_and_monitoring"], facet_tags: ["matrix:freshwater"], plastic_related: false, cited_by_count: 3, is_oa: false, author_names: ["Ann Lee"], abstract: "" },
  { work_id: "W3", title: "Untagged work", year: 2021, domain_tags: [], facet_tags: [], plastic_related: true, cited_by_count: 0, author_names: [], abstract: "" },
  { work_id: "W4", title: "Air fibres", year: 2021, domain_tags: ["air"], facet_tags: ["matrix:air", "matrix:marine"], plastic_related: true, cited_by_count: 7, is_oa: true, author_names: ["Cy Park"], abstract: "fibres in air" },
  { work_id: "W5", title: "No year", year: null, domain_tags: ["air"], facet_tags: [], author_names: [] }
];

const R = JSON.parse(vm.runInContext(`JSON.stringify((() => {
  const w = works;
  const hm = buildHeatmap(w, domainKeys);
  const mhm = buildHeatmap(w, matrixKeys);
  const ids = (list) => list.map((x) => x.work_id);
  const occ2019 = { kind: "domain", key: "occurrence_and_monitoring", year: 2019 };
  return {
    years: hm.years,
    rows: hm.rows.map((r) => [r.key, r.label, r.counts, r.total]),
    colTotals: hm.colTotals,
    total: hm.total,
    max: hm.max,
    matrixRows: mhm.rows.map((r) => [r.key, r.label, r.counts, r.total]),
    matrixCol: mhm.colTotals,
    matrixTotal: mhm.total,
    cellOnly: ids(filterWorks(w, { cell: occ2019 })),
    cellPlastic: ids(filterWorks(w, { cell: occ2019, plasticOnly: true })),
    cellQuery: ids(filterWorks(w, { cell: occ2019, query: "fish" })),
    cellVsTopic: ids(filterWorks(w, { cell: occ2019, topic: "air" })),
    authorQuery: ids(filterWorks(w, { query: "ANN" })),
    topicYear: ids(filterWorks(w, { topic: "air", yearFrom: "2021", yearTo: "2021" })),
    untaggedCell: ids(filterWorks(w, { cell: { kind: "domain", key: UNTAGGED, year: 2021 } })),
    facetCell: ids(filterWorks(w, { cell: { kind: "facet", key: "matrix:marine", year: 2021 } })),
    yearBoundDropsUndated: ids(filterWorks(w, { yearFrom: "2000" })),
    newest: ids(sortWorks(w, "newest")),
    cited: ids(sortWorks(w, "cited")),
    summary: summarize(w),
    emptyHm: buildHeatmap([], domainKeys),
    labels: hm.rows.map((r) => r.label),
    fills: [heatFill(0, 2), heatFill(2, 2)],
    ink: [inkFor("#0b4f9c"), inkFor("#eaf2fb")],
    inst: [instParam("#inst=I84218800", ""), instParam("", "?inst=I1"), instParam("#foo=1", "")],
    valid: [isValidInstId("I84218800"), isValidInstId("../x")],
    progressive: [visibleCount(301, 100), visibleCount(300, 100)],
    ex: (() => {
      const experts = [
        { author_id: "A1", name: "Zed Ng", in_atlas_index: true, works_at_institution: 5, h_index: 10, plastic_citations: 50, years: { "2018": 2, "2020": 3 }, topics: [["air", 3]] },
        { author_id: "A2", name: "Amy Roe", in_atlas_index: false, works_at_institution: 3, h_index: 30, plastic_citations: null, years: { "2021": 3 }, topics: [] },
        { author_id: "A3", name: "Bob Fox", in_atlas_index: true, works_at_institution: 2, h_index: null, plastic_citations: 5, years: { "2020": 1, "2021": 1 }, topics: [] }
      ];
      const ids = (l) => l.map((e) => e.author_id);
      const all = filterExperts(experts, {});
      const r2020 = filterExperts(experts, { yearFrom: "2020", yearTo: "2020" });
      const m = expertYearMatrix(experts, { yearFrom: "2020", yearTo: "2021" });
      return {
        all: ids(sortExperts(all, "works", "desc")),
        byH: ids(sortExperts(all, "h_index", "desc")),
        byHAsc: ids(sortExperts(all, "h_index", "asc")),
        byName: ids(sortExperts(all, "name", "asc")),
        byCites: ids(sortExperts(all, "citations", "desc")),
        r2020: r2020.map((e) => [e.author_id, e.in_range]),
        r2020Sorted: ids(sortExperts(r2020, "works", "desc")),
        none: filterExperts(experts, { yearFrom: "2030" }).length,
        matrixYears: m.years,
        matrixRows: m.rows.map((r) => [r.author_id, r.counts, r.total]),
        matrixMax: m.max,
        linked: [expertHref(experts[0]), expertHref(experts[1])],
        nameHtml: expertNameHtml(experts[0])
      };
    })(),
    notice: [collabNoticeText({ scope: "collaborator" }, [1, 2, 3]), collabNoticeText({ scope: "collaborator" }, [1]), collabNoticeText({ scope: "california" }, [1])],
    conn: caConnectionHtml({ ca_connection: { authors: [{ author_id: "A9", name: "Kim <b>", ca_basis: "registry" }], institutions: [{ inst_id: "I1", name: "UC Davis", ca_basis: ["registry"] }] } }),
    connNone: caConnectionHtml({ ca_connection: { authors: [], institutions: [] } }) + caConnectionHtml({}),
    pubConn: pubItemHtml({ work_id: "W1", title: "T", year: 2020, domain_tags: [], facet_tags: [], ca_connection: { authors: [{ author_id: "A9", name: "Kim", ca_basis: "registry" }], institutions: [] } }),
    href: [workHref({ doi: "https://doi.org/10.1/a", work_id: "W1" }), workHref({ work_id: "W9" }), workHref({ doi: "javascript:alert(1)", work_id: "W9" })]
  };
})())`, context));

// Heatmap: every year from 2019 to 2021 (2020 is empty), untagged row last, works without a year excluded.
assert.deepEqual(R.years, [2019, 2020, 2021]);
assert.deepEqual(R.rows, [
  ["occurrence_and_monitoring", "Occurrence & monitoring", [2, 0, 0], 2],
  ["ecotoxicology_and_trophic_transfer", "Ecotoxicology & food webs", [1, 0, 0], 1],
  ["air", "Air & atmosphere", [0, 0, 1], 1],
  ["__untagged__", "Untagged", [0, 0, 1], 1]
]);
assert.deepEqual(R.colTotals, [2, 0, 2], "column totals count each publication once");
assert.equal(R.total, 4);
assert.equal(R.max, 2);
assert.deepEqual(R.matrixRows, [
  ["matrix:air", "Air", [0, 0, 1], 1],
  ["matrix:freshwater", "Freshwater", [1, 0, 0], 1],
  ["matrix:marine", "Marine", [1, 0, 1], 2]
]);
assert.deepEqual(R.matrixCol, [2, 0, 1]);
assert.equal(R.matrixTotal, 3);
assert.ok(R.labels.every((l) => !l.includes("_")), "no raw tag keys in labels");

// Filters compose with AND.
assert.deepEqual(R.cellOnly, ["W1", "W2"]);
assert.deepEqual(R.cellPlastic, ["W1"]);
assert.deepEqual(R.cellQuery, ["W1"]);
assert.deepEqual(R.cellVsTopic, [], "a cell and a conflicting topic select leave nothing");
assert.deepEqual(R.authorQuery, ["W1", "W2"], "text search matches author names");
assert.deepEqual(R.topicYear, ["W4"], "topic plus year range; undated works drop out of a year range");
assert.deepEqual(R.untaggedCell, ["W3"]);
assert.deepEqual(R.facetCell, ["W4"]);
assert.deepEqual(R.yearBoundDropsUndated, ["W1", "W2", "W3", "W4"]);

// Sorting.
assert.deepEqual(R.newest, ["W4", "W3", "W1", "W2", "W5"]);
assert.deepEqual(R.cited, ["W1", "W4", "W2", "W3", "W5"]);

// Summary tiles.
assert.equal(R.summary.publications, 5);
assert.equal(R.summary.plastic, 3);
assert.equal(R.summary.citations, 20);
assert.equal(R.summary.authors, 3);
assert.equal(R.summary.yearMin, 2019);
assert.equal(R.summary.yearMax, 2021);
assert.equal(R.summary.yearsWithOutput, 2);
assert.equal(R.summary.oaCount, 2);
assert.ok(Math.abs(R.summary.oaShare - 0.4) < 1e-9);

assert.deepEqual(R.emptyHm.years, []);
assert.deepEqual(R.emptyHm.rows, []);
assert.equal(R.emptyHm.total, 0);

// Colour ramp and contrast.
assert.equal(R.fills[0], "#f3f5f6");
assert.equal(R.fills[1], "#0b4f9c");
assert.equal(R.ink[0], "#ffffff");
assert.equal(R.ink[1], "#17324d");

// Institution id parsing and link safety.
assert.deepEqual(R.inst, ["I84218800", "I1", ""]);
assert.deepEqual(R.valid, [true, false]);
assert.deepEqual(R.progressive, [100, 300], "lists over 300 render 100 at a time; smaller lists render in full");
assert.equal(R.href[0], "https://doi.org/10.1/a");
assert.equal(R.href[1], "https://openalex.org/W9");
assert.equal(R.href[2], "https://openalex.org/W9", "non-http DOI values fall back to OpenAlex");

// Top experts: sort, year filter, years matrix.
assert.deepEqual(R.ex.all, ["A1", "A2", "A3"]);
assert.deepEqual(R.ex.byH, ["A2", "A1", "A3"], "missing h-index sorts last when descending");
assert.deepEqual(R.ex.byHAsc, ["A3", "A1", "A2"]);
assert.deepEqual(R.ex.byName, ["A2", "A3", "A1"]);
assert.deepEqual(R.ex.byCites, ["A1", "A3", "A2"]);
assert.deepEqual(R.ex.r2020, [["A1", 3], ["A3", 1]], "year range keeps only experts active in range");
assert.deepEqual(R.ex.r2020Sorted, ["A1", "A3"]);
assert.equal(R.ex.none, 0);
assert.deepEqual(R.ex.matrixYears, [2020, 2021]);
assert.deepEqual(R.ex.matrixRows, [["A2", [0, 3], 3], ["A1", [3, 0], 3], ["A3", [1, 1], 2]]);
assert.equal(R.ex.matrixMax, 3);
assert.equal(R.ex.linked[0], "index.html#experts?author=A1");
assert.equal(R.ex.linked[1], "");
assert.ok(R.ex.nameHtml.includes('href="index.html#experts?author=A1"'));

// Collaborator notice and California connection.
assert.equal(R.notice[0], "Outside California. Listed because of 3 works co-authored with California researchers.");
assert.ok(R.notice[1].includes("1 work co-authored"));
assert.equal(R.notice[2], "");
assert.ok(R.conn.includes("California connection:") && R.conn.includes("UC Davis") && R.conn.includes("experts?author=A9"));
assert.ok(R.conn.includes("Kim &lt;b&gt;") && !R.conn.includes("<b>"), "names are escaped");
assert.equal(R.connNone, "");
assert.ok(R.pubConn.includes("California connection:") && R.pubConn.includes("registry"));

console.log("SEM page runtime checks passed: matrix builder, filter composition, sorting, summary, ids.");
"""  # noqa: E501

ATTR_RE = re.compile(r"""\b(?:src|href)\s*=\s*["']([^"']*)["']""", re.IGNORECASE)


def test_sem_page_has_no_external_hosts() -> None:
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


def test_sem_page_includes_topics_script() -> None:
    html = PAGE.read_text(encoding="utf-8")
    assert '<script src="assets/topics.js"></script>' in html
    assert 'href="index.html#institutions"' in html
    assert "Independent project; not an official OEHHA or State product." in html


def test_sem_page_matrix_filter_runtime(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for the SEM page runtime check; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    script = tmp_path / "sem_page_check.cjs"
    script.write_text(NODE_CHECK, encoding="utf-8")
    subprocess.run([node, str(script), str(ROOT)], cwd=ROOT, check=True)
