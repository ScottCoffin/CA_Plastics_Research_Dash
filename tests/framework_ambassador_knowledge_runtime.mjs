// Runtime checks for the "Add local knowledge" helpers (ambassador workspace knowledge task). The helpers live in
// framework/src/components/ambassador_knowledge.js; the DOM flow is checked in a browser (mocked API).
import assert from "node:assert/strict";
import {
  KNOWLEDGE_KINDS,
  OFFERED_KNOWLEDGE_KINDS,
  GROUP_KINDS,
  httpsAddress,
  isIsoDate,
  knowledgeBody,
  knowledgeErrorText,
  knowledgeFormFields,
  knowledgeKindLabel,
  mySubmissions,
  statusText,
} from "../framework/src/components/ambassador_knowledge.js";

let passed = 0;
const check = (name, fn) => {
  fn();
  passed += 1;
  console.log(`ok - ${name}`);
};

const REGION = "california";
const body = (kind, fields) => knowledgeBody({region: REGION, kind, fields});
const PERMISSION_NOTE = "The ambassador confirmed permission to list it.";

// The Worker's KINDS for the knowledge stream (worker/src/submissions.ts), minus correction.
const WORKER = {
  community_group: [["name", "url"], ["description", "contact_route", "note"]],
  volunteer_group: [["name", "url"], ["description", "contact_route", "note"]],
  policy: [["name", "url"], ["description", "note"]],
  funder: [["name", "url"], ["description", "note"]],
  dataset: [["name", "url", "licence"], ["description", "contact_route", "note"]],
  research_network: [["name", "url"], ["description", "contact_route", "note"]],
  event: [["name"], ["url", "description", "note"]],
  media: [["name", "url"], ["description", "note"]],
  institution: [["name"], ["url", "description", "note"]],
  researcher: [["name", "url"], ["description", "note"]],
  community_knowledge: [["name", "contact_route"], ["url", "description", "note"]],
};

check("the form offers the eleven knowledge kinds of the Worker, without correction", () => {
  const kinds = KNOWLEDGE_KINDS.map((k) => k.kind);
  assert.equal(kinds.length, Object.keys(WORKER).length);
  assert.deepEqual([...kinds].sort(), Object.keys(WORKER).sort());
  assert.ok(!kinds.includes("correction"));
  assert.ok(!kinds.includes("confirm"));
});
check("new group entries route to the group stream while historical names remain readable", () => {
  assert.deepEqual(GROUP_KINDS, ["community_group", "volunteer_group", "research_network"]);
  assert.equal(OFFERED_KNOWLEDGE_KINDS.length, 8);
  assert.ok(OFFERED_KNOWLEDGE_KINDS.every((item) => !GROUP_KINDS.includes(item.kind)));
  assert.equal(knowledgeKindLabel("community_group"), "Community group or coalition");
  assert.equal(knowledgeKindLabel("research_network"), "Research network or lab");
});

check("each kind mirrors the Worker's required and optional fields and has a plain label", () => {
  for (const item of KNOWLEDGE_KINDS) {
    const [required, optional] = WORKER[item.kind];
    assert.deepEqual(item.required, required, item.kind);
    assert.deepEqual(item.optional, optional, item.kind);
    assert.ok(item.label.length > 0 && !/stream|payload|AMB-1/i.test(item.label), item.label);
    assert.ok(item.group.length > 0, item.kind);
  }
});

check("estimates are 8 minutes for policy, 10 for dataset and 5 for the rest", () => {
  for (const item of KNOWLEDGE_KINDS) {
    const want = item.kind === "policy" ? 8 : item.kind === "dataset" ? 10 : 5;
    assert.equal(item.minutes, want, item.kind);
  }
});

check("knowledgeKindLabel and knowledgeFormFields follow the kind", () => {
  assert.equal(knowledgeKindLabel("policy"), "Local policy, plan or target");
  assert.equal(knowledgeKindLabel("correction"), "");
  assert.deepEqual(knowledgeFormFields("policy"), ["name", "level", "url", "adopted_on", "applies_from", "next_date", "description", "note"]);
  assert.deepEqual(knowledgeFormFields("community_group"), ["name", "url", "area", "description", "contact_route", "note", "permission"]);
  assert.deepEqual(knowledgeFormFields("correction"), []);
});

check("httpsAddress accepts https and refuses the other forms the Worker refuses", () => {
  assert.equal(httpsAddress("https://example.org/a?b=1"), true);
  assert.equal(httpsAddress("http://example.org"), false);
  assert.equal(httpsAddress("https://user:pw@example.org"), false);
  assert.equal(httpsAddress("https://user@example.org"), false);
  assert.equal(httpsAddress("https://example.org/a b"), false);
  assert.equal(httpsAddress("https://example.org/<x>"), false);
  assert.equal(httpsAddress("https://"), false);
  assert.equal(httpsAddress("not a url"), false);
  assert.equal(httpsAddress(`https://example.org/${"a".repeat(500)}`), false, "over 500 characters");
  assert.equal(httpsAddress(42), false);
});

check("isIsoDate accepts real calendar dates only", () => {
  assert.equal(isIsoDate("2026-02-28"), true);
  assert.equal(isIsoDate("2024-02-29"), true);
  assert.equal(isIsoDate("2025-02-29"), false);
  assert.equal(isIsoDate("2020-13-01"), false);
  assert.equal(isIsoDate("2020-1-01"), false);
  assert.equal(isIsoDate("01/02/2020"), false);
});

check("a community group keeps its own fields and drops empty optional ones", () => {
  const result = body("community_group", {name: "  Beach Clean Co  ", url: "https://example.org", description: "", contact_route: "  ", note: "", area: "", permission: true});
  assert.deepEqual(result, {
    region: REGION,
    stream: "knowledge",
    kind: "community_group",
    payload: {name: "Beach Clean Co", url: "https://example.org", note: PERMISSION_NOTE},
  });
  assert.ok(!("description" in result.payload) && !("contact_route" in result.payload));
});

check("an unknown key is never sent", () => {
  const result = body("funder", {name: "Fund", url: "https://example.org", status: "approved", item_id: "x", stream: "confirm", licence: "CC0"});
  assert.deepEqual(Object.keys(result.payload).sort(), ["name", "url"]);
  assert.equal(result.stream, "knowledge");
});

check("each kind's required fields are enforced in order", () => {
  for (const item of KNOWLEDGE_KINDS) {
    const [required] = WORKER[item.kind];
    const full = {name: "A", url: "https://example.org", licence: "CC0", contact_route: "a@example.org", permission: true};
    for (const field of required) {
      const fields = {...full};
      delete fields[field];
      assert.deepEqual(body(item.kind, fields), {error: field}, `${item.kind} without ${field}`);
    }
  }
});

check("a blank required field counts as missing", () => {
  assert.deepEqual(body("funder", {name: "   ", url: "https://example.org"}), {error: "name"});
  assert.deepEqual(body("funder", {name: "F", url: ""}), {error: "url"});
});

check("the https rule applies to every url field", () => {
  for (const bad of ["http://example.org", "https://user:pw@example.org", "https://example.org/a b", "https://<b>"]) {
    assert.deepEqual(body("funder", {name: "F", url: bad}), {error: "url"}, bad);
  }
  assert.deepEqual(body("event", {name: "E", url: "ftp://example.org"}), {error: "url"});
  assert.equal(body("event", {name: "E"}).payload.url, undefined, "event url is optional");
});

check("names, descriptions and contact routes refuse < and > and respect their limits", () => {
  assert.deepEqual(body("funder", {name: "<b>F</b>", url: "https://example.org"}), {error: "name"});
  assert.deepEqual(body("funder", {name: "F", url: "https://example.org", description: "a > b"}), {error: "description"});
  assert.deepEqual(body("funder", {name: "a".repeat(201), url: "https://example.org"}), {error: "name"});
  assert.deepEqual(body("funder", {name: "F", url: "https://example.org", description: "d".repeat(1001)}), {error: "description"});
  assert.deepEqual(body("research_network", {name: "N", url: "https://example.org", contact_route: "c".repeat(301)}), {error: "contact_route"});
});

check("a dataset needs a licence from the list", () => {
  assert.deepEqual(body("dataset", {name: "D", url: "https://example.org"}), {error: "licence"});
  assert.deepEqual(body("dataset", {name: "D", url: "https://example.org", licence: "MIT"}), {error: "licence"});
  const ok = body("dataset", {name: "D", url: "https://example.org", licence: "Other or unknown (we will ask)"});
  assert.equal(ok.payload.licence, "Other or unknown (we will ask)");
  assert.equal(body("dataset", {name: "D", url: "https://example.org", licence: "CC0"}).payload.licence, "CC0");
  assert.equal(body("funder", {name: "F", url: "https://example.org", licence: "CC0"}).payload.licence, undefined);
});

check("a policy folds its level and dates into the note, in order, before the user's note", () => {
  const result = body("policy", {
    name: "Plan",
    url: "https://example.org",
    level: "National",
    adopted_on: "2020-01-02",
    applies_from: "2021-03-04",
    next_date: "2026-12-01",
    note: "Check the annex.",
  });
  assert.equal(
    result.payload.note,
    "Level: National. Adopted on: 2020-01-02. Applies from: 2021-03-04. Next decision date: 2026-12-01. Check the annex.",
  );
  assert.deepEqual(Object.keys(result.payload), ["name", "url", "note"]);
});

check("only the policy dates and level that are given are folded", () => {
  assert.equal(body("policy", {name: "P", url: "https://example.org", level: "Municipal"}).payload.note, "Level: Municipal.");
  assert.equal(body("policy", {name: "P", url: "https://example.org", applies_from: "2021-03-04"}).payload.note, "Applies from: 2021-03-04.");
  assert.equal(body("policy", {name: "P", url: "https://example.org"}).payload.note, undefined);
});

check("a policy refuses an unknown level or an invalid date", () => {
  assert.deepEqual(body("policy", {name: "P", url: "https://example.org", level: "Global"}), {error: "level"});
  assert.deepEqual(body("policy", {name: "P", url: "https://example.org", adopted_on: "2020-02-30"}), {error: "adopted_on"});
  assert.deepEqual(body("policy", {name: "P", url: "https://example.org", next_date: "soon"}), {error: "next_date"});
});

check("a policy url is required, as the Worker requires it", () => {
  assert.deepEqual(body("policy", {name: "P", level: "National"}), {error: "url"});
});

check("a group folds its area into the note before the permission sentence", () => {
  const result = body("volunteer_group", {name: "V", url: "https://example.org", area: "Oslofjord", permission: true, note: "Monthly."});
  assert.equal(result.payload.note, `Area: Oslofjord. ${PERMISSION_NOTE} Monthly.`);
});

check("the permission box is required for groups and knowledge holders, and never for the others", () => {
  assert.deepEqual(body("community_group", {name: "C", url: "https://example.org"}), {error: "permission"});
  assert.deepEqual(body("volunteer_group", {name: "V", url: "https://example.org", permission: false}), {error: "permission"});
  assert.deepEqual(body("community_knowledge", {name: "K", contact_route: "k@example.org"}), {error: "permission"});
  const knowledge = body("community_knowledge", {name: "K", contact_route: "k@example.org", permission: true});
  assert.equal(knowledge.payload.note, PERMISSION_NOTE);
  const funder = body("funder", {name: "F", url: "https://example.org"});
  assert.equal(funder.payload.note, undefined, "no permission sentence for a funder");
});

check("the folded note is capped at 1000 characters", () => {
  const user = "n".repeat(1000);
  assert.deepEqual(body("funder", {name: "F", url: "https://example.org", note: user}).payload.note, user);
  assert.deepEqual(body("funder", {name: "F", url: "https://example.org", note: "n".repeat(1001)}), {error: "note"});
  // The policy sentences push a 990-character note over the cap.
  const over = body("policy", {name: "P", url: "https://example.org", level: "National", note: "n".repeat(990)});
  assert.deepEqual(over, {error: "note"});
  const fits = body("policy", {name: "P", url: "https://example.org", level: "National", note: "n".repeat(970)});
  assert.ok(fits.payload.note.length <= 1000);
});

check("a note with < or > is refused", () => {
  assert.deepEqual(body("funder", {name: "F", url: "https://example.org", note: "see <here>"}), {error: "note"});
});

check("an unknown kind, including correction, is refused", () => {
  assert.deepEqual(body("correction", {item_id: "x", name: "y"}), {error: "kind"});
  assert.deepEqual(body("confirm", {item_id: "x"}), {error: "kind"});
  assert.deepEqual(body("nope", {name: "y"}), {error: "kind"});
});

check("knowledgeErrorText gives one plain sentence for each field and a fallback", () => {
  for (const field of ["kind", "name", "url", "description", "contact_route", "licence", "note", "area", "permission", "level", "adopted_on", "applies_from", "next_date"]) {
    const text = knowledgeErrorText(field);
    assert.ok(text.endsWith("."), field);
    assert.ok(!/stream|payload|AMB-1/i.test(text), field);
  }
  assert.equal(knowledgeErrorText("whatever"), "Check this answer and try again.");
});

check("mySubmissions keeps this region's knowledge rows, newest first, without duplicates", () => {
  const rows = [
    {id: "a", region: REGION, stream: "knowledge", created_at: 100},
    {id: "b", region: REGION, stream: "knowledge", created_at: 300},
    {id: "c", region: "norway", stream: "knowledge", created_at: 400},
    {id: "d", region: REGION, stream: "confirm", created_at: 500},
    {id: "b", region: REGION, stream: "knowledge", created_at: 300},
    {id: "e", region: REGION, stream: "knowledge", created_at: "2026-05-01T00:00:00Z"},
    {id: "g1", region: REGION, stream: "knowledge", kind: "group_tag", created_at: 600},
    {id: "g2", region: REGION, stream: "knowledge", kind: "group_suggest", created_at: 700},
  ];
  assert.deepEqual(mySubmissions(rows, REGION).map((r) => r.id), ["e", "b", "a"]);
  assert.deepEqual(mySubmissions(undefined, REGION), []);
});

check("statusText gives the plain words for each status", () => {
  assert.equal(statusText("pending"), "Waiting for review");
  assert.equal(statusText("approved"), "Approved");
  assert.equal(statusText("rejected"), "Not accepted");
  assert.equal(statusText("other"), "");
});

console.log(`${passed} checks passed`);
