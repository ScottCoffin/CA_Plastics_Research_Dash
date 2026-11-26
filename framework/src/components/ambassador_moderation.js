// Moderation page for the owner and region leads (AMB-1 front end slice 2c; docs/AMBASSADORS_SPEC.md, section 5 and
// "Front end slice 2c"). The static markup is in ambassador_moderation.md. This module reads /me and the Worker's
// /moderation/queue, shows one item per screen, and saves each decision as soon as it is clicked. Submitted text is
// written with textContent only, and links are built only for http(s) URLs. Pure helpers are exported for
// tests/framework_ambassador_moderation_runtime.mjs; nothing touches the DOM at import time.
import {REGION_NAMES, api, apiUrl, errorText} from "./ambassador_signup.js";

/** Time estimate per queue item (docs/AMBASSADORS_SPEC.md, section 12: about one minute). */
export const MINUTES_PER_ITEM = 1;
/** Lead promotion estimate (section 12: about two minutes). */
export const MINUTES_PER_PROMOTION = 2;
export const NOTE_MAX = 1000;
export const NOT_MODERATOR_TEXT = "This page is for the owner and region leads.";
const SIGN_IN_TEXT = "Moderation is for the owner and region leads. Sign in with ORCID to moderate.";
const URL_RE = /^https?:\/\/[^\s<>"]+$/i;
// Control characters (except tab and newline) and angle brackets: the Worker refuses them in a note.
const NOTE_UNSAFE = /[<>\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/;

const ERROR_TEXT = {
  self_decision: "You cannot decide your own submission.",
  already_decided: "Someone has already decided this item. Use Next to go on.",
  not_found: "This item is no longer in the queue. Use Next to go on.",
  invalid_note: `The note must be plain text of up to ${NOTE_MAX} characters, with no < or > signs.`,
  rate_limited: "There have been too many moderation actions this hour. Wait a while and try again.",
  self_promotion: "You cannot make your own account a lead.",
  is_owner: "The owner's account cannot be changed here.",
  not_active: "Only an active ambassador can become a lead.",
  not_region_member: "That ambassador is not an active member of the region you chose.",
  invalid_ambassador: "Enter the ambassador's id.",
  invalid_region: "Choose a region.",
  cannot_suspend_owner: "The owner's account cannot be suspended.",
  allowlist_fields_required: "To approve an institution, choose its region, enter its email domain and choose its type.",
  invalid_domain: "Enter the domain in lowercase, such as oehha.ca.gov, with no www. and no path.",
  free_mail_domain: "A free-mail provider cannot be an institution's domain. Enter the institution's own domain.",
  invalid_institution_type: "Choose one of the four institution types.",
};

/** Institution types an approved proposal can carry (the Worker's list, in the same order). */
export const INSTITUTION_TYPE_NAMES = {education: "Education", government: "Government", nonprofit: "Nonprofit", facility: "Facility"};

/** Maps a Worker error code to a plain sentence. `action` is "decide", "lead" or "suspend" (for the 403 text). */
export function moderationErrorText(code, action = "") {
  if (code === "forbidden") {
    return action === "suspend" ? "Only the owner can suspend an account." : NOT_MODERATOR_TEXT;
  }
  return Object.prototype.hasOwnProperty.call(ERROR_TEXT, code) ? ERROR_TEXT[code] : errorText(code);
}

/** The queue URL, filtered by region when one is chosen ("" means all regions). */
export function queueUrl(region) {
  return region ? `/moderation/queue?region=${encodeURIComponent(region)}` : "/moderation/queue";
}

/** One list for the page: submissions and proposals, oldest first (ties: submissions first, then by id). */
export function sortQueue(items) {
  const typeRank = (type) => (type === "submission" ? 0 : 1);
  return [...items].sort(
    (a, b) =>
      (a.created_at - b.created_at) || (typeRank(a.type) - typeRank(b.type)) || (a.id - b.id),
  );
}

/** Flattens the Worker's {submissions, proposals} queue into one sorted list. Proposals carry no region. */
export function normaliseItems(queue) {
  const submissions = (queue?.submissions || []).map((s) => ({
    type: "submission",
    id: s.id,
    region: s.region || null,
    kind: s.kind,
    payload: s.payload,
    created_at: s.created_at,
    submitter: s.submitter || {},
    own: Boolean(s.own),
    status: null,
  }));
  const proposals = (queue?.proposals || []).map((p) => ({
    type: "proposal",
    id: p.id,
    region: null,
    kind: p.kind,
    payload: p.payload,
    created_at: p.created_at,
    submitter: p.submitter || {},
    own: Boolean(p.own),
    status: null,
    // An unlisted institution whose work email was confirmed: the domain it was confirmed at, and what was proposed.
    email_confirmed: Boolean(p.email_confirmed),
    confirmed_domain: p.confirmed_domain || null,
    proposed_region: p.proposed_region || null,
    proposed_domain: p.proposed_domain || null,
  }));
  return sortQueue([...submissions, ...proposals]);
}

/** Items not yet decided in this view. */
export function pendingItems(items) {
  return (items || []).filter((item) => !item.status);
}

export function estimateMinutes(count) {
  return Math.max(0, count) * MINUTES_PER_ITEM;
}

export function estimateText(count) {
  if (count <= 0) return "Nothing is waiting for review.";
  const minutes = estimateMinutes(count);
  return `Estimated time: about ${minutes} ${minutes === 1 ? "minute" : "minutes"} for ${count} ${count === 1 ? "item" : "items"}.`;
}

/** "3 waiting: 2 submissions, 1 proposal." (undecided items only). */
export function countsText(items) {
  const open = pendingItems(items);
  const submissions = open.filter((item) => item.type === "submission").length;
  const proposals = open.length - submissions;
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  return `${plural(open.length, "item", "items")} waiting: ${plural(submissions, "submission", "submissions")}, ${plural(proposals, "proposal", "proposals")}.`;
}

export function labelFor(key) {
  const text = String(key).replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** A field value as plain text. Arrays are joined; objects are shown as JSON text. */
export function valueText(value) {
  if (Array.isArray(value)) return value.map(valueText).join(", ");
  if (value !== null && typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** The https or http address in a value, or null. Only these become links. */
export function safeHref(value) {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return URL_RE.test(trimmed) ? trimmed : null;
}

/** Rows for the submitted fields: {label, value, href}. Empty values are skipped. */
export function fieldRows(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return [];
  return Object.entries(payload)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => ({label: labelFor(key), value: valueText(value), href: safeHref(value)}));
}

/** The submitter's display name, only when the Worker says credit is public. Otherwise null. */
export function creditName(submitter) {
  if (!submitter || submitter.credit_public !== true) return null;
  const name = typeof submitter.display_name === "string" ? submitter.display_name.trim() : "";
  return name || null;
}

/** YYYY-MM-DD from a millisecond timestamp (UTC), or a plain fallback. */
export function dateText(ms) {
  const date = new Date(ms);
  return Number.isFinite(ms) && !Number.isNaN(date.getTime()) ? date.toISOString().slice(0, 10) : "Date not recorded";
}

/** A note problem as a sentence, or null. Notes are optional. */
export function noteProblem(note) {
  const text = String(note ?? "").trim();
  if (text.length > NOTE_MAX || NOTE_UNSAFE.test(text)) return moderationErrorText("invalid_note");
  return null;
}

/**
 * The email domain to prefill from a proposal's URL: its host, lowercase, with a leading "www." removed. "" when the
 * value is not an http(s) address. Moderators can edit it before approving.
 */
export function prefillDomain(url) {
  const href = safeHref(url);
  if (!href) return "";
  try {
    return new URL(href).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return "";
  }
}

/** "Email confirmed at <domain>" for a proposal whose work email was confirmed; "" otherwise. */
export function confirmedText(item) {
  return item?.type === "proposal" && item.email_confirmed && item.confirmed_domain
    ? `Email confirmed at ${item.confirmed_domain}`
    : "";
}

/** The region to prefill for an approval: the proposal's own region when it is a known slug, else "". */
export function prefillRegion(item) {
  const slug = item?.proposed_region;
  return slug && Object.prototype.hasOwnProperty.call(REGION_NAMES, slug) ? slug : "";
}

/** The domain to prefill: the proposed domain when the proposal has one, else the URL's host (prefillDomain). */
export function prefillAllowDomain(item) {
  return item?.proposed_domain || prefillDomain(item?.payload?.url);
}

/** Whether a proposal is an institution, the only kind whose approval needs region, domain and type. */
export function needsAllowlist(item) {
  return Boolean(item) && item.type === "proposal" && item.kind === "institution";
}

/** The three allowlist fields, trimmed. The Worker checks the domain's format and free-mail status. */
export function allowlistBody({region, domain, institution_type}) {
  return {region: String(region ?? ""), domain: String(domain ?? "").trim(), institution_type: String(institution_type ?? "")};
}

export function checkAllowlist({region, domain, institution_type}) {
  const errors = [];
  if (!Object.prototype.hasOwnProperty.call(REGION_NAMES, region)) errors.push({field: "allow-region", message: "Choose a region."});
  if (!String(domain ?? "").trim()) errors.push({field: "allow-domain", message: "Enter the institution's email domain."});
  if (!Object.prototype.hasOwnProperty.call(INSTITUTION_TYPE_NAMES, institution_type)) {
    errors.push({field: "allow-type", message: "Choose an institution type."});
  }
  return errors;
}

// ---- request bodies and checks (pure) ------------------------------------------------------------------------
/** The decision body. Only an approval carries the allowlist fields (the Worker needs them for institutions). */
export function decisionBody({type, id, decision, note, allowlist}) {
  const body = {type, id, decision};
  const text = String(note ?? "").trim();
  if (text) body.note = text;
  if (decision === "approve" && allowlist) Object.assign(body, allowlistBody(allowlist));
  return body;
}

export function checkLead({ambassadorId, region}) {
  const errors = [];
  if (!String(ambassadorId ?? "").trim()) errors.push({field: "lead-id", message: "Enter the ambassador's id."});
  if (!Object.prototype.hasOwnProperty.call(REGION_NAMES, region)) {
    errors.push({field: "lead-region", message: "Choose a region."});
  }
  return errors;
}

export function leadBody({ambassadorId, region}) {
  return {ambassador_id: String(ambassadorId ?? "").trim(), region};
}

export function checkSuspend({ambassadorId}) {
  return String(ambassadorId ?? "").trim() ? [] : [{field: "suspend-id", message: "Enter the ambassador's id."}];
}

export function suspendBody({ambassadorId}) {
  return {ambassador_id: String(ambassadorId ?? "").trim()};
}

// ---- DOM ----------------------------------------------------------------------------------------------------
let root = null;
let body = null;
let statusEl = null;
let state = null; // {region, items, index}
let view = null; // the item on screen: {heading, approve, reject, note, result, item}
let pendingSuspend = null;

/** Small element builder. Children that are strings become text nodes, never HTML. */
function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  node.append(...children);
  return node;
}

function setStatus(text) {
  if (statusEl) statusEl.textContent = text;
}

/** Region options; `first` is the label of the empty choice, or null for none. */
const regionOptions = (first) =>
  [first === null ? "" : `<option value="">${first}</option>`, ...Object.entries(REGION_NAMES).map(([slug, label]) => `<option value="${slug}">${label}</option>`)].join("");

const SHELL = `
<div class="mod-tools">
  <div class="field">
    <label for="mod-region">Region</label>
    <select id="mod-region" class="mod-select">${regionOptions("All regions")}</select>
  </div>
  <p class="mod-count" data-mod-counts role="status" aria-live="polite"></p>
  <p class="hint" data-mod-estimate></p>
</div>
<div data-mod-queue class="mod-queue"></div>
<section class="sec" aria-labelledby="h-lead">
  <div class="sec-head"><h2 id="h-lead">Make a region lead</h2><span class="sec-note">About 2 minutes each</span></div>
  <p class="hint">Leads moderate and can make further leads. The ambassador must be an active member of the region you choose.</p>
  <form data-form="lead" class="mod-form" novalidate>
    <div class="field">
      <label for="lead-id">Ambassador id</label>
      <input id="lead-id" name="ambassador_id" type="text" maxlength="64" autocomplete="off">
    </div>
    <div class="field">
      <label for="lead-region">Region</label>
      <select id="lead-region" name="region" class="mod-select"><option value="">Choose a region</option>${regionOptions(null)}</select>
    </div>
    <div class="btns"><button type="submit" class="btn solid">Make lead</button></div>
    <p class="hint mod-result" data-lead-result role="status" aria-live="polite"></p>
  </form>
</section>
<section class="sec" aria-labelledby="h-suspend">
  <div class="sec-head"><h2 id="h-suspend">Suspend an account</h2><span class="sec-note">Owner only</span></div>
  <p class="hint">A suspended ambassador's sessions end at once and they cannot sign in. Their pending items leave the queue.</p>
  <form data-form="suspend-ask" class="mod-form" novalidate>
    <div class="field">
      <label for="suspend-id">Ambassador id</label>
      <input id="suspend-id" name="ambassador_id" type="text" maxlength="64" autocomplete="off">
    </div>
    <div class="btns"><button type="submit" class="btn">Suspend this account</button></div>
  </form>
  <div data-suspend-confirm></div>
  <p class="hint mod-result" data-suspend-result role="status" aria-live="polite"></p>
</section>`;

function shellHost() {
  return body.querySelector("[data-mod-queue]");
}

function updateCounts() {
  if (!state) return;
  const open = pendingItems(state.items).length;
  body.querySelector("[data-mod-counts]").textContent = countsText(state.items);
  body.querySelector("[data-mod-estimate]").textContent = estimateText(open);
}

function setResult(text, isError = false) {
  if (!view) return;
  view.result.textContent = text;
  view.result.className = isError ? "mod-result is-error" : "mod-result";
}

function setBusy(busy) {
  if (!view) return;
  const locked = busy || Boolean(view.item.status);
  view.approve.disabled = locked;
  view.reject.disabled = locked;
  view.note.disabled = locked;
  if (view.allow) {
    for (const field of Object.values(view.allow)) field.disabled = locked;
  }
}

/** Region, email domain and type for an institution proposal. The domain is prefilled from the proposal's URL. */
function allowlistFields(item) {
  const region = el("select", {id: "mod-allow-region", name: "region", class: "mod-select"}, [
    el("option", {value: ""}, ["Choose a region"]),
    ...Object.entries(REGION_NAMES).map(([slug, label]) => el("option", {value: slug}, [label])),
  ]);
  region.value = prefillRegion(item);
  const domain = el("input", {id: "mod-allow-domain", name: "domain", type: "text", maxlength: "253", autocomplete: "off", spellcheck: "false", value: prefillAllowDomain(item)});
  const type = el("select", {id: "mod-allow-type", name: "institution_type", class: "mod-select"}, [
    el("option", {value: ""}, ["Choose a type"]),
    ...Object.entries(INSTITUTION_TYPE_NAMES).map(([slug, label]) => el("option", {value: slug}, [label])),
  ]);
  const group = el("fieldset", {class: "mod-allow"}, [
    el("legend", {}, ["If approved, this institution joins the eligible list"]),
    el("div", {class: "field"}, [el("label", {for: "mod-allow-region"}, ["Region"]), region]),
    el("div", {class: "field"}, [el("label", {for: "mod-allow-domain"}, ["Email domain"]), domain]),
    el("div", {class: "field"}, [el("label", {for: "mod-allow-type"}, ["Type"]), type]),
  ]);
  return {group, fields: {region, domain, institution_type: type}};
}

function itemDetails(item) {
  const list = el("dl", {class: "mod-facts"}, [
    el("dt", {}, ["Kind"]), el("dd", {}, [item.kind || "Not stated"]),
    el("dt", {}, ["Region"]), el("dd", {}, [item.region ? REGION_NAMES[item.region] || item.region : "Not stated"]),
    el("dt", {}, ["Date"]), el("dd", {}, [dateText(item.created_at)]),
  ]);
  const confirmed = confirmedText(item);
  if (confirmed) list.append(el("dt", {}, ["Email"]), el("dd", {}, [confirmed]));
  const name = creditName(item.submitter);
  if (name) list.append(el("dt", {}, ["Submitted by"]), el("dd", {}, [name]));
  return list;
}

function itemFields(item) {
  const rows = fieldRows(item.payload);
  if (rows.length === 0) return el("p", {class: "hint"}, ["No details were submitted."]);
  const list = el("dl", {class: "mod-fields"});
  for (const row of rows) {
    const value = row.href
      ? el("a", {href: row.href, target: "_blank", rel: "noopener noreferrer nofollow"}, [row.value])
      : row.value;
    list.append(el("dt", {}, [row.label]), el("dd", {}, [value]));
  }
  return list;
}

/** Builds the one item on screen. Its heading takes focus; Approve and Reject save at once. */
function renderItem(item, index, total) {
  const heading = el("h2", {tabindex: "-1", class: "mod-heading"}, [
    `${item.type === "submission" ? "Submission" : "Proposal"} ${index + 1} of ${total}`,
  ]);
  const note = el("textarea", {id: "mod-note", name: "note", rows: "3", maxlength: String(NOTE_MAX)});
  const result = el("p", {class: "hint mod-result", role: "status", "aria-live": "polite"});
  const approve = el("button", {type: "button", class: "btn solid"}, ["Approve"]);
  const reject = el("button", {type: "button", class: "btn"}, ["Reject"]);
  const next = el("button", {type: "button", class: "btn"}, ["Next item"]);
  const allow = needsAllowlist(item) ? allowlistFields(item) : null;
  view = {heading, approve, reject, note, result, item, allow: allow ? allow.fields : null};
  approve.addEventListener("click", () => decide(item, "approve"));
  reject.addEventListener("click", () => decide(item, "reject"));
  next.addEventListener("click", () => {
    state.index += 1;
    renderQueue();
  });

  const article = el("article", {class: "mod-item", "aria-label": `${item.type} ${item.id}`}, [
    heading,
    itemDetails(item),
    itemFields(item),
    ...(item.own ? [el("p", {class: "hint"}, ["This one is your own. Another moderator must decide it."])] : []),
    el("div", {class: "field"}, [el("label", {for: "mod-note"}, ["Note (optional)"]), note]),
    ...(allow ? [allow.group] : []),
    el("div", {class: "btns"}, [approve, reject]),
    result,
    el("div", {class: "btns"}, [next]),
  ]);
  if (item.status) {
    setResult(`Saved as ${item.status}.`);
  }
  setBusy(false);
  return article;
}

/** Shows the current item (or the empty and finished states) and moves focus to its heading. */
function renderQueue() {
  const host = shellHost();
  updateCounts();
  if (!host) return;
  if (state.items.length === 0) {
    host.replaceChildren(el("p", {}, [state.region ? `Nothing is waiting for review in ${REGION_NAMES[state.region] || state.region}.` : "Nothing is waiting for review."]));
    view = null;
    setStatus("Nothing is waiting for review.");
    return;
  }
  if (state.index >= state.items.length) {
    const refresh = el("button", {type: "button", class: "btn"}, ["Refresh the queue"]);
    refresh.addEventListener("click", () => loadQueue(state.region));
    host.replaceChildren(el("p", {}, ["That was the last item in this view."]), el("div", {class: "btns"}, [refresh]));
    view = null;
    setStatus("No more items in this view.");
    return;
  }
  const item = state.items[state.index];
  const article = renderItem(item, state.index, state.items.length);
  host.replaceChildren(article);
  view.heading.focus();
  setStatus(`${view.heading.textContent}.`);
}

/** The current values of an institution's allowlist fields on screen. */
function readAllowlist(fields) {
  return {region: fields.region.value, domain: fields.domain.value, institution_type: fields.institution_type.value};
}

async function decide(item, decision) {
  if (item.status || !view || view.item !== item) return;
  const problem = noteProblem(view.note.value);
  if (problem) return setResult(problem, true);
  const allowlist = view.allow && decision === "approve" ? readAllowlist(view.allow) : null;
  if (allowlist) {
    const errors = checkAllowlist(allowlist);
    if (errors.length) return setResult(errors[0].message, true);
  }
  setBusy(true);
  setResult("Saving your decision.");
  const response = await api("/moderation/decide", {
    method: "POST",
    body: decisionBody({type: item.type, id: item.id, decision, note: view.note.value, allowlist}),
  });
  if (view.item !== item) return undefined; // the page moved on while the request ran
  if (!response.ok) {
    // A decided or removed item cannot be decided again: keep the message, lock the buttons, let Next go on.
    if (response.error === "already_decided" || response.error === "not_found") item.status = "closed";
    setResult(moderationErrorText(response.error, "decide"), true);
    setBusy(false);
    updateCounts();
    return undefined;
  }
  item.status = response.data.status;
  setResult(`Saved as ${response.data.status}.`);
  setBusy(false);
  updateCounts();
  return setStatus(`Saved as ${response.data.status}. Use Next to go on.`);
}

/** Loads the queue for a region ("" for all) and draws the first item. */
async function loadQueue(region) {
  const response = await api(queueUrl(region));
  if (!response.ok) {
    if (response.status === 403 || response.error === "forbidden") return showNotModerator();
    if (response.error === "not_signed_in") return showSignIn();
    return showFailure(errorText(response.error));
  }
  state = {region, items: normaliseItems(response.data), index: 0};
  if (!shellHost()) {
    body.innerHTML = SHELL;
    body.querySelector("#mod-region").value = region;
    body.querySelector("#mod-region").addEventListener("change", (event) => loadQueue(event.target.value));
  }
  renderQueue();
  return undefined;
}

function showSignIn() {
  body.replaceChildren(
    el("p", {}, [SIGN_IN_TEXT]),
    el("div", {class: "btns"}, [el("a", {class: "btn solid", href: apiUrl("/orcid/start")}, ["Sign in with ORCID to moderate"])]),
  );
  setStatus(SIGN_IN_TEXT);
}

function showNotModerator() {
  body.replaceChildren(el("p", {tabindex: "-1"}, [NOT_MODERATOR_TEXT]));
  body.querySelector("p").focus();
  setStatus(NOT_MODERATOR_TEXT);
}

function showFailure(text) {
  const retry = el("button", {type: "button", class: "btn"}, ["Try again"]);
  retry.addEventListener("click", () => loadQueue(state ? state.region : ""));
  body.replaceChildren(el("p", {}, [text]), el("div", {class: "btns"}, [retry]));
  setStatus(text);
}

async function promote(form) {
  const ambassadorId = form.elements.ambassador_id.value;
  const region = form.elements.region.value;
  const result = body.querySelector("[data-lead-result]");
  const errors = checkLead({ambassadorId, region});
  if (errors.length) {
    result.className = "hint mod-result is-error";
    result.textContent = errors[0].message;
    return;
  }
  result.className = "hint mod-result";
  result.textContent = "Saving.";
  const response = await api("/moderation/leads", {method: "POST", body: leadBody({ambassadorId, region})});
  if (!response.ok) {
    result.className = "hint mod-result is-error";
    result.textContent = moderationErrorText(response.error, "lead");
    return;
  }
  result.textContent = `${response.data.ambassador_id} is now a lead for ${REGION_NAMES[response.data.region] || response.data.region}.`;
  setStatus(result.textContent);
}

function askSuspend(form) {
  const ambassadorId = form.elements.ambassador_id.value;
  const result = body.querySelector("[data-suspend-result]");
  const host = body.querySelector("[data-suspend-confirm]");
  const errors = checkSuspend({ambassadorId});
  if (errors.length) {
    result.className = "hint mod-result is-error";
    result.textContent = errors[0].message;
    return;
  }
  pendingSuspend = String(ambassadorId).trim();
  result.textContent = "";
  const heading = el("h3", {tabindex: "-1", id: "mod-confirm-h"}, ["Suspend this account?"]);
  const confirm = el("button", {type: "button", class: "btn solid"}, ["Confirm suspension"]);
  const cancel = el("button", {type: "button", class: "btn"}, ["Cancel"]);
  confirm.addEventListener("click", () => confirmSuspend(host));
  cancel.addEventListener("click", () => {
    pendingSuspend = null;
    host.replaceChildren();
    setStatus("Suspension cancelled.");
  });
  host.replaceChildren(el("div", {class: "mod-confirm", role: "group", "aria-labelledby": "mod-confirm-h"}, [
    heading,
    el("p", {}, [`Account ${pendingSuspend} will be suspended. Its sessions end at once and it cannot sign in.`]),
    el("div", {class: "btns"}, [confirm, cancel]),
  ]));
  heading.focus();
  setStatus("Confirm or cancel the suspension.");
}

async function confirmSuspend(host) {
  const result = body.querySelector("[data-suspend-result]");
  if (!pendingSuspend) return;
  const response = await api("/moderation/suspend", {method: "POST", body: suspendBody({ambassadorId: pendingSuspend})});
  host.replaceChildren();
  if (!response.ok) {
    result.className = "hint mod-result is-error";
    result.textContent = moderationErrorText(response.error, "suspend");
    setStatus(result.textContent);
  } else {
    result.className = "hint mod-result";
    result.textContent = `Suspended ${response.data.ambassador_id}. Their sessions have ended.`;
    setStatus(result.textContent);
  }
  pendingSuspend = null;
}

function onSubmit(event) {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.dataset.form) return;
  event.preventDefault();
  if (form.dataset.form === "lead") promote(form);
  if (form.dataset.form === "suspend-ask") askSuspend(form);
}

/** Mounts the moderation page. Call once after the page markup is in the DOM. */
export async function mountModeration(rootEl) {
  root = rootEl;
  body = root.querySelector("#mod-body");
  statusEl = root.querySelector("#mod-status");
  if (!body) return;
  body.addEventListener("submit", onSubmit);

  const me = await api("/me");
  if (!me.ok) {
    if (me.error === "not_signed_in") return showSignIn();
    return showFailure(errorText(me.error));
  }
  return loadQueue("");
}
