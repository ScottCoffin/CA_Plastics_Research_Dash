// Runtime regression checks for the ported Institutions page helpers (AT-5e).
// Covers the tiers helpers (inst_tiers.js) and the DOM-free institution helpers in institutions.js.
// Run with: node tests/framework_institutions_runtime.mjs (driven by tests/test_framework_institutions.py).
import assert from "node:assert/strict";
import {instTiers} from "../framework/src/components/inst_tiers.js";
import {
  buildInstitutionWorksIndex,
  institutionComparator,
  institutionMetrics,
  metricNumber,
  primaryTopic,
  topicShare
} from "../framework/src/components/institutions.js";

// Tiers helpers.
assert.equal(instTiers.viewFromParams(new URLSearchParams("")), "tiers");
assert.equal(instTiers.viewFromParams(new URLSearchParams("inst_view=list")), "list");
assert.equal(instTiers.viewFromParams(new URLSearchParams("inst_view=bogus")), "tiers");
const hashParams = new URLSearchParams("");
instTiers.applyViewParam(hashParams, "tiers");
assert.equal(hashParams.toString(), "", "tiers is the default and stays out of the URL");
instTiers.applyViewParam(hashParams, "list");
assert.equal(hashParams.get("inst_view"), "list");

assert.equal(instTiers.fmt(2), "2.0");
assert.equal(instTiers.fmt(null), "0.0");
assert.equal(instTiers.esc(`<a "x" & 'y'>`), "&lt;a &quot;x&quot; &amp; &#39;y&#39;&gt;");

const tierRows = [
  { inst_id: "a", name: "Beta", atlas_type: "university", tier: 1, works_full: 10, works_frac: 4.5, frac_lo: 3, frac_hi: 6, rank_lo: 1, rank_hi: 2 },
  { inst_id: "b", name: "Alpha", atlas_type: "university", tier: 1, works_full: 9, works_frac: 4.5, frac_lo: 2, frac_hi: 7, rank_lo: 1, rank_hi: 3 },
  { inst_id: "c", name: "Gamma", atlas_type: "utility", tier: 2, works_full: 3, works_frac: 1.25, frac_lo: 0.5, frac_hi: 2, rank_lo: 4, rank_hi: 4 },
];
const groups = instTiers.groupTiers(tierRows, "");
assert.deepEqual(groups.map((g) => g.tier), [1, 2]);
assert.deepEqual(groups[0].rows.map((r) => r.name), ["Alpha", "Beta"], "ties on fractional works sort by name");
assert.equal(groups[0].scaleMin, 2);
assert.equal(groups[0].scaleMax, 7);
assert.equal(instTiers.summary(groups[0]), "Tier 1 · 2 institutions · fractional works 4.5–4.5");
assert.equal(instTiers.groupTiers(tierRows, "utility").length, 1);
assert.equal(instTiers.rankText(tierRows[0]), "ranks 1–2");
assert.equal(instTiers.rankText(tierRows[2]), "rank 4");
const tierHtml = instTiers.tiersHtml(tierRows, "");
assert.ok(tierHtml.includes('<details class="tier-group" open>'), "tiers 1 and 2 open by default");
assert.ok(tierHtml.includes('data-institution-id="c"'));
assert.ok(instTiers.tiersHtml(tierRows, "nope").includes("No ranked institutions match this type filter."));

// Institution helpers.
const index = {
  works: [
    { year: 2018, plastic_related: true, institution_ids: ["I1", "I1", "I2"], domain_tags: ["air"] },
    { year: 2020, plastic_related: true, institution_ids: ["I1"], domain_tags: [] },
    { year: 2024, plastic_related: false, institution_ids: ["I1"], domain_tags: ["air"] },
    { year: 2024, plastic_related: true, institution_ids: ["I1"], domain_tags: ["air"] },
  ],
};
const worksByInst = buildInstitutionWorksIndex(index);
assert.equal(worksByInst.get("I1").length, 3, "untagged works are excluded");
assert.equal(worksByInst.get("I2").length, 1, "an institution is counted once per work");

const metric = institutionMetrics({ inst_id: "I1", name: "One" }, worksByInst);
assert.equal(metric.taggedCount, 3);
assert.equal(metric.recentCount, 2, "recent window is the latest year and the four before it");
assert.deepEqual(metric.trendYears, [2018, 2019, 2020, 2021, 2022, 2023, 2024]);
assert.deepEqual(metric.series, [1, 0, 1, 0, 0, 0, 1]);
const empty = institutionMetrics({ inst_id: "none", name: "None" }, worksByInst);
assert.equal(empty.taggedCount, 0);
assert.deepEqual(empty.trendYears, []);
assert.equal(empty.recentCount, 0);

const mk = (name, taggedCount, recentCount, topics = []) => ({ institution: { name }, taggedCount, recentCount, topics });
const names = (list) => list.map((m) => m.institution.name);
const sample = () => [mk("B", 2, 1), mk("A", 2, 3), mk("C", 5, 0)];
assert.deepEqual(names(sample().sort(institutionComparator("tagged"))), ["C", "A", "B"]);
assert.deepEqual(names(sample().sort(institutionComparator("name"))), ["A", "B", "C"]);
assert.deepEqual(names(sample().sort(institutionComparator("recent"))), ["A", "B", "C"]);
const shareSample = [mk("A", 4, 0, [["air", 2]]), mk("B", 2, 0, [["air", 2]]), mk("C", 5, 0)];
assert.deepEqual(names(shareSample.sort(institutionComparator("share:air"))), ["B", "A", "C"]);

const topicMetric = mk("T", 4, 0, [["matrix:sediment", 3], ["air", 2]]);
assert.equal(primaryTopic(topicMetric), "air", "matrix facets are not primary topics");
assert.equal(primaryTopic(mk("M", 1, 0, [["matrix:sediment", 1]])), "");
assert.deepEqual(topicShare(topicMetric, "air"), { count: 2, share: 0.5 });
assert.deepEqual(topicShare(topicMetric, "missing"), { count: 0, share: 0 });

assert.equal(metricNumber(null), "—");
assert.equal(metricNumber(""), "—");
assert.equal(metricNumber(1234), "1,234");
assert.equal(metricNumber("12"), "12");

console.log("framework institutions runtime checks passed");
