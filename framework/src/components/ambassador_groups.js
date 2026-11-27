// Signed-in group tagging. Assignments use short background holds. Two screens share this module:
// mountGroups ("Tag local groups") and mountGroupSuggest ("Suggest a missing group").
import {escapeHtml, globalDataUrl} from "./atlas.js";
import {safeUrl} from "./region_page.js";
import {
  languageDefaults, languageName, languageOptions, pickerMatch, placeDefaults, placeOptions,
} from "./ambassador_groups_pickers.js";
import {groupLabel} from "./group_labels.js";

export const GROUP_TAXONOMY = {
  entity_type: ["organisation", "network_coalition", "programme_project", "campaign", "informal_group", "chapter_branch", "other"],
  sector: ["ngo_civil_society", "community_informal", "foundation", "academia_research", "private_sector", "government", "joint_power_authority", "igo", "other"],
  plastics_centrality: ["primary", "substantial", "incidental", "none", "cannot_determine"],
  primary_activities: ["advocacy_campaigning", "policy_governance", "research_monitoring", "education_awareness", "cleanup_removal", "waste_management_recycling", "reuse_refill_alternatives", "business_innovation", "community_organising_justice", "coalition_building_capacity", "funding_grantmaking", "legal_action", "other"],
  geographic_scope: ["local", "subnational", "national", "regional_multi_country", "global"],
};
export const TIER2_TAXONOMY = {
  legal_form: ["registered_nonprofit", "unincorporated", "company", "public_body", "university", "unknown"],
  participation_in_science: ["contractual", "contributory", "collaborative", "co_created", "collegial", "not_applicable"],
  constituency: ["frontline_fenceline", "indigenous", "youth", "waste_workers", "coastal_fishing", "faith", "consumers", "industry", "other"],
  relation: ["member_of", "partner_of", "fiscal_sponsor", "parent_of", "funded_by"],
};
export const TAG_FACETS = ["entity_type", "sector", "plastics_centrality", "primary_activities", "geographic_scope"];
export const CANNOT_REASONS = ["no_web_presence", "dead_link", "language_barrier", "insufficient_information"];
export const GROUP_EVIDENCE_FACETS = [...TAG_FACETS];
/** Facets the Worker requires evidence for. The shared quote backs both. */
const TIER1_EVIDENCE = ["plastics_centrality", "primary_activities"];
/** Centrality values whose page may not mention plastics at all; the form offers "not stated" only for these. */
const NOT_STATED_CENTRALITY = ["incidental", "none"];
/** Facets that may carry their own optional quote, shown behind an "Add a quote for this" disclosure. */
const FACET_QUOTE_FACETS = ["entity_type", "sector", "geographic_scope"];
const MAX_PLACES = 5;
const MAX_LANGUAGES = 10;
const LABELS = {
  entity_type: "Organisation type", sector: "Sector", plastics_centrality: "How central are plastics?",
  primary_activities: "Main activities (choose 1 to 5)", geographic_scope: "Geographic scope",
};
/** Plain names for the fields and checks that an error message points at. */
const ERROR_FIELDS = {
  group: "this group", organisation_check: "the organisation check", ...LABELS, places: "Places", website_languages: "Website languages",
  legal_form: "Legal form", legal_form_note: "Legal form note", participation_in_science: "Participation in science", themes: "Themes",
  constituency: "Constituency", tier2_evidence: "the source for the optional details", stated_affiliations: "Stated affiliations",
  cannot_determine_reason: "Reason", page_url: "Page you read", accessed_at: "Date read", quote: "Quote", payload: "answers",
  name: "Group name", name_correction: "Correct the name", url: "Public web address", country: "Country", note: "Note",
  same_as: "the same-organisation question",
};
const esc = (value) => escapeHtml(String(value ?? ""));
/** Today's date on the ambassador's own calendar (not UTC), as YYYY-MM-DD. */
const isoToday = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};
const isIsoDate = (value) => /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
const isWebUrl = (value) => {
  if (typeof value !== "string" || value.length > 500 || /\s|[<>]/.test(value)) return false;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password && !!url.hostname; } catch { return false; }
};
/** A quote is non-empty, at most 25 words and 400 characters, with no markup or control characters. */
const quoteOk = (quote) => quote !== "" && quote.split(/\s+/).length <= 25 && quote.length <= 400 && !/[<>\u0000-\u001f\u007f]/.test(quote);
/** The main plastics quote (the shared evidence quote) is 10 to 50 words and at most 600 characters. */
export const PLASTICS_QUOTE_MIN_WORDS = 10;
export const PLASTICS_QUOTE_MAX_WORDS = 50;
export const PLASTICS_QUOTE_MAX_CHARS = 600;
/** Whitespace-separated words in a text; 0 for blank text. */
export function wordCount(text) {
  const trimmed = String(text ?? "").trim();
  return trimmed === "" ? 0 : trimmed.split(/\s+/).length;
}
const plasticsQuoteOk = (quote) => {
  const words = wordCount(quote);
  return words >= PLASTICS_QUOTE_MIN_WORDS && words <= PLASTICS_QUOTE_MAX_WORDS && quote.length <= PLASTICS_QUOTE_MAX_CHARS && !/[<>\u0000-\u001f\u007f]/.test(quote);
};
/** Live counter text for the plastics quote: the visible text and the state used to decide when to announce. */
export function plasticsQuoteStatus(text) {
  const words = wordCount(text);
  const label = `${words} ${words === 1 ? "word" : "words"}`;
  if (words === 0) return {state: "short", text: label};
  if (words < PLASTICS_QUOTE_MIN_WORDS) return {state: "short", text: `${label} · add at least ${PLASTICS_QUOTE_MIN_WORDS - words} more`};
  if (words > PLASTICS_QUOTE_MAX_WORDS) return {state: "long", text: `${label} · remove ${words - PLASTICS_QUOTE_MAX_WORDS}`};
  return {state: "ok", text: label};
}
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;
const GROUP_ID_RE = /^cg_[0-9a-f]{16}$/;

// Roster quality checks (AMB-ROSTER-QC). Answers to "same organisation?" questions go to the Worker as same_as.
export const SAME_AS_ANSWERS = ["same", "different", "unsure"];
const SAME_AS_LABELS = {same: "Same", different: "Different", unsure: "Not sure"};
const MAX_DUPLICATE_QUESTIONS = 3;
const DUPLICATE_HINTS = {
  same_domain: "We think these may be duplicates because they share a website.",
  similar_name: "We think these may be duplicates because their names are very similar.",
};
const SUSPECT_NAME_HINTS = {
  double_question_mark: "The name has a double question mark",
  broken_character: "The name has a broken character",
  backtick: "The name uses a backtick instead of an apostrophe",
  web_address: "The name looks like a web address",
  domain_only: "The name looks like a website domain",
  short_one_case: "The name is very short",
};

// Picker data is computed once. Names are English Intl names; codes are what the Worker stores.
const LANGUAGE_OPTIONS = languageOptions();
const PLACE_OPTIONS = placeOptions();
const PLACE_LABELS = new Map(PLACE_OPTIONS.map((option) => [option.code, option.label]));
const COUNTRY_OPTIONS = PLACE_OPTIONS.filter((option) => !option.code.includes("-"));
const PICKERS = {
  places: {
    label: "Places (optional, up to five)", placeholder: "Type a country or US state", noun: "a place", max: MAX_PLACES,
    options: PLACE_OPTIONS, nameOf: (code) => PLACE_LABELS.get(code) || code, full: "You can add up to five places.",
  },
  website_languages: {
    label: "Website languages (optional, up to ten)", placeholder: "Type a language, for example Spanish", noun: "a language", max: MAX_LANGUAGES,
    options: LANGUAGE_OPTIONS, nameOf: languageName, full: "You can add up to ten languages.",
  },
};

/**
 * Duplicate questions for one group: up to three roster pairs that include it, with the other group's name and
 * safe website from rosterById (a Map of group_id to {name, url}). A pair whose other group is not listed is skipped.
 */
export function duplicateQuestions(groupId, qc, rosterById) {
  const pairs = Array.isArray(qc?.pairs) ? qc.pairs : [];
  const questions = [];
  const seen = new Set();
  for (const pair of pairs) {
    if (questions.length >= MAX_DUPLICATE_QUESTIONS) break;
    const other = pair?.a === groupId ? pair.b : pair?.b === groupId ? pair.a : null;
    if (typeof other !== "string" || other === groupId || seen.has(other)) continue;
    const record = rosterById?.get?.(other);
    if (!record?.name) continue;
    seen.add(other);
    questions.push({group_id: other, name: record.name, url: safeUrl(record.url), reason: pair.reason});
  }
  return questions;
}

/** Plain hint for a duplicate question, or "" for an unknown reason. */
export const duplicateHint = (reason) => DUPLICATE_HINTS[reason] || "";

/** True when the roster QC file flags this group's name. */
export function isSuspectName(groupId, qc) {
  return (Array.isArray(qc?.suspect_names) ? qc.suspect_names : []).some((item) => item?.group_id === groupId);
}

/** One plain sentence (or several) built from the known reasons for a suspect name; "" when none is known. */
export function suspectHint(groupId, qc) {
  const entry = (Array.isArray(qc?.suspect_names) ? qc.suspect_names : []).find((item) => item?.group_id === groupId);
  const sentences = [...new Set(Array.isArray(entry?.reasons) ? entry.reasons : [])]
    .filter((code) => Object.hasOwn(SUSPECT_NAME_HINTS, code)).map((code) => `${SUSPECT_NAME_HINTS[code]}.`);
  return sentences.join(" ");
}

/** Official register search pages by roster country. Links only: no register data is loaded. */
const REGISTERS = new Map([
  ["US", {label: "IRS Tax Exempt Organization Search", url: "https://apps.irs.gov/app/eos/"}],
  ["GB", {label: "Charity Commission register", url: "https://register-of-charities.charitycommission.gov.uk/charity-search"}],
  ["CA", {label: "Canada Revenue Agency charities listing", url: "https://apps.cra-arc.gc.ca/ebci/hacc/srch/pub/dsplyBscSrch?request_locale=en"}],
  ["AU", {label: "ACNC Charity Register", url: "https://www.acnc.gov.au/charity/charities"}],
]);

/** Register search links for a country code: [] for countries without one. */
export function registerLinks(country) {
  const entry = REGISTERS.get(String(country ?? "").toUpperCase());
  return entry ? [entry] : [];
}

/** The Wikidata suggestion for one group (normalised), or null. Only well-formed entries are used. */
export function suggestionFor(groupId, suggestions) {
  const groups = suggestions?.groups;
  if (!groups || typeof groups !== "object" || !Object.hasOwn(groups, groupId)) return null;
  const entry = groups[groupId];
  if (!entry || typeof entry !== "object" || !/^Q\d+$/.test(String(entry.qid ?? ""))) return null;
  const year = Number(entry.inception_year);
  return {
    qid: entry.qid,
    match: entry.match === "label" ? "label" : "website",
    website: safeUrl(entry.website),
    inceptionYear: Number.isInteger(year) && year > 0 ? year : null,
    typeLabels: (Array.isArray(entry.type_labels) ? entry.type_labels : []).filter((label) => typeof label === "string" && label.trim()).map((label) => label.trim()).slice(0, 10),
  };
}

/** Formats a nine-digit EIN as NN-NNNNNNN. Any other input is returned as text, unchanged. */
export function formatEin(ein) {
  const digits = String(ein ?? "");
  return /^\d{9}$/.test(digits) ? `${digits.slice(0, 2)}-${digits.slice(2)}` : digits;
}

/** The IRS register entry for one group (normalised), or null. Needs a nine-digit EIN and a registered name. */
export function registerSuggestionFor(groupId, data) {
  const groups = data?.groups;
  if (!groups || typeof groups !== "object" || !Object.hasOwn(groups, groupId)) return null;
  const entry = groups[groupId];
  if (!entry || typeof entry !== "object") return null;
  const ein = String(entry.ein ?? "");
  const name = typeof entry.registered_name === "string" ? entry.registered_name.trim() : "";
  if (!/^\d{9}$/.test(ein) || !name) return null;
  const text = (value) => (typeof value === "string" ? value.trim() : "");
  const year = Number(entry.ruling_year);
  const hints = Array.isArray(entry.activity_hints) ? entry.activity_hints.filter((hint) => typeof hint === "string" && hint.trim()).slice(0, 10) : [];
  const sector = text(entry.sector_hint);
  return {
    ein,
    einFormatted: formatEin(ein),
    registeredName: name,
    city: text(entry.city),
    state: text(entry.state),
    rulingYear: Number.isInteger(year) && year > 0 ? year : null,
    sectorLabel: sector ? groupLabel("sector", sector) : "",
    activityLabels: hints.map((hint) => groupLabel("primary_activities", hint.trim())),
  };
}

/**
 * Suggestions box for the tag form: a closed <details> when Wikidata or the IRS register has a suggestion, plus the
 * register row by country. Returns "" when there is none of these. Nothing here fills in a field; the ambassador confirms
 * each value by hand.
 */
export function suggestionHTML(group, suggestions, registerData) {
  const hit = suggestionFor(group?.group_id, suggestions);
  const irs = registerSuggestionFor(group?.group_id, registerData);
  const registers = registerLinks(group?.country);
  const register = registers.length
    ? `<p class="g-register">Look it up in an official register: ${registers.map((r) => `<a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.label)}<span class="sr"> (opens in a new tab)</span></a>`).join("")}</p>`
    : "";
  if (!hit && !irs) return register;
  const newTab = '<span class="sr"> (opens in a new tab)</span>';
  const parts = [];
  if (hit) {
    const items = [
      `<li>Wikidata entry: <a href="${esc(`https://www.wikidata.org/wiki/${hit.qid}`)}" target="_blank" rel="noopener noreferrer">Open the Wikidata entry${newTab}</a></li>`,
      hit.website ? `<li>Official website: <a href="${esc(hit.website)}" target="_blank" rel="noopener noreferrer">Open their official website${newTab}</a></li>` : "",
      hit.inceptionYear ? `<li>Founded ${esc(hit.inceptionYear)}</li>` : "",
      hit.typeLabels.length ? `<li>Listed in Wikidata as: ${esc(hit.typeLabels.join(", "))}</li>` : "",
    ];
    const warning = hit.match === "label" ? `<p class="g-hints-warn">Matched by name only. Check that this is the same organisation.</p>` : "";
    parts.push(`<div class="g-hints-part"><p><strong>From Wikidata</strong></p>${warning}<ul>${items.join("")}</ul></div>`);
  }
  if (irs) {
    const place = [irs.city, irs.state].filter(Boolean).join(", ");
    const hintParts = [irs.sectorLabel, irs.activityLabels.join(", ")].filter(Boolean).join(" · ");
    const items = [
      `<li>Registered as ${esc(irs.registeredName)}${place ? `, ${esc(place)}` : ""}</li>`,
      irs.rulingYear ? `<li>Tax-exempt since ${esc(irs.rulingYear)}</li>` : "",
      `<li>Employer Identification Number <a href="${esc(`https://apps.irs.gov/app/eos/details/?ein=${irs.ein}`)}" target="_blank" rel="noopener noreferrer">${esc(irs.einFormatted)}${newTab}</a></li>`,
      hintParts ? `<li>The register's activity code suggests: ${esc(hintParts)}</li>` : "",
    ];
    parts.push(`<div class="g-hints-part"><p><strong>IRS register</strong></p><ul>${items.join("")}</ul><p class="g-hints-warn">Matched by registered name. Check that this is the same organisation.</p></div>`);
  }
  return `<details class="g-hints"><summary>Suggestions to check</summary>
    <div class="g-hints-body"><p class="hint">These are hints, not tags. Confirm each value on the group's own pages before you use it.</p>
    ${parts.join("")}${register}</div></details>`;
}

/** Roster records keyed by group id, as the duplicate questions read them. */
export function rosterLookup(roster) {
  const index = new Map();
  for (const record of Array.isArray(roster?.records) ? roster.records : []) {
    if (record?.group_id === undefined || record?.group_id === null) continue;
    index.set(String(record.group_id), {name: typeof record.name === "string" ? record.name.trim() : "", url: record.url});
  }
  return index;
}

/** Same-organisation answers: only answered questions, at most three, distinct, never the group itself. */
function sameAsAnswers(group, answers) {
  if (answers === undefined || answers === null) return {list: []};
  if (!Array.isArray(answers) || answers.length > MAX_DUPLICATE_QUESTIONS) return {error: "same_as"};
  const seen = new Set();
  for (const item of answers) {
    const other = item?.group_id;
    if (typeof other !== "string" || !GROUP_ID_RE.test(other) || other === group.group_id || seen.has(other)) return {error: "same_as"};
    if (!SAME_AS_ANSWERS.includes(item.answer)) return {error: "same_as"};
    seen.add(other);
  }
  return {list: answers.map(({group_id, answer}) => ({group_id, answer}))};
}

/** Build a tag payload from form values, or return a field key to focus. */
export function groupTagPayload({group, values, today = isoToday()} = {}) {
  if (!group?.group_id) return {error: "group"};
  if (typeof values.notOrganisation !== "boolean") return {error: "organisation_check"};
  const sameAs = sameAsAnswers(group, values.same_as);
  if (sameAs.error) return {error: sameAs.error};
  const sameAsPart = sameAs.list.length ? {same_as: sameAs.list} : {};
  if (values.notOrganisation) {
    return {region: values.region, stream: "knowledge", kind: "group_tag", payload: {
      group_id: group.group_id, status: "cannot_determine", cannot_determine_reason: "not_an_organisation", not_an_organisation: true,
      ...sameAsPart,
    }};
  }
  // The name field starts at the current name, so a name is sent only when it differs from the current one.
  const currentName = String(group.name || "").trim();
  const correctedName = String(values.name_correction || "").trim();
  const nameChanged = correctedName !== "" && correctedName !== currentName;
  if (nameChanged && (correctedName.length < 2 || correctedName.length > 200 || /[<>\u0000-\u001f\u007f]/.test(correctedName) || EMAIL.test(correctedName))) return {error: "name_correction"};
  const correction = nameChanged ? {name_correction: correctedName} : {};
  if (values.status === "cannot_determine") {
    if (!CANNOT_REASONS.includes(values.reason)) return {error: "cannot_determine_reason"};
    return {region: values.region, stream: "knowledge", kind: "group_tag", payload: {
      group_id: group.group_id, status: "cannot_determine", cannot_determine_reason: values.reason,
      ...correction, ...sameAsPart,
    }};
  }
  const payload = {group_id: group.group_id, status: "ambassador_tagged", ...correction, ...sameAsPart};
  // "Their pages do not mention plastics" applies only to incidental or none; the Worker then wants no quote for that row.
  const plasticsNotStated = values.plastics_not_stated === true && NOT_STATED_CENTRALITY.includes(values.plastics_centrality);
  for (const facet of TAG_FACETS) {
    const value = values[facet];
    if (facet === "primary_activities") {
      if (!Array.isArray(value) || value.length < 1 || value.length > 5 || new Set(value).size !== value.length || value.some((v) => !GROUP_TAXONOMY[facet].includes(v))) return {error: facet};
      payload[facet] = value;
    } else {
      if (!GROUP_TAXONOMY[facet].includes(value)) return {error: facet};
      if (facet === "plastics_centrality" && value === "cannot_determine") return {error: facet};
      payload[facet] = value;
    }
  }
  const places = Array.isArray(values.places) ? values.places.map(String) : [];
  if (places.length > MAX_PLACES || places.some((v) => !/^[A-Z]{2}(?:-[A-Z0-9]{1,3})?$/.test(v)) || new Set(places).size !== places.length) return {error: "places"};
  if (places.length) payload.places = places;
  const languages = Array.isArray(values.website_languages) ? values.website_languages.map(String) : [];
  if (languages.length > MAX_LANGUAGES || languages.some((v) => !/^[a-z]{2}$/.test(v)) || new Set(languages).size !== languages.length) return {error: "website_languages"};
  if (languages.length) payload.website_languages = languages;
  const evidence = [];
  const legalForm = values.legal_form || "";
  const legalNote = String(values.legal_form_note || "").trim();
  const participation = values.participation_in_science || "";
  const themes = String(values.themes || "").split(/[;\n]+/).map((v) => v.trim()).filter(Boolean);
  const constituency = Array.isArray(values.constituency) ? values.constituency : [];
  const tier2Used = Boolean(legalForm || legalNote || participation || themes.length || constituency.length);
  if (legalForm && !TIER2_TAXONOMY.legal_form.includes(legalForm)) return {error: "legal_form"};
  if (legalNote && (!legalForm || legalNote.length > 200 || /[<>\u0000-\u001f]/.test(legalNote))) return {error: "legal_form_note"};
  if (participation && !TIER2_TAXONOMY.participation_in_science.includes(participation)) return {error: "participation_in_science"};
  if (participation && participation !== "not_applicable" && !payload.primary_activities.includes("research_monitoring")) return {error: "participation_in_science"};
  if (themes.length > 10 || themes.some((v) => v.length > 80 || /[<>\u0000-\u001f]/.test(v)) || new Set(themes).size !== themes.length) return {error: "themes"};
  if (constituency.length > 10 || constituency.some((v) => !TIER2_TAXONOMY.constituency.includes(v)) || new Set(constituency).size !== constituency.length) return {error: "constituency"};
  if (legalForm) payload.legal_form = legalForm;
  if (legalNote) payload.legal_form_note = legalNote;
  if (participation) payload.participation_in_science = participation;
  if (themes.length) payload.themes = themes;
  if (constituency.length) payload.constituency = constituency;
  if (tier2Used) {
    const ev = values.tier2_evidence || {};
    const url = String(ev.url || "").trim(); const date = String(ev.accessed_at || ""); const quote = String(ev.quote || "").trim();
    if (!isWebUrl(url) || !isIsoDate(date) || !quoteOk(quote)) return {error: "tier2_evidence"};
    for (const facet of [legalForm || legalNote ? "legal_form" : null, participation ? "participation_in_science" : null, themes.length ? "themes" : null, constituency.length ? "constituency" : null].filter(Boolean)) evidence.push({facet, url, accessed_at: date, quote, not_stated: false});
  }
  const affiliationRows = Array.isArray(values.affiliations) ? values.affiliations : [{target_name: values.affiliation_name, relation: values.affiliation_relation, evidence: values.affiliation_evidence}];
  if (affiliationRows.length > 10) return {error: "stated_affiliations"};
  const affiliations = [];
  for (const row of affiliationRows) {
    const name = String(row?.target_name || "").trim(); const relation = row?.relation || ""; const ev = row?.evidence || {};
    const url = String(ev.url || "").trim(); const date = String(ev.accessed_at || ""); const quote = String(ev.quote || "").trim();
    if (!(name || relation || url || quote)) continue;
    if (!name || name.length > 200 || /[<>\u0000-\u001f]/.test(name) || !TIER2_TAXONOMY.relation.includes(relation) || !isWebUrl(url) || !isIsoDate(date) || !quoteOk(quote)) return {error: "stated_affiliations"};
    affiliations.push({target_name: name, relation, evidence: {url, accessed_at: date, quote}});
  }
  if (affiliations.length) payload.stated_affiliations = affiliations;
  // One page and date are shared by every evidence row. The shared quote backs primary_activities and, unless the
  // page does not mention plastics, plastics_centrality; the optional facet quotes add a row only when filled.
  const pageUrl = String(values.page_url ?? group.url ?? "").trim();
  const date = String(values.accessed_at || today);
  // Line breaks from a pasted quote become single spaces so the word count and the stored text agree.
  const quote = String(values.quote || "").replace(/\s+/g, " ").trim();
  if (!isWebUrl(pageUrl)) return {error: "page_url"};
  if (!isIsoDate(date)) return {error: "accessed_at"};
  if (!plasticsQuoteOk(quote)) return {error: "quote"};
  for (const facet of TAG_FACETS) {
    if (facet === "plastics_centrality" && plasticsNotStated) {
      evidence.push({facet, url: pageUrl, accessed_at: date, not_stated: true});
    } else if (TIER1_EVIDENCE.includes(facet)) {
      evidence.push({facet, url: pageUrl, accessed_at: date, quote, not_stated: false});
    } else if (FACET_QUOTE_FACETS.includes(facet)) {
      const extra = String(values.facet_quotes?.[facet] || "").trim();
      if (!extra) continue;
      if (!quoteOk(extra)) return {error: `quote-${facet}`};
      evidence.push({facet, url: pageUrl, accessed_at: date, quote: extra, not_stated: false});
    }
  }
  if (evidence.some((row) => EMAIL.test(JSON.stringify(row)))) return {error: "email"};
  payload.evidence = evidence;
  if (EMAIL.test(JSON.stringify(payload))) return {error: "email"};
  if (JSON.stringify(payload).length > 12000) return {error: "payload"};
  return {region: values.region, stream: "knowledge", kind: "group_tag", payload};
}

/** Suggestion payload with the Worker contract's required name and URL. */
export function groupSuggestionPayload({region, name, url, country, note, isOrganisation} = {}) {
  if (isOrganisation !== true) return {error: "organisation_check"};
  const cleanName = String(name || "").trim();
  const cleanUrl = String(url || "").trim();
  if (!cleanName || cleanName.length > 200 || /[<>\u0000-\u001f]/.test(cleanName)) return {error: "name"};
  if (!isWebUrl(cleanUrl)) return {error: "url"};
  const payload = {name: cleanName, url: cleanUrl};
  if (country) {
    if (!/^[A-Za-z]{2}$/.test(country)) return {error: "country"};
    payload.country = country.toUpperCase();
  }
  const cleanNote = String(note || "").trim();
  if (cleanNote) {
    if (cleanNote.length > 1000 || /[<>\u0000-\u001f]/.test(cleanNote)) return {error: "note"};
    payload.note = cleanNote;
  }
  if (EMAIL.test(JSON.stringify(payload))) return {error: "email"};
  return {region, stream: "knowledge", kind: "group_suggest", payload};
}

const ERRORS = {
  network: "The service could not be reached. Check your connection and retry.",
  upstream_unavailable: "The group roster could not be read. Your work is safe; retry in a few minutes.",
  not_signed_in: "Your sign-in has ended. Sign in again to continue.",
  not_region_member: "This region is no longer open to your account. Reload your tasks.",
  group_not_in_region: "This group is unavailable for tagging in your region. Your draft is still open.",
  invalid_group_id: "This group's task details are no longer valid. Reload your assignments.",
  invalid_request: "The service could not read this request. Reload your assignments and retry.",
  invalid_region: "This region is no longer open for group tasks.",
  not_found: "Group tasks are not available on this service yet. Try again after the service update.",
  http_404: "Group tasks are not available on this service yet. Try again after the service update.",
  invalid_payload: "Some answers do not match the tagging rules. Check the highlighted field and retry.",
  rate_limited: "Too many submissions were sent in a short time. Wait a moment and retry.",
};
const errorText = (code, fallback) => ERRORS[code] || fallback?.(code) || "Something went wrong. Try again in a few minutes.";

/** Plain-language message for a payload error key from groupTagPayload. */
function tagErrorMessage(error) {
  if (error === "name_correction") return "Enter the group's public name in plain text, using 2 to 200 characters.";
  if (error === "quote") return "Add 10 to 50 words from their page about plastics, or about the group if plastics are not part of their work.";
  if (error.startsWith("quote-")) return "Check the optional quote for this choice. Use 25 words or fewer.";
  if (error === "page_url") return "Check the page you read. It must be a web address that starts with https://.";
  if (error === "accessed_at") return "Check the date read. Choose a real date.";
  if (error === "email") return "Remove any email address from the form. Only web addresses and quotes from the group's pages are allowed.";
  return `Check ${ERROR_FIELDS[error] || "this answer"} and try again.`;
}

const selectOptions = (items, selected = "", placeholder = "Choose one") => `<option value="">${esc(placeholder)}</option>${items.map(({value, label}) => `<option value="${esc(value)}"${value === selected ? " selected" : ""}>${esc(label)}</option>`).join("")}`;
const optionList = (kind, values, selected = "", placeholder = "Choose one") => selectOptions(values.map((v) => ({value: v, label: groupLabel(kind, v)})), selected, placeholder);

/** Two large yes/no buttons for the organisation check. aria-pressed shows the choice; attr is the data hook. */
function orgChoiceHTML({attr, choice, question, yes, no}) {
  return `<fieldset class="g-org-check"><legend>Organisation check</legend><p>${esc(question)}</p>
    <div class="g-org-buttons"><button type="button" class="g-org-btn" ${attr}="yes" aria-pressed="${choice === "yes"}">${esc(yes)}</button><button type="button" class="g-org-btn" ${attr}="no" aria-pressed="${choice === "no"}">${esc(no)}</button></div></fieldset>`;
}

const chipHTML = (key, code, label) => `<li class="g-chip" data-code="${esc(code)}"><span>${esc(label)}</span><button type="button" class="g-chip-remove" data-g-picker-remove="${esc(key)}" data-code="${esc(code)}" aria-label="Remove ${esc(label)}">×</button></li>`;

/** A name picker: type a name, choose Add (or press Enter), and the choice becomes a removable chip. */
function pickerHTML(key, codes) {
  const cfg = PICKERS[key];
  return `<div class="field g-picker" data-g-picker="${key}">
    <label for="gp-${key}">${esc(cfg.label)}</label>
    <div class="g-picker-row"><input id="gp-${key}" type="text" list="gpl-${key}" autocomplete="off" placeholder="${esc(cfg.placeholder)}" data-g-picker-input="${key}" aria-describedby="gp-${key}-hint"><button type="button" class="btn" data-g-picker-add="${key}">Add</button></div>
    <datalist id="gpl-${key}">${cfg.options.map((option) => `<option value="${esc(option.label)}"></option>`).join("")}</datalist>
    <p class="hint" id="gp-${key}-hint">Type a name and choose Add. Remove a choice with its × button.</p>
    <p class="ws-error g-picker-error" role="alert" data-g-picker-error="${key}" hidden></p>
    <ul class="g-chips" data-g-chips="${key}">${codes.map((code) => chipHTML(key, code, cfg.nameOf(code))).join("")}</ul>
  </div>`;
}

/** "Add a quote for this" disclosure beside an optional facet field. */
function facetQuoteHTML(facet, draft) {
  const quote = draft.facet_quotes?.[facet] || "";
  return `<details class="g-facet-quote"${quote ? " open" : ""}><summary>Add a quote for this</summary>
    <div class="field"><label for="gfq-${facet}">Quote for ${esc(LABELS[facet].toLowerCase())} (optional, 25 words or fewer)</label><textarea id="gfq-${facet}" rows="2" maxlength="400" data-g-facet-quote="${facet}">${esc(quote)}</textarea></div></details>`;
}

function selectFieldHTML(facet, options, draft) {
  return `<div class="field"><label for="grp-${facet}">${esc(LABELS[facet])}</label><select id="grp-${facet}" data-g-field="${facet}">${optionList(facet, options, draft[facet])}</select>${FACET_QUOTE_FACETS.includes(facet) ? facetQuoteHTML(facet, draft) : ""}</div>`;
}

function centralityHTML(draft) {
  const options = GROUP_TAXONOMY.plastics_centrality.filter((v) => v !== "cannot_determine");
  return `<fieldset class="g-chip-set g-wide"><legend>${esc(LABELS.plastics_centrality)}</legend><div class="g-radio-chips">${options.map((v) => `<label class="g-radio-chip"><input type="radio" name="g-centrality" value="${esc(v)}" data-g-centrality${draft.plastics_centrality === v ? " checked" : ""}><span>${esc(groupLabel("plastics_centrality", v))}</span></label>`).join("")}</div></fieldset>`;
}

function activitiesHTML(draft) {
  return `<fieldset class="g-activities g-wide"><legend>${esc(LABELS.primary_activities)}</legend><div class="g-check-grid">${GROUP_TAXONOMY.primary_activities.map((v) => `<label class="g-chip-check"><input type="checkbox" data-g-activity value="${esc(v)}"${draft.primary_activities?.includes(v) ? " checked" : ""}><span>${esc(groupLabel("primary_activities", v))}</span></label>`).join("")}</div></fieldset>`;
}

/** The single evidence block: page, date (shown as text with a change control), and the shared quote. */
function evidenceHTML(group, draft) {
  const date = draft.accessed_at || isoToday();
  const notStatedShown = NOT_STATED_CENTRALITY.includes(draft.plastics_centrality);
  return `<fieldset class="g-evidence g-wide"><legend>Evidence</legend>
    <p class="hint">Reviewers need a quote from the page for main activities and for plastics. Other choices can add their own quote.</p>
    <div class="field"><label for="g-page-url">Page you read</label><input id="g-page-url" type="url" maxlength="500" placeholder="https://" data-g-field="page_url" value="${esc(draft.page_url ?? group.url ?? "")}"></div>
    <div class="g-date"><p>Date read: <strong data-g-date-text>${esc(date)}</strong> <button type="button" class="link-btn" data-g-date-change aria-controls="g-date-wrap" aria-expanded="false">change<span class="sr"> the date read</span></button></p>
      <div class="field" id="g-date-wrap" data-g-date-wrap hidden><label for="g-date">Date read</label><input id="g-date" type="date" data-g-field="accessed_at" value="${esc(date)}"></div></div>
    <div class="field"><label for="g-quote">Words from their page about plastics (10 to 50 words)</label><textarea id="g-quote" rows="2" maxlength="${PLASTICS_QUOTE_MAX_CHARS}" data-g-field="quote" aria-describedby="g-quote-hint g-quote-count">${esc(draft.quote || "")}</textarea>
      <p class="hint" id="g-quote-hint">If plastics are not part of their work, quote what the group says about itself.</p>
      <p class="g-quote-count" id="g-quote-count" aria-live="polite" data-g-quote-count data-state="${plasticsQuoteStatus(draft.quote).state}"><span aria-hidden="true" data-g-count-text>${plasticsQuoteStatus(draft.quote).text}</span><span class="sr" data-g-count-announce></span></p></div>
    <div class="field" data-g-not-stated-wrap${notStatedShown ? "" : " hidden"}><label class="g-chip-check g-not-stated"><input type="checkbox" data-g-not-stated${draft.plastics_not_stated === true ? " checked" : ""}><span>Their pages do not mention plastics</span></label></div>
  </fieldset>`;
}

function tagFieldsHTML(group, draft, picks) {
  return `<div class="g-fields">${selectFieldHTML("entity_type", GROUP_TAXONOMY.entity_type, draft)}${selectFieldHTML("sector", GROUP_TAXONOMY.sector, draft)}${centralityHTML(draft)}${activitiesHTML(draft)}${selectFieldHTML("geographic_scope", GROUP_TAXONOMY.geographic_scope, draft)}${pickerHTML("places", picks.places)}${pickerHTML("website_languages", picks.website_languages)}</div>
    ${evidenceHTML(group, draft)}`;
}

function tier2HTML(draft = {}) {
  const ev = draft.tier2_evidence || {};
  const affiliations = Array.isArray(draft.affiliations) && draft.affiliations.length ? draft.affiliations : [{}];
  const affiliationRows = affiliations.map((row, i) => `<fieldset class="g-evidence g-affiliation" data-g-aff-row="${i}"><legend>Stated affiliation ${i + 1}</legend><p class="hint">Record this only when the group's own page names the relationship and other organisation.</p>
      <div class="field"><label for="g-aff-name-${i}">Other organisation</label><input id="g-aff-name-${i}" type="text" maxlength="200" data-g-affiliation="target_name" data-aff-index="${i}" value="${esc(row.target_name || "")}"></div>
      <div class="field"><label for="g-aff-relation-${i}">Relationship</label><select id="g-aff-relation-${i}" data-g-affiliation="relation" data-aff-index="${i}">${optionList("relation", TIER2_TAXONOMY.relation, row.relation)}</select></div>
      <div class="field"><label for="g-aff-url-${i}">Source web address</label><input id="g-aff-url-${i}" type="url" data-g-affiliation-evidence="url" data-aff-index="${i}" value="${esc(row.evidence?.url || "")}" placeholder="https://"></div>
      <div class="field"><label for="g-aff-date-${i}">Date read</label><input id="g-aff-date-${i}" type="date" data-g-affiliation-evidence="accessed_at" data-aff-index="${i}" value="${esc(row.evidence?.accessed_at || isoToday())}"></div>
      <div class="field"><label for="g-aff-quote-${i}">Exact words from the page (up to 25 words)</label><textarea id="g-aff-quote-${i}" rows="2" maxlength="400" data-g-affiliation-evidence="quote" data-aff-index="${i}">${esc(row.evidence?.quote || "")}</textarea></div>
      ${affiliations.length > 1 ? `<button type="button" class="link-btn" data-g-aff-action="remove" data-aff-index="${i}">Remove this affiliation</button>` : ""}</fieldset>`).join("");
  return `<details class="g-tier2" data-g-tier2${draft.tier2Open ? " open" : ""}><summary>Optional details about the organisation</summary>
    <p class="hint">Use these only when the group's own pages state the details. Leave every field blank if you are unsure.</p>
    <div class="g-fields">
      <div class="field"><label for="g-legal-form">Legal form</label><select id="g-legal-form" data-g-tier2-field="legal_form">${optionList("legal_form", TIER2_TAXONOMY.legal_form, draft.legal_form)}</select></div>
      <div class="field"><label for="g-legal-note">Legal form note (optional)</label><input id="g-legal-note" type="text" maxlength="200" data-g-tier2-field="legal_form_note" value="${esc(draft.legal_form_note || "")}"></div>
      <div class="field"><label for="g-science">Participation in science</label><select id="g-science" data-g-tier2-field="participation_in_science">${optionList("participation_in_science", TIER2_TAXONOMY.participation_in_science, draft.participation_in_science)}</select><p class="hint">Choose a value other than “Not applicable” only when research and monitoring is a main activity.</p></div>
      <div class="field"><label for="g-themes">Themes (optional; separate with semicolons)</label><input id="g-themes" type="text" maxlength="850" data-g-tier2-field="themes" value="${esc(draft.themes || "")}"></div>
      <fieldset class="g-activities g-wide"><legend>Constituency (optional)</legend><div class="g-check-grid">${TIER2_TAXONOMY.constituency.map((v) => `<label class="g-chip-check"><input type="checkbox" data-g-constituency value="${esc(v)}"${draft.constituency?.includes(v) ? " checked" : ""}><span>${esc(groupLabel("constituency", v))}</span></label>`).join("")}</div></fieldset>
    </div>
    <fieldset class="g-evidence"><legend>Evidence for optional details</legend><p class="hint">One short quote can support the optional details you entered above.</p>
      <div class="field"><label for="g-tier2-url">Source web address</label><input id="g-tier2-url" type="url" data-g-tier2-evidence="url" value="${esc(ev.url || "")}" placeholder="https://"></div>
      <div class="field"><label for="g-tier2-date">Date read</label><input id="g-tier2-date" type="date" data-g-tier2-evidence="accessed_at" value="${esc(ev.accessed_at || isoToday())}"></div>
      <div class="field"><label for="g-tier2-quote">Exact words from the page (up to 25 words)</label><textarea id="g-tier2-quote" rows="2" maxlength="400" data-g-tier2-evidence="quote">${esc(ev.quote || "")}</textarea></div>
    </fieldset>
    <section class="g-affiliations" aria-labelledby="g-affiliations-h"><h4 id="g-affiliations-h">Stated affiliations (optional)</h4><p class="hint">Record partners or parent bodies only when the group's own page names the relationship and the other organisation. You can add up to ten.</p>${affiliationRows}<button type="button" class="btn" data-g-aff-action="add"${affiliations.length >= 10 ? " disabled" : ""}>Add another affiliation</button></section>
  </details>`;
}

/** Same-organisation question: a link to the other group's website (http(s) only) and three answer chips. */
function sameAsHTML(groupId, questions, draft) {
  if (!questions.length) return "";
  const chosen = (other) => (Array.isArray(draft.same_as) ? draft.same_as : []).find((item) => item?.group_id === other)?.answer;
  const items = questions.map((question, i) => {
    const link = question.url ? ` (<a href="${esc(question.url)}" target="_blank" rel="noopener noreferrer">their website<span class="sr"> (opens in a new tab)</span></a>)` : "";
    const hint = duplicateHint(question.reason);
    return `<fieldset class="g-same-as-item" data-g-same-as-item="${esc(question.group_id)}"><legend>Is this the same organisation as ${esc(question.name)}${link}?</legend>
      ${hint ? `<p class="hint" id="g-same-as-hint-${i}">${esc(hint)}</p>` : ""}
      <div class="g-radio-chips">${Object.keys(SAME_AS_LABELS).map((answer) => `<label class="g-radio-chip"><input type="radio" name="g-same-as-${esc(question.group_id)}" value="${esc(answer)}" data-g-same-as="${esc(question.group_id)}"${chosen(question.group_id) === answer ? " checked" : ""}${hint ? ` aria-describedby="g-same-as-hint-${i}"` : ""}><span>${esc(SAME_AS_LABELS[answer])}</span></label>`).join("")}</div></fieldset>`;
  });
  return `<fieldset class="g-same-as g-wide" data-g-same-as-wrap><legend>Possible duplicates (optional)</legend><p class="hint">Answer only if you can tell from the pages. Skip any question you are unsure about.</p>${items.join("")}</fieldset>`;
}

/**
 * Loads the small quality-check file once per page, and the full roster (about 1 MB) only when a group in the batch
 * has a possible duplicate, because the question needs the other group's name and website. A failed fetch gives no
 * questions and no name hints.
 */
let qcCache = null;
let rosterCache = null;
const getJson = (path) => fetch(globalDataUrl(path), {cache: "no-cache"}).then((response) => (response.ok ? response.json() : null)).catch(() => null);
export function needsRoster(qc, groupIds) {
  const ids = new Set(groupIds);
  return Boolean(qc?.pairs?.some((pair) => ids.has(pair?.a) || ids.has(pair?.b)));
}
async function loadRosterChecks(groupIds = []) {
  if (!qcCache) qcCache = getJson("groups/roster_qc.json").then((qc) => (qc?.schema === "cg-roster-qc-v1" ? qc : null));
  const qc = await qcCache;
  if (!needsRoster(qc, groupIds)) return {roster: rosterLookup(null), qc};
  if (!rosterCache) rosterCache = getJson("groups/roster.json").then(rosterLookup);
  return {roster: await rosterCache, qc};
}
/** Wikidata suggestions, loaded once per page. A failed fetch means no suggestions; nothing else changes. */
let suggestionsCache = null;
function loadSuggestions() {
  if (!suggestionsCache) suggestionsCache = getJson("groups/suggestions.json").then((data) => (data?.schema === "cg-suggestions-v1" ? data : null));
  return suggestionsCache;
}
/** IRS register suggestions, loaded once per page on the same terms as the Wikidata ones. */
let registerSuggestionsCache = null;
function loadRegisterSuggestions() {
  if (!registerSuggestionsCache) registerSuggestionsCache = getJson("groups/register_suggestions.json").then((data) => (data?.schema === "cg-register-suggestions-v1" ? data : null));
  return registerSuggestionsCache;
}

/** The "Group work you sent" list, shown on both screens. */
function sentHTML(ctx) {
  const sent = (ctx.submissions || []).filter((row) => row?.region === ctx.region && row.stream === "knowledge" && ["group_tag", "group_suggest"].includes(row.kind)).sort((a, b) => (Number(b.created_at) || 0) - (Number(a.created_at) || 0));
  if (!sent.length) return "";
  const status = (row) => row.second_tag ? "Saved for the agreement check" : row.status === "approved" ? "Approved" : row.status === "rejected" ? "Not accepted" : "Waiting for review";
  return `<section class="g-history" aria-labelledby="g-history-h"><h3 id="g-history-h">Group work you sent</h3><ul>${sent.map((row) => `<li><strong>${row.kind === "group_suggest" ? esc(row.payload?.name || "Group suggestion") : "Group tag"}</strong><span>${status(row)}</span></li>`).join("")}</ul></section>`;
}

const crumb = '<p class="ws-crumb"><button type="button" class="link-btn" data-ws-action="home">Back to your tasks</button></p>';
const HOLD_REFRESH_MS = 15 * 60 * 1000;
const SECOND_TAG_NOTICE = "Someone else just tagged this group. Your answers still help check agreement.";

/** Mounts one assignment at a time and guards detached/stale responses after navigation. */
export function mountGroups(host, ctx) {
  const state = {leases: [], remaining: 0, index: 0, loading: true, busy: false, error: "", formError: "", notice: "", generation: 0, drafts: {}, activityOrder: [], checks: {roster: new Map(), qc: null, suggestions: null, registerSuggestions: null}};
  let alive = true;
  let holdTimer;
  const current = () => state.leases[state.index] || null;
  const detached = () => !alive || !host.isConnected;
  const batchPath = `/groups/batch?region=${encodeURIComponent(ctx.region)}`;
  const orgChoice = () => host.querySelector("[data-g-org][aria-pressed='true']")?.dataset.gOrg;
  const pickerCodes = (key) => [...host.querySelectorAll(`[data-g-chips="${key}"] > li`)].map((li) => li.dataset.code);
  const fieldValue = (name) => host.querySelector(`[data-g-field="${name}"]`)?.value || "";
  const render = () => {
    if (detached()) return;
    const group = current();
    const draft = group ? state.drafts[group.group_id] || {} : {};
    state.activityOrder = Array.isArray(draft.primary_activities) ? [...draft.primary_activities] : [];
    const picks = {places: draft.places ?? placeDefaults(ctx.region, group), website_languages: draft.website_languages ?? languageDefaults(ctx.region)};
    const groupLink = safeUrl(group?.url);
    const {roster, qc} = state.checks;
    const questions = group ? duplicateQuestions(group.group_id, qc, roster) : [];
    const suspect = group ? isSuspectName(group.group_id, qc) : false;
    const nameHint = suspect && suspectHint(group.group_id, qc)
      ? `${suspectHint(group.group_id, qc)} Correct it to the name on the group's public website, or leave it as it is.`
      : "Use the name on the group's public website.";
    host.innerHTML = `${crumb}
      <h2 tabindex="-1">Tag local groups</h2><p class="lede">Check each group's public pages and record what they say about their work in ${esc(ctx.regionName)}. Do not guess.</p>
      <p class="ws-error" role="alert" tabindex="-1" data-g-error${state.error ? "" : " hidden"}>${esc(state.error)}</p>
      ${state.error ? `<button type="button" class="btn" data-g-action="reload"${state.busy ? " disabled" : ""}>Reload assignments</button>` : ""}
      ${state.loading ? `<p class="status" role="status">Loading your assigned groups…</p>` : ""}
      ${state.notice ? `<p class="g-success" role="status">${esc(state.notice)}</p>` : ""}
      ${!state.loading && !state.error && !group ? `<section class="g-empty"><h3>No groups assigned right now</h3><p>${state.remaining > 0 ? `${state.remaining} more groups are available in this region. Reload to claim the next batch.` : "There are no more unclaimed groups in this region right now."}</p><button type="button" class="btn" data-g-action="reload"${state.busy ? " disabled" : ""}>Reload assignments</button></section>` : ""}
      ${group ? `<div class="g-progress"><p>Group ${state.index + 1} of ${state.leases.length} in your batch</p><progress aria-label="Group progress" max="${state.leases.length}" value="${state.index + 1}"></progress></div>
        <section class="g-group" aria-labelledby="g-group-name"><h3 id="g-group-name" tabindex="-1">${esc(group.name)}</h3><p class="g-meta">${esc(group.country)}</p>
        ${groupLink ? `<p class="g-open-site"><a class="btn solid" href="${esc(groupLink)}" target="_blank" rel="noopener noreferrer">Open their website<span class="sr"> (opens in a new tab)</span></a></p>` : `<p class="hint">No website is listed for this group. Enter the page you read in the evidence section.</p>`}
        <form data-g-tag-form novalidate aria-busy="${state.busy}">
        ${suggestionHTML(group, state.checks.suggestions, state.checks.registerSuggestions)}
        <div class="field g-name-correction"><label for="g-name-correction">Correct the name (optional)</label><input id="g-name-correction" type="text" maxlength="200" autocomplete="off" data-g-field="name_correction" value="${esc(draft.name_correction ?? (suspect ? group.name : ""))}" aria-describedby="g-name-correction-hint"><p class="hint" id="g-name-correction-hint">${esc(nameHint)}</p></div>
        ${orgChoiceHTML({attr: "data-g-org", choice: draft.notOrganisation === true ? "no" : draft.notOrganisation === false ? "yes" : "", question: "Is this a collective organisation, rather than an individual or single-person practice?", yes: "Yes, a collective organisation", no: "No, a personal profile or individual"})}
        ${sameAsHTML(group.group_id, questions, draft)}
        <div data-g-tag-fields>${tagFieldsHTML(group, draft, picks)}</div>
        ${tier2HTML(draft)}
        <div class="field g-status-field"><label for="g-status">Tag status</label><select id="g-status" data-g-status><option value="ambassador_tagged"${draft.status !== "cannot_determine" ? " selected" : ""}>I can tag this group</option><option value="cannot_determine"${draft.status === "cannot_determine" ? " selected" : ""}>I cannot determine this from the available information</option></select></div>
        <div class="field" data-g-reason-wrap><label for="g-reason">Why can you not determine this?</label><select id="g-reason" data-g-reason>${optionList("cannot_determine_reason", CANNOT_REASONS, draft.reason, "Choose a reason")}</select></div>
        <div class="ws-error g-form-error" role="alert" tabindex="-1" data-g-form-error${state.formError ? "" : " hidden"}>${esc(state.formError)}</div>
        <div class="g-submit-row"><button type="submit" class="btn solid" data-g-submit${state.busy ? " disabled" : ""}>Send tag for review</button>${state.index > 0 ? `<button type="button" class="btn" data-g-action="previous">Previous group</button>` : ""}${state.index + 1 < state.leases.length ? `<button type="button" class="btn" data-g-action="next">Skip to next group</button>` : ""}</div></form></section>` : ""}
      ${sentHTML(ctx)}`;
    if (group) applyTagVisibility();
  };
  const actionError = (code) => errorText(code, ctx.errorText);
  function keepHoldOpen(refreshNow = false) {
    clearTimeout(holdTimer);
    const group = current();
    if (detached() || !group) return;
    if (refreshNow && !state.busy) void ctx.api(`${batchPath}&group_id=${encodeURIComponent(group.group_id)}`);
    holdTimer = setTimeout(() => keepHoldOpen(true), HOLD_REFRESH_MS);
  }
  async function reload() {
    if (detached() || state.busy) return;
    state.loading = true; state.error = ""; state.notice = ""; state.leases = []; state.index = 0;
    keepHoldOpen();
    const generation = ++state.generation; render();
    const result = await ctx.api(batchPath);
    const leased = Array.isArray(result?.data?.leases) ? result.data.leases.map((lease) => lease?.group_id) : [];
    const [checks, suggestions, registerSuggestions] = await Promise.all([loadRosterChecks(leased), loadSuggestions(), loadRegisterSuggestions()]);
    if (detached() || generation !== state.generation) return;
    state.checks = {...checks, suggestions, registerSuggestions};
    state.loading = false;
    if (!result?.ok) state.error = actionError(result?.error);
    else { state.leases = Array.isArray(result.data?.leases) ? result.data.leases : []; state.remaining = Number(result.data?.remaining_in_region) || 0; }
    render();
    keepHoldOpen();
  }
  /** Reads every field of the tag form into one values object (also the draft shape). */
  function tagValues() {
    const values = {region: ctx.region, notOrganisation: orgChoice() === undefined ? undefined : orgChoice() === "no"};
    values.name_correction = fieldValue("name_correction");
    values.status = host.querySelector("[data-g-status]")?.value;
    values.reason = host.querySelector("[data-g-reason]")?.value;
    for (const facet of TAG_FACETS) {
      if (facet === "primary_activities") values[facet] = state.activityOrder.filter((v) => host.querySelector(`[data-g-activity][value="${v}"]`)?.checked);
      else if (facet === "plastics_centrality") values[facet] = host.querySelector("[data-g-centrality]:checked")?.value || "";
      else values[facet] = fieldValue(facet);
    }
    values.places = pickerCodes("places");
    values.website_languages = pickerCodes("website_languages");
    values.same_as = [...host.querySelectorAll("[data-g-same-as]:checked")].map((el) => ({group_id: el.dataset.gSameAs, answer: el.value}));
    values.page_url = fieldValue("page_url");
    values.accessed_at = fieldValue("accessed_at");
    values.quote = fieldValue("quote");
    values.plastics_not_stated = host.querySelector("[data-g-not-stated]")?.checked === true;
    values.facet_quotes = {};
    for (const facet of FACET_QUOTE_FACETS) values.facet_quotes[facet] = host.querySelector(`[data-g-facet-quote="${facet}"]`)?.value || "";
    values.legal_form = host.querySelector('[data-g-tier2-field="legal_form"]')?.value || "";
    values.legal_form_note = host.querySelector('[data-g-tier2-field="legal_form_note"]')?.value || "";
    values.participation_in_science = host.querySelector('[data-g-tier2-field="participation_in_science"]')?.value || "";
    values.themes = host.querySelector('[data-g-tier2-field="themes"]')?.value || "";
    values.constituency = [...host.querySelectorAll("[data-g-constituency]:checked")].map((el) => el.value);
    values.tier2_evidence = {};
    host.querySelectorAll("[data-g-tier2-evidence]").forEach((el) => { values.tier2_evidence[el.dataset.gTier2Evidence] = el.value; });
    values.affiliations = [...host.querySelectorAll("[data-g-aff-row]")].map((row) => ({
      target_name: row.querySelector('[data-g-affiliation="target_name"]')?.value || "",
      relation: row.querySelector('[data-g-affiliation="relation"]')?.value || "",
      evidence: Object.fromEntries([...row.querySelectorAll("[data-g-affiliation-evidence]")].map((el) => [el.dataset.gAffiliationEvidence, el.value])),
    }));
    values.tier2Open = host.querySelector("[data-g-tier2]")?.open === true;
    return values;
  }
  function saveDraft() {
    const group = current(); if (!group || !host.querySelector("[data-g-tag-form]")) return;
    state.drafts[group.group_id] = tagValues();
  }
  /** Updates the plastics quote counter on every keystroke; the polite live text changes only when the state changes. */
  function updateQuoteCount(text) {
    const counter = host.querySelector("[data-g-quote-count]"); if (!counter) return;
    const {state: next, text: visible} = plasticsQuoteStatus(text);
    counter.querySelector("[data-g-count-text]").textContent = visible;
    if (counter.dataset.state === next) return;
    counter.dataset.state = next;
    counter.querySelector("[data-g-count-announce]").textContent = visible;
  }
  /** Shows or hides the sections that depend on the organisation check and the tag status. */
  function applyTagVisibility() {
    const no = orgChoice() === "no";
    const status = host.querySelector("[data-g-status]");
    const cannot = status?.value === "cannot_determine";
    const set = (selector, hidden) => { const el = host.querySelector(selector); if (el) el.hidden = hidden; };
    set(".g-name-correction", no);
    set("[data-g-tag-fields]", no || cannot);
    set("[data-g-tier2]", no || cannot);
    set("[data-g-reason-wrap]", !cannot);
    const centrality = host.querySelector("[data-g-centrality]:checked")?.value;
    set("[data-g-not-stated-wrap]", !NOT_STATED_CENTRALITY.includes(centrality));
    if (status) status.disabled = no;
    const submit = host.querySelector("[data-g-submit]");
    if (submit && !state.busy) submit.textContent = no ? "Mark not an organisation" : "Send tag for review";
  }
  function setOrgChoice(choice) {
    host.querySelectorAll("[data-g-org]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.gOrg === choice)));
    applyTagVisibility();
    saveDraft();
  }
  function showError(selector, text) {
    const box = host.querySelector(selector); if (!box) return;
    box.textContent = text; box.hidden = false; box.focus();
  }
  function addPickerChoice(key) {
    const cfg = PICKERS[key];
    const input = host.querySelector(`[data-g-picker-input="${key}"]`);
    const error = host.querySelector(`[data-g-picker-error="${key}"]`);
    const {code, ambiguous} = pickerMatch(cfg.options, input?.value);
    const chosen = pickerCodes(key);
    let message = "";
    if (ambiguous) message = "Choose one from the list. More than one name matches what you typed.";
    else if (!code) message = `Choose ${cfg.noun} from the list. Start typing its name and pick it.`;
    else if (chosen.includes(code)) message = "That one is already added.";
    else if (chosen.length >= cfg.max) message = cfg.full;
    if (message) { if (error) { error.textContent = message; error.hidden = false; } input?.focus(); return; }
    host.querySelector(`[data-g-chips="${key}"]`)?.insertAdjacentHTML("beforeend", chipHTML(key, code, cfg.nameOf(code)));
    input.value = ""; if (error) { error.hidden = true; error.textContent = ""; }
    saveDraft(); input.focus();
  }
  function removePickerChoice(button) {
    const key = button.dataset.gPickerRemove;
    button.closest("li")?.remove();
    saveDraft();
    host.querySelector(`[data-g-picker-input="${key}"]`)?.focus();
  }
  async function submitTag(event) {
    event.preventDefault(); if (state.busy || !current()) return;
    const body = groupTagPayload({group: current(), values: tagValues()});
    if (body.error) { state.formError = tagErrorMessage(body.error); showError("[data-g-form-error]", state.formError); focusFailure(body.error); return; }
    state.busy = true; const group = current(); const generation = state.generation; setBusy(true);
    const result = await ctx.api("/submissions", {method: "POST", body});
    if (detached() || generation !== state.generation) return;
    state.busy = false;
    if (!result?.ok) { setBusy(false); const message = actionError(result?.error); state.formError = message; showError("[data-g-form-error]", message); ctx.say?.(message); return; }
    const secondTag = result.data?.second_tag === true;
    const id = result.data?.id;
    if (id != null && !ctx.submissions?.some((row) => row.id === id)) {
      ctx.onSubmitted?.({id, region: ctx.region, stream: "knowledge", kind: "group_tag", payload: body.payload, status: result.data?.status || "pending", second_tag: secondTag, created_at: Date.now(), decided_at: null, decision_note: null});
    }
    delete state.drafts[group.group_id];
    state.leases = state.leases.filter((g) => g.group_id !== group.group_id);
    state.index = Math.min(state.index, Math.max(0, state.leases.length - 1));
    state.error = ""; state.formError = "";
    const next = current();
    state.notice = secondTag ? SECOND_TAG_NOTICE : next ? `Sent. Next group: ${next.name}` : "Sent. No more groups in this batch.";
    ctx.say?.(state.notice); render();
    keepHoldOpen(true);
    host.querySelector(next ? "#g-group-name" : "h2")?.focus();
  }
  function moveToGroup(action) {
    if (state.busy || !current()) return;
    state.index = Math.max(0, Math.min(state.index + (action === "next" ? 1 : -1), state.leases.length - 1));
    state.notice = "";
    state.formError = "";
    render();
    keepHoldOpen(true);
    host.querySelector("#g-group-name")?.focus();
  }
  function setBusy(on) {
    const form = host.querySelector("[data-g-tag-form]"); if (form) form.setAttribute("aria-busy", on ? "true" : "false");
    host.querySelectorAll("[data-g-submit], [data-g-action]").forEach((button) => { button.disabled = on; });
    const tag = host.querySelector("[data-g-submit]"); if (tag) tag.textContent = on ? "Sending…" : orgChoice() === "no" ? "Mark not an organisation" : "Send tag for review";
  }
  function focusFailure(error) {
    const target = error === "primary_activities" ? host.querySelector("[data-g-activity]")
      : error === "organisation_check" ? host.querySelector("[data-g-org]")
        : error === "plastics_centrality" ? host.querySelector("[data-g-centrality]")
          : error === "cannot_determine_reason" ? host.querySelector("[data-g-reason]")
            : error === "stated_affiliations" ? firstInvalidAffiliationControl()
              : error === "tier2_evidence" ? host.querySelector("[data-g-tier2-evidence='url']")
                : error === "quote" ? host.querySelector('[data-g-field="quote"]')
                  : error.startsWith("quote-") ? host.querySelector(`[data-g-facet-quote="${error.slice(6)}"]`)
                    : host.querySelector(`[data-g-field="${error}"], [data-g-tier2-field="${error}"], [data-g-picker-input="${error}"]`);
    target?.closest?.("details")?.setAttribute("open", "");
    target?.focus();
  }
  function firstInvalidAffiliationControl() {
    for (const row of host.querySelectorAll("[data-g-aff-row]")) {
      const name = row.querySelector('[data-g-affiliation="target_name"]');
      const relation = row.querySelector('[data-g-affiliation="relation"]');
      const url = row.querySelector('[data-g-affiliation-evidence="url"]');
      const date = row.querySelector('[data-g-affiliation-evidence="accessed_at"]');
      const quote = row.querySelector('[data-g-affiliation-evidence="quote"]');
      if (!name?.value.trim()) return name;
      if (!TIER2_TAXONOMY.relation.includes(relation?.value)) return relation;
      if (!isWebUrl(url?.value.trim())) return url;
      if (!isIsoDate(date?.value)) return date;
      if (!quote?.value.trim() || quote.value.trim().split(/\s+/).length > 25) return quote;
    }
    return host.querySelector('[data-g-affiliation="target_name"]');
  }
  host.addEventListener("click", (event) => {
    const target = event.target;
    if (target.closest?.(".g-tier2 > summary")) {
      const group = current();
      if (group) state.drafts[group.group_id] = {...(state.drafts[group.group_id] || {}), tier2Open: !host.querySelector("[data-g-tier2]")?.open};
    }
    const org = target.closest?.("[data-g-org]");
    if (org) { setOrgChoice(org.dataset.gOrg); return; }
    const add = target.closest?.("[data-g-picker-add]");
    if (add) { addPickerChoice(add.dataset.gPickerAdd); return; }
    const remove = target.closest?.("[data-g-picker-remove]");
    if (remove) { removePickerChoice(remove); return; }
    if (target.closest?.("[data-g-date-change]")) {
      const wrap = host.querySelector("[data-g-date-wrap]"); const control = target.closest("[data-g-date-change]");
      if (wrap) { wrap.hidden = false; control.setAttribute("aria-expanded", "true"); wrap.querySelector("input")?.focus(); }
      return;
    }
    const affButton = target.closest?.("[data-g-aff-action]");
    if (affButton) {
      if (state.busy) return;
      saveDraft();
      const group = current(); if (!group) return;
      const draft = state.drafts[group.group_id] || {};
      const rows = Array.isArray(draft.affiliations) && draft.affiliations.length ? draft.affiliations : [{}];
      const index = Number(affButton.dataset.affIndex);
      if (affButton.dataset.gAffAction === "add" && rows.length < 10) rows.push({});
      if (affButton.dataset.gAffAction === "remove" && rows.length > 1) rows.splice(index, 1);
      state.drafts[group.group_id] = {...draft, affiliations: rows};
      render();
      host.querySelector(`[data-g-aff-row="${affButton.dataset.gAffAction === "add" ? rows.length - 1 : Math.max(0, index - 1)}"] input`)?.focus();
      return;
    }
    const button = target.closest?.("[data-g-action]"); if (!button) return;
    saveDraft();
    if (button.dataset.gAction === "reload") return reload();
    moveToGroup(button.dataset.gAction);
  });
  host.addEventListener("keydown", (event) => {
    const key = event.target.dataset?.gPickerInput;
    if (key && event.key === "Enter") { event.preventDefault(); addPickerChoice(key); }
  });
  host.addEventListener("change", (event) => {
    const target = event.target;
    if (target.matches?.("[data-g-activity]")) { const value = target.value; state.activityOrder = state.activityOrder.filter((v) => v !== value); if (target.checked) state.activityOrder.push(value); }
    if (target.matches?.('[data-g-field="accessed_at"]')) { const text = host.querySelector("[data-g-date-text]"); if (text) text.textContent = target.value; }
    if (target.matches?.("[data-g-status]") || target.matches?.("[data-g-centrality]")) applyTagVisibility();
    saveDraft();
  });
  host.addEventListener("input", (event) => {
    if (event.target.matches?.('[data-g-field="quote"]')) updateQuoteCount(event.target.value);
    saveDraft();
  });
  host.addEventListener("submit", (event) => {
    if (event.target.matches?.("[data-g-tag-form]")) submitTag(event);
  });
  render();
  reload();
  return () => { alive = false; state.generation += 1; clearTimeout(holdTimer); };
}

/** The "Suggest a missing group" screen: a collective organisation the lists do not have yet. */
export function mountGroupSuggest(host, ctx) {
  const state = {busy: false, suggested: false, suggestion: {}};
  let alive = true;
  const detached = () => !alive || !host.isConnected;
  const suggestOrg = () => host.querySelector("[data-g-suggest-org][aria-pressed='true']")?.dataset.gSuggestOrg;
  const render = () => {
    if (detached()) return;
    const s = state.suggestion;
    const choice = s.isOrganisation === true ? "yes" : s.isOrganisation === false ? "no" : "";
    host.innerHTML = `${crumb}
      <h2 tabindex="-1">Suggest a missing group</h2>
      <p class="lede">Add an organisation that is missing from the list. Only suggest a collective organisation with a public web page. Suggestions are reviewed before appearing.</p>
      <form class="g-suggest" data-g-suggest-form novalidate>${orgChoiceHTML({attr: "data-g-suggest-org", choice, question: "Is this a collective organisation, rather than an individual or single-person practice?", yes: "Yes, a collective organisation", no: "No, an individual or personal profile"})}
        <div class="g-fields">
          <div class="field"><label for="gs-name">Group name</label><input id="gs-name" type="text" maxlength="200" data-g-suggest="name" value="${esc(s.name || "")}"></div>
          <div class="field"><label for="gs-url">Public web address</label><input id="gs-url" type="url" maxlength="500" placeholder="https://" data-g-suggest="url" value="${esc(s.url || "")}"></div>
          <div class="field"><label for="gs-country">Country (optional)</label><select id="gs-country" data-g-suggest="country">${selectOptions(COUNTRY_OPTIONS.map((o) => ({value: o.code, label: o.label})), s.country || "", "No country chosen")}</select></div>
          <div class="field g-wide"><label for="gs-note">Note (optional)</label><textarea id="gs-note" rows="3" maxlength="1000" data-g-suggest="note">${esc(s.note || "")}</textarea></div>
        </div>
        <div class="ws-error g-form-error" role="alert" tabindex="-1" data-g-suggest-error hidden></div>
        <div class="g-submit-row"><button type="submit" class="btn solid" data-g-suggest-submit${state.busy ? " disabled" : ""}>Suggest group</button></div>
      </form>
      ${state.suggested ? `<p class="g-success" role="status">Suggestion sent for review.</p>` : ""}
      ${sentHTML(ctx)}`;
  };
  function saveSuggestionDraft() {
    if (!host.querySelector("[data-g-suggest-form]")) return;
    for (const key of ["name", "url", "country", "note"]) state.suggestion[key] = host.querySelector(`[data-g-suggest="${key}"]`)?.value || "";
    const choice = suggestOrg();
    state.suggestion.isOrganisation = choice === undefined ? undefined : choice === "yes";
  }
  async function submitSuggestion(event) {
    event.preventDefault(); if (state.busy) return;
    saveSuggestionDraft();
    const value = (key) => state.suggestion[key] || "";
    const body = groupSuggestionPayload({region: ctx.region, name: value("name"), url: value("url"), country: value("country"), note: value("note"), isOrganisation: state.suggestion.isOrganisation});
    if (body.error) {
      const message = body.error === "organisation_check"
        ? state.suggestion.isOrganisation === false ? "Only collective organisations can be suggested here. This entry cannot be submitted." : "Confirm that the suggestion is a collective organisation before sending it."
        : `Check ${ERROR_FIELDS[body.error] || "this answer"} and try again.`;
      showSuggestError(message);
      if (body.error === "organisation_check") host.querySelector("[data-g-suggest-org]")?.focus();
      return;
    }
    state.busy = true; const submitButton = host.querySelector("[data-g-suggest-submit]"); if (submitButton) submitButton.disabled = true;
    const result = await ctx.api("/submissions", {method: "POST", body});
    if (detached()) return;
    state.busy = false;
    if (!result?.ok) { if (submitButton) submitButton.disabled = false; showSuggestError(errorText(result?.error, ctx.errorText)); return; }
    ctx.onSubmitted?.({id: result.data?.id, region: ctx.region, stream: "knowledge", kind: "group_suggest", payload: body.payload, status: "pending", created_at: Date.now(), decided_at: null, decision_note: null});
    state.suggestion = {}; state.suggested = true; render(); ctx.say?.("Group suggestion sent for review."); host.querySelector("h2")?.focus();
  }
  function showSuggestError(text) {
    const box = host.querySelector("[data-g-suggest-error]"); if (!box) return;
    box.textContent = text; box.hidden = false; box.focus();
  }
  host.addEventListener("click", (event) => {
    const org = event.target.closest?.("[data-g-suggest-org]");
    if (!org) return;
    host.querySelectorAll("[data-g-suggest-org]").forEach((button) => button.setAttribute("aria-pressed", String(button === org)));
    saveSuggestionDraft();
  });
  host.addEventListener("input", () => saveSuggestionDraft());
  host.addEventListener("change", () => saveSuggestionDraft());
  host.addEventListener("submit", (event) => {
    if (event.target.matches?.("[data-g-suggest-form]")) submitSuggestion(event);
  });
  render();
  return () => { alive = false; };
}
