// Node runtime checks for the Framework Experts view (AT-5d). Imports the DOM-free model
// (framework/src/components/experts_model.js) and asserts the classic-site behaviour it ports:
// filters, default sort with nulls last, hash round trip (incl. legacy #experts?), CSV rows.
import assert from "node:assert/strict";
import "../framework/src/components/shared/topics.js";
import {
  buildLookups,
  csvText,
  defaultFilters,
  expertMetricsHtml,
  filterAuthors,
  formatExpertHash,
  formatExpertQuery,
  parseExpertHash,
  resetFilters,
  rowHeightForWidth,
  summarizeAuthor,
  virtualWindow
} from "../framework/src/components/experts_model.js";

// Works: W1 CA-led and CA-sampled (both), OA; W2 CA-led, closed; W3 CA-affiliated, closed; W4 CA-sampled, OA.
const index = {
  works: [
    {work_id: "W1", year: 2020, domain_tags: ["occurrence_and_monitoring"], facet_tags: ["matrix:water"], institution_ids: ["I1"], ca_led: true, ca_sampled: true, is_oa: true},
    {work_id: "W2", year: 2012, domain_tags: ["human_exposure_and_health_risk"], facet_tags: [], institution_ids: ["I2"], ca_led: true, is_oa: false},
    {work_id: "W3", year: 2008, domain_tags: ["air"], facet_tags: [], institution_ids: ["I2"], ca_any_author: true, is_oa: false},
    {work_id: "W4", year: 2021, domain_tags: ["air"], facet_tags: ["matrix:sediment"], institution_ids: ["I3"], ca_sampled: true, is_oa: true}
  ],
  authors: [
    {author_id: "A100", name: "Chelsea Rochman", work_ids: ["W1", "W2"], institution_ids: ["I1"], cited_by_count: 500, h_index: 10, plastic_citations: 100, plastic_works_count: 5, work_count: 2, ca_works_count: 2, first_year: 2012, last_year: 2020, early_career: false, plastic_basis: "atlas_corpus", orcid: "https://orcid.org/0000-0000-0000-0001"},
    {author_id: "A200", name: "Beth Ann", work_ids: ["W3"], institution_ids: [], cited_by_count: 900, h_index: 20, plastic_citations: null, plastic_works_count: 1, work_count: 1, ca_works_count: 1, first_year: 2008, last_year: 2008, early_career: false},
    {author_id: "A300", name: "Zed Quinn", work_ids: ["W2", "W4"], institution_ids: ["I3"], cited_by_count: 80, h_index: 4, plastic_citations: 100, plastic_works_count: 3, work_count: 2, ca_works_count: 1, first_year: 2012, last_year: 2021, early_career: true, rising_pct: 90},
    {author_id: "A400", name: "Mid Person", work_ids: ["W1"], institution_ids: [], cited_by_count: 60, h_index: 3, plastic_citations: 50, plastic_works_count: 1, work_count: 1, ca_works_count: 1, first_year: 2020, last_year: 2020, early_career: true}
  ]
};
const institutions = [
  {inst_id: "I1", name: "UC Davis", atlas_type: "university", ca_flag: true},
  {inst_id: "I2", name: "Oregon State", atlas_type: "university", ca_flag: false},
  {inst_id: "I3", name: "Consulting Co", atlas_type: "company", ca_flag: true}
];

const lookups = buildLookups(index, institutions);
const summaries = index.authors.map((author) => summarizeAuthor(author, lookups.worksById, lookups.institutionsById));
const byId = new Map(summaries.map((author) => [author.author_id, author]));
const run = (overrides, rankedIds = null) => filterAuthors(summaries, {...defaultFilters(), ...overrides}, rankedIds).map((author) => author.author_id);

// Summaries follow the classic authorSummary.
assert.deepEqual(byId.get("A100").tags, ["human_exposure_and_health_risk", "matrix:water", "occurrence_and_monitoring"]);
assert.equal(byId.get("A100").basis, "both");
assert.equal(byId.get("A300").basis, "both");
assert.equal(byId.get("A200").basis, "ca-affiliated");
assert.equal(byId.get("A100").recentCount, 1);
assert.deepEqual(byId.get("A100").types, ["university"]);

// Default sort: plastics citations descending, nulls last, ties broken by CA works (A100 has 2).
assert.deepEqual(run({}), ["A100", "A300", "A400", "A200"]);
assert.deepEqual(run({sort: "h_index"}), ["A200", "A100", "A300", "A400"]);

// Search: substring fallback, exact id, trimming and case, ranked ids.
assert.deepEqual(run({search: "rochman"}), ["A100"]);
assert.deepEqual(run({search: "a200"}), ["A200"], "exact author id matches");
assert.deepEqual(run({search: "  QUINN "}), ["A300"], "search is trimmed and case-insensitive");
assert.deepEqual(run({search: "zzz"}), []);
assert.deepEqual(run({search: "Zed"}, new Set(["A400"])), ["A400"], "ranked ids replace the substring match");

// Filters.
assert.deepEqual(run({tag: "human_exposure_and_health_risk"}), ["A100", "A300"]);
assert.deepEqual(run({tag: "matrix:sediment"}), ["A300"]);
assert.deepEqual(run({institution: "I2"}), ["A100", "A300", "A200"]);
assert.deepEqual(run({institutionType: "company"}), ["A300"]);
assert.deepEqual(run({yearFrom: "2019"}), ["A100", "A300", "A400"]);
assert.deepEqual(run({yearTo: "2009"}), ["A200"]);
assert.deepEqual(run({yearFrom: "2010", yearTo: "2012"}), ["A100", "A300"]);
assert.deepEqual(run({caBasis: "ca-sampled"}), []);
assert.deepEqual(run({caBasis: "both"}), ["A100", "A300", "A400"]);
assert.deepEqual(run({oa: "oa"}), ["A100", "A300", "A400"]);
assert.deepEqual(run({oa: "closed"}), ["A200"]);
assert.deepEqual(run({early: true}), ["A300", "A400"]);

// Hash: parse, format and the legacy prefix.
const modern = parseExpertHash("#search=roch&sort=h_index&early=1&oa=oa");
assert.deepEqual(modern.filters, {...defaultFilters(), search: "roch", sort: "h_index", early: true, oa: "oa"});
assert.equal(modern.author, "");
assert.deepEqual(parseExpertHash("#experts?search=roch&sort=h_index&early=1&oa=oa"), modern, "legacy #experts? prefix");
assert.deepEqual(parseExpertHash("#experts"), {filters: defaultFilters(), author: ""});
assert.deepEqual(parseExpertHash(""), {filters: defaultFilters(), author: ""});
assert.equal(parseExpertHash("#sort=bogus&oa=both").filters.sort, "plastic_citations", "invalid sort falls back to the default");
assert.equal(parseExpertHash("#oa=both").filters.oa, "", "invalid oa falls back to any");
assert.equal(parseExpertHash("#author=A100").author, "A100");
assert.equal(parseExpertHash("#author=../x").author, "", "malformed author id is ignored");
assert.equal(formatExpertHash(defaultFilters()), "", "defaults write no hash");
assert.equal(formatExpertQuery({...defaultFilters(), sort: "plastic_citations"}), "", "default sort is not written");
const full = {...defaultFilters(), search: "a b", institutionType: "company", institution: "I3", tag: "matrix:water", yearFrom: "2000", yearTo: "2020", caBasis: "ca-led", oa: "closed", early: true, sort: "m_quotient", collab: true};
const hash = formatExpertHash(full);
assert.ok(hash.startsWith("#"));
assert.deepEqual(parseExpertHash(hash).filters, full, "hash round trip keeps every filter");
assert.deepEqual(parseExpertHash(hash.replace("#", "#experts?")).filters, full, "round trip through the legacy prefix");
assert.equal(resetFilters(full).sort, "m_quotient", "reset keeps the sort order");
assert.equal(resetFilters(full).search, "", "reset clears the search");

// Metrics line bolds the active sort key and flags CA-corpus-only plastics citations.
const metrics = expertMetricsHtml(byId.get("A100"), "plastic_citations");
assert.ok(metrics.includes("<strong>100 on plastics (20%)</strong>"), metrics);
assert.ok(metrics.includes('class="basis-note"'), "atlas_corpus basis is flagged");
assert.ok(!expertMetricsHtml(byId.get("A100"), "h_index").includes("<strong>100 on plastics"));

// Virtual window and row height.
assert.deepEqual(virtualWindow({scrollTop: 0, clientHeight: 500, rowHeight: 232, count: 4, overscan: 4}), {start: 0, end: 4});
assert.deepEqual(virtualWindow({scrollTop: 2320, clientHeight: 232, rowHeight: 232, count: 100, overscan: 4}), {start: 6, end: 15});
assert.equal(rowHeightForWidth(500), 264);
assert.equal(rowHeightForWidth(1024), 232);

// CSV: header, doubled quotes, empty cells for null metrics.
const quoted = summarizeAuthor({...index.authors[0], author_id: "A900", name: 'Jo "JJ" Smith', plastic_citations: null}, lookups.worksById, lookups.institutionsById);
const lines = csvText([quoted]).split("\n");
assert.equal(lines.length, 2);
assert.equal(lines[0], '"author_id","name","work_count","ca_works_count","first_year","last_year","ca_basis","domain_tags","institution_ids","cited_by_count","h_index","plastic_works_count","plastic_citations","plastic_citation_share_pct","topic_counts"');
assert.ok(lines[1].startsWith('"A900","Jo ""JJ"" Smith","2","2","2012","2020","both","'), lines[1]);
const topicCell = quoted.topicWeights.map(([tag, count]) => `${tag}:${count}`).join(";");
assert.ok(lines[1].endsWith(`,"5","","","${topicCell}"`), lines[1]);

console.log("framework_experts_runtime: all assertions passed");
