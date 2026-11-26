// Ambassador "Add local knowledge" forms for the signed-in workspace. Each form sends one public item to review through
// POST /submissions (stream "knowledge"). Only the fields a kind has are sent; the Worker refuses anything else.
// Pure helpers are exported for tests/framework_ambassador_knowledge_runtime.mjs and touch no DOM at import time.
// mountKnowledge(host, ctx) draws the forms into the workspace's host element. Nothing personal is kept in the
// browser: no browser storage, nothing in the URL.
import {escapeHtml} from "./atlas.js";

/** Field limits from the Worker (worker/src/submissions.ts MAX_LENGTH), plus the area limit used here. */
const MAX = {name: 200, url: 500, description: 1000, contact_route: 300, licence: 200, note: 1000, area: 200};
const DESCRIPTION_SHOWN = 240;
const BAD_TEXT = /[<>\u0000-\u001f\u007f]/;
const PERMISSION_SENTENCE = "The ambassador confirmed permission to list it.";
export const LICENCES = ["CC BY 4.0", "CC0", "CC BY-NC 4.0", "Open Government Licence", "Other or unknown (we will ask)"];
export const LEVELS = ["National", "Regional", "Municipal"];

/** The knowledge kinds the form offers: every stream "knowledge" kind in the Worker's KINDS except correction. */
export const KNOWLEDGE_KINDS = [
  {kind: "community_group", label: "Community group or coalition", group: "Groups and people", required: ["name", "url"], optional: ["description", "contact_route", "note"], minutes: 5},
  {kind: "volunteer_group", label: "Volunteer organisation (clean-ups, citizen science)", group: "Groups and people", required: ["name", "url"], optional: ["description", "contact_route", "note"], minutes: 5},
  {kind: "community_knowledge", label: "Indigenous or community knowledge holder", group: "Groups and people", required: ["name", "contact_route"], optional: ["url", "description", "note"], minutes: 5},
  {kind: "researcher", label: "Researcher with a public profile", group: "Groups and people", required: ["name", "url"], optional: ["description", "note"], minutes: 5},
  {kind: "research_network", label: "Research network or lab", group: "Organisations and funding", required: ["name", "url"], optional: ["description", "contact_route", "note"], minutes: 5},
  {kind: "institution", label: "Missing institution", group: "Organisations and funding", required: ["name"], optional: ["url", "description", "note"], minutes: 5},
  {kind: "funder", label: "Funder or programme", group: "Organisations and funding", required: ["name", "url"], optional: ["description", "note"], minutes: 5},
  {kind: "policy", label: "Local policy, plan or target", group: "Policy and data", required: ["name", "url"], optional: ["description", "note"], minutes: 8},
  {kind: "dataset", label: "Monitoring dataset or data portal", group: "Policy and data", required: ["name", "url", "licence"], optional: ["description", "contact_route", "note"], minutes: 10},
  {kind: "event", label: "Local event or conference", group: "Events and media", required: ["name"], optional: ["url", "description", "note"], minutes: 5},
  {kind: "media", label: "Local media or outreach channel", group: "Events and media", required: ["name", "url"], optional: ["description", "note"], minutes: 5},
];

/** Fields the form adds that have no Worker slot. They are folded into the note, or (permission) must be ticked. */
const EXTRA_FIELDS = {
  community_group: ["area", "permission"],
  volunteer_group: ["area", "permission"],
  community_knowledge: ["permission"],
  policy: ["level", "adopted_on", "applies_from", "next_date"],
};
const FORM_ORDER = ["name", "level", "url", "adopted_on", "applies_from", "next_date", "area", "description", "contact_route", "licence", "note", "permission"];
const LABELS = {
  name: "Name",
  level: "Level",
  url: "Web address",
  adopted_on: "Adopted on",
  applies_from: "Applies from",
  next_date: "Next decision date (if known)",
  area: "Area",
  description: "Short description",
  contact_route: "Public contact route",
  licence: "Licence for the data",
  note: "Note (optional)",
};
const POLICY_LABELS = {name: "Policy or plan name", url: "Official web address", description: "What it asks for"};
const HINTS = {
  url: "Must start with https://.",
  contact_route: "A public email address or contact page.",
  area: "Where they work, for example a city or a stretch of coast.",
  licence: "Needed for data. Choose Other or unknown if you are not sure.",
  next_date: "Leave dates blank if unknown. We show unknown dates as “date not known”, never as a guess.",
};
const ERROR_TEXT = {
  kind: "Choose what you are adding.",
  name: "Add a name, 200 characters or fewer.",
  url: "Add or check the web address: it must start with https:// and have no spaces.",
  description: "Check the description: plain text with no < or > characters.",
  contact_route: "Add a public contact route: an email address or contact page, 300 characters or fewer.",
  licence: "Choose the licence for the data.",
  note: "Check the note: plain text with no < or > characters, 1000 characters or fewer in total.",
  area: "Check the area: plain text with no < or > characters, 200 characters or fewer.",
  permission: "Tick the box to confirm you have permission to list it.",
  level: "Choose a level: National, Regional or Municipal.",
  adopted_on: "Check the adopted date, or leave it blank if it is not known.",
  applies_from: "Check the date it applies from, or leave it blank if it is not known.",
  next_date: "Check the next decision date, or leave it blank if it is not known.",
};
const STATUS_TEXT = {pending: "Waiting for review", approved: "Approved", rejected: "Not accepted"};
const GENERIC_ERROR = "Check this answer and try again.";

const specFor = (kind) => KNOWLEDGE_KINDS.find((k) => k.kind === kind) || null;
const extrasFor = (kind) => EXTRA_FIELDS[kind] || [];
const plain = (value) => (typeof value === "string" ? value.trim() : "");
const has = (object, key) => Object.prototype.hasOwnProperty.call(object, key);

/** Same rules as the Worker's isHttpsUrl: at most 500 characters, https only, no credentials, no spaces or < >. */
export function httpsAddress(text) {
  if (typeof text !== "string" || text.length > MAX.url || /\s/.test(text) || /[<>]/.test(text)) return false;
  let url;
  try {
    url = new URL(text);
  } catch {
    return false;
  }
  return url.protocol === "https:" && url.username === "" && url.password === "" && url.hostname !== "";
}

/** A real calendar date written YYYY-MM-DD. */
export function isIsoDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

/** The fields a kind's form shows, in form order. */
export function knowledgeFormFields(kind) {
  const spec = specFor(kind);
  if (!spec) return [];
  const used = new Set([...spec.required, ...spec.optional, ...extrasFor(kind)]);
  return FORM_ORDER.filter((field) => used.has(field));
}

/** "About N minutes" for a form's estimate. */
export function estimateLabel(minutes) {
  return `About ${minutes} minutes`;
}

export function knowledgeKindLabel(kind) {
  return specFor(kind)?.label || "";
}

/**
 * The POST body for one knowledge item, or {error: field} naming the first field to fix. `fields` holds the form's
 * values by field name (strings, and a boolean for permission). Empty optional fields are dropped. Extras with no
 * Worker slot are written into the note as plain sentences, before the user's own note.
 */
export function knowledgeBody({region, kind, fields = {}} = {}) {
  const spec = specFor(kind);
  if (!spec) return {error: "kind"};
  const extras = extrasFor(kind);
  const payload = {};
  for (const field of [...spec.required, ...spec.optional]) {
    const value = plain(fields[field]);
    if (!value) {
      if (spec.required.includes(field)) return {error: field};
      continue;
    }
    if (BAD_TEXT.test(value) || value.length > MAX[field]) return {error: field};
    if (field === "url" && !httpsAddress(value)) return {error: field};
    if (field === "licence" && !LICENCES.includes(value)) return {error: field};
    payload[field] = value;
  }
  if (extras.includes("permission") && fields.permission !== true) return {error: "permission"};

  const notes = [];
  if (extras.includes("level")) {
    const level = plain(fields.level);
    if (level && !LEVELS.includes(level)) return {error: "level"};
    if (level) notes.push(`Level: ${level}.`);
  }
  for (const [field, label] of [["adopted_on", "Adopted on"], ["applies_from", "Applies from"], ["next_date", "Next decision date"]]) {
    if (!extras.includes(field)) continue;
    const value = plain(fields[field]);
    if (!value) continue;
    if (!isIsoDate(value)) return {error: field};
    notes.push(`${label}: ${value}.`);
  }
  if (extras.includes("area")) {
    const area = plain(fields.area);
    if (area) {
      if (BAD_TEXT.test(area) || area.length > MAX.area) return {error: "area"};
      notes.push(`Area: ${area}.`);
    }
  }
  if (extras.includes("permission")) notes.push(PERMISSION_SENTENCE);

  const folded = [...notes, payload.note || ""].filter(Boolean).join(" ");
  if (folded.length > MAX.note) return {error: "note"};
  if (folded) payload.note = folded;
  else delete payload.note;
  return {region, stream: "knowledge", kind, payload};
}

/** One plain sentence for a field's error, shown in the error list. */
export function knowledgeErrorText(field) {
  return has(ERROR_TEXT, field) ? ERROR_TEXT[field] : GENERIC_ERROR;
}

const submittedTime = (value) => {
  const time = typeof value === "number" ? value : Date.parse(value);
  return Number.isFinite(time) ? time : 0;
};

/** This region's knowledge rows, newest first, without duplicates. */
export function mySubmissions(submissions, region) {
  const seen = new Set();
  const rows = [];
  for (const row of submissions || []) {
    if (!row || row.region !== region || row.stream !== "knowledge") continue;
    if (row.id !== undefined) {
      if (seen.has(row.id)) continue;
      seen.add(row.id);
    }
    rows.push(row);
  }
  return rows.sort((a, b) => submittedTime(b.created_at) - submittedTime(a.created_at));
}

export function statusText(status) {
  return has(STATUS_TEXT, status) ? STATUS_TEXT[status] : "";
}

// ---- the forms ----------------------------------------------------------------------------------------------------

const esc = (value) => escapeHtml(value);
const option = (value, label, selected) => `<option value="${esc(value)}"${value === selected ? " selected" : ""}>${esc(label)}</option>`;
const countText = (count) => `${count} of ${DESCRIPTION_SHOWN} characters`;
const isRequired = (kind, field) => specFor(kind)?.required.includes(field) || field === "permission";

function permissionText(kind) {
  return kind === "community_knowledge" ? "I have permission to list them here." : "I have the organisation's permission to list it here.";
}

function controlHTML(key, value, describedBy) {
  const id = `kn-f-${key}`;
  const text = typeof value === "string" ? value : "";
  const v = esc(text);
  const described = describedBy ? ` aria-describedby="${describedBy}"` : "";
  const attrs = `id="${id}" data-kn-field="${key}"`;
  switch (key) {
    case "level":
      return `<select ${attrs}>${[option("", "Not known", text), ...LEVELS.map((level) => option(level, level, text))].join("")}</select>`;
    case "licence":
      return `<select ${attrs}${described}>${[option("", "Choose one", text), ...LICENCES.map((item) => option(item, item, text))].join("")}</select>`;
    case "description":
      return `<textarea ${attrs} rows="3" maxlength="${DESCRIPTION_SHOWN}" aria-describedby="${id}-c">${v}</textarea><p class="counter" id="${id}-c">${countText(text.length)}</p>`;
    case "note":
      return `<textarea ${attrs} rows="3" maxlength="${MAX.note}">${v}</textarea>`;
    case "url":
      return `<input ${attrs} type="url" maxlength="${MAX.url}" placeholder="https://" value="${v}"${described}>`;
    case "adopted_on":
    case "applies_from":
    case "next_date":
      return `<input ${attrs} type="date" value="${v}"${described}>`;
    default:
      return `<input ${attrs} type="text" maxlength="${MAX[key]}" value="${v}"${described}>`;
  }
}

function fieldHTML(kind, key, values) {
  const id = `kn-f-${key}`;
  const label = (kind === "policy" && POLICY_LABELS[key]) || LABELS[key];
  const required = isRequired(kind, key) ? ` <span class="hint">(required)</span>` : "";
  const hintId = `${id}-h`;
  // The applies-from date shares the hint under the next-decision date.
  const describedBy = key === "applies_from" ? "kn-f-next_date-h" : HINTS[key] ? hintId : "";
  const hint = HINTS[key] ? `<p class="hint" id="${hintId}">${esc(HINTS[key])}</p>` : "";
  const wide = ["name", "description", "note", "licence"].includes(key) ? " kn-wide" : "";
  return `<div class="field${wide}"><label for="${id}">${esc(label)}${required}</label>${controlHTML(key, values[key], describedBy)}${hint}</div>`;
}

/**
 * Draws the "Add local knowledge" task into host. ctx = {region, regionName, api, errorText, say, submissions,
 * onSubmitted}: api is the sign-up's api(path, {method, body}), which resolves to {ok, data, error}; errorText maps a
 * Worker error code to a sentence; say announces a message; onSubmitted(row) receives the new item.
 */
export function mountKnowledge(host, ctx) {
  const region = ctx.region;
  const local = [];
  const state = {kind: KNOWLEDGE_KINDS[0].kind, values: {}, busy: false};

  function readValues() {
    const values = {};
    host.querySelectorAll("[data-kn-field]").forEach((el) => {
      values[el.dataset.knField] = el.type === "checkbox" ? el.checked : el.value;
    });
    return values;
  }

  function kindOptions() {
    const groups = [...new Set(KNOWLEDGE_KINDS.map((item) => item.group))];
    return groups
      .map((group) => {
        const options = KNOWLEDGE_KINDS.filter((item) => item.group === group)
          .map((item) => `<option value="${esc(item.kind)}"${item.kind === state.kind ? " selected" : ""}>${esc(item.label)}</option>`)
          .join("");
        return `<optgroup label="${esc(group)}">${options}</optgroup>`;
      })
      .join("");
  }

  function sentItemHTML(row) {
    const name = row.payload?.name || "Untitled item";
    const status = statusText(row.status);
    const kind = knowledgeKindLabel(row.kind);
    const detail = [kind, status].filter(Boolean).join(". ");
    return `<li class="kn-sent-item"><p class="kn-sent-name">${esc(name)}</p>${detail ? `<p class="hint">${esc(detail)}</p>` : ""}</li>`;
  }

  function html() {
    const spec = specFor(state.kind);
    const values = state.values;
    const fields = knowledgeFormFields(state.kind);
    const grid = fields.filter((key) => key !== "permission").map((key) => fieldHTML(state.kind, key, values)).join("");
    const permission = fields.includes("permission")
      ? `<div class="check-row kn-check"><input type="checkbox" id="kn-f-permission" data-kn-field="permission"${values.permission === true ? " checked" : ""}><label for="kn-f-permission">${esc(permissionText(state.kind))} <span class="hint">(required)</span></label></div>`
      : "";
    const sent = mySubmissions([...local, ...(ctx.submissions || [])], region);
    const sentHTML = sent.length
      ? `<section class="kn-sent" aria-labelledby="kn-sent-h"><h3 id="kn-sent-h">What you have sent</h3><ul class="kn-sent-list">${sent.map(sentItemHTML).join("")}</ul></section>`
      : "";
    return `<p class="ws-crumb"><button type="button" class="link-btn" data-ws-action="home">Back to your tasks</button></p><h2 tabindex="-1">Add local knowledge</h2>
<p class="lede">Add what you know about local work in ${esc(ctx.regionName)}. Only add what is public.</p>
<p class="est kn-est">${esc(estimateLabel(spec.minutes))}</p>
<div class="field kn-kind"><label for="kn-kind">What are you adding?</label><select id="kn-kind" data-kn-kind>${kindOptions()}</select></div>
<form class="kn-form" data-kn-form novalidate>
  <div class="kn-grid">${grid}</div>
  ${permission}
  <div class="kn-actions"><button type="submit" class="btn solid" data-kn-submit>Send for review</button></div>
</form>
<div class="ws-error kn-errors" role="alert" tabindex="-1" data-kn-errors hidden><p class="kn-errors-title"><strong>Please fix this to continue</strong></p><ul data-kn-error-list></ul></div>
<p class="hint">After you send it, the item waits for review. You will get a notice when it is approved or when a reviewer asks for changes.</p>
${sentHTML}`;
  }

  function render() {
    host.innerHTML = html();
  }

  function showErrors(items) {
    const box = host.querySelector("[data-kn-errors]");
    const list = host.querySelector("[data-kn-error-list]");
    if (!box || !list) return;
    list.innerHTML = items
      .map(({field, text}) => `<li>${field ? `<a href="#kn-f-${field}" data-kn-focus="${field}">${esc(text)}</a>` : esc(text)}</li>`)
      .join("");
    box.hidden = false;
    box.focus();
  }

  function setBusy(on) {
    const button = host.querySelector("[data-kn-submit]");
    const form = host.querySelector("[data-kn-form]");
    if (button) {
      button.disabled = on;
      button.textContent = on ? "Sending…" : "Send for review";
    }
    if (form) form.setAttribute("aria-busy", on ? "true" : "false");
  }

  async function submit() {
    if (state.busy) return;
    const body = knowledgeBody({region, kind: state.kind, fields: readValues()});
    if (body.error) {
      showErrors([{field: body.error, text: knowledgeErrorText(body.error)}]);
      return;
    }
    state.busy = true;
    setBusy(true);
    let res;
    try {
      res = await ctx.api("/submissions", {method: "POST", body});
    } catch {
      res = {ok: false, error: "network"};
    }
    state.busy = false;
    if (!res || !res.ok) {
      setBusy(false);
      showErrors([{text: ctx.errorText(res?.error)}]);
      return;
    }
    const row = {
      id: res.data?.id,
      region,
      stream: "knowledge",
      kind: state.kind,
      payload: body.payload,
      status: "pending",
      created_at: Date.now(),
      decided_at: null,
      decision_note: null,
    };
    // The workspace adds the row to ctx.submissions; keep a local copy only when nobody else does.
    if (ctx.onSubmitted) ctx.onSubmitted(row);
    else local.unshift(row);
    state.values = {};
    render();
    ctx.say?.("Sent for review.");
    host.querySelector("h2")?.focus();
  }

  host.addEventListener("click", (event) => {
    const link = event.target.closest?.("[data-kn-focus]");
    if (!link) return;
    event.preventDefault();
    host.querySelector(`[data-kn-field="${link.dataset.knFocus}"]`)?.focus();
  });
  host.addEventListener("change", (event) => {
    if (!event.target.matches?.("[data-kn-kind]")) return;
    state.values = readValues();
    state.kind = event.target.value;
    render();
    host.querySelector("[data-kn-kind]")?.focus();
  });
  host.addEventListener("input", (event) => {
    if (event.target.dataset?.knField !== "description") return;
    const counter = host.querySelector("#kn-f-description-c");
    if (counter) counter.textContent = countText(event.target.value.length);
  });
  host.addEventListener("submit", (event) => {
    if (!event.target.matches?.("[data-kn-form]")) return;
    event.preventDefault();
    submit();
  });

  render();
}
