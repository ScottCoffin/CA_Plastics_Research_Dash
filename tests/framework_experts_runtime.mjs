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
  bylineNames,
  coauthorSummary,
  currentAffiliationHtml,
  currentAffiliationStatus,
  NOW_VALUES,
  drawerContentHtml,
  expertRowHtml,
  summarizeAuthor,
  virtualWindow,
  workAuthorsHtml
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

// Byline and co-authors (works carry authors[] and author_count; old snapshots do not).
const bylineWorks = [
  {work_id: "W1", title: "Paper <one>", year: 2021, journal: "J", author_ids: ["A100", "A200", "A300", "A500"], author_count: 27,
    authors: [{id: "A100", name: "Chelsea Rochman"}, {id: "A200", name: "Beth Ann"}, {id: "A300", name: "Zed Quinn"}, {id: "A500", name: "Outside <Writer>"}]},
  {work_id: "W2", title: "Paper two", year: 2022, journal: "K", author_ids: ["A100", "A500", "A600"],
    authors: [{id: "A100", name: "Chelsea Rochman"}, {id: "A500", name: "Outside <Writer>"}]},
  {work_id: "W3", title: "Old snapshot", year: 2019, journal: "L", author_ids: ["A100", "A700"]}
];
assert.equal(workAuthorsHtml(bylineWorks[0], "A100"), '<p class="work-authors"><strong>Chelsea Rochman</strong>, Beth Ann, Zed Quinn, Outside &lt;Writer&gt;, et al. (27 authors)</p>');
assert.equal(workAuthorsHtml(bylineWorks[2], "A100"), "", "old snapshot without authors adds no line");
assert.equal(workAuthorsHtml({authors: [{id: "A1", name: "Solo"}], author_count: 1}, "A9"), '<p class="work-authors">Solo</p>');
assert.deepEqual(Object.fromEntries(bylineNames(bylineWorks)), {A100: "Chelsea Rochman", A200: "Beth Ann", A300: "Zed Quinn", A500: "Outside <Writer>"});
const expertsForWorks = new Map([["A200", {author_id: "A200", name: "Beth Ann"}], ["A300", {author_id: "A300", name: "Zed Quinn"}]]);
const coSummary = coauthorSummary(bylineWorks, "A100", expertsForWorks);
assert.equal(coSummary.coauthorCount, 5, "distinct co-author ids, unchanged by names");
assert.deepEqual(coSummary.namedCoauthors.map(([id, count]) => [id, count]), [["A200", 1], ["A300", 1]]);
assert.deepEqual(coSummary.otherCoauthors, [{author_id: "A500", name: "Outside <Writer>", shared: 2}], "non-expert co-author named from the byline; unnamed A600 and A700 omitted");
const drawerHtml = drawerContentHtml({author: {author_id: "A100", name: "Chelsea Rochman"}, works: bylineWorks, authorId: "A100", profile: null, expertsById: expertsForWorks, institutionsById: new Map(), histogramSvg: null});
assert.ok(drawerHtml.includes("(2 CA experts, 1 others)"), "summary count text");
assert.ok(drawerHtml.includes("Outside &lt;Writer&gt; </span>") || drawerHtml.includes("<span>Outside &lt;Writer&gt;</span>"), "other co-author shown unlinked and escaped");
assert.ok(!drawerHtml.includes("Co-author outside"), "old placeholder text is gone");
assert.ok(drawerHtml.includes('<p class="work-authors"><strong>Chelsea Rochman</strong>'), "work byline in the drawer");

// Current affiliation (owner request 2026-11-13): now=ca | outside | unknown, from current_in_ca.
// A100 outside (last California year 2019), A200 in California, A300 null, A400 field absent (unknown).
const nowAuthors = [
  {...index.authors[0], current_in_ca: false, last_ca_year: 2019},
  {...index.authors[1], current_in_ca: true, last_ca_year: null},
  {...index.authors[2], current_in_ca: null, last_ca_year: null},
  {...index.authors[3]}
];
const nowSummaries = nowAuthors.map((author) => summarizeAuthor(author, lookups.worksById, lookups.institutionsById));
const runNow = (now) => filterAuthors(nowSummaries, {...defaultFilters(), now}).map((author) => author.author_id);
assert.deepEqual(NOW_VALUES, ["", "ca", "outside", "unknown"]);
assert.deepEqual(nowSummaries.map(currentAffiliationStatus), ["outside", "ca", "unknown", "unknown"]);
assert.deepEqual(runNow(""), ["A100", "A300", "A400", "A200"], "any: no current-affiliation filtering");
assert.deepEqual(runNow("ca"), ["A200"], "in California now");
assert.deepEqual(runNow("outside"), ["A100"], "outside California now");
assert.deepEqual(runNow("unknown"), ["A300", "A400"], "unknown includes a missing field");
assert.equal(parseExpertHash("#now=outside").filters.now, "outside");
assert.equal(parseExpertHash("#experts?now=ca").filters.now, "ca", "legacy prefix");
assert.equal(parseExpertHash("#now=sometimes").filters.now, "", "invalid now falls back to any");
assert.equal(formatExpertHash({...defaultFilters(), now: "unknown"}), "#now=unknown");
assert.equal(formatExpertHash({...defaultFilters(), now: ""}), "", "any writes no hash");
assert.equal(resetFilters({...defaultFilters(), now: "ca", sort: "h_index"}).now, "", "reset clears the current-affiliation filter");
assert.equal(resetFilters({...defaultFilters(), now: "ca", sort: "h_index"}).sort, "h_index", "reset keeps the sort");
assert.equal(currentAffiliationHtml(nowSummaries[0]), '<span class="now-badge">Now outside California</span> <span class="detail-meta">· last California affiliation 2019</span>');
assert.equal(currentAffiliationHtml({current_in_ca: false, last_ca_year: null}), '<span class="now-badge">Now outside California</span>', "no year when none is recorded");
assert.equal(currentAffiliationHtml(nowSummaries[1]), "", "in California: no badge");
assert.equal(currentAffiliationHtml(nowSummaries[2]), "", "unknown: no badge");
const outsideRow = expertRowHtml(nowSummaries[0], 0, 232, "plastic_citations");
assert.ok(outsideRow.includes('<p class="card-meta expert-affil" title="') && outsideRow.includes('</span> <span class="detail-meta">· last California affiliation 2019</span> · '), outsideRow);
assert.ok(!expertRowHtml(nowSummaries[1], 0, 232, "plastic_citations").includes("now-badge"), "in-California row has no badge");

console.log("framework_experts_runtime: all assertions passed");
