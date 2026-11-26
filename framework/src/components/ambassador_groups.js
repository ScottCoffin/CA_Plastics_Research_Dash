// Signed-in group tagging (CG-6c). Each operation is a separate Worker call: leases are
// claimed/renewed/released independently from tag and suggestion submissions.
import {escapeHtml} from "./atlas.js";
import {safeUrl} from "./region_page.js";

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
const LABELS = {
  entity_type: "Organisation type", sector: "Sector", plastics_centrality: "How central are plastics?",
  primary_activities: "Main activities (choose 1 to 5)", geographic_scope: "Geographic scope",
};
const NICE = (value) => String(value).replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
const esc = (value) => escapeHtml(String(value ?? ""));
const isoToday = () => new Date().toISOString().slice(0, 10);
const isIsoDate = (value) => /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
const isWebUrl = (value) => {
  if (typeof value !== "string" || value.length > 500 || /\s|[<>]/.test(value)) return false;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password && !!url.hostname; } catch { return false; }
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
  const places = String(values.places || "").split(/[;,\s]+/).filter(Boolean).map((v) => v.toUpperCase());
  if (places.length > 5 || places.some((v) => !/^[A-Z]{2}(?:-[A-Z0-9]{1,3})?$/.test(v)) || new Set(places).size !== places.length) return {error: "places"};
  if (places.length) payload.places = places;
  const languages = String(values.website_languages || "").split(/[;,\s]+/).filter(Boolean).map((v) => v.toLowerCase());
  if (languages.length > 10 || languages.some((v) => !/^[a-z]{2}$/.test(v)) || new Set(languages).size !== languages.length) return {error: "website_languages"};
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
    if (!isWebUrl(url) || !isIsoDate(date) || !quote || quote.split(/\s+/).length > 25 || quote.length > 400 || /[<>\u0000-\u001f\u007f]/.test(quote)) return {error: "tier2_evidence"};
    for (const facet of [legalForm || legalNote ? "legal_form" : null, participation ? "participation_in_science" : null, themes.length ? "themes" : null, constituency.length ? "constituency" : null].filter(Boolean)) evidence.push({facet, url, accessed_at: date, quote, not_stated: false});
  }
  const affiliationRows = Array.isArray(values.affiliations) ? values.affiliations : [{target_name: values.affiliation_name, relation: values.affiliation_relation, evidence: values.affiliation_evidence}];
  if (affiliationRows.length > 10) return {error: "stated_affiliations"};
  const affiliations = [];
  for (const row of affiliationRows) {
    const name = String(row?.target_name || "").trim(); const relation = row?.relation || ""; const ev = row?.evidence || {};
    const url = String(ev.url || "").trim(); const date = String(ev.accessed_at || ""); const quote = String(ev.quote || "").trim();
    if (!(name || relation || url || quote)) continue;
    if (!name || name.length > 200 || /[<>\u0000-\u001f]/.test(name) || !TIER2_TAXONOMY.relation.includes(relation) || !isWebUrl(url) || !isIsoDate(date) || !quote || quote.split(/\s+/).length > 25 || quote.length > 400 || /[<>\u0000-\u001f\u007f]/.test(quote)) return {error: "stated_affiliations"};
    affiliations.push({target_name: name, relation, evidence: {url, accessed_at: date, quote}});
  }
  if (affiliations.length) payload.stated_affiliations = affiliations;
  for (const facet of TAG_FACETS) {
    const item = values.evidence?.[facet] || {};
    const url = String(item.url || group.url || "").trim();
    const date = String(item.accessed_at || today);
    const quote = String(item.quote || "").trim();
    const notStated = item.not_stated === true;
    if (!isWebUrl(url)) return {error: `evidence-${facet}-url`};
    if (!isIsoDate(date)) return {error: `evidence-${facet}-date`};
    if (notStated ? quote !== "" : (!quote || quote.split(/\s+/).length > 25 || quote.length > 400 || /[<>\u0000-\u001f\u007f]/.test(quote))) return {error: `evidence-${facet}-quote`};
    evidence.push({facet, url, accessed_at: date, quote: notStated ? undefined : quote, not_stated: notStated});
  }
  if (evidence.some((row) => /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/.test(JSON.stringify(row)))) return {error: "email"};
  payload.evidence = evidence;
  if (/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/.test(JSON.stringify(payload))) return {error: "email"};
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
  if (/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/.test(JSON.stringify(payload))) return {error: "email"};
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

function optionList(values, selected = "", placeholder = "Choose one") {
  return `<option value="">${esc(placeholder)}</option>${values.map((v) => `<option value="${esc(v)}"${v === selected ? " selected" : ""}>${esc(NICE(v))}</option>`).join("")}`;
}

function tagFieldsHTML(group, draft = {}) {
  const selectors = TAG_FACETS.filter((facet) => facet !== "primary_activities").map((facet) => `<div class="field"><label for="grp-${facet}">${esc(LABELS[facet])}</label><select id="grp-${facet}" data-g-field="${facet}">${optionList(facet === "plastics_centrality" ? GROUP_TAXONOMY[facet].filter((v) => v !== "cannot_determine") : GROUP_TAXONOMY[facet], draft[facet])}</select></div>`).join("");
  const activities = `<fieldset class="g-activities"><legend>${esc(LABELS.primary_activities)}</legend><div class="g-check-grid">${GROUP_TAXONOMY.primary_activities.map((v) => `<label><input type="checkbox" data-g-activity value="${esc(v)}"${draft.primary_activities?.includes(v) ? " checked" : ""}> ${esc(NICE(v))}</label>`).join("")}</div></fieldset>`;
  const langs = (Array.isArray(draft.website_languages) ? draft.website_languages.join(", ") : draft.website_languages) || "";
  const evidence = TAG_FACETS.map((facet) => `<fieldset class="g-evidence"><legend>Evidence · ${esc(LABELS[facet])}</legend>
    <div class="field"><label for="ge-${facet}-url">Source web address</label><input id="ge-${facet}-url" type="url" data-g-evidence="${facet}" data-part="url" value="${esc(draft.evidence?.[facet]?.url ?? group.url ?? "")}" placeholder="https://"></div>
    <div class="field"><label for="ge-${facet}-date">Date read</label><input id="ge-${facet}-date" type="date" data-g-evidence="${facet}" data-part="accessed_at" value="${esc(draft.evidence?.[facet]?.accessed_at || isoToday())}"></div>
    <div class="field"><label for="ge-${facet}-quote">Exact words from the page (up to 25 words)</label><textarea id="ge-${facet}-quote" rows="2" maxlength="400" data-g-evidence="${facet}" data-part="quote">${esc(draft.evidence?.[facet]?.quote || "")}</textarea></div>
    <label class="g-not-stated"><input type="checkbox" data-g-evidence="${facet}" data-part="not_stated"${draft.evidence?.[facet]?.not_stated ? " checked" : ""}><span>The page does not state this</span></label></fieldset>`).join("");
  return `<div class="g-fields">${selectors}<div class="field"><label for="grp-places">Places (ISO codes, up to five; optional)</label><input id="grp-places" type="text" data-g-field="places" value="${esc(draft.places || "")}" placeholder="US-CA, US"></div><div class="field"><label for="grp-languages">Website languages (ISO 639-1 codes, optional)</label><input id="grp-languages" type="text" data-g-field="website_languages" value="${esc(langs)}" placeholder="en, es"></div>${activities}</div>
    <section class="g-evidence-list" aria-labelledby="g-evidence-heading"><h3 id="g-evidence-heading">Evidence</h3><p class="hint">Use the group's own page where possible. Each facet needs a URL, today's date, and an exact quote of 25 words or fewer, or mark it as not stated.</p>${evidence}</section>`;
}

function tier2HTML(draft = {}) {
  const ev = draft.tier2_evidence || {};
  const affiliations = Array.isArray(draft.affiliations) && draft.affiliations.length ? draft.affiliations : [{}];
  const affiliationRows = affiliations.map((row, i) => `<fieldset class="g-evidence g-affiliation" data-g-aff-row="${i}"><legend>Stated affiliation ${i + 1}</legend><p class="hint">Record this only when the group's own page names the relationship and other organisation.</p>
      <div class="field"><label for="g-aff-name-${i}">Other organisation</label><input id="g-aff-name-${i}" type="text" maxlength="200" data-g-affiliation="target_name" data-aff-index="${i}" value="${esc(row.target_name || "")}"></div>
      <div class="field"><label for="g-aff-relation-${i}">Relationship</label><select id="g-aff-relation-${i}" data-g-affiliation="relation" data-aff-index="${i}">${optionList(TIER2_TAXONOMY.relation, row.relation)}</select></div>
      <div class="field"><label for="g-aff-url-${i}">Source web address</label><input id="g-aff-url-${i}" type="url" data-g-affiliation-evidence="url" data-aff-index="${i}" value="${esc(row.evidence?.url || "")}" placeholder="https://"></div>
      <div class="field"><label for="g-aff-date-${i}">Date read</label><input id="g-aff-date-${i}" type="date" data-g-affiliation-evidence="accessed_at" data-aff-index="${i}" value="${esc(row.evidence?.accessed_at || isoToday())}"></div>
      <div class="field"><label for="g-aff-quote-${i}">Exact words from the page (up to 25 words)</label><textarea id="g-aff-quote-${i}" rows="2" maxlength="400" data-g-affiliation-evidence="quote" data-aff-index="${i}">${esc(row.evidence?.quote || "")}</textarea></div>
      ${affiliations.length > 1 ? `<button type="button" class="link-btn" data-g-aff-action="remove" data-aff-index="${i}">Remove this affiliation</button>` : ""}</fieldset>`).join("");
  return `<details class="g-tier2" data-g-tier2${draft.tier2Open ? " open" : ""}${draft.status === "cannot_determine" || draft.notOrganisation === true ? " hidden" : ""}><summary>Optional details about the organisation</summary>
    <p class="hint">Use these only when the group's own pages state the details. Leave every field blank if you are unsure.</p>
    <div class="g-fields">
      <div class="field"><label for="g-legal-form">Legal form</label><select id="g-legal-form" data-g-tier2-field="legal_form">${optionList(TIER2_TAXONOMY.legal_form, draft.legal_form)}</select></div>
      <div class="field"><label for="g-legal-note">Legal form note (optional)</label><input id="g-legal-note" type="text" maxlength="200" data-g-tier2-field="legal_form_note" value="${esc(draft.legal_form_note || "")}"></div>
      <div class="field"><label for="g-science">Participation in science</label><select id="g-science" data-g-tier2-field="participation_in_science">${optionList(TIER2_TAXONOMY.participation_in_science, draft.participation_in_science)}</select><p class="hint">Choose a value other than “Not applicable” only when research and monitoring is a main activity.</p></div>
      <div class="field"><label for="g-themes">Themes (optional; separate with semicolons)</label><input id="g-themes" type="text" maxlength="850" data-g-tier2-field="themes" value="${esc(draft.themes || "")}"></div>
      <fieldset class="g-activities"><legend>Constituency (optional)</legend><div class="g-check-grid">${TIER2_TAXONOMY.constituency.map((v) => `<label><input type="checkbox" data-g-constituency value="${esc(v)}"${draft.constituency?.includes(v) ? " checked" : ""}> ${esc(NICE(v))}</label>`).join("")}</div></fieldset>
    </div>
    <fieldset class="g-evidence"><legend>Evidence for optional details</legend><p class="hint">One short quote can support the optional details you entered above.</p>
      <div class="field"><label for="g-tier2-url">Source web address</label><input id="g-tier2-url" type="url" data-g-tier2-evidence="url" value="${esc(ev.url || "")}" placeholder="https://"></div>
      <div class="field"><label for="g-tier2-date">Date read</label><input id="g-tier2-date" type="date" data-g-tier2-evidence="accessed_at" value="${esc(ev.accessed_at || isoToday())}"></div>
      <div class="field"><label for="g-tier2-quote">Exact words from the page (up to 25 words)</label><textarea id="g-tier2-quote" rows="2" maxlength="400" data-g-tier2-evidence="quote">${esc(ev.quote || "")}</textarea></div>
    </fieldset>
    <section class="g-affiliations" aria-labelledby="g-affiliations-h"><h4 id="g-affiliations-h">Stated affiliations (optional)</h4><p class="hint">Record partners or parent bodies only when the group's own page names the relationship and the other organisation. You can add up to ten.</p>${affiliationRows}<button type="button" class="btn" data-g-aff-action="add"${affiliations.length >= 10 ? " disabled" : ""}>Add another affiliation</button></section>
  </details>`;
}

/** Mounts one assignment at a time and guards detached/stale responses after navigation. */
export function mountGroups(host, ctx) {
  const state = {leases: [], remaining: 0, index: 0, loading: true, busy: false, error: "", formError: "", generation: 0, suggested: false, drafts: {}, suggestion: {}, activityOrder: []};
  let alive = true;
  const current = () => state.leases[state.index] || null;
  const detached = () => !alive || !host.isConnected;
  const render = () => {
    if (detached()) return;
    const group = current();
    const draft = group ? state.drafts[group.group_id] || {} : {};
    state.activityOrder = Array.isArray(draft.primary_activities) ? [...draft.primary_activities] : [];
    const groupLink = safeUrl(group?.url);
    const expiry = group?.expires_at ? new Date(group.expires_at).toLocaleDateString() : "";
    const sent = (ctx.submissions || []).filter((row) => row?.region === ctx.region && row.stream === "knowledge" && ["group_tag", "group_suggest"].includes(row.kind)).sort((a, b) => (Number(b.created_at) || 0) - (Number(a.created_at) || 0));
    const sentHTML = sent.length ? `<section class="g-history" aria-labelledby="g-history-h"><h3 id="g-history-h">Group work you sent</h3><ul>${sent.map((row) => `<li><strong>${row.kind === "group_suggest" ? esc(row.payload?.name || "Group suggestion") : "Group tag"}</strong><span>${row.status === "approved" ? "Approved" : row.status === "rejected" ? "Not accepted" : "Waiting for review"}</span></li>`).join("")}</ul></section>` : "";
    host.innerHTML = `<p class="ws-crumb"><button type="button" class="link-btn" data-ws-action="home">Back to your tasks</button></p>
      <h2 tabindex="-1">Tag local groups</h2><p class="lede">Check each group's public pages and record what they say about their work in ${esc(ctx.regionName)}. Do not guess.</p>
      <p class="ws-error" role="alert" tabindex="-1" data-g-error${state.error ? "" : " hidden"}>${esc(state.error)}</p>
      ${state.error ? `<button type="button" class="btn" data-g-action="reload"${state.busy ? " disabled" : ""}>Reload assignments</button>` : ""}
      ${state.loading ? `<p class="status" role="status">Loading your assigned groups…</p>` : ""}
      ${!state.loading && !state.error && !group ? `<section class="g-empty"><h3>No groups assigned right now</h3><p>${state.remaining > 0 ? `${state.remaining} more groups are available in this region. Reload to claim the next batch.` : "There are no more unclaimed groups in this region right now."}</p><button type="button" class="btn" data-g-action="reload"${state.busy ? " disabled" : ""}>Reload assignments</button></section>` : ""}
      ${group ? `<div class="g-progress"><p>Group ${state.index + 1} of ${state.leases.length} in your batch</p><progress aria-label="Group progress" max="${state.leases.length}" value="${state.index + 1}"></progress></div>
        <section class="g-group" aria-labelledby="g-group-name"><h3 id="g-group-name">${esc(group.name)}</h3><p class="g-meta">${esc(group.country)}${expiry ? ` · Lease until ${esc(expiry)}` : ""}</p>
        ${groupLink ? `<p><a href="${esc(groupLink)}" target="_blank" rel="noopener noreferrer">Open the group's website<span class="sr"> (opens in a new tab)</span></a></p>` : `<p class="hint">No website is listed for this group.</p>`}
        <div class="g-lease-actions"><button type="button" class="btn" data-g-action="renew"${group.renewals > 0 || state.busy ? " disabled" : ""}>${group.renewals > 0 ? "Lease renewed" : "Renew lease"}</button><button type="button" class="link-btn" data-g-action="release"${state.busy ? " disabled" : ""}>Return this group to the pool</button></div>
        <form data-g-tag-form novalidate aria-busy="${state.busy}"><fieldset class="g-org-check"><legend>Organisation check</legend><p>Does this entry represent a collective organisation, rather than an individual or single-person practice?</p><label><input type="radio" name="g-org" value="yes" data-g-org${draft.notOrganisation === false ? " checked" : ""}> Yes, it is a collective</label><label><input type="radio" name="g-org" value="no" data-g-org${draft.notOrganisation === true ? " checked" : ""}> No, or this is a personal profile</label></fieldset>
        <div data-g-tag-fields${draft.notOrganisation === true ? " hidden" : ""}>${tagFieldsHTML(group, draft)}</div>
        ${tier2HTML(draft)}
        <div class="field g-status-field"><label for="g-status">Tag status</label><select id="g-status" data-g-status${draft.notOrganisation === true ? " disabled" : ""}><option value="ambassador_tagged"${draft.status !== "cannot_determine" ? " selected" : ""}>I can tag this group</option><option value="cannot_determine"${draft.status === "cannot_determine" ? " selected" : ""}>I cannot determine this from the available information</option></select></div>
        <div class="field" data-g-reason-wrap${draft.status === "cannot_determine" ? "" : " hidden"}><label for="g-reason">Why can you not determine this?</label><select id="g-reason" data-g-reason>${optionList(CANNOT_REASONS, draft.reason, "Choose a reason")}</select></div>
        <div class="ws-error g-form-error" role="alert" tabindex="-1" data-g-form-error${state.formError ? "" : " hidden"}>${esc(state.formError)}</div>
        <div class="g-submit-row"><button type="submit" class="btn solid" data-g-submit${state.busy ? " disabled" : ""}>Send tag for review</button>${state.index > 0 ? `<button type="button" class="btn" data-g-action="previous">Previous group</button>` : ""}${state.index + 1 < state.leases.length ? `<button type="button" class="btn" data-g-action="next">Skip to next group</button>` : ""}</div></form></section>` : ""}
      <section class="g-suggest" aria-labelledby="g-suggest-h"><h3 id="g-suggest-h">Suggest a missing group</h3><p>Only suggest a collective organisation with a public web page. Suggestions are reviewed before appearing.</p>
        <form data-g-suggest-form novalidate><fieldset class="g-org-check"><legend>Organisation check</legend><p>Is this a collective organisation, rather than an individual or single-person practice?</p><label><input type="radio" name="g-suggest-org" value="yes" data-g-suggest-org${state.suggestion.isOrganisation === true ? " checked" : ""}> Yes, it is a collective</label><label><input type="radio" name="g-suggest-org" value="no" data-g-suggest-org${state.suggestion.isOrganisation === false ? " checked" : ""}> No</label></fieldset><div class="g-fields"><div class="field"><label for="gs-name">Group name</label><input id="gs-name" type="text" maxlength="200" data-g-suggest="name" value="${esc(state.suggestion.name || "")}"></div><div class="field"><label for="gs-url">Public web address</label><input id="gs-url" type="url" maxlength="500" placeholder="https://" data-g-suggest="url" value="${esc(state.suggestion.url || "")}"></div><div class="field"><label for="gs-country">Country code (optional)</label><input id="gs-country" type="text" maxlength="2" data-g-suggest="country" placeholder="US" value="${esc(state.suggestion.country || "")}"></div><div class="field g-wide"><label for="gs-note">Note (optional)</label><textarea id="gs-note" rows="3" maxlength="1000" data-g-suggest="note">${esc(state.suggestion.note || "")}</textarea></div></div><div class="ws-error g-form-error" role="alert" tabindex="-1" data-g-suggest-error hidden></div><button type="submit" class="btn solid" data-g-suggest-submit${state.busy ? " disabled" : ""}>Suggest group</button></form>
        ${state.suggested ? `<p class="g-success" role="status">Suggestion sent for review.</p>` : ""}</section>${sentHTML}`;
  };
  const actionError = (code) => errorText(code, ctx.errorText);
  async function reload() {
    if (detached() || state.busy) return;
    state.loading = true; state.error = ""; state.leases = []; state.index = 0;
    const generation = ++state.generation; render();
    const result = await ctx.api(`/groups/batch?region=${encodeURIComponent(ctx.region)}`);
    if (detached() || generation !== state.generation) return;
    state.loading = false;
    if (!result?.ok) state.error = actionError(result?.error);
    else { state.leases = Array.isArray(result.data?.leases) ? result.data.leases : []; state.remaining = Number(result.data?.remaining_in_region) || 0; }
    render();
  }
  function tagValues() {
    const orgChoice = host.querySelector("[data-g-org]:checked")?.value;
    const values = {region: ctx.region, notOrganisation: orgChoice === undefined ? undefined : orgChoice === "no"};
    values.status = host.querySelector("[data-g-status]")?.value;
    values.reason = host.querySelector("[data-g-reason]")?.value;
    for (const facet of TAG_FACETS) {
      if (facet === "primary_activities") values[facet] = state.activityOrder.filter((v) => host.querySelector(`[data-g-activity][value="${v}"]`)?.checked);
      else values[facet] = host.querySelector(`[data-g-field="${facet}"]`)?.value || "";
    }
    values.places = host.querySelector('[data-g-field="places"]')?.value || "";
    values.website_languages = host.querySelector('[data-g-field="website_languages"]')?.value || "";
    values.legal_form = host.querySelector('[data-g-tier2-field="legal_form"]')?.value || "";
    values.legal_form_note = host.querySelector('[data-g-tier2-field="legal_form_note"]')?.value || "";
    values.participation_in_science = host.querySelector('[data-g-tier2-field="participation_in_science"]')?.value || "";
    values.themes = host.querySelector('[data-g-tier2-field="themes"]')?.value || "";
    values.constituency = [...host.querySelectorAll("[data-g-constituency]:checked")].map((el) => el.value);
    values.tier2_evidence = {};
    host.querySelectorAll("[data-g-tier2-evidence]").forEach((el) => { values.tier2_evidence[el.dataset.gTier2Evidence] = el.value; });
    values.affiliations = [...host.querySelectorAll("[data-g-aff-row]")].map((row) => {
      const get = (selector) => row.querySelector(selector);
      return {
        target_name: get('[data-g-affiliation="target_name"]')?.value || "",
        relation: get('[data-g-affiliation="relation"]')?.value || "",
        evidence: Object.fromEntries([...row.querySelectorAll("[data-g-affiliation-evidence]")].map((el) => [el.dataset.gAffiliationEvidence, el.value])),
      };
    });
    values.evidence = {};
    for (const facet of TAG_FACETS) {
      values.evidence[facet] = {};
      host.querySelectorAll(`[data-g-evidence="${facet}"]`).forEach((el) => { values.evidence[facet][el.dataset.part] = el.type === "checkbox" ? el.checked : el.value; });
    }
    values.tier2Open = host.querySelector("[data-g-tier2]")?.open === true;
    return values;
  }
  function saveDraft() {
    const group = current(); if (!group || !host.querySelector("[data-g-tag-form]")) return;
    state.drafts[group.group_id] = tagValues();
  }
  function saveSuggestionDraft() {
    if (!host.querySelector("[data-g-suggest-form]")) return;
    for (const key of ["name", "url", "country", "note"]) state.suggestion[key] = host.querySelector(`[data-g-suggest="${key}"]`)?.value || "";
    const selected = host.querySelector("[data-g-suggest-org]:checked")?.value;
    state.suggestion.isOrganisation = selected === undefined ? undefined : selected === "yes";
  }
  function showError(selector, text) {
    const box = host.querySelector(selector); if (!box) return;
    box.textContent = text; box.hidden = false; box.focus();
  }
  async function submitTag(event) {
    event.preventDefault(); if (state.busy || !current()) return;
    const body = groupTagPayload({group: current(), values: tagValues()});
    if (body.error) { state.formError = body.error.startsWith("evidence-") ? "Add a valid source, date and quote for each Tier 1 facet, or select ‘The page does not state this’. Quotes must be no more than 25 words." : `Check ${NICE(body.error)} and try again.`; showError("[data-g-form-error]", state.formError); focusFailure(body.error); return; }
    state.busy = true; const group = current(); const generation = state.generation; setBusy(true);
    const result = await ctx.api("/submissions", {method: "POST", body});
    if (detached() || generation !== state.generation) return;
    state.busy = false;
    if (!result?.ok) { setBusy(false); const message = actionError(result?.error); state.formError = message; showError("[data-g-form-error]", message); ctx.say?.(message); return; }
    ctx.onSubmitted?.({id: result.data?.id, region: ctx.region, stream: "knowledge", kind: "group_tag", payload: body.payload, status: "pending", created_at: Date.now(), decided_at: null, decision_note: null});
    delete state.drafts[group.group_id];
    state.leases = state.leases.filter((g) => g.group_id !== group.group_id); state.index = Math.min(state.index, Math.max(0, state.leases.length - 1));
    state.error = ""; state.formError = ""; ctx.say?.("Tag sent for review."); render(); host.querySelector("h2")?.focus();
  }
  async function leaseAction(action) {
    if (state.busy || !current()) return;
    const group = current();
    if (action === "next" || action === "previous") { state.index = Math.max(0, Math.min(state.index + (action === "next" ? 1 : -1), state.leases.length - 1)); state.activityOrder = []; render(); host.querySelector("#g-group-name")?.focus(); return; }
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
    else { state.leases = state.leases.filter((g) => g.group_id !== group.group_id); state.index = Math.min(state.index, Math.max(0, state.leases.length - 1)); }
    render();
  }
  async function submitSuggestion(event) {
    event.preventDefault(); if (state.busy) return;
    saveSuggestionDraft();
    const value = (key) => state.suggestion[key] || "";
    const body = groupSuggestionPayload({region: ctx.region, name: value("name"), url: value("url"), country: value("country"), note: value("note"), isOrganisation: state.suggestion.isOrganisation});
    if (body.error) {
      const message = body.error === "organisation_check"
        ? state.suggestion.isOrganisation === false ? "Only collective organisations can be suggested here. This entry cannot be submitted." : "Confirm that the suggestion is a collective organisation before sending it."
        : `Check ${NICE(body.error)} and try again.`;
      showError("[data-g-suggest-error]", message);
      if (body.error === "organisation_check") host.querySelector("[data-g-suggest-org]")?.focus();
      return;
    }
    state.busy = true; const submitButton = host.querySelector("[data-g-suggest-submit]"); if (submitButton) submitButton.disabled = true;
    const result = await ctx.api("/submissions", {method: "POST", body});
    if (detached()) return;
    state.busy = false;
    if (!result?.ok) { if (submitButton) submitButton.disabled = false; showError("[data-g-suggest-error]", actionError(result?.error)); return; }
    ctx.onSubmitted?.({id: result.data?.id, region: ctx.region, stream: "knowledge", kind: "group_suggest", payload: body.payload, status: "pending", created_at: Date.now(), decided_at: null, decision_note: null});
    state.suggestion = {}; state.suggested = true; render(); ctx.say?.("Group suggestion sent for review."); host.querySelector("#g-suggest-h")?.focus();
  }
  host.addEventListener("click", (event) => {
    if (event.target.closest?.(".g-tier2 > summary")) {
      const group = current();
      if (group) state.drafts[group.group_id] = {...(state.drafts[group.group_id] || {}), tier2Open: !host.querySelector("[data-g-tier2]")?.open};
    }
    const affButton = event.target.closest?.("[data-g-aff-action]");
    if (affButton) {
      if (state.busy) return;
      saveDraft();
      saveSuggestionDraft();
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
    const button = event.target.closest?.("[data-g-action]"); if (!button) return;
    saveDraft();
    saveSuggestionDraft();
    if (button.dataset.gAction === "reload") return reload();
    leaseAction(button.dataset.gAction);
  });
  host.addEventListener("change", (event) => {
    if (event.target.matches?.("[data-g-activity]")) { const value = event.target.value; state.activityOrder = state.activityOrder.filter((v) => v !== value); if (event.target.checked) state.activityOrder.push(value); }
    saveDraft();
    if (event.target.matches?.("[data-g-suggest], [data-g-suggest-org]")) saveSuggestionDraft();
    if (event.target.matches?.("[data-g-status]")) { const wrap = host.querySelector("[data-g-reason-wrap]"); if (wrap) wrap.hidden = event.target.value !== "cannot_determine"; const fields = host.querySelector("[data-g-tag-fields]"); if (fields) fields.hidden = event.target.value === "cannot_determine" || host.querySelector('[data-g-org]:checked')?.value === "no"; const tier2 = host.querySelector("[data-g-tier2]"); if (tier2) tier2.hidden = event.target.value === "cannot_determine"; }
    if (event.target.matches?.("[data-g-org]")) { const fields = host.querySelector("[data-g-tag-fields]"); const tier2 = host.querySelector("[data-g-tier2]"); const submit = host.querySelector("[data-g-submit]"); const status = host.querySelector("[data-g-status]"); if (fields) fields.hidden = event.target.value === "no" || status?.value === "cannot_determine"; if (tier2) tier2.hidden = event.target.value === "no" || status?.value === "cannot_determine"; if (submit) submit.textContent = event.target.value === "no" ? "Mark not an organisation" : "Send tag for review"; if (status) status.disabled = event.target.value === "no"; }
  });
  host.addEventListener("input", (event) => {
    if (event.target.closest?.("[data-g-tag-form]")) saveDraft();
    if (event.target.matches?.("[data-g-suggest], [data-g-suggest-org]")) saveSuggestionDraft();
  });
  host.addEventListener("submit", (event) => {
    if (event.target.matches?.("[data-g-tag-form]")) submitTag(event);
    if (event.target.matches?.("[data-g-suggest-form]")) submitSuggestion(event);
  });
  function setBusy(on) {
    const form = host.querySelector("[data-g-tag-form]"); if (form) form.setAttribute("aria-busy", on ? "true" : "false");
    host.querySelectorAll("[data-g-submit], [data-g-action], [data-g-suggest-submit]").forEach((button) => { button.disabled = on || button.dataset.gAction === "renew" && current()?.renewals > 0; });
    const tag = host.querySelector("[data-g-submit]"); if (tag) tag.textContent = on ? "Sending…" : host.querySelector('[data-g-org][value="no"]')?.checked ? "Mark not an organisation" : "Send tag for review";
  }
  function focusFailure(error) {
    if (!error) return;
    const evidence = /^evidence-(.+)-(url|date|quote)$/.exec(error);
    const target = evidence
      ? host.querySelector(`[data-g-evidence="${evidence[1]}"][data-part="${evidence[2] === "date" ? "accessed_at" : evidence[2]}"]`)
      : error === "primary_activities" ? host.querySelector("[data-g-activity]")
        : error === "organisation_check" ? host.querySelector("[data-g-org]")
            : error === "cannot_determine_reason" ? host.querySelector("[data-g-reason]")
              : error === "stated_affiliations" ? firstInvalidAffiliationControl()
                : error === "tier2_evidence" ? host.querySelector("[data-g-tier2-evidence='url']")
            : host.querySelector(`[data-g-field="${error}"]`);
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
  render();
  reload();
  return () => { alive = false; state.generation += 1; };
}
