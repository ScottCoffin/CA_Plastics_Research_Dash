// "Invite your co-authors" screen of the signed-in ambassador workspace (AMB-1 front end slice 3c).
// The screen lists the people who co-wrote works with the ambassador (from the public author file, California
// corpus) and says whether each person's institution is eligible in a region. The Worker issues one personal
// invitation link per screen visit (POST /invitations); the Atlas never shows, asks for or stores co-authors'
// email addresses: the ambassador adds the address in their own email program. Pure helpers are exported for
// tests/framework_ambassador_invite_runtime.mjs and touch no DOM at import time. No browser storage is used.
import {escapeHtml, regionFileUrl} from "./atlas.js";

export const MAX_ROWS = 50;
/** Order in which regions are named in eligibility sentences; each has an ambassador_institutions.json file. */
const REGION_SLUGS = ["california", "norway", "belgium"];
/** Display names of the regions (same as REGION_NAMES in ambassador_signup.js; kept here so this module does not load the workspace). */
const REGION_NAMES = {belgium: "Belgium", california: "California", norway: "Norway"};
const AUTHOR_ID = /^[A-Za-z0-9_-]+$/;
const NOT_IN_ATLAS = "Your co-authors are not in the Atlas yet, so there is no list to show. You can still invite them with one general invitation.";
const COULD_NOT_LOAD = "Your co-authors could not be loaded just now. Try again in a few minutes. You can still invite them with one general invitation.";
const NO_CO_AUTHORS = "No co-authors are listed for your works yet. You can still invite colleagues with one general invitation.";

/** Co-authors of an author file's works, self excluded, each counted once per work: [{id, name, shared}]. */
export function coAuthors(authorFile, selfId) {
  const works = Array.isArray(authorFile?.works) ? authorFile.works : [];
  const counts = new Map();
  for (const work of works) {
    const seen = new Set();
    const authors = Array.isArray(work?.authors) ? work.authors : [];
    for (const author of authors) {
      const id = author?.id;
      if (!id || id === selfId || seen.has(id)) continue;
      seen.add(id);
      const entry = counts.get(id) || {id: String(id), name: "", shared: 0};
      entry.shared += 1;
      if (!entry.name && author.name) entry.name = String(author.name);
      counts.set(id, entry);
    }
  }
  return [...counts.values()]
    .map((entry) => ({...entry, name: entry.name || entry.id}))
    .sort((a, b) => b.shared - a.shared || a.name.localeCompare(b.name));
}

/** Region slugs whose eligible institution set contains any of the given institution ids. */
export function eligibleRegions(institutionIds, eligibleBySlug) {
  const ids = Array.isArray(institutionIds) ? institutionIds : [];
  return Object.keys(eligibleBySlug || {}).filter((slug) => ids.some((id) => eligibleBySlug[slug].has(id)));
}

/** Rows for the first `limit` co-authors: {id, name, shared, institution, regions}. */
export function coAuthorRows(list, indexAuthors, eligibleBySlug, regionNames, limit = MAX_ROWS) {
  const byId = new Map((Array.isArray(indexAuthors) ? indexAuthors : []).filter((a) => a?.author_id).map((a) => [a.author_id, a]));
  return (Array.isArray(list) ? list : []).slice(0, limit).map((person) => {
    const known = byId.get(person.id);
    const first = known?.primary_affiliations?.[0];
    const regions = eligibleRegions(known?.institution_ids, eligibleBySlug).map((slug) => regionNames[slug] || slug);
    return {id: person.id, name: person.name, shared: person.shared, institution: first ? String(first) : null, regions};
  });
}

function joinNames(names) {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** Plain sentence about the person's institution and the regions where it is eligible. */
export function eligibilityText(row) {
  const regions = Array.isArray(row?.regions) ? row.regions : [];
  if (regions.length) return `Their institution is eligible in ${joinNames(regions)}`;
  if (row?.institution) return "Their institution is not on a region list yet. They can still sign up and propose it.";
  return "Institution not known. They can still sign up.";
}

/** Text for the clipboard: the subject line, a blank line, then the body. */
export function copyText(subject, body) {
  return `Subject: ${subject}\n\n${body}`;
}

function decodeField(text) {
  try {
    return decodeURIComponent(text);
  } catch {
    return text;
  }
}

/** Subject and body of a mailto: href (percent-decoded; a literal + stays a plus sign). */
export function parseMailto(href) {
  const query = String(href || "").split("?").slice(1).join("?");
  const fields = {subject: "", body: ""};
  for (const part of query.split("&")) {
    const eq = part.indexOf("=");
    const key = eq < 0 ? part : part.slice(0, eq);
    if (key === "subject" || key === "body") fields[key] = decodeField(eq < 0 ? "" : part.slice(eq + 1));
  }
  return fields;
}

function countText(n) {
  return n === 1 ? "1 shared work" : `${n} shared works`;
}

async function loadJson(url) {
  try {
    const response = await fetch(url, {cache: "no-cache"});
    if (!response.ok) return {ok: false, status: response.status, data: null};
    return {ok: true, status: response.status, data: await response.json()};
  } catch {
    return {ok: false, status: 0, data: null};
  }
}

function institutionIdsOf(result) {
  const list = Array.isArray(result?.data?.institutions) ? result.data.institutions : [];
  return list.map((item) => item?.id).filter(Boolean);
}

/** The one general pair of buttons, used when there is no person list to show. */
function generalActionsHTML() {
  return `<div class="iv-actions">
      <button type="button" class="btn solid" data-iv-action="draft">Draft invitation</button>
      <button type="button" class="btn" data-iv-action="copy">Copy invitation</button>
    </div>`;
}

function rowHTML(row) {
  const name = escapeHtml(row.name);
  const meta = [countText(row.shared), row.institution ? escapeHtml(row.institution) : ""].filter(Boolean).join(" · ");
  return `<li class="iv-row">
      <div class="iv-who">
        <p class="iv-name">${name}</p>
        <p class="iv-meta">${meta}</p>
        <p class="iv-elig">${escapeHtml(eligibilityText(row))}</p>
      </div>
      <div class="iv-actions">
        <button type="button" class="btn solid" data-iv-action="draft">Draft invitation<span class="sr"> for ${name}</span></button>
        <button type="button" class="btn" data-iv-action="copy">Copy invitation<span class="sr"> for ${name}</span></button>
      </div>
    </li>`;
}

/**
 * Mounts the invite screen into host. ctx = {ambassador, api, errorText, say}: api(path, {method, body}) from the
 * sign-up module, errorText(code) for Worker error codes, and say(text) for the workspace's status line.
 */
export function mountInvite(host, ctx) {
  const ambassador = ctx?.ambassador || {};
  const authorId = typeof ambassador.author_id === "string" ? ambassador.author_id : "";
  host.innerHTML = `<p class="ws-crumb"><button type="button" class="link-btn" data-ws-action="home">Back to your tasks</button></p>
    <h2 tabindex="-1">Invite your co-authors</h2>
    <p class="lede">These people co-wrote works in the corpus with you. Each shows whether their institution is eligible and in which region. Draft invitation opens a ready email in your own email program. Copy invitation copies the text and your personal link.</p>
    <div class="iv-root" data-iv-root><p class="hint" data-iv-loading>Loading your co-authors...</p></div>
    <p class="hint" role="status" aria-live="polite" data-iv-status></p>
    <div data-iv-fallback></div>
    <p class="hint">We never show or store your co-authors' email addresses. You add the address yourself in your email program.</p>`;

  const root = host.querySelector("[data-iv-root]");
  const status = host.querySelector("[data-iv-status]");
  const fallback = host.querySelector("[data-iv-fallback]");
  // One personal link per screen visit: the first Draft or Copy click asks the Worker, later clicks reuse it.
  let link = null;
  let linkRequest = null;

  function say(text) {
    status.textContent = text;
    if (ctx.say) ctx.say(text);
  }

  function personalLink() {
    if (link) return Promise.resolve({ok: true, link});
    if (!linkRequest) {
      linkRequest = ctx.api("/invitations", {method: "POST", body: {}}).then((response) => {
        const data = response.data || {};
        if (response.ok && data.url && data.mailto) {
          link = {url: String(data.url), mailto: String(data.mailto)};
          return {ok: true, link};
        }
        linkRequest = null;
        return {ok: false, error: response.error || "network"};
      });
    }
    return linkRequest;
  }

  async function draft() {
    const result = await personalLink();
    if (!result.ok) return say(ctx.errorText(result.error));
    window.location.href = result.link.mailto;
    return say("Your email program should open with the invitation. Add the address there.");
  }

  async function copy() {
    const result = await personalLink();
    if (!result.ok) return say(ctx.errorText(result.error));
    const {subject, body} = parseMailto(result.link.mailto);
    const text = copyText(subject, body);
    try {
      if (!navigator.clipboard) throw new Error("no clipboard");
      await navigator.clipboard.writeText(text);
      fallback.innerHTML = "";
      return say("Invitation copied, with your personal link. Paste it into your own email program and add the address there.");
    } catch {
      const area = host.ownerDocument.createElement("textarea");
      area.className = "iv-copy";
      area.readOnly = true;
      area.rows = 10;
      area.setAttribute("aria-label", "Invitation text");
      area.value = text;
      fallback.replaceChildren(area);
      area.focus();
      area.select();
      return say("Select the text and copy it.");
    }
  }

  host.addEventListener("click", (event) => {
    if (!root.isConnected) return;
    const button = event.target.closest?.("[data-iv-action]");
    if (!button || !host.contains(button)) return;
    if (button.dataset.ivAction === "draft") draft();
    else if (button.dataset.ivAction === "copy") copy();
  });

  function renderGeneral(message) {
    root.innerHTML = `<p class="iv-elig">${escapeHtml(message)}</p>${generalActionsHTML()}`;
  }

  function renderList(rows, total) {
    const more = total > rows.length ? `<p class="hint">Showing the first ${rows.length} of ${total} co-authors.</p>` : "";
    root.innerHTML = `<ul class="iv-list" aria-label="Your co-authors">${rows.map(rowHTML).join("")}</ul>${more}`;
  }

  async function load() {
    const file = await loadJson(regionFileUrl("california", `authors/${authorId}.json`));
    if (!root.isConnected) return;
    if (!file.ok && file.status === 404) return renderGeneral(NOT_IN_ATLAS);
    if (!file.ok || !file.data) return renderGeneral(COULD_NOT_LOAD);
    const people = coAuthors(file.data, authorId);
    const [index, ...eligible] = await Promise.all([
      loadJson(regionFileUrl("california", "index.json")),
      ...REGION_SLUGS.map((slug) => loadJson(regionFileUrl(slug, "ambassador_institutions.json"))),
    ]);
    if (!root.isConnected) return;
    const eligibleBySlug = {};
    REGION_SLUGS.forEach((slug, i) => {
      eligibleBySlug[slug] = new Set(institutionIdsOf(eligible[i]));
    });
    const rows = coAuthorRows(people, index.data?.authors, eligibleBySlug, REGION_NAMES);
    if (!rows.length) return renderGeneral(NO_CO_AUTHORS);
    return renderList(rows, people.length);
  }

  if (!AUTHOR_ID.test(authorId)) renderGeneral(NOT_IN_ATLAS);
  else load();
}
