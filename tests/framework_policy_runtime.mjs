// Runtime checks for the Framework Policy page helpers (EM-18 timeline, EM-17 OPC track).
// The pure helpers live in framework/src/components/policy.js; the timeline check reads the
// committed site/data/dtsc_timeline.json and asserts that dates are shown exactly as stated.
// The OPC checks read the committed site/data/opc_actions.json.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {
  CAVEAT,
  OPC_DISCLAIMER,
  OPC_STRATEGY,
  atlasHref,
  isHttps,
  opcBodyHtml,
  opcFrameHtml,
  opcGroups,
  timelineItems
} from "../framework/src/components/policy.js";

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

// OPC Solutions track (EM-17): the disclaimer and strategy constants match the curated data.
const opc = JSON.parse(readFileSync(fileURLToPath(new URL("../site/data/opc_actions.json", import.meta.url)), "utf8"));
assert.equal(OPC_DISCLAIMER, "The Global Plastic Laws Database is an educational and research resource and should not be regarded as fully comprehensive or completely up to date for legal purposes.");
assert.equal(opc.gpl.disclaimer, OPC_DISCLAIMER);
assert.deepEqual(OPC_STRATEGY, opc.strategy);

// Atlas cell links: a keyword search or a topic filter on the Evidence page.
assert.equal(atlasHref({q: "packaging"}), "./evidence#q=packaging");
assert.equal(atlasHref({q: "a b&c"}), "./evidence#q=a%20b%26c");
assert.equal(atlasHref({topic: "wastewater_and_treatment"}), "./evidence#topic=wastewater_and_treatment");
assert.equal(atlasHref({}), null);
assert.equal(atlasHref(null), null);

// The committed data: three objectives, 22 actions, topic and California links, deadlines verbatim.
{
  const groups = opcGroups(opc);
  assert.deepEqual(groups.map((g) => g.id), ["1", "2", "3"]);
  assert.equal(groups.reduce((n, g) => n + g.actions.length, 0), 22);
  const first = groups[0].actions[0];
  assert.equal(first.code, "2A.1.1");
  assert.equal(first.deadline, "by 2022");
  assert.deepEqual(first.topics, [{slug: "reduction", name: "Reduction", href: "https://www.globalplasticlaws.org/topic/reduction"}]);
  assert.equal(first.californiaHref, "https://www.globalplasticlaws.org/search?search=california");
  assert.equal(first.atlasHref, "./evidence#q=packaging");
  assert.deepEqual(groups[1].actions.find((a) => a.code === "2A.2.1").topics, []);
  assert.equal(groups[1].actions.find((a) => a.code === "2A.2.3").deadline, "adopted or reissued after December 31, 2023");
}

// An unsafe base URL and unknown slugs are not linked.
{
  const [group] = opcGroups({
    gpl: {base_url: "javascript:alert(1)", california_search_url: "http://x.example/", topics: {reduction: "Reduction"}},
    objectives: [{id: 1, name: "One"}],
    actions: [{code: "2A.1.1", objective: 1, group: "g", summary: "s", deadline_as_stated: "by 2022", gpl_topics: ["reduction", "unknown"], atlas: {q: "x"}}]
  });
  assert.deepEqual(group.actions[0].topics, [{slug: "reduction", name: "Reduction", href: null}]);
  assert.equal(group.actions[0].californiaHref, null);
}

// The rendered panel: disclaimer callout, draft badge, cards, deadlines verbatim, escaping.
{
  const frame = opcFrameHtml();
  assert.ok(frame.includes('class="atlas-callout atlas-callout--info opc-disclaimer" role="note"'));
  assert.ok(frame.includes(OPC_DISCLAIMER));
  assert.ok(frame.includes("adopted 23 February 2022"));
  assert.ok(frame.includes('href="https://opc.ca.gov/water-quality/plastics/"'));

  const html = opcBodyHtml(opc);
  assert.equal(opc.mapping_status, "draft");
  assert.ok(html.includes("Draft mapping, not yet reviewed"));
  assert.equal((html.match(/class="opc-card"/g) || []).length, 22);
  assert.equal((html.match(/data-objective-section=/g) || []).length, 3);
  assert.equal((html.match(/California laws/g) || []).length, 22);
  assert.equal((html.match(/No matching topic/g) || []).length, opc.actions.filter((a) => a.gpl_topics.length === 0).length);
  for (const action of opc.actions) assert.ok(html.includes(action.deadline_as_stated), action.code);
  assert.equal(opcBodyHtml({...opc, mapping_status: "owner_reviewed"}).includes("Draft mapping"), false);
  assert.ok(opcBodyHtml({...opc, mapping_status: undefined}).includes("Draft mapping"));

  const evil = opcBodyHtml({...opc, actions: [{...opc.actions[0], summary: "<img src=x onerror=alert(1)>"}]});
  assert.equal(evil.includes("<img"), false);
  assert.ok(evil.includes("&lt;img src=x"));

  assert.ok(opcBodyHtml({}).includes("No early actions are available."));
  assert.ok(opcBodyHtml(null).includes("No early actions are available."));
}

console.log("framework_policy_runtime: all checks passed");
