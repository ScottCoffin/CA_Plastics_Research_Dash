// Runtime checks for the group tag checks (CG-7c). The pure helpers live in
// framework/src/components/ambassador_group_review.js; the DOM flow is checked in a browser (mocked API).
import assert from "node:assert/strict";
import {
  FACET_VALUES,
  MAX_ACTIVITIES,
  REVIEW_REASONS,
  TAG_FACETS,
  facetEvidence,
  facetValueText,
  groupDisplay,
  initialChoices,
  progressText,
  reasonLabel,
  reviewBody,
  reviewErrorText,
  reviewProblem,
  rosterIndex,
  safeHttpUrl,
} from "../framework/src/components/ambassador_group_review.js";

let passed = 0;
const check = (name, fn) => {
  fn();
  passed += 1;
  console.log(`ok - ${name}`);
};

const PAYLOAD = {
  group_id: "g-101",
  status: "ambassador_tagged",
  entity_type: "organisation",
  sector: "ngo_civil_society",
  plastics_centrality: "primary",
  primary_activities: ["advocacy_campaigning", "cleanup_removal"],
  geographic_scope: "local",
  evidence: [
    {facet: "entity_type", url: "https://example.org/about", accessed_at: "2026-11-20", quote: "We are a registered nonprofit.", not_stated: false, note: null},
    {facet: "plastics_centrality", url: "https://example.org/plastics", accessed_at: "2026-11-20", quote: "Our campaign targets single-use plastic.", not_stated: false, note: null},
    {facet: "primary_activities", url: "https://example.org/programmes", accessed_at: "2026-11-20", quote: "We run beach cleanups.", not_stated: false, note: null},
    {facet: "geographic_scope", url: "javascript:alert(1)", accessed_at: "2026-11-20", quote: null, not_stated: true, note: null},
  ],
};

/** A choice set with one edit, for the tests below. */
const edit = (facet, value, reason = "slip") => ({...initialChoices(), [facet]: {outcome: "edit", value, reason}});

check("the five fields are the ones the Worker requires, in order", () => {
  assert.deepEqual(TAG_FACETS, ["entity_type", "sector", "plastics_centrality", "primary_activities", "geographic_scope"]);
});

check("initial choices agree on every field", () => {
  const choices = initialChoices();
  assert.deepEqual(Object.keys(choices), TAG_FACETS);
  for (const facet of TAG_FACETS) assert.deepEqual(choices[facet], {outcome: "agree"});
});

check("an all-agree check sends one agree per field and no edit keys", () => {
  const body = reviewBody("sub-1", initialChoices());
  assert.equal(body.submission_id, "sub-1");
  assert.deepEqual(Object.keys(body.facets), TAG_FACETS);
  for (const facet of TAG_FACETS) assert.deepEqual(body.facets[facet], {outcome: "agree"});
  assert.equal(reviewProblem(PAYLOAD, initialChoices()), null);
});

check("an edit is sent with value and reason_code, and activities keep their order", () => {
  const body = reviewBody("sub-2", edit("primary_activities", ["cleanup_removal", "advocacy_campaigning"], "activity_order"));
  assert.deepEqual(body.facets.primary_activities, {outcome: "edit", value: ["cleanup_removal", "advocacy_campaigning"], reason_code: "activity_order"});
  const copy = ["cleanup_removal"];
  const copied = reviewBody("sub-3", edit("primary_activities", copy)).facets.primary_activities.value;
  assert.notEqual(copied, copy);
});

check("a valid edit passes the problem check", () => {
  assert.equal(reviewProblem(PAYLOAD, edit("sector", "foundation")), null);
  assert.equal(reviewProblem(PAYLOAD, edit("primary_activities", ["cleanup_removal", "advocacy_campaigning"])), null);
});

check("an edit with no reason is refused with a sentence about that field", () => {
  const problem = reviewProblem(PAYLOAD, {...initialChoices(), sector: {outcome: "edit", value: "foundation"}});
  assert.equal(problem, "Choose a reason for the change to the sector.");
});

check("an edit equal to the tagged value is refused (activities compare in order)", () => {
  assert.match(reviewProblem(PAYLOAD, edit("sector", "ngo_civil_society")), /Change the value for the sector/);
  assert.match(reviewProblem(PAYLOAD, edit("primary_activities", ["advocacy_campaigning", "cleanup_removal"])), /Change the main activities/);
  assert.equal(reviewProblem(PAYLOAD, edit("primary_activities", ["cleanup_removal", "advocacy_campaigning"])), null);
});

check("activities must be 1 to 5 distinct values from the list", () => {
  assert.match(reviewProblem(PAYLOAD, edit("primary_activities", [])), /Choose 1 to 5 main activities/);
  const six = ["legal_action", "funding_grantmaking", "other", "education_awareness", "research_monitoring", "policy_governance"];
  assert.equal(MAX_ACTIVITIES, 5);
  assert.match(reviewProblem(PAYLOAD, edit("primary_activities", six)), /Choose 1 to 5 main activities/);
  assert.match(reviewProblem(PAYLOAD, edit("primary_activities", ["legal_action", "legal_action"])), /once/);
  assert.match(reviewProblem(PAYLOAD, edit("primary_activities", ["not_a_value"])), /once/);
});

check("plastics centrality may not be cannot_determine", () => {
  assert.equal(reviewProblem(PAYLOAD, edit("plastics_centrality", "cannot_determine")), "Plastics cannot be marked as cannot determine here. Choose another value.");
  assert.equal(reviewProblem(PAYLOAD, edit("plastics_centrality", "substantial")), null);
});

check("a value outside the vocabulary or a missing value is refused", () => {
  assert.equal(reviewProblem(PAYLOAD, edit("geographic_scope", "continental")), "Choose a value for the geographic scope.");
  assert.equal(reviewProblem(PAYLOAD, {...initialChoices(), entity_type: {outcome: "edit", value: null, reason: "slip"}}), "Choose a value for the organisation type.");
});

check("the reason must be one of the reason codes", () => {
  assert.match(reviewProblem(PAYLOAD, edit("sector", "foundation", "made_up")), /Choose a reason/);
});

check("facet evidence: quote, not stated, and each field's own entry", () => {
  assert.deepEqual(facetEvidence(PAYLOAD, "entity_type"), {quote: "We are a registered nonprofit.", notStated: false, url: "https://example.org/about", accessedAt: "2026-11-20"});
  assert.equal(facetEvidence(PAYLOAD, "geographic_scope").notStated, true);
  assert.equal(facetEvidence(PAYLOAD, "geographic_scope").url, null);
  assert.equal(facetEvidence(PAYLOAD, "primary_activities").quote, "We run beach cleanups.");
  assert.equal(facetEvidence({evidence: [PAYLOAD.evidence[1]]}, "primary_activities"), null);
  assert.equal(facetEvidence(PAYLOAD, "sector"), null);
  assert.equal(facetEvidence({}, "sector"), null);
});

check("links are built only for http and https", () => {
  assert.equal(safeHttpUrl("https://example.org/x"), "https://example.org/x");
  assert.equal(safeHttpUrl(" http://example.org "), "http://example.org");
  assert.equal(safeHttpUrl("javascript:alert(1)"), null);
  assert.equal(safeHttpUrl("https://example.org/<b>"), null);
  assert.equal(safeHttpUrl(42), null);
});

check("field values read in plain labels; activities mark the main one", () => {
  assert.equal(facetValueText("entity_type", "chapter_branch"), "Chapter or branch");
  assert.equal(facetValueText("primary_activities", ["cleanup_removal", "legal_action"]), "Clean-ups and litter removal (main), Legal action");
  assert.equal(facetValueText("sector", undefined), "");
});

check("the roster gives the name and website, and falls back to the group id", () => {
  const index = rosterIndex({records: [{group_id: "g-101", name: "Harbour Watch", url: "https://harbour.example/"}, {group_id: "g-9", url: "ftp://x"}]});
  assert.deepEqual(groupDisplay(index, "g-101"), {name: "Harbour Watch", url: "https://harbour.example/"});
  assert.deepEqual(groupDisplay(index, "g-9"), {name: "g-9", url: null});
  assert.deepEqual(groupDisplay(index, "g-404"), {name: "g-404", url: null});
  assert.equal(rosterIndex(null).size, 0);
  assert.equal(groupDisplay(null, "g-1").name, "g-1");
});

check("progress text and reason labels", () => {
  assert.equal(progressText(2, 7), "Tag 2 of 7");
  assert.equal(reasonLabel("slip"), "A slip (the wrong option was picked)");
  assert.equal(reasonLabel("unknown"), "");
  assert.deepEqual(Object.keys(REVIEW_REASONS), ["evidence_contradicts", "better_evidence_found", "guide_rule", "activity_order", "slip", "other"]);
});

check("error codes map to plain sentences; unknown codes get the generic text", () => {
  assert.match(reviewErrorText("already_reviewed"), /already checked/);
  assert.match(reviewErrorText("rate_limited"), /too many checks/);
  assert.match(reviewErrorText("self_review"), /tagged yourself/);
  assert.match(reviewErrorText("not_selected"), /Moving on/);
  assert.match(reviewErrorText("invalid_review"), /not valid/);
  assert.ok(reviewErrorText("something_new").length > 0);
  assert.ok(!/[A-Z]{2,}-\d|tier|payload|facet/i.test(reviewErrorText("invalid_review")));
});

check("vocabulary lists are present for every field that has a picker", () => {
  assert.equal(FACET_VALUES.plastics_centrality.length, 5);
  assert.equal(FACET_VALUES.primary_activities.length, 13);
});

console.log(`${passed} checks passed`);
