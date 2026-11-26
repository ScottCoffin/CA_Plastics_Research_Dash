// CG-6c pure contract checks. Browser interactions run in the shared mocked-API gate.
import assert from "node:assert/strict";
import {CANNOT_REASONS, GROUP_TAXONOMY, TIER2_TAXONOMY, groupSuggestionPayload, groupTagPayload} from "../framework/src/components/ambassador_groups.js";

const check = (name, fn) => { fn(); console.log(`ok - ${name}`); };
const GROUP = {group_id: "cg_0123456789abcdef", name: "Coastal Group", country: "US", url: "https://example.org", expires_at: Date.now() + 1000, renewals: 0};
const evidence = Object.fromEntries(["entity_type", "sector", "plastics_centrality", "primary_activities", "geographic_scope"].map((facet) => [facet, {url: "https://example.org/about", accessed_at: "2026-11-26", quote: `We work on ${facet.replaceAll("_", " ")} in our community.`}]));

check("taxonomy includes the owner-added joint power authority and activity choices", () => {
  assert.ok(GROUP_TAXONOMY.sector.includes("joint_power_authority"));
  assert.equal(GROUP_TAXONOMY.primary_activities.length, 13);
  assert.deepEqual(CANNOT_REASONS, ["no_web_presence", "dead_link", "language_barrier", "insufficient_information"]);
});
check("tag body carries Tier 1 facets and evidence in chosen activity order", () => {
  const result = groupTagPayload({group: GROUP, values: {
    region: "california", notOrganisation: false, status: "ambassador_tagged", entity_type: "organisation", sector: "joint_power_authority",
    plastics_centrality: "substantial", primary_activities: ["education_awareness", "cleanup_removal"], geographic_scope: "local", places: "us-ca", evidence,
  }, today: "2026-11-26"});
  assert.equal(result.kind, "group_tag");
  assert.deepEqual(result.payload.primary_activities, ["education_awareness", "cleanup_removal"]);
  assert.equal(result.payload.evidence.length, 5);
  assert.equal(result.payload.evidence[0].not_stated, false);
});
check("blank optional details add no fields or validation burden", () => {
  const result = groupTagPayload({group: GROUP, values: {
    region: "california", notOrganisation: false, status: "ambassador_tagged", entity_type: "organisation", sector: "ngo_civil_society",
    plastics_centrality: "primary", primary_activities: ["cleanup_removal"], geographic_scope: "local", evidence,
    legal_form: "", legal_form_note: "", participation_in_science: "", themes: "", constituency: [],
    tier2_evidence: {url: "", accessed_at: "", quote: ""}, affiliation_name: "", affiliation_relation: "", affiliation_evidence: {},
  }, today: "2026-11-26"});
  assert.equal(result.error, undefined);
  assert.equal("legal_form" in result.payload, false);
  assert.equal("stated_affiliations" in result.payload, false);
});
check("Tier 2 fields and repeated stated affiliations carry source, date and short quote", () => {
  const result = groupTagPayload({group: GROUP, values: {
    region: "california", notOrganisation: false, status: "ambassador_tagged", entity_type: "organisation", sector: "ngo_civil_society",
    plastics_centrality: "primary", primary_activities: ["research_monitoring"], geographic_scope: "local", evidence,
    legal_form: "registered_nonprofit", legal_form_note: "Registered charity", participation_in_science: "collaborative",
    themes: "marine litter; plastic policy", constituency: ["coastal_fishing"],
    tier2_evidence: {url: "https://example.org/about", accessed_at: "2026-11-26", quote: "We are a registered charity conducting collaborative coastal monitoring."},
    affiliations: [
      {target_name: "Harbour Alliance", relation: "member_of", evidence: {url: "https://example.org/network", accessed_at: "2026-11-26", quote: "We are members of Harbour Alliance."}},
      {target_name: "Coastal Parent Body", relation: "parent_of", evidence: {url: "https://example.org/about", accessed_at: "2026-11-26", quote: "We are a chapter of Coastal Parent Body."}},
    ],
  }, today: "2026-11-26"});
  assert.equal(result.error, undefined);
  assert.deepEqual(result.payload.themes, ["marine litter", "plastic policy"]);
  assert.equal(result.payload.stated_affiliations.length, 2);
  assert.deepEqual(result.payload.stated_affiliations[0], {target_name: "Harbour Alliance", relation: "member_of", evidence: {url: "https://example.org/network", accessed_at: "2026-11-26", quote: "We are members of Harbour Alliance."}});
});
check("science participation requires a research activity and a stated-affiliation taxonomy", () => {
  const base = {region: "california", notOrganisation: false, status: "ambassador_tagged", entity_type: "organisation", sector: "ngo_civil_society", plastics_centrality: "primary", primary_activities: ["cleanup_removal"], geographic_scope: "local", evidence, participation_in_science: "collaborative", tier2_evidence: {url: GROUP.url, accessed_at: "2026-11-26", quote: "We collaborate."}};
  assert.equal(groupTagPayload({group: GROUP, values: base}).error, "participation_in_science");
  assert.ok(TIER2_TAXONOMY.relation.includes("fiscal_sponsor"));
});
check("organisation check must be explicit and activities are limited to five", () => {
  assert.equal(groupTagPayload({group: GROUP, values: {region: "california"}}).error, "organisation_check");
  const values = {region: "california", notOrganisation: false, status: "ambassador_tagged", entity_type: "organisation", sector: "ngo_civil_society", plastics_centrality: "primary", primary_activities: ["other", "other", "other", "other", "other", "other"], geographic_scope: "local", evidence};
  assert.equal(groupTagPayload({group: GROUP, values}).error, "primary_activities");
});
check("not an organisation is a minimal, untaggable status payload", () => {
  const result = groupTagPayload({group: GROUP, values: {region: "california", notOrganisation: true}});
  assert.deepEqual(result.payload, {group_id: GROUP.group_id, status: "cannot_determine", cannot_determine_reason: "not_an_organisation", not_an_organisation: true});
});
check("cannot determine uses only supported non-COI reasons", () => {
  assert.equal(groupTagPayload({group: GROUP, values: {region: "california", notOrganisation: false, status: "cannot_determine", reason: "language_barrier"}}).payload.cannot_determine_reason, "language_barrier");
  assert.equal(groupTagPayload({group: GROUP, values: {region: "california", notOrganisation: false, status: "cannot_determine", reason: "conflict_of_interest"}}).error, "cannot_determine_reason");
});
check("evidence enforces a valid ISO day and quote length", () => {
  const values = {region: "california", notOrganisation: false, status: "ambassador_tagged", entity_type: "organisation", sector: "ngo_civil_society", plastics_centrality: "primary", primary_activities: ["other"], geographic_scope: "local", evidence};
  const invalidDay = structuredClone(values); invalidDay.evidence.sector.accessed_at = "2026-02-31";
  assert.equal(groupTagPayload({group: GROUP, values: invalidDay}).error, "evidence-sector-date");
  const unstated = structuredClone(values); unstated.evidence.entity_type = {url: GROUP.url, accessed_at: "2026-11-26", not_stated: true};
  assert.equal(groupTagPayload({group: GROUP, values: unstated}).payload.evidence[0].quote, undefined);
  const tooLong = structuredClone(values); tooLong.evidence.entity_type.quote = Array(27).fill("word").join(" ");
  assert.equal(groupTagPayload({group: GROUP, values: tooLong}).error, "evidence-entity_type-quote");
});
check("suggestion body is separate and validates its public URL", () => {
  assert.deepEqual(groupSuggestionPayload({region: "norway", name: "Harbour Collective", url: "https://example.org", country: "no", isOrganisation: true}), {
    region: "norway", stream: "knowledge", kind: "group_suggest", payload: {name: "Harbour Collective", url: "https://example.org", country: "NO"},
  });
  assert.equal(groupSuggestionPayload({region: "norway", name: "Harbour Collective", url: "https://example.org"}).error, "organisation_check");
  assert.equal(groupSuggestionPayload({region: "norway", name: "Harbour Collective", url: "javascript:alert(1)", isOrganisation: true}).error, "url");
});
