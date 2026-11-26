// Signed-in group tagging (CG-6c; streamlined in AMB-GROUPS-UX). Each operation is a separate Worker call: leases are
// claimed/renewed/released independently from tag and suggestion submissions. Two screens share this module:
// mountGroups ("Tag local groups") and mountGroupSuggest ("Suggest a missing group").
import {escapeHtml} from "./atlas.js";
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
  name: "Group name", url: "Public web address", country: "Country", note: "Note",
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
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;

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

/** Build a tag payload from form values, or return a field key to focus. */
export function groupTagPayload({group, values, today = isoToday()} = {}) {
  if (!group?.group_id) return {error: "group"};
  if (typeof values.notOrganisation !== "boolean") return {error: "organisation_check"};
  if (values.notOrganisation) {
    return {region: values.region, stream: "knowledge", kind: "group_tag", payload: {
      group_id: group.group_id, status: "cannot_determine", cannot_determine_reason: "not_an_organisation", not_an_organisation: true,
    }};
  }
  if (values.status === "cannot_determine") {
    if (!CANNOT_REASONS.includes(values.reason)) return {error: "cannot_determine_reason"};
    return {region: values.region, stream: "knowledge", kind: "group_tag", payload: {
      group_id: group.group_id, status: "cannot_determine", cannot_determine_reason: values.reason,
    }};
  }
  const payload = {group_id: group.group_id, status: "ambassador_tagged"};
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
  const quote = String(values.quote || "").trim();
  if (!isWebUrl(pageUrl)) return {error: "page_url"};
  if (!isIsoDate(date)) return {error: "accessed_at"};
  if (!quoteOk(quote)) return {error: "quote"};
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
  lease_not_found: "This task is no longer assigned to you. Reload the batch to see available work.",
  renewal_used: "This task has already been renewed. You can keep working until its expiry.",
  renewal_refused: "The lease changed before it could be renewed. Reload the batch and try again.",
  invalid_group_id: "This group's task details are no longer valid. Reload your assignments.",
  invalid_request: "The service could not read this request. Reload your assignments and retry.",
  invalid_region: "This region is no longer open for group tasks.",
  not_found: "Group tasks are not available on this service yet. Try again after the service update.",
  http_404: "Group tasks are not available on this service yet. Try again after the service update.",
  not_leased: "This task is no longer assigned to you. Reload the batch before submitting.",
  invalid_payload: "Some answers do not match the tagging rules. Check the highlighted field and retry.",
  rate_limited: "Too many submissions were sent in a short time. Wait a moment and retry.",
};
const errorText = (code, fallback) => ERRORS[code] || fallback?.(code) || "Something went wrong. Try again in a few minutes.";

/** Plain-language message for a payload error key from groupTagPayload. */
function tagErrorMessage(error) {
  if (error === "quote") return "Add the words from their page that show their work. Use 25 words or fewer.";
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
    <div class="field"><label for="g-quote">Words from their page that show their plastics work (up to 25 words)</label><textarea id="g-quote" rows="2" maxlength="400" data-g-field="quote">${esc(draft.quote || "")}</textarea></div>
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

/** The "Group work you sent" list, shown on both screens. */
function sentHTML(ctx) {
  const sent = (ctx.submissions || []).filter((row) => row?.region === ctx.region && row.stream === "knowledge" && ["group_tag", "group_suggest"].includes(row.kind)).sort((a, b) => (Number(b.created_at) || 0) - (Number(a.created_at) || 0));
  if (!sent.length) return "";
  return `<section class="g-history" aria-labelledby="g-history-h"><h3 id="g-history-h">Group work you sent</h3><ul>${sent.map((row) => `<li><strong>${row.kind === "group_suggest" ? esc(row.payload?.name || "Group suggestion") : "Group tag"}</strong><span>${row.status === "approved" ? "Approved" : row.status === "rejected" ? "Not accepted" : "Waiting for review"}</span></li>`).join("")}</ul></section>`;
}

const crumb = '<p class="ws-crumb"><button type="button" class="link-btn" data-ws-action="home">Back to your tasks</button></p>';
const TIP_RENEW = "Keep this group reserved for you for another 30 days. You can renew once.";
const TIP_RELEASE = "Give this group back so another ambassador can tag it. Anything you entered for it is discarded.";

/** Mounts one assignment at a time and guards detached/stale responses after navigation. */
export function mountGroups(host, ctx) {
  const state = {leases: [], remaining: 0, index: 0, loading: true, busy: false, error: "", formError: "", notice: "", generation: 0, drafts: {}, activityOrder: []};
  let alive = true;
  const current = () => state.leases[state.index] || null;
  const detached = () => !alive || !host.isConnected;
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
    const expiry = group?.expires_at ? new Date(group.expires_at).toLocaleDateString() : "";
    host.innerHTML = `${crumb}
      <h2 tabindex="-1">Tag local groups</h2><p class="lede">Check each group's public pages and record what they say about their work in ${esc(ctx.regionName)}. Do not guess.</p>
      <p class="ws-error" role="alert" tabindex="-1" data-g-error${state.error ? "" : " hidden"}>${esc(state.error)}</p>
      ${state.error ? `<button type="button" class="btn" data-g-action="reload"${state.busy ? " disabled" : ""}>Reload assignments</button>` : ""}
      ${state.loading ? `<p class="status" role="status">Loading your assigned groups…</p>` : ""}
      ${state.notice ? `<p class="g-success" role="status">${esc(state.notice)}</p>` : ""}
      ${!state.loading && !state.error && !group ? `<section class="g-empty"><h3>No groups assigned right now</h3><p>${state.remaining > 0 ? `${state.remaining} more groups are available in this region. Reload to claim the next batch.` : "There are no more unclaimed groups in this region right now."}</p><button type="button" class="btn" data-g-action="reload"${state.busy ? " disabled" : ""}>Reload assignments</button></section>` : ""}
      ${group ? `<div class="g-progress"><p>Group ${state.index + 1} of ${state.leases.length} in your batch</p><progress aria-label="Group progress" max="${state.leases.length}" value="${state.index + 1}"></progress></div>
        <section class="g-group" aria-labelledby="g-group-name"><h3 id="g-group-name" tabindex="-1">${esc(group.name)}</h3><p class="g-meta">${esc(group.country)}${expiry ? ` · Lease until ${esc(expiry)}` : ""}</p>
        ${groupLink ? `<p class="g-open-site"><a class="btn solid" href="${esc(groupLink)}" target="_blank" rel="noopener noreferrer">Open their website<span class="sr"> (opens in a new tab)</span></a></p>` : `<p class="hint">No website is listed for this group. Enter the page you read in the evidence section.</p>`}
        <div class="g-lease-actions">
          <span class="g-tip-wrap"><button type="button" class="btn" data-g-action="renew" aria-describedby="g-tip-renew"${group.renewals > 0 || state.busy ? " disabled" : ""}>${group.renewals > 0 ? "Lease renewed" : "Renew lease"}</button><span class="g-tip" id="g-tip-renew" role="tooltip">${TIP_RENEW}</span></span>
          <span class="g-tip-wrap"><button type="button" class="link-btn" data-g-action="release" aria-describedby="g-tip-release"${state.busy ? " disabled" : ""}>Return this group to the pool</button><span class="g-tip" id="g-tip-release" role="tooltip">${TIP_RELEASE}</span></span>
        </div>
        <form data-g-tag-form novalidate aria-busy="${state.busy}">
        ${orgChoiceHTML({attr: "data-g-org", choice: draft.notOrganisation === true ? "no" : draft.notOrganisation === false ? "yes" : "", question: "Is this a collective organisation, rather than an individual or single-person practice?", yes: "Yes, a collective organisation", no: "No, a personal profile or individual"})}
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
  async function reload() {
    if (detached() || state.busy) return;
    state.loading = true; state.error = ""; state.notice = ""; state.leases = []; state.index = 0;
    const generation = ++state.generation; render();
    const result = await ctx.api(`/groups/batch?region=${encodeURIComponent(ctx.region)}`);
    if (detached() || generation !== state.generation) return;
    state.loading = false;
    if (!result?.ok) state.error = actionError(result?.error);
    else { state.leases = Array.isArray(result.data?.leases) ? result.data.leases : []; state.remaining = Number(result.data?.remaining_in_region) || 0; }
    render();
  }
  /** Reads every field of the tag form into one values object (also the draft shape). */
  function tagValues() {
    const values = {region: ctx.region, notOrganisation: orgChoice() === undefined ? undefined : orgChoice() === "no"};
    values.status = host.querySelector("[data-g-status]")?.value;
    values.reason = host.querySelector("[data-g-reason]")?.value;
    for (const facet of TAG_FACETS) {
      if (facet === "primary_activities") values[facet] = state.activityOrder.filter((v) => host.querySelector(`[data-g-activity][value="${v}"]`)?.checked);
      else if (facet === "plastics_centrality") values[facet] = host.querySelector("[data-g-centrality]:checked")?.value || "";
      else values[facet] = fieldValue(facet);
    }
    values.places = pickerCodes("places");
    values.website_languages = pickerCodes("website_languages");
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
  /** Shows or hides the sections that depend on the organisation check and the tag status. */
  function applyTagVisibility() {
    const no = orgChoice() === "no";
    const status = host.querySelector("[data-g-status]");
    const cannot = status?.value === "cannot_determine";
    const set = (selector, hidden) => { const el = host.querySelector(selector); if (el) el.hidden = hidden; };
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
    ctx.onSubmitted?.({id: result.data?.id, region: ctx.region, stream: "knowledge", kind: "group_tag", payload: body.payload, status: "pending", created_at: Date.now(), decided_at: null, decision_note: null});
    delete state.drafts[group.group_id];
    state.leases = state.leases.filter((g) => g.group_id !== group.group_id);
    state.index = Math.min(state.index, Math.max(0, state.leases.length - 1));
    state.error = ""; state.formError = "";
    const next = current();
    state.notice = next ? `Sent. Next group: ${next.name}` : "Sent. No more groups in this batch.";
    ctx.say?.(state.notice); render();
    host.querySelector(next ? "#g-group-name" : "h2")?.focus();
  }
  async function leaseAction(action) {
    if (state.busy || !current()) return;
    const group = current();
    if (action === "next" || action === "previous") {
      state.index = Math.max(0, Math.min(state.index + (action === "next" ? 1 : -1), state.leases.length - 1));
      state.notice = ""; state.activityOrder = []; render(); host.querySelector("#g-group-name")?.focus(); return;
    }
    state.busy = true; const generation = state.generation; setBusy(true);
    const result = await ctx.api(`/groups/${action}`, {method: "POST", body: {group_id: group.group_id}});
    if (detached() || generation !== state.generation) return;
    state.busy = false;
    if (!result?.ok) { setBusy(false); state.error = actionError(result?.error); showError("[data-g-error]", state.error); ctx.say?.(state.error); return; }
    else if (action === "renew") {
      Object.assign(group, {expires_at: result.data.expires_at, renewals: result.data.renewals});
      const button = host.querySelector('[data-g-action="renew"]'); if (button) { button.disabled = true; button.textContent = "Lease renewed"; }
      const meta = host.querySelector(".g-meta"); if (meta && group.expires_at) meta.textContent = `${group.country} · Lease until ${new Date(group.expires_at).toLocaleDateString()}`;
      setBusy(false); ctx.say?.("Lease renewed for 30 days."); return;
    }
    else {
      delete state.drafts[group.group_id];
      state.leases = state.leases.filter((g) => g.group_id !== group.group_id); state.index = Math.min(state.index, Math.max(0, state.leases.length - 1));
    }
    render();
  }
  function setBusy(on) {
    const form = host.querySelector("[data-g-tag-form]"); if (form) form.setAttribute("aria-busy", on ? "true" : "false");
    host.querySelectorAll("[data-g-submit], [data-g-action]").forEach((button) => { button.disabled = on || button.dataset.gAction === "renew" && current()?.renewals > 0; });
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
    leaseAction(button.dataset.gAction);
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
  host.addEventListener("input", () => saveDraft());
  host.addEventListener("submit", (event) => {
    if (event.target.matches?.("[data-g-tag-form]")) submitTag(event);
  });
  render();
  reload();
  return () => { alive = false; state.generation += 1; };
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
