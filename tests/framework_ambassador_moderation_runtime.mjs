// Runtime checks for the moderation page (AMB-1 slice 2c). The pure helpers live in
// framework/src/components/ambassador_moderation.js; the DOM flow is checked in a browser (mocked API).
import assert from "node:assert/strict";
import {
  INSTITUTION_TYPE_NAMES,
  checkAllowlist,
  checkLead,
  checkSuspend,
  countsText,
  creditName,
  dateText,
  decisionBody,
  estimateMinutes,
  estimateText,
  fieldRows,
  leadBody,
  moderationErrorText,
  needsAllowlist,
  noteProblem,
  confirmedText,
  normaliseItems,
  prefillAllowDomain,
  prefillRegion,
  pendingItems,
  prefillDomain,
  queueUrl,
  safeHref,
  sortQueue,
  suspendBody,
} from "../framework/src/components/ambassador_moderation.js";

let passed = 0;
const check = (name, fn) => {
  fn();
  passed += 1;
  console.log(`ok - ${name}`);
};

const QUEUE = {
  ok: true,
  region: null,
  submissions: [
    {type: "submission", id: 7, region: "norway", stream: "B", kind: "place", payload: {name: "Bergen"}, created_at: 300, submitter: {display_name: "Ada", credit_public: true}, own: false},
    {type: "submission", id: 3, region: "belgium", stream: "C", kind: "fact", payload: {}, created_at: 100, submitter: {display_name: null}, own: true},
  ],
  proposals: [
    {type: "proposal", id: 2, kind: "institution", payload: {name: "Lab B", url: "https://example.org/lab"}, created_at: 100, submitter: {display_name: "Bo"}, own: false},
  ],
};

check("queue ordering: oldest first, submissions before proposals at a tie, then by id", () => {
  const items = normaliseItems(QUEUE);
  assert.deepEqual(items.map((i) => `${i.type}:${i.id}`), ["submission:3", "proposal:2", "submission:7"]);
  assert.deepEqual(sortQueue([{type: "proposal", id: 1, created_at: 5}, {type: "submission", id: 9, created_at: 5}]).map((i) => i.type), ["submission", "proposal"]);
});

check("proposals carry no region; submissions keep theirs", () => {
  const items = normaliseItems(QUEUE);
  assert.equal(items.find((i) => i.type === "proposal").region, null);
  assert.equal(items.find((i) => i.id === 7).region, "norway");
});

check("empty or missing queues normalise to an empty list", () => {
  assert.deepEqual(normaliseItems({}), []);
  assert.deepEqual(normaliseItems(null), []);
});

check("estimate text: about one minute per item, with plural rules", () => {
  assert.equal(estimateMinutes(3), 3);
  assert.equal(estimateMinutes(-2), 0);
  assert.equal(estimateText(0), "Nothing is waiting for review.");
  assert.equal(estimateText(1), "Estimated time: about 1 minute for 1 item.");
  assert.equal(estimateText(4), "Estimated time: about 4 minutes for 4 items.");
});

check("counts text counts only undecided items", () => {
  const items = normaliseItems(QUEUE);
  assert.equal(countsText(items), "3 items waiting: 2 submissions, 1 proposal.");
  items[0].status = "approved";
  assert.equal(pendingItems(items).length, 2);
  assert.equal(countsText(items), "2 items waiting: 1 submission, 1 proposal.");
});

check("queue URL filters by region only when one is chosen", () => {
  assert.equal(queueUrl(""), "/moderation/queue");
  assert.equal(queueUrl("norway"), "/moderation/queue?region=norway");
});

check("decision body carries the note only when it has text", () => {
  assert.deepEqual(decisionBody({type: "submission", id: 7, decision: "approve", note: "  "}), {type: "submission", id: 7, decision: "approve"});
  assert.deepEqual(decisionBody({type: "proposal", id: 2, decision: "reject", note: " Duplicate "}), {type: "proposal", id: 2, decision: "reject", note: "Duplicate"});
});

check("note problems: empty is fine; angle brackets, control characters and length are refused", () => {
  assert.equal(noteProblem(""), null);
  assert.equal(noteProblem("Looks fine."), null);
  assert.match(noteProblem("<b>x</b>"), /no < or > signs/);
  assert.match(noteProblem("a\u0001b"), /plain text/);
  assert.match(noteProblem("x".repeat(1001)), /1000 characters/);
});

check("lead and suspend bodies trim the id and check it is present", () => {
  assert.deepEqual(leadBody({ambassadorId: " abc ", region: "belgium"}), {ambassador_id: "abc", region: "belgium"});
  assert.deepEqual(suspendBody({ambassadorId: "abc "}), {ambassador_id: "abc"});
  assert.deepEqual(checkLead({ambassadorId: "", region: ""}).map((e) => e.field), ["lead-id", "lead-region"]);
  assert.deepEqual(checkLead({ambassadorId: "x", region: "norway"}), []);
  assert.equal(checkSuspend({ambassadorId: "  "}).length, 1);
  assert.deepEqual(checkSuspend({ambassadorId: "x"}), []);
});

check("error text: moderation codes get plain sentences; the 403 text depends on the action", () => {
  assert.equal(moderationErrorText("self_decision", "decide"), "You cannot decide your own submission.");
  assert.equal(moderationErrorText("forbidden", "suspend"), "Only the owner can suspend an account.");
  assert.equal(moderationErrorText("forbidden", "decide"), "This page is for the owner and region leads.");
  assert.equal(moderationErrorText("is_owner", "lead"), "The owner's account cannot be changed here.");
  assert.equal(moderationErrorText("network"), "We could not reach the sign-up service. Check your connection and try again.");
  assert.equal(moderationErrorText("sql_error_xyz"), "Something went wrong on our side. Try again in a few minutes.");
});

check("submitted fields become label and value rows; objects and arrays are text", () => {
  assert.deepEqual(fieldRows({place_name: "Bergen", empty: "", none: null}), [{label: "Place name", value: "Bergen", href: null}]);
  assert.deepEqual(fieldRows({tags: ["a", "b"], meta: {x: 1}}).map((r) => r.value), ["a, b", '{"x":1}']);
  assert.deepEqual(fieldRows("text"), []);
});

check("only http and https values become links", () => {
  assert.equal(safeHref("https://example.org/a"), "https://example.org/a");
  assert.equal(safeHref("http://example.org"), "http://example.org");
  assert.equal(safeHref("javascript:alert(1)"), null);
  assert.equal(safeHref("https://example.org/<x>"), null);
  assert.equal(safeHref(42), null);
});

check("credit name shows only when credit is public", () => {
  assert.equal(creditName({display_name: "Ada", credit_public: true}), "Ada");
  assert.equal(creditName({display_name: "Ada", credit_public: false}), null);
  assert.equal(creditName({display_name: "Ada"}), null);
  assert.equal(creditName({display_name: "  ", credit_public: true}), null);
});

check("prefilled domain is the lowercase host without a leading www.; non-http values give nothing", () => {
  assert.equal(prefillDomain("https://oehha.ca.gov/programmes"), "oehha.ca.gov");
  assert.equal(prefillDomain("https://www.OEHHA.ca.gov/"), "oehha.ca.gov");
  assert.equal(prefillDomain("http://www.example.org"), "example.org");
  assert.equal(prefillDomain("javascript:alert(1)"), "");
  assert.equal(prefillDomain(undefined), "");
  assert.equal(prefillDomain(""), "");
});

check("only institution proposals need the allowlist fields", () => {
  assert.equal(needsAllowlist({type: "proposal", kind: "institution"}), true);
  assert.equal(needsAllowlist({type: "proposal", kind: "region"}), false);
  assert.equal(needsAllowlist({type: "submission", kind: "institution"}), false);
  assert.equal(needsAllowlist(null), false);
  assert.deepEqual(Object.keys(INSTITUTION_TYPE_NAMES), ["education", "government", "nonprofit", "facility"]);
});

check("allowlist checks: region, domain and type are each required before approval", () => {
  assert.deepEqual(checkAllowlist({region: "norway", domain: "niva.no", institution_type: "nonprofit"}), []);
  assert.deepEqual(checkAllowlist({region: "", domain: " ", institution_type: ""}).map((e) => e.field), ["allow-region", "allow-domain", "allow-type"]);
  assert.deepEqual(checkAllowlist({region: "mars", domain: "x.org", institution_type: "company"}).map((e) => e.field), ["allow-region", "allow-type"]);
});

check("an approval carries the trimmed allowlist fields; a rejection carries none", () => {
  const allowlist = {region: "california", domain: " oehha.ca.gov ", institution_type: "government"};
  assert.deepEqual(decisionBody({type: "proposal", id: 2, decision: "approve", allowlist}), {
    type: "proposal", id: 2, decision: "approve", region: "california", domain: "oehha.ca.gov", institution_type: "government",
  });
  assert.deepEqual(decisionBody({type: "proposal", id: 2, decision: "reject", allowlist}), {type: "proposal", id: 2, decision: "reject"});
  assert.deepEqual(decisionBody({type: "submission", id: 7, decision: "approve"}), {type: "submission", id: 7, decision: "approve"});
});

check("allowlist error codes get plain sentences", () => {
  assert.match(moderationErrorText("allowlist_fields_required", "decide"), /choose its region, enter its email domain and choose its type/);
  assert.match(moderationErrorText("free_mail_domain", "decide"), /free-mail provider/);
  assert.match(moderationErrorText("invalid_domain", "decide"), /oehha\.ca\.gov/);
  assert.match(moderationErrorText("invalid_institution_type", "decide"), /four institution types/);
});

check("dates are UTC calendar days; bad timestamps have a fallback", () => {
  assert.equal(dateText(Date.UTC(2026, 10, 25, 12)), "2026-11-25");
  assert.equal(dateText(undefined), "Date not recorded");
});

check("unlisted proposals carry email confirmation and the proposed region and domain", () => {
  const [item] = normaliseItems({
    proposals: [
      {
        id: "p1",
        kind: "institution",
        payload: {name: "OEHHA", domain: "oehha.ca.gov", url: "https://oehha.ca.gov"},
        created_at: 1,
        email_confirmed: true,
        confirmed_domain: "oehha.ca.gov",
        proposed_region: "california",
        proposed_domain: "oehha.ca.gov",
      },
    ],
  });
  assert.equal(item.email_confirmed, true);
  assert.equal(confirmedText(item), "Email confirmed at oehha.ca.gov");
  assert.equal(prefillRegion(item), "california");
  assert.equal(prefillAllowDomain(item), "oehha.ca.gov");
});

check("older proposals without the new fields keep the URL-host prefill; unknown regions prefill nothing", () => {
  const [item] = normaliseItems({proposals: [{id: "p2", kind: "institution", payload: {name: "Lab", url: "https://www.lab.example.org/x"}, created_at: 1}]});
  assert.equal(item.email_confirmed, false);
  assert.equal(confirmedText(item), "");
  assert.equal(prefillRegion(item), "");
  assert.equal(prefillAllowDomain(item), "lab.example.org");
  assert.equal(prefillRegion({type: "proposal", proposed_region: "mars"}), "");
  assert.equal(confirmedText({type: "submission", email_confirmed: true, confirmed_domain: "x.edu"}), "");
});

console.log(`${passed} ambassador moderation runtime checks passed`);
