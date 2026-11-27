// Runtime checks for the Community groups composition views. The pure helpers live in
// framework/src/components/groups_composition.js; the Plot and d3 drawing is checked in a browser.
import assert from "node:assert/strict";
import {
  EMPTY_MESSAGE,
  NO_IMPOSSIBLE_REASONS,
  SMALL_CELL,
  activityByRegion,
  agreementLines,
  centralityBySector,
  contrastRatio,
  compositionTree,
  evidenceRows,
  heatmapSummary,
  inkFor,
  labelFits,
  labelFor,
  orderedKeys,
  reasonRows,
  taggedGroups,
  treeTotal,
  treemapSummary,
} from "../framework/src/components/groups_composition.js";
import {GROUP_TAXONOMY} from "../framework/src/components/ambassador_groups.js";
import {CHROME, INK_DARK, INK_LIGHT, SEQ, rampFill} from "../framework/src/components/shared/palette.js";

const SECTORS = ["ngo_civil_society", "community_informal", "foundation"];
const CENTRALITY = ["primary", "substantial", "incidental", "none"];
const ACTIVITIES = ["advocacy_campaigning", "cleanup_removal", "research_monitoring", "waste_management_recycling", "education_awareness"];
const REGIONS = ["Northern America", "Eastern Africa", "Eastern Asia"];
const TAGGED_STATUS = ["ambassador_tagged", "reviewed", "group_confirmed"];

// 30 tagged groups (status cycles through the three tagged statuses; the first 20 are primary, so some cells reach
// the small-cell threshold and others stay under it). Group 29 has no sector, so it lands in "Not recorded".
const tagged = Array.from({length: 30}, (_, i) => ({
  group_id: `cg_${String(i).padStart(16, "0")}`,
  name: `Group ${i}`,
  status: TAGGED_STATUS[i % 3],
  layer: i % 3 === 0 ? "adjacent" : "core",
  sector: i === 29 ? null : SECTORS[i % 3],
  plastics_centrality: i < 20 ? "primary" : CENTRALITY[1 + (i % 3)],
  primary_activities: [ACTIVITIES[(i * 7) % ACTIVITIES.length], "other"],
  region: REGIONS[i % REGIONS.length],
}));
// Three untagged roster rows, one in a region with no tagged group: that region must not get a heatmap row.
const untagged = [0, 1, 2].map((i) => ({
  group_id: `cg_u${i}`, name: `Roster ${i}`, status: "unlabelled", layer: "untagged", sector: null,
  plastics_centrality: null, primary_activities: [], region: "Western Africa",
}));
const groups = [...untagged, ...tagged];

const expectedCount = (predicate) => tagged.filter(predicate).length;

// ---- tagged filter ----
assert.equal(taggedGroups(groups).length, 30, "only the three tagged statuses count");
assert.equal(taggedGroups([{status: "unlabelled"}, {status: "ambassador_tagged"}]).length, 1);
assert.deepEqual(taggedGroups(null), []);

// ---- heatmap 1: plastics centrality by sector (counts only) ----
const sectorMatrix = centralityBySector(groups);
assert.equal(sectorMatrix.total, 30);
assert.equal(sectorMatrix.cells.reduce((s, c) => s + c.n, 0), 30, "heatmap 1 cells sum to the tagged count");
assert.equal(sectorMatrix.cells.length, (GROUP_TAXONOMY.sector.length + 1) * GROUP_TAXONOMY.plastics_centrality.length,
  "every taxonomy sector row is present, plus a Not recorded row for group 29");
const sectorCell = sectorMatrix.cells.find((c) => c.row === "foundation" && c.col === "substantial");
assert.equal(sectorCell.n, expectedCount((g) => g.sector === "foundation" && g.plastics_centrality === "substantial"));
assert.equal(sectorCell.label, String(sectorCell.n), "heatmap 1 shows counts");
assert.equal(sectorCell.share, null);
assert.equal(sectorMatrix.cells.filter((c) => c.row === "").reduce((s, c) => s + c.n, 0), 1,
  "group with no sector is counted, not dropped");
assert.equal(sectorMatrix.yDomain.at(-1), "Not recorded");
assert.ok(sectorMatrix.cells.some((c) => !c.small && c.n >= SMALL_CELL), "some cells reach the threshold");
assert.ok(sectorMatrix.smallCount > 0 && sectorMatrix.smallCount < sectorMatrix.cells.length);
assert.ok(sectorMatrix.cells.every((c) => typeof c.fill === "string" && c.fill.length > 0), "every cell has a fill");
assert.ok(sectorMatrix.cells.filter((c) => c.small && c.n > 0).every((c) => c.ink === CHROME.axis), "muted cells use muted ink");
assert.ok(sectorMatrix.cells.filter((c) => c.n === 0).every((c) => c.fill === SEQ[0]), "zero cells take the lightest step");

// ---- heatmap 2 (transposed): regions as rows, main activities as columns ----
const actMatrix = activityByRegion(groups);
assert.equal(actMatrix.shareOver, "row");
assert.deepEqual(actMatrix.yDomain, [...REGIONS].sort(), "rows are only the regions with tagged groups, alphabetical");
assert.ok(!actMatrix.yDomain.includes("Western Africa"), "a region with no tagged group gets no row");
assert.equal(actMatrix.xDomain.length, GROUP_TAXONOMY.primary_activities.length, "all activity columns in taxonomy order");
assert.equal(actMatrix.cells.reduce((s, c) => s + c.n, 0), 30);
for (const region of REGIONS) {
  const inRegion = tagged.filter((g) => g.region === region);
  const row = actMatrix.cells.filter((c) => c.row === region);
  assert.equal(row.reduce((s, c) => s + c.n, 0), inRegion.length);
  const shareSum = row.reduce((s, c) => s + (c.share ?? 0), 0);
  assert.ok(Math.abs(shareSum - 1) < 1e-9, `within-region shares sum to 1 for ${region}`);
  const cell = actMatrix.cells.find((c) => c.row === region && c.col === "cleanup_removal");
  const n = expectedCount((g) => g.region === region && g.primary_activities[0] === "cleanup_removal");
  assert.equal(cell.n, n);
  assert.equal(cell.base, inRegion.length);
  assert.equal(cell.share, n / inRegion.length);
  assert.equal(cell.label, n === 0 ? "" : String(n), "cell text is the count only");
  assert.ok(cell.tip.includes(`${Math.round((n / inRegion.length) * 100)}%`), "the share is in the cell tooltip");
}
const zeroCell = actMatrix.cells.find((c) => c.n === 0);
assert.ok(zeroCell, "fixture has a zero cell");
assert.equal(zeroCell.label, "", "zero cells carry no text");
assert.equal(zeroCell.fill, SEQ[0], "zero cells take the lightest step");
assert.ok(actMatrix.xDomain.indexOf("Advocacy and campaigns") < actMatrix.xDomain.indexOf("Clean-ups and litter removal"),
  "activities follow taxonomy order");

// ---- ordering helper ----
assert.deepEqual(orderedKeys(["a", "b", "c"], ["c", "a", "zz", ""]), ["a", "c", "zz", ""]);
assert.deepEqual(orderedKeys(["a", "b", "c"], ["c"], {includeAll: true}), ["a", "b", "c"]);
assert.equal(labelFor("layer", "adjacent"), "Adjacent groups");
assert.equal(labelFor("sector", ""), "Not recorded");
assert.equal(labelFor(null, "Western Asia"), "Western Asia");

// ---- label colour: the ink with the higher contrast, at least 4.5:1 on every fill used ----
assert.ok(Math.abs(contrastRatio("#000000", "#ffffff") - 21) < 1e-9, "black on white is 21:1");
for (const fill of SEQ) {
  assert.ok(contrastRatio(fill, inkFor(fill)) >= 4.5, `ink for ${fill} meets 4.5:1`);
}
for (let i = 0; i <= 100; i += 1) {
  const fill = rampFill(i / 100);
  assert.ok(contrastRatio(fill, inkFor(fill)) >= 4.5, `ink for ramp step ${i} meets 4.5:1 (${fill})`);
}
assert.equal(inkFor("#23305e"), INK_LIGHT, "navy takes light text");
assert.equal(inkFor("#f6f3ec"), INK_DARK, "paper takes dark text");
assert.ok(contrastRatio(CHROME.sunken, CHROME.axis) >= 4.5, "muted cells: axis ink on sunken fill meets 4.5:1");

// ---- heatmap summaries ----
assert.equal(heatmapSummary(centralityBySector([]), {rowNoun: "sector", colNoun: "centrality"}),
  EMPTY_MESSAGE, "no tagged groups gives the empty message");
const summary = heatmapSummary(sectorMatrix, {rowNoun: "sector", colNoun: "centrality"});
assert.match(summary, /^30 tagged groups/);
assert.match(summary, /fewer than 5 groups/);
const shareSummary = heatmapSummary(actMatrix, {rowNoun: "region", colNoun: "main activity"});
assert.match(shareSummary, /^30 tagged groups, by region and main activity\./);
assert.match(shareSummary, /of \d+ tagged groups there/, "the share summary names the base");

// ---- treemap: layer, sector, activity; totals equal the tagged count ----
const tree = compositionTree(groups);
assert.equal(treeTotal(tree), 30, "treemap total equals tagged groups");
assert.deepEqual(tree.children.map((n) => n.id), ["layer:core", "layer:adjacent"], "core is listed before adjacent");
assert.equal(tree.children[0].children.length > 0, true, "the layer has sector children for the two-level view");
assert.equal(treeTotal(tree.children[0]), expectedCount((g) => g.layer === "core"));
const leaves = [];
const walk = (n) => (n.children ? n.children.forEach(walk) : leaves.push(n));
walk(tree);
assert.ok(leaves.every((leaf) => leaf.value > 0), "empty branches are left out");
assert.equal(leaves.reduce((s, l) => s + l.value, 0), 30);
assert.match(treemapSummary(tree), /^30 tagged groups/);
assert.equal(treeTotal(compositionTree(untagged)), 0, "no tagged groups gives an empty tree");
assert.equal(treemapSummary(compositionTree([])), EMPTY_MESSAGE);

// ---- label fit ----
assert.equal(labelFits(300, 80, "Sector"), true);
assert.equal(labelFits(30, 80, "Sector"), false, "narrow tiles get no label");
assert.equal(labelFits(300, 10, "Sector"), false, "short tiles get no label");

// ---- evidence rows from a precision card fixture with a null-agreement field ----
const precision = {
  schema: "cg-precision-v2",
  tier1_facets: ["entity_type", "sector", "plastics_centrality", "primary_activities", "geographic_scope"],
  facets: {
    sector: {
      tagged_n: 30, with_evidence_n: 27, reviewed_n: 6,
      agreement: {
        n_pairs: 12, observed: 0.8, prevalence: 0.4,
        statistics: {weighted_kappa: {value: 0.71, ci95: [0.42, 0.9]}, gwet_ac1: {value: 0.74, ci95: [0.5, 0.92]}},
      },
      agreement_reason: null,
      review: {audited_n: 6, agree_n: 5, agree_share: 0.833, ci95: [0.36, 0.99], edit_reasons: {}},
    },
    plastics_centrality: {
      tagged_n: 30, with_evidence_n: 30, reviewed_n: 0,
      agreement: null, agreement_reason: "fewer than 10 double-tagged pairs", review: null,
    },
    entity_type: {tagged_n: 30, with_evidence_n: 0, reviewed_n: 0, agreement: null, agreement_reason: "no double-tagged sample yet", review: null},
    primary_activities: {tagged_n: 30, with_evidence_n: 28, reviewed_n: 2, agreement: null, agreement_reason: "no double-tagged sample yet", review: null},
    geographic_scope: {tagged_n: 30, with_evidence_n: 15, reviewed_n: 1, agreement: null, agreement_reason: "no double-tagged sample yet", review: null},
  },
  cannot_determine_reasons: {no_web_presence: 2, dead_link: 0, insufficient_information: 1},
  denominator_note: "Based on 30 of 2673 roster organisations tagged (1.1%). Tagged groups are not a random sample.",
};
const rows = evidenceRows(precision);
assert.deepEqual(rows.map((r) => r.field), ["entity_type", "sector", "plastics_centrality", "primary_activities", "geographic_scope"]);
const sectorRow = rows.find((r) => r.field === "sector");
assert.equal(sectorRow.evidenceShare, 0.9);
assert.equal(sectorRow.reviewedShare, 0.2);
assert.deepEqual(sectorRow.agreement.statistics.map((s) => s.key), ["weighted_kappa", "gwet_ac1"]);
assert.deepEqual(sectorRow.agreement.statistics[0].interval, [0.42, 0.9]);
assert.equal(sectorRow.agreement.pairs, 12);
assert.equal(sectorRow.review.share, 0.833);
assert.match(agreementLines(sectorRow.agreement)[0], /^Agreement between volunteers \(Cohen's weighted kappa\): 0\.71 \(95% interval 0\.42 to 0\.90\)$/);
const centralityRow = rows.find((r) => r.field === "plastics_centrality");
assert.equal(centralityRow.agreement.statistics.length, 0, "null agreement has no statistics");
assert.deepEqual(agreementLines(centralityRow.agreement), ["fewer than 10 double-tagged pairs"]);
assert.equal(centralityRow.review, null);
assert.equal(centralityRow.reviewedShare, 0);

const emptyRows = evidenceRows({facets: {}, cannot_determine_reasons: {}});
assert.equal(emptyRows.length, 5);
assert.ok(emptyRows.every((r) => r.evidenceShare === null && r.reviewedShare === null && r.tagged === 0));
assert.deepEqual(emptyRows[0].agreement, {reason: "Not yet measured", statistics: [], pairs: null});

// ---- reasons: only counts above zero, never conflict_of_interest ----
assert.deepEqual(reasonRows(precision).map((r) => [r.label, r.count]), [
  ["No web presence", 2], ["Insufficient information", 1],
]);
assert.deepEqual(
  reasonRows({cannot_determine_reasons: {conflict_of_interest: 4, dead_link: 0}}),
  [],
  "a retired reason is never listed, even with a count",
);
assert.deepEqual(reasonRows({}), []);
assert.equal(NO_IMPOSSIBLE_REASONS, "No group has been marked as impossible to tag yet.");

console.log("groups composition runtime checks passed");
