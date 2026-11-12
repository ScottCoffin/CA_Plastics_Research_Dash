// Runtime checks for the Framework Policy page helpers (EM-18, UI part).
// The pure helpers live in framework/src/components/policy.js; the timeline check reads the
// committed site/data/dtsc_timeline.json and asserts that dates are shown exactly as stated.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {CAVEAT, isHttps, timelineItems} from "../framework/src/components/policy.js";

const data = JSON.parse(readFileSync(fileURLToPath(new URL("../site/data/dtsc_timeline.json", import.meta.url)), "utf8"));

// The hardcoded caveat is the spec sentence.
assert.equal(CAVEAT, "Listing does not by itself create requirements; Priority Product designation is a separate rulemaking.");
assert.equal(data.caveat, CAVEAT);

// https-only links.
assert.equal(isHttps("https://dtsc.ca.gov/x"), true);
assert.equal(isHttps("http://dtsc.ca.gov/x"), false);
assert.equal(isHttps("javascript:alert(1)"), false);
assert.equal(isHttps(null), false);
assert.equal(isHttps(undefined), false);

// Newest-first ordering, including month-only dates, and malformed entries dropped.
{
  const items = timelineItems({
    entries: [
      {id: "a", date_as_stated: "May 2024", date_iso: "2024-05", event: "e", source_label: "s", source_url: null, kind: "work_plan"},
      {id: "b", date_as_stated: "2 June 2024", date_iso: "2024-06-02", event: "e", source_label: "s", source_url: "https://x.example/", kind: "workshop"},
      {id: "c", date_as_stated: "June 2024", date_iso: "2024-06", event: "e", source_label: "s", source_url: "http://insecure.example/", kind: "proposal"},
      {id: "d", event: "no date", date_iso: "2030-01-01"},
      null
    ]
  });
  assert.deepEqual(items.map((i) => i.id), ["b", "c", "a"]);
  assert.equal(items[1].sourceUrl, null);
  assert.equal(items[0].sourceUrl, "https://x.example/");
  assert.equal(items[0].kindLabel, "Workshop");
  assert.deepEqual(timelineItems(null), []);
  assert.deepEqual(timelineItems({}), []);
}

// The committed file: dates verbatim, newest-first, every URL https or null.
{
  const items = timelineItems(data);
  assert.equal(items.length, data.entries.length);
  assert.deepEqual(items.map((i) => i.dateAsStated), data.entries.map((e) => e.date_as_stated));
  assert.equal(items[0].dateAsStated, "1 October 2026");
  const keys = items.map((i) => (/^\d{4}-\d{2}-\d{2}$/.test(i.dateIso) ? i.dateIso : `${i.dateIso}-01`));
  assert.deepEqual(keys, [...keys].sort().reverse());
  for (const item of items) {
    assert.ok(item.sourceUrl === null || item.sourceUrl.startsWith("https://"), item.id);
  }
}

console.log("framework_policy_runtime: all checks passed");
