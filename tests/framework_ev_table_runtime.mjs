// Runtime checks for the Evidence map publication table model (EV-TABLE).
// The pure helpers live in framework/src/components/ev_table_model.js.
import assert from "node:assert/strict";
import {
  authorLine,
  dateLabel,
  escapeHtml,
  filterRows,
  isRecent,
  normaliseRows,
  pageInfo,
  pageRows,
  recentRows,
  safeHttpUrl,
  sortRows,
  tagsPresent,
  toCsv
} from "../framework/src/components/ev_table_model.js";

const TODAY = new Date("2026-11-12T18:00:00Z");

function work(overrides = {}) {
  return {
    work_id: "W1",
    title: "Microplastics in California rivers",
    year: 2025,
    pub_date: "2025-06-01",
    first_seen: "2026-01-02",
    doi: "https://doi.org/10.1000/abc",
    journal: "Water Research",
    type: "article",
    cited_by_count: 10,
    is_oa: false,
    oa_url: "",
    plastic_related: true,
    ca_led: false,
    domain_tags: ["occurrence_and_monitoring"],
    facet_tags: ["matrix:freshwater"],
    authors: ["Ada Lovelace"],
    author_count: 1,
    has_abstract: true,
    ...overrides
  };
}

// Days before TODAY as a YYYY-MM-DD string (UTC).
function daysBefore(days) {
  const date = new Date(Date.UTC(2026, 10, 12) - days * 86400000);
  return date.toISOString().slice(0, 10);
}

// normaliseRows: malformed, duplicate and unsafe fields.
{
  const rows = normaliseRows({
    schema_version: "1",
    works: [
      work({work_id: "W2", doi: "javascript:alert(1)", oa_url: "mailto:x@example.org", pub_date: "2026-02-30", year: 2026}),
      work({work_id: "W3", pub_date: "", year: "2024", cited_by_count: -4, authors: ["A", "A", " B "], author_count: 1}),
      work({work_id: "W1"}),
      {title: "no id"},
      null
    ]
  });
  assert.deepEqual(rows.map((row) => row.work_id), ["W2", "W3", "W1"]);
  assert.equal(rows[0].doi, "");
  assert.equal(rows[0].oa_url, "");
  assert.equal(rows[0].pub_date, "");
  assert.equal(rows[0].year, 2026);
  assert.equal(rows[1].year, 2024);
  assert.equal(rows[1].cited_by_count, 0);
  assert.deepEqual(rows[1].authors, ["A", "B"]);
  assert.equal(rows[1].author_count, 2);
  assert.equal(rows[2].plastic_related, true);
  assert.deepEqual(normaliseRows(null), []);
  assert.deepEqual(normaliseRows([work()]).map((row) => row.work_id), ["W1"]);
}

// Year is derived from pub_date when the year field is missing.
assert.equal(normaliseRows({works: [work({year: undefined, pub_date: "2023-05-04"})]})[0].year, 2023);

// isRecent: 14 days back is inclusive, 15 is not; future and undated rows are not recent.
{
  assert.equal(isRecent({pub_date: daysBefore(0)}, TODAY), true);
  assert.equal(isRecent({pub_date: daysBefore(13)}, TODAY), true);
  assert.equal(isRecent({pub_date: daysBefore(14)}, TODAY), true);
  assert.equal(isRecent({pub_date: daysBefore(15)}, TODAY), false);
  assert.equal(isRecent({pub_date: "2026-11-13"}, TODAY), false);
  assert.equal(isRecent({pub_date: ""}, TODAY), false);
  assert.equal(isRecent({year: 2026}, TODAY), false);
  assert.equal(isRecent({pub_date: "2026-11-01"}, new Date("invalid")), false);
  assert.equal(isRecent({pub_date: daysBefore(1)}, TODAY, 0), false);
}

// recentRows keeps only the recent window.
{
  const rows = [
    work({work_id: "R13", pub_date: daysBefore(13)}),
    work({work_id: "R14", pub_date: daysBefore(14)}),
    work({work_id: "R15", pub_date: daysBefore(15)}),
    work({work_id: "NONE", pub_date: ""})
  ];
  assert.deepEqual(recentRows(rows, TODAY).map((row) => row.work_id), ["R13", "R14"]);
}

// sortRows: default newest first, undated rows last (ordered by year), other keys and directions.
{
  const rows = [
    work({work_id: "OLD", pub_date: "2020-03-01", year: 2020, title: "b", journal: "Zeta", cited_by_count: 5}),
    work({work_id: "NODATE25", pub_date: "", year: 2025, title: "a", journal: "", cited_by_count: 50}),
    work({work_id: "NEW", pub_date: "2026-10-01", year: 2026, title: "c", journal: "Alpha", cited_by_count: 1}),
    work({work_id: "NODATE19", pub_date: "", year: 2019, title: "d", journal: "Mid", cited_by_count: 0}),
    work({work_id: "NODATE_NULL", pub_date: "", year: null, title: "e", journal: "Mid", cited_by_count: 2})
  ];
  const ids = (list) => list.map((row) => row.work_id);
  assert.deepEqual(ids(sortRows(rows)), ["NEW", "OLD", "NODATE25", "NODATE19", "NODATE_NULL"]);
  assert.deepEqual(ids(sortRows(rows, "pub_date", "asc")), ["OLD", "NEW", "NODATE19", "NODATE25", "NODATE_NULL"]);
  assert.deepEqual(ids(sortRows(rows, "year", "desc")), ["NEW", "NODATE25", "OLD", "NODATE19", "NODATE_NULL"]);
  assert.deepEqual(ids(sortRows(rows, "cited_by_count")), ["NODATE25", "OLD", "NODATE_NULL", "NEW", "NODATE19"]);
  assert.deepEqual(ids(sortRows(rows, "title", "asc")), ["NODATE25", "OLD", "NEW", "NODATE19", "NODATE_NULL"]);
  // Missing journal sorts last in both directions.
  assert.equal(sortRows(rows, "journal", "asc").at(-1).work_id, "NODATE25");
  assert.equal(sortRows(rows, "journal", "desc").at(-1).work_id, "NODATE25");
  // Unknown keys fall back to pub_date; the input array is not reordered.
  assert.deepEqual(ids(sortRows(rows, "nonsense")), ids(sortRows(rows)));
  assert.equal(rows[0].work_id, "OLD");
}

// filterRows: text (every term), topic, minimum citations, open access, recent.
{
  const rows = [
    work({work_id: "A", title: "Plastic in soil", authors: ["Grace Hopper"], journal: "Soil Sci", cited_by_count: 3, is_oa: true,
      domain_tags: ["soil_and_agriculture"], facet_tags: []}),
    work({work_id: "B", title: "Air samples", authors: ["Alan Turing"], journal: "Atmos Env", cited_by_count: 40,
      domain_tags: ["air"], facet_tags: ["matrix:air"], pub_date: daysBefore(2)}),
    work({work_id: "C", title: "Fish gut", authors: [], journal: "Marine Pollution", cited_by_count: 12, domain_tags: [], facet_tags: ["matrix:marine"], pub_date: daysBefore(20)})
  ];
  const ids = (list) => list.map((row) => row.work_id).sort();
  assert.deepEqual(ids(filterRows(rows, {}, TODAY)), ["A", "B", "C"]);
  assert.deepEqual(ids(filterRows(rows, {q: "  PLASTIC   soil "}, TODAY)), ["A"]);
  assert.deepEqual(ids(filterRows(rows, {q: "hopper atmos"}, TODAY)), []);
  assert.deepEqual(ids(filterRows(rows, {q: "turing"}, TODAY)), ["B"]);
  assert.deepEqual(ids(filterRows(rows, {q: "marine"}, TODAY)), ["C"]);
  assert.deepEqual(ids(filterRows(rows, {tag: "matrix:marine"}, TODAY)), ["C"]);
  assert.deepEqual(ids(filterRows(rows, {tag: "air"}, TODAY)), ["B"]);
  assert.deepEqual(ids(filterRows(rows, {minCites: "10"}, TODAY)), ["B", "C"]);
  assert.deepEqual(ids(filterRows(rows, {minCites: ""}, TODAY)), ["A", "B", "C"]);
  assert.deepEqual(ids(filterRows(rows, {minCites: "abc"}, TODAY)), ["A", "B", "C"]);
  assert.deepEqual(ids(filterRows(rows, {oaOnly: true}, TODAY)), ["A"]);
  assert.deepEqual(ids(filterRows(rows, {recentOnly: true}, TODAY)), ["B"]);
  assert.deepEqual(ids(filterRows(rows, {oaOnly: true, minCites: 5, recentOnly: true}, TODAY)), []);
}

// pageInfo and pageRows: 25 per page by default; page numbers are clamped.
{
  const rows = Array.from({length: 60}, (_, i) => ({i}));
  assert.deepEqual(pageInfo(60, 3), {page: 3, pages: 3, size: 25, total: 60, start: 51, end: 60});
  assert.equal(pageRows(rows, 3).length, 10);
  assert.equal(pageRows(rows, 1)[0].i, 0);
  assert.equal(pageRows(rows, 99)[0].i, 50);
  assert.deepEqual(pageInfo(0, 1), {page: 1, pages: 1, size: 25, total: 0, start: 0, end: 0});
  assert.deepEqual(pageRows([], 1), []);
}

// authorLine: full list when short, "et al." with the full count when long.
{
  assert.equal(authorLine(work({authors: ["A", "B", "C"], author_count: 3})), "A, B, C");
  assert.equal(authorLine(work({authors: ["A", "B", "C"], author_count: 3}), 2), "A, B et al. (3 authors)");
  const names = Array.from({length: 20}, (_, i) => `Author ${i + 1}`);
  assert.equal(
    authorLine(work({authors: names, author_count: 27})),
    "Author 1, Author 2, Author 3, Author 4, Author 5, Author 6 et al. (27 authors)"
  );
  assert.equal(authorLine(work({authors: []})), "");
}

// dateLabel: full date, year only, or a plain note.
assert.equal(dateLabel({pub_date: "2026-11-02", year: 2026}), "2 Nov 2026");
assert.equal(dateLabel({pub_date: "", year: 2024}), "2024");
assert.equal(dateLabel({pub_date: "", year: null}), "Date not listed");

// tagsPresent: unique tags across both tag lists.
assert.deepEqual(tagsPresent([work(), work({work_id: "W9", facet_tags: ["matrix:air"]})]), [
  "matrix:air",
  "matrix:freshwater",
  "occurrence_and_monitoring"
]);

// toCsv: header, quoting of commas and quotes, line breaks, formula guard, no-data case.
{
  const csv = toCsv([
    work({title: 'Say "hi", twice', authors: ["Ada Lovelace", "Grace Hopper"], is_oa: true, oa_url: "https://example.org/a"}),
    work({work_id: "W2", title: "=HYPERLINK(\"x\")", journal: "Line\nbreak", doi: "", domain_tags: [], facet_tags: []})
  ]);
  const lines = csv.split("\r\n");
  assert.equal(lines[0], "work_id,title,authors,journal,publication_date,year,citations,doi,open_access,open_access_url,topics");
  assert.equal(
    lines[1],
    'W1,"Say ""hi"", twice",Ada Lovelace; Grace Hopper,Water Research,2025-06-01,2025,10,https://doi.org/10.1000/abc,yes,https://example.org/a,occurrence_and_monitoring; matrix:freshwater'
  );
  assert.ok(csv.includes("W2,\"'=HYPERLINK(\"\"x\"\")\""));
  assert.ok(csv.includes('"Line\nbreak"'));
  assert.equal(toCsv([]), "work_id,title,authors,journal,publication_date,year,citations,doi,open_access,open_access_url,topics\r\n");
}

// safeHttpUrl keeps http and https only.
assert.equal(safeHttpUrl(" https://doi.org/10.1/x "), "https://doi.org/10.1/x");
assert.equal(safeHttpUrl("http://example.org"), "http://example.org/");
assert.equal(safeHttpUrl("javascript:alert(1)"), "");
assert.equal(safeHttpUrl("not a url"), "");
assert.equal(safeHttpUrl(null), "");

// escapeHtml neutralises markup characters.
assert.equal(escapeHtml(`<a href="x">&'`), "&lt;a href=&quot;x&quot;&gt;&amp;&#39;");
assert.equal(escapeHtml(null), "");

console.log("framework_ev_table_runtime: all checks passed");
