// Runtime checks for the institution detail page helpers (INST-PAGE, institution_model.js).
// Run with: node tests/framework_institution_runtime.mjs (driven by tests/test_framework_institution.py).
import assert from "node:assert/strict";
import {
  LEAD_AUTHOR_LIMIT,
  barChartLayout,
  collaborators,
  fontSizeRem,
  isSafeInstId,
  labelStep,
  leadAuthors,
  mostCited,
  openAlexUrl,
  parseInstitutionHash,
  plasticWorks,
  recentWindow,
  rorUrl,
  searchInstitutions,
  summaryStats,
  topJournals,
  topicWeights,
  workIds,
  worksPerYear,
  worksWithTag,
} from "../framework/src/components/institution_model.js";

// Hash parsing and id safety.
assert.deepEqual(parseInstitutionHash("#inst=I84218800"), {instId: "I84218800", section: ""});
assert.deepEqual(parseInstitutionHash("#inst=CAAG-OEHHA&section=publications"), {instId: "CAAG-OEHHA", section: "publications"});
assert.deepEqual(parseInstitutionHash("#inst=I1&section=bogus"), {instId: "I1", section: ""});
assert.deepEqual(parseInstitutionHash("#inst=../etc/passwd"), {instId: "", section: ""}, "unsafe ids are dropped");
assert.deepEqual(parseInstitutionHash(""), {instId: "", section: ""});
assert.equal(isSafeInstId("I151201029"), true);
assert.equal(isSafeInstId("a b"), false);
assert.equal(isSafeInstId(""), false);

// Links.
assert.equal(rorUrl("04vnq7t77"), "https://ror.org/04vnq7t77", "bare ROR ids become ror.org links");
assert.equal(rorUrl("https://ror.org/04vnq7t77"), "https://ror.org/04vnq7t77");
assert.equal(rorUrl(""), "");
assert.equal(rorUrl("javascript:alert(1)"), "", "non-ROR values never become links");
assert.equal(openAlexUrl("I84218800"), "https://openalex.org/I84218800");
assert.equal(openAlexUrl("CAAG-OEHHA"), "", "only OpenAlex institution ids link out");

// Works, years and the recent window.
const works = [
  {work_id: "W1", year: 2018, plastic_related: true, domain_tags: ["air"], facet_tags: ["matrix:marine"], author_ids: ["A1", "A2", "A3"], institution_ids: ["I1", "I2"], journal: "J A", cited_by_count: 5, is_oa: true, ca_led: true, title: "Five", doi: "https://doi.org/1"},
  {work_id: "W2", year: 2020, plastic_related: true, domain_tags: ["air", "water"], facet_tags: [], author_ids: ["A2"], institution_ids: ["I1", "I3"], journal: "J A", cited_by_count: 9, is_oa: false, ca_led: false, title: "Nine"},
  {work_id: "W3", year: 2024, plastic_related: true, domain_tags: ["air"], facet_tags: ["matrix:marine"], author_ids: ["A1", "A4"], institution_ids: ["I1", "I2"], journal: "J B", cited_by_count: 1, is_oa: true, ca_led: true, title: "One"},
  {work_id: "W4", year: 2024, plastic_related: false, domain_tags: ["air"], facet_tags: [], author_ids: ["A9"], institution_ids: ["I1"], journal: "J C", cited_by_count: 100, is_oa: true, ca_led: true, title: "Not plastic"},
];
const tagged = plasticWorks(works);
assert.deepEqual(tagged.map((w) => w.work_id), ["W1", "W2", "W3"], "non-plastic works are excluded");
assert.deepEqual(plasticWorks(null), []);

assert.deepEqual(worksPerYear(tagged), [
  {year: 2018, count: 1}, {year: 2019, count: 0}, {year: 2020, count: 1},
  {year: 2021, count: 0}, {year: 2022, count: 0}, {year: 2023, count: 0}, {year: 2024, count: 1},
], "years run contiguously from the first to the last plastic-related work");
assert.deepEqual(worksPerYear([]), []);

const today = new Date("2026-11-13T12:00:00Z");
assert.deepEqual(recentWindow(today), {from: 2021, to: 2025}, "last five complete years exclude the current year");

const stats = summaryStats({experts: [{author_id: "A1"}, {author_id: "A2"}], works}, today);
assert.equal(stats.plasticWorks, 3);
assert.equal(stats.experts, 2);
assert.equal(stats.citations, 15);
assert.ok(Math.abs(stats.oaShare - 2 / 3) < 1e-9);
assert.ok(Math.abs(stats.caLedShare - 2 / 3) < 1e-9);
assert.equal(stats.firstYear, 2018);
assert.equal(stats.lastYear, 2024);
assert.equal(stats.recentWorks, 1, "only the 2024 work falls in 2021-2025");
const emptyStats = summaryStats({experts: [], works: []}, today);
assert.equal(emptyStats.oaShare, null);
assert.equal(emptyStats.firstYear, null);
assert.equal(emptyStats.recentWorks, 0);

// Topic weights: font size scales with sqrt(count / largest), inside 0.85-1.7rem.
const weights = topicWeights(tagged);
assert.deepEqual(weights.topics.map((t) => [t.tag, t.count]), [["air", 3], ["water", 1]]);
assert.equal(weights.topics[0].fontRem, 1.7, "the largest topic gets the maximum size");
assert.equal(weights.topics[0].share, 1);
assert.ok(Math.abs(weights.topics[1].fontRem - (0.85 + 0.85 * Math.sqrt(1 / 3))) < 0.001, "smaller counts scale by sqrt");
assert.ok(weights.topics[1].fontRem > 0.85 && weights.topics[1].fontRem < 1.7);
assert.deepEqual(weights.matrices.map((t) => [t.tag, t.count]), [["matrix:marine", 2]], "matrix tags come from facet_tags");
assert.equal(weights.matrices[0].fontRem, 1.1, "matrix chips use their own, smaller range");
assert.equal(fontSizeRem(0, 0), 0.85, "no works gives the minimum size");
assert.equal(fontSizeRem(4, 4), 1.7);

assert.deepEqual(workIds(worksWithTag(tagged, "water")), ["W2"]);
assert.deepEqual(workIds(worksWithTag(tagged, "matrix:marine")), ["W1", "W3"]);
assert.deepEqual(workIds(worksWithTag(tagged, "")), ["W1", "W2", "W3"], "an empty tag keeps every work");
assert.deepEqual(workIds(worksWithTag(tagged, "missing")), []);

// Lead authors: ranked by works here, then plastic citations, then name. First and last counts come from author order.
const experts = [
  {author_id: "A2", name: "Bee", in_atlas_index: true, works_at_institution: 2, plastic_citations: 10, first_year: 2018, last_year: 2024, topics: [["water", 1], ["matrix:marine", 9], ["air", 3]]},
  {author_id: "A1", name: "Ann", in_atlas_index: false, works_at_institution: 2, plastic_citations: 40, first_year: 2018, last_year: 2024, topics: [["air", 2]]},
  {author_id: "A3", name: "Cy", in_atlas_index: true, works_at_institution: 1, plastic_citations: 0, first_year: null, last_year: null, topics: []},
];
const leads = leadAuthors(experts, tagged);
assert.deepEqual(leads.map((l) => l.name), ["Ann", "Bee", "Cy"]);
assert.equal(leads[0].firstHere, 2, "Ann leads W1 and W3");
assert.equal(leads[0].lastHere, 0, "Ann is never last author here");
assert.equal(leads[1].firstHere, 1, "Bee is the only author on W2, so counts as first");
assert.equal(leads[1].lastHere, 0, "Bee is a middle author on W1 and does not count as last");
assert.equal(leads[2].lastHere, 1, "Cy ends the W1 author list");
assert.equal(leads[2].firstHere, 0);
assert.deepEqual(leads[1].topTopics, [{tag: "air", count: 3}, {tag: "water", count: 1}], "top topics skip matrix tags");
assert.equal(leads[2].firstYear, null);
assert.equal(LEAD_AUTHOR_LIMIT, 15);

// Collaborating institutions, journals and most-cited works.
const names = new Map([["I2", "Two"], ["I3", "Three"]]);
const collab = collaborators(tagged, "I1", (id) => names.get(id) || id);
assert.deepEqual(collab, [
  {inst_id: "I2", name: "Two", works: 2},
  {inst_id: "I3", name: "Three", works: 1},
], "co-occurring institutions, counted once per work, excluding the institution itself");
assert.deepEqual(collaborators([], "I1"), []);

assert.deepEqual(topJournals(tagged), [{journal: "J A", count: 2}, {journal: "J B", count: 1}]);
assert.deepEqual(mostCited(tagged, 2).map((w) => w.work_id), ["W2", "W1"]);

// Per-year chart geometry: bars are scaled to the largest year and stay inside the viewBox.
const layout = barChartLayout(worksPerYear(tagged), 600, 200, 12, 26);
assert.equal(layout.bars.length, 7);
assert.equal(layout.bars[2].height, (1 / 1) * (200 - 12 - 26), "the largest year fills the plot");
assert.equal(layout.bars[1].height, 0, "gap years have zero height");
assert.equal(layout.baseline, 174);
assert.ok(layout.bars.every((b) => b.x >= 0 && b.x + b.width <= 600 && b.y >= 0));
assert.deepEqual(barChartLayout([]).bars, []);
assert.equal(labelStep(7), 1);
assert.equal(labelStep(100), 9);

// Search for the no-id page.
const list = [
  {inst_id: "I1", name: "Alpha Institute", city: "Davis", region: "California", atlas_type: "UC"},
  {inst_id: "I2", name: "beta Lab", city: "Irvine", region: "California", atlas_type: "federal"},
  {inst_id: "I3", name: "Gamma Co", city: "Davis", region: "California", atlas_type: "company"},
  {name: "No id"},
];
const all = searchInstitutions(list, "");
assert.equal(all.total, 3, "entries without a safe id are skipped");
assert.deepEqual(all.shown.map((i) => i.name), ["Alpha Institute", "beta Lab", "Gamma Co"], "sorted by name");
assert.deepEqual(searchInstitutions(list, "davis").shown.map((i) => i.inst_id), ["I1", "I3"], "matches city");
assert.deepEqual(searchInstitutions(list, "DAVIS  company").shown.map((i) => i.inst_id), ["I3"], "every term must match");
assert.equal(searchInstitutions(list, "nothing").total, 0);
assert.equal(searchInstitutions(list, "", 2).shown.length, 2);
assert.equal(searchInstitutions(list, "", 2).total, 3);

console.log("framework institution runtime checks passed");
