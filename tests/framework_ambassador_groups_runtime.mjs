// CG-6c / AMB-GROUPS-UX pure contract checks. Browser interactions run in the shared mocked-API gate.
import assert from "node:assert/strict";
import {CANNOT_REASONS, GROUP_TAXONOMY, TIER2_TAXONOMY, groupSuggestionPayload, groupTagPayload} from "../framework/src/components/ambassador_groups.js";
import {
  COUNTRY_CODES, LANGUAGE_CODES, US_STATES, languageDefaults, languageName, languageOptions, lookupPickerCode, pickerMatch, placeDefaults, placeOptions,
} from "../framework/src/components/ambassador_groups_pickers.js";
import {GROUP_LABELS, groupLabel} from "../framework/src/components/group_labels.js";

const check = (name, fn) => { fn(); console.log(`ok - ${name}`); };
const GROUP = {group_id: "cg_0123456789abcdef", name: "Coastal Group", country: "US", url: "https://example.org"};
const QUOTE = "We run beach cleanups and plastics education in our community.";
/** Form values as the tag screen reads them: one shared quote and one page, with no optional facet quotes. */
const base = (overrides = {}) => ({
  region: "california", notOrganisation: false, status: "ambassador_tagged", entity_type: "organisation", sector: "ngo_civil_society",
  plastics_centrality: "primary", primary_activities: ["cleanup_removal"], geographic_scope: "local", places: ["US", "US-CA"], website_languages: ["en"],
  page_url: "https://example.org/about", accessed_at: "2026-11-26", quote: QUOTE, facet_quotes: {entity_type: "", sector: "", geographic_scope: ""},
  ...overrides,
});

check("taxonomy includes the owner-added joint power authority and activity choices", () => {
  assert.ok(GROUP_TAXONOMY.sector.includes("joint_power_authority"));
  assert.equal(GROUP_TAXONOMY.primary_activities.length, 13);
  assert.deepEqual(CANNOT_REASONS, ["no_web_presence", "dead_link", "language_barrier", "insufficient_information"]);
});
check("not-stated plastics: incidental or none gives a quote-free plastics row and the quote backs activities only", () => {
  for (const plastics_centrality of ["incidental", "none"]) {
    const result = groupTagPayload({group: GROUP, values: base({plastics_centrality, plastics_not_stated: true}), today: "2026-11-26"});
    assert.equal(result.error, undefined);
    assert.deepEqual(result.payload.evidence, [
      {facet: "plastics_centrality", url: "https://example.org/about", accessed_at: "2026-11-26", not_stated: true},
      {facet: "primary_activities", url: "https://example.org/about", accessed_at: "2026-11-26", quote: QUOTE, not_stated: false},
    ]);
    assert.equal("quote" in result.payload.evidence[0], false, "a not-stated row carries no quote key");
  }
  assert.equal(groupTagPayload({group: GROUP, values: base({plastics_centrality: "incidental", plastics_not_stated: true, quote: ""})}).error, "quote");
});
check("not-stated is ignored unless centrality is incidental or none", () => {
  const result = groupTagPayload({group: GROUP, values: base({plastics_centrality: "substantial", plastics_not_stated: true}), today: "2026-11-26"});
  assert.equal(result.payload.evidence[0].quote, QUOTE);
  assert.equal(result.payload.evidence[0].not_stated, false);
});
check("one shared quote becomes the two required evidence rows with the page and date", () => {
  const result = groupTagPayload({group: GROUP, values: base({primary_activities: ["education_awareness", "cleanup_removal"]}), today: "2026-11-26"});
  assert.equal(result.kind, "group_tag");
  assert.deepEqual(result.payload.primary_activities, ["education_awareness", "cleanup_removal"]);
  assert.deepEqual(result.payload.evidence, [
    {facet: "plastics_centrality", url: "https://example.org/about", accessed_at: "2026-11-26", quote: QUOTE, not_stated: false},
    {facet: "primary_activities", url: "https://example.org/about", accessed_at: "2026-11-26", quote: QUOTE, not_stated: false},
  ]);
  assert.deepEqual(result.payload.places, ["US", "US-CA"]);
  assert.deepEqual(result.payload.website_languages, ["en"]);
});
check("an optional facet quote adds one row for that facet only when filled", () => {
  const result = groupTagPayload({group: GROUP, values: base({facet_quotes: {entity_type: "", sector: "We are a community foundation.", geographic_scope: ""}}), today: "2026-11-26"});
  assert.equal(result.error, undefined);
  assert.deepEqual(result.payload.evidence.map((row) => row.facet), ["sector", "plastics_centrality", "primary_activities"]);
  assert.equal(result.payload.evidence[0].quote, "We are a community foundation.");
  assert.equal(result.payload.evidence[0].url, "https://example.org/about");
});
check("blank optional details add no fields or validation burden", () => {
  const result = groupTagPayload({group: GROUP, values: base({
    legal_form: "", legal_form_note: "", participation_in_science: "", themes: "", constituency: [],
    tier2_evidence: {url: "", accessed_at: "", quote: ""}, affiliation_name: "", affiliation_relation: "", affiliation_evidence: {},
  }), today: "2026-11-26"});
  assert.equal(result.error, undefined);
  assert.equal("legal_form" in result.payload, false);
  assert.equal("stated_affiliations" in result.payload, false);
});
check("the shared quote and page are required and validated", () => {
  assert.equal(groupTagPayload({group: GROUP, values: base({quote: ""})}).error, "quote");
  assert.equal(groupTagPayload({group: GROUP, values: base({quote: Array(26).fill("word").join(" ")})}).error, "quote");
  assert.equal(groupTagPayload({group: GROUP, values: base({page_url: "javascript:alert(1)"})}).error, "page_url");
  assert.equal(groupTagPayload({group: GROUP, values: base({accessed_at: "2026-02-31"})}).error, "accessed_at");
  assert.equal(groupTagPayload({group: GROUP, values: base({facet_quotes: {sector: Array(26).fill("word").join(" ")}})}).error, "quote-sector");
});
check("the quote may not carry markup or an email address", () => {
  assert.equal(groupTagPayload({group: GROUP, values: base({quote: "Write to info@example.org today"})}).error, "email");
  assert.equal(groupTagPayload({group: GROUP, values: base({quote: "<b>bold</b> work"})}).error, "quote");
});
check("place and language codes are validated (five places, ten languages, ISO shapes)", () => {
  assert.equal(groupTagPayload({group: GROUP, values: base({places: ["US", "US-CA", "NO", "BE", "FR", "DE"]})}).error, "places");
  assert.equal(groupTagPayload({group: GROUP, values: base({places: ["US", "US"]})}).error, "places");
  assert.equal(groupTagPayload({group: GROUP, values: base({website_languages: ["EN"]})}).error, "website_languages");
  assert.equal(groupTagPayload({group: GROUP, values: base({website_languages: []})}).payload.website_languages, undefined);
});
check("tier 2 fields and repeated stated affiliations carry source, date and short quote", () => {
  const result = groupTagPayload({group: GROUP, values: base({
    legal_form: "registered_nonprofit", legal_form_note: "Registered charity", participation_in_science: "collaborative",
    primary_activities: ["research_monitoring"],
    themes: "marine litter; plastic policy", constituency: ["coastal_fishing"],
    tier2_evidence: {url: "https://example.org/about", accessed_at: "2026-11-26", quote: "We are a registered charity conducting collaborative coastal monitoring."},
    affiliations: [
      {target_name: "Harbour Alliance", relation: "member_of", evidence: {url: "https://example.org/network", accessed_at: "2026-11-26", quote: "We are members of Harbour Alliance."}},
      {target_name: "Coastal Parent Body", relation: "parent_of", evidence: {url: "https://example.org/about", accessed_at: "2026-11-26", quote: "We are a chapter of Coastal Parent Body."}},
    ],
  }), today: "2026-11-26"});
  assert.equal(result.error, undefined);
  assert.deepEqual(result.payload.themes, ["marine litter", "plastic policy"]);
  assert.equal(result.payload.stated_affiliations.length, 2);
  assert.deepEqual(result.payload.stated_affiliations[0], {target_name: "Harbour Alliance", relation: "member_of", evidence: {url: "https://example.org/network", accessed_at: "2026-11-26", quote: "We are members of Harbour Alliance."}});
});
check("science participation requires a research activity and a stated-affiliation taxonomy", () => {
  const values = base({participation_in_science: "collaborative", tier2_evidence: {url: GROUP.url, accessed_at: "2026-11-26", quote: "We collaborate."}});
  assert.equal(groupTagPayload({group: GROUP, values}).error, "participation_in_science");
  assert.ok(TIER2_TAXONOMY.relation.includes("fiscal_sponsor"));
});
check("organisation check must be explicit and activities are limited to five", () => {
  assert.equal(groupTagPayload({group: GROUP, values: {region: "california"}}).error, "organisation_check");
  const values = base({primary_activities: ["other", "other", "other", "other", "other", "other"]});
  assert.equal(groupTagPayload({group: GROUP, values}).error, "primary_activities");
});
check("plastics centrality must be a chosen value other than cannot determine", () => {
  assert.equal(groupTagPayload({group: GROUP, values: base({plastics_centrality: ""})}).error, "plastics_centrality");
  assert.equal(groupTagPayload({group: GROUP, values: base({plastics_centrality: "cannot_determine"})}).error, "plastics_centrality");
});
check("not an organisation is a minimal, untaggable status payload", () => {
  const result = groupTagPayload({group: GROUP, values: {region: "california", notOrganisation: true}});
  assert.deepEqual(result.payload, {group_id: GROUP.group_id, status: "cannot_determine", cannot_determine_reason: "not_an_organisation", not_an_organisation: true});
});
check("cannot determine uses only supported non-COI reasons", () => {
  assert.equal(groupTagPayload({group: GROUP, values: {region: "california", notOrganisation: false, status: "cannot_determine", reason: "language_barrier"}}).payload.cannot_determine_reason, "language_barrier");
  assert.equal(groupTagPayload({group: GROUP, values: {region: "california", notOrganisation: false, status: "cannot_determine", reason: "conflict_of_interest"}}).error, "cannot_determine_reason");
});
check("suggestion body is separate and validates its public URL", () => {
  assert.deepEqual(groupSuggestionPayload({region: "norway", name: "Harbour Collective", url: "https://example.org", country: "no", isOrganisation: true}), {
    region: "norway", stream: "knowledge", kind: "group_suggest", payload: {name: "Harbour Collective", url: "https://example.org", country: "NO"},
  });
  assert.equal(groupSuggestionPayload({region: "norway", name: "Harbour Collective", url: "https://example.org"}).error, "organisation_check");
  assert.equal(groupSuggestionPayload({region: "norway", name: "Harbour Collective", url: "javascript:alert(1)", isOrganisation: true}).error, "url");
});
check("language picker: names come from Intl and chosen names map to codes", () => {
  assert.equal(LANGUAGE_CODES.length, 184);
  assert.equal(languageName("es"), "Spanish");
  assert.equal(languageName("no"), "Norwegian");
  const options = languageOptions();
  assert.equal(lookupPickerCode(options, "Spanish"), "es");
  assert.equal(lookupPickerCode(options, "  spanish "), "es");
  assert.equal(lookupPickerCode(options, "Spanis"), "es", "a unique prefix picks Spanish");
  assert.deepEqual(pickerMatch(options, "Ara"), {code: "", ambiguous: true}, "too many prefix matches pick nothing");
  assert.equal(lookupPickerCode(options, ""), "");
});
check("picker matches: exact, then prefix, then word prefix, then substring; several equal matches pick nothing", () => {
  const languages = languageOptions();
  assert.equal(lookupPickerCode(languages, "Calif"), "", "a language picker does not match California");
  assert.equal(lookupPickerCode(languages, "span"), "es", "a unique prefix picks the single best match");
  assert.equal(lookupPickerCode(languages, "Spanish"), "es");
  assert.equal(lookupPickerCode(languages, "es"), "es", "a typed code still works");
  const places = placeOptions();
  assert.equal(lookupPickerCode(places, "Calif"), "US-CA");
  assert.equal(lookupPickerCode(places, "US-CA"), "US-CA");
  assert.equal(lookupPickerCode(places, "US"), "US", "a typed country code still works");
  assert.equal(lookupPickerCode(places, "Georgia"), "GE", "an exact name beats a prefix");
  assert.equal(lookupPickerCode(places, "rica"), "CR", "a word prefix in the middle of a name");
  assert.deepEqual(pickerMatch(places, "New"), {code: "", ambiguous: true});
  assert.deepEqual(pickerMatch(places, "Zzzz"), {code: "", ambiguous: false});
  assert.equal(lookupPickerCode(places, "  calif  "), "US-CA", "case and spacing are ignored");
});
check("plain labels: every facet value has a label and an unknown value falls back to a readable name", () => {
  assert.equal(groupLabel("primary_activities", "cleanup_removal"), "Clean-ups and litter removal");
  assert.equal(groupLabel("sector", "joint_power_authority"), "Joint powers authority");
  assert.equal(groupLabel("participation_in_science", "co_created"), "Co-created");
  assert.equal(groupLabel("relation", "fiscal_sponsor"), "Fiscal sponsor");
  assert.equal(groupLabel("primary_activities", "brand_new_value"), "Brand new value");
  assert.equal(groupLabel("sector", ""), "");
  for (const facet of ["primary_activities", "entity_type", "sector", "plastics_centrality", "geographic_scope", "legal_form", "participation_in_science", "constituency", "relation"]) {
    const taxonomy = {...GROUP_TAXONOMY, ...TIER2_TAXONOMY};
    for (const value of taxonomy[facet]) assert.ok(GROUP_LABELS[facet][value], `${facet}.${value} has a label`);
  }
});
check("place picker: countries by name, US states as US-XX, with the 50 states and DC", () => {
  assert.equal(COUNTRY_CODES.length, 249);
  assert.equal(US_STATES.length, 51);
  const options = placeOptions();
  assert.equal(lookupPickerCode(options, "Norway"), "NO");
  assert.equal(lookupPickerCode(options, "California (US state)"), "US-CA");
  assert.equal(lookupPickerCode(options, "Georgia"), "GE");
  assert.equal(lookupPickerCode(options, "Georgia (US state)"), "US-GA");
  assert.equal(lookupPickerCode(options, "District of Columbia (US state)"), "US-DC");
  assert.ok(options.every((option) => option.label.length > 2 && !/^[A-Z]{2}(-[A-Z]{2})?$/.test(option.label)), "labels are names, not codes");
});
check("region defaults: languages and places prefill for the region and the roster country", () => {
  assert.deepEqual(languageDefaults("california"), ["en"]);
  assert.deepEqual(languageDefaults("norway"), ["no"]);
  assert.deepEqual(languageDefaults("belgium"), ["nl", "fr"]);
  assert.deepEqual(languageDefaults("elsewhere"), []);
  assert.deepEqual(placeDefaults("california", {country: "US"}), ["US", "US-CA"]);
  assert.deepEqual(placeDefaults("norway", {country: "NO"}), ["NO"]);
  assert.deepEqual(placeDefaults("elsewhere", {country: "XX"}), []);
});
