// Runtime check for the community groups coverage and map (CG-12 part 1): framework/src/components/groups_coverage.js.
// Pure helpers and string builders only, on the real data files: no network, no DOM. Run by
// tests/test_groups_coverage.py.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";
import {
  NO_WEEKLY_TEXT,
  REGION_LIMIT,
  SMALL_CELL,
  STATUS_ORDER,
  activityRows,
  californiaGroups,
  countryAnchor,
  countryAnchors,
  countryRows,
  coverageMarkup,
  plural,
  regionView,
  toggleLabel,
  isSmallCell,
  legendSizes,
  niceCount,
  regionRows,
  shareBand,
  sizeRadius,
  stackSegments,
  statusCounts,
  tagShare,
  weeklyPoints,
  breakdownText,
} from "../framework/src/components/groups_coverage.js";
import {frameXY} from "../framework/src/components/world_map.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const readJson = (rel) => JSON.parse(readFileSync(join(ROOT, rel), "utf8"));
const world = readJson("site/assets/world/world.json");
const coverage = readJson("site/data/global/groups/coverage.json");
const groups = readJson("site/data/global/groups/groups.json");

let passed = 0;
const check = (name, fn) => {
  fn();
  passed += 1;
  console.log(`ok - ${name}`);
};

check("anchor of a two-part path picks the larger part", () => {
  // A small square at the origin and a larger square further right: the larger one's centre wins.
  const d = "M0,0L2,0L2,2L0,2ZM100,100L110,100L110,130L100,130Z";
  assert.deepEqual(countryAnchor(d), [105, 115]);
});

check("anchor of a single polygon is its bounding-box centre; empty path gives null", () => {
  assert.deepEqual(countryAnchor("M10,20L30,20L30,60L10,60Z"), [20, 40]);
  assert.equal(countryAnchor(""), null);
  assert.equal(countryAnchor(undefined), null);
});

check("France is placed on the mainland, not on French Guiana", () => {
  const fr = world.countries.find((c) => c.iso_a2 === "FR");
  assert.ok(fr, "France is in world.json");
  const [x, y] = countryAnchor(fr.d);
  const [ex, ey] = frameXY(2.5, 46.5);
  assert.ok(Math.abs(x - ex) < 60 && Math.abs(y - ey) < 60, `France anchor ${x},${y} near Europe ${ex},${ey}`);
});

check("countryAnchors uses world.small for countries without a path", () => {
  const anchors = countryAnchors({countries: [], small: [{iso: "AD", x: 504, y: 122.9}]});
  assert.deepEqual(anchors.get("AD"), [504, 122.9]);
});

check("status counts are zero-filled and segments follow the status order", () => {
  assert.deepEqual(Object.keys(statusCounts({})), STATUS_ORDER);
  assert.equal(statusCounts({reviewed: 3}).reviewed, 3);
  const segs = stackSegments(statusCounts({unlabelled: 2, assigned: 3}), 10);
  assert.deepEqual(segs.map((s) => s.status), STATUS_ORDER);
  assert.equal(segs[0].from, 0);
  assert.equal(segs[0].to, 0.2);
  assert.equal(segs[1].from, 0.2);
  assert.equal(segs[1].to, 0.5);
});

check("regions sort by size, unknown region labelled in plain words", () => {
  const rows = regionRows({by_region: {Small: {roster: 2}, Big: {roster: 9}, region_unknown: {roster: 5}}});
  assert.deepEqual(rows.map((r) => r.label), ["Big", "Small", "Region not recorded"]);
});

check("real coverage: every region row adds up to its roster", () => {
  for (const row of regionRows(coverage)) {
    const sum = Object.values(row.counts).reduce((a, b) => a + b, 0);
    assert.equal(sum, row.roster, row.label);
  }
});

check("size scale: area proportional to the count, largest gets the maximum radius", () => {
  assert.equal(sizeRadius(0, 100), 0);
  const full = sizeRadius(100, 100, 18);
  assert.equal(full, 18);
  const quarter = sizeRadius(25, 100, 18);
  assert.ok(Math.abs(quarter - 9) < 1e-9, "a quarter of the count has half the radius");
});

check("nice reference sizes round down to 1, 2 or 5 times a power of ten", () => {
  assert.equal(niceCount(2673), 2000);
  assert.equal(niceCount(0.5), 0);
  assert.equal(niceCount(7), 5);
  assert.deepEqual(legendSizes(2673), [2000, 500, 100]);
  assert.deepEqual(legendSizes(0), []);
});

check("small-cell flag: below the threshold of 5 only", () => {
  assert.equal(SMALL_CELL, 5);
  assert.equal(isSmallCell(4), true);
  assert.equal(isSmallCell(5), false);
  assert.equal(isSmallCell(0), true);
});

check("share and colour band: none tagged is band 0, quarters after that", () => {
  assert.equal(tagShare(0, 0), 0);
  assert.equal(tagShare(1, 4), 0.25);
  assert.deepEqual([0, 0.1, 0.25, 0.5, 0.75, 1].map(shareBand), [0, 1, 2, 3, 4, 4]);
});

check("weekly points: empty list gives no points; the empty sentence is shown", () => {
  assert.deepEqual(weeklyPoints(undefined), []);
  assert.deepEqual(weeklyPoints([]), []);
  assert.equal(NO_WEEKLY_TEXT, "Tagging has not started yet.");
  const markup = coverageMarkup({coverage: {...coverage, weekly_tagged: []}, groups, world});
  assert.ok(markup.includes(NO_WEEKLY_TEXT));
});

check("weekly points: cumulative rows are read and listed", () => {
  const points = weeklyPoints([{week: "2026-11-02", cumulative: 3}, {week: "", cumulative: 9}]);
  assert.deepEqual(points, [{week: "2026-11-02", cumulative: 3}]);
});

check("country rows: every country is listed, with its anchor when one exists", () => {
  const rows = countryRows(coverage, world);
  assert.equal(rows.length, Object.keys(coverage.by_country).length);
  assert.ok(rows.every((r) => r.roster >= 0));
});

check("California: only tagged groups with US-CA count; activities are counted once per group", () => {
  const sample = [
    {status: "reviewed", places: ["US-CA"], primary_activities: ["recycling", "recycling", "policy"]},
    {status: "unlabelled", places: ["US-CA"], primary_activities: ["recycling"]},
    {status: "ambassador_tagged", places: ["US-TX"], primary_activities: ["policy"]},
  ];
  assert.equal(californiaGroups(sample).length, 1);
  assert.deepEqual(activityRows(californiaGroups(sample)).map((r) => [r.label, r.n]), [["Policy", 1], ["Recycling", 1]]);
  assert.equal(californiaGroups(groups.groups).length, 0, "no California group is tagged yet");
});

check("markup: the progress, map and California blocks are present; the table holds every country", () => {
  const markup = coverageMarkup({coverage, groups, world});
  assert.ok(markup.includes("Progress by region"));
  assert.ok(markup.includes("Where the groups are"));
  assert.ok(markup.includes("No California groups are tagged yet."));
  assert.ok(markup.includes("Show as a table"));
  assert.ok(markup.includes(coverage.denominator_note.split(".")[0]));
  assert.ok(markup.includes('role="img"'));
});

check("scoped panels can show coverage progress without a second coverage map", () => {
  const markup = coverageMarkup({coverage, groups, world, showMap: false});
  assert.ok(markup.includes("Progress by region"));
  assert.ok(!markup.includes("Where the groups are"));
  assert.ok(!markup.includes('class="gm-map"'));
});

check("plural: the noun is singular only for exactly one", () => {
  assert.equal(plural(1, "group"), "1 group");
  assert.equal(plural(0, "group"), "0 groups");
  assert.equal(plural(706, "group"), "706 groups");
  assert.equal(plural(1234, "group"), "1,234 groups");
  assert.equal(plural(1, "country", "countries"), "1 country");
  assert.equal(plural(2, "country", "countries"), "2 countries");
});

check("regions: the unknown-region bucket is last even when it is the largest", () => {
  const rows = regionRows({by_region: {region_unknown: {roster: 900}, A: {roster: 3}, B: {roster: 5}}});
  assert.deepEqual(rows.map((r) => r.label), ["B", "A", "Region not recorded"]);
});

check("region view: the first 12 rows are shown, the rest are behind the toggle", () => {
  const rows = Array.from({length: 14}, (_, i) => ({region: `R${i}`, label: `R${i}`, roster: 14 - i}));
  const view = regionView(rows);
  assert.equal(REGION_LIMIT, 12);
  assert.equal(view.shown.length, 12);
  assert.deepEqual(view.hidden.map((r) => r.label), ["R12", "R13"]);
  assert.equal(view.regionCount, 14);
  assert.deepEqual(regionView(rows.slice(0, 12)).hidden, []);
});

check("region view: the unknown bucket is not counted as a region", () => {
  const rows = [...Array.from({length: 3}, (_, i) => ({region: `R${i}`, label: `R${i}`, roster: 1})),
    {region: "region_unknown", label: "Region not recorded", roster: 9}];
  assert.equal(regionView(rows).regionCount, 3);
});

check("toggle label: the count of regions, and the reverse label when expanded", () => {
  assert.equal(toggleLabel(false, 22), "Show all 22 regions");
  assert.equal(toggleLabel(false, 1), "Show all 1 region");
  assert.equal(toggleLabel(true, 22), "Show fewer regions");
});

check("real coverage: 12 regions shown, the toggle offers all 22, the unknown bucket is last", () => {
  const rows = regionRows(coverage);
  const view = regionView(rows);
  assert.equal(view.shown.length, 12);
  assert.equal(view.regionCount, 22);
  assert.equal(view.hidden.at(-1).label, "Region not recorded");
  const markup = coverageMarkup({coverage, groups, world});
  assert.ok(markup.includes("Show all 22 regions"));
  assert.ok(markup.includes('aria-controls="gc-regions"'));
  assert.equal((markup.match(/class="gc-row gc-extra" hidden/g) || []).length, view.hidden.length);
});

check("region rows: one compact row with the count and the full breakdown in the bar tooltip", () => {
  const markup = coverageMarkup({coverage, groups, world});
  assert.ok(/\d+ groups · \d+ tagged/.test(markup));
  assert.ok(markup.includes("Not yet tagged: "));
  assert.ok(!/1 groups/.test(markup), "no plural mistake for one");
  assert.ok(markup.includes("Groups by region and status"), "region table");
});

check("breakdown text lists every status", () => {
  const text = breakdownText({unlabelled: 2, assigned: 0, ambassador_tagged: 0, reviewed: 0, group_confirmed: 0, cannot_determine: 0});
  assert.equal(text.split("; ").length, 6);
  assert.ok(text.startsWith("Not yet tagged: 2;"));
});

console.log(`${passed} groups coverage runtime checks passed`);
