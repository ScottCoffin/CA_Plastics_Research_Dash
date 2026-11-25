// Related resources page (EM-16, Add-on A2 §8): one card per link-out registry entry.
// Link, don't mirror: names, stewards and descriptions are quoted from site/data/california/linkouts.json
// as each steward states them; nothing is fetched from the linked resources. Pure helpers are
// exported for Node tests, and nothing touches `document` at module load.
import {classicUrl, loadJson} from "./atlas.js";

const NOT_STATED = "not stated";
const ICON_SIZE = 40; // px, shown in the card header (the stored icons are 64 x 64)
const ICON_PATH_PATTERN = /^assets\/linkouts\/[a-z0-9][a-z0-9._-]*\.(?:png|svg)$/;
const INST_ID_PATTERN = /^[A-Za-z0-9._-]{1,64}$/;
const INITIALS_PATTERN = /^[A-Z0-9]{1,3}$/;

export function isHttps(url) {
  if (typeof url !== "string") return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && parsed.hostname !== "";
  } catch {
    return false;
  }
}

export function matchesQuery(entry, query) {
  const needle = String(query ?? "").trim().toLowerCase();
  if (!needle) return true;
  return [entry?.name, entry?.steward, entry?.description]
    .some((value) => String(value ?? "").toLowerCase().includes(needle));
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function externalLink(href, text) {
  const link = el("a", "", text);
  link.href = href;
  link.target = "_blank";
  link.rel = "noreferrer";
  return link;
}

// A value is text, or a node (the steward link) that is appended as it is.
function labelled(label, value) {
  const p = el("p", "rs-field");
  const body = value && typeof value === "object" ? value : document.createTextNode(String(value));
  p.append(el("span", "rs-label", `${label}: `), body);
  return p;
}

// The icon file for a card as an absolute URL on the site root (assets/ sits there in both
// layouts). Only paths under assets/linkouts/ qualify; anything else gets the initials plane.
export function iconUrl(path) {
  return typeof path === "string" && ICON_PATH_PATTERN.test(path) ? classicUrl(path) : null;
}

// The Atlas institution page for a steward, ./institution#inst=<id>; null for an unsafe id.
export function institutionHref(instId) {
  if (typeof instId !== "string" || !INST_ID_PATTERN.test(instId)) return null;
  const base = typeof document !== "undefined" && document.baseURI ? document.baseURI : "http://localhost/";
  return new URL(`institution#inst=${encodeURIComponent(instId)}`, base).href;
}

function iconNode(entry) {
  const src = iconUrl(entry.icon);
  if (src) {
    // Decorative: the card title names the site, so the icon has an empty alt text.
    const img = el("img", "rs-icon");
    img.src = src;
    img.alt = "";
    img.width = ICON_SIZE;
    img.height = ICON_SIZE;
    img.loading = "lazy";
    return img;
  }
  const initials = typeof entry.initials === "string" && INITIALS_PATTERN.test(entry.initials) ? entry.initials : "";
  const plane = el("span", "rs-icon rs-icon-initials", initials);
  plane.setAttribute("aria-hidden", "true");
  return plane;
}

// The steward name links to its Atlas institution page when the registry names one.
function stewardNode(entry) {
  const href = institutionHref(entry.steward_inst_id);
  if (!href) return String(entry.steward);
  const link = el("a", "", entry.steward);
  link.href = href;
  return link;
}

export function buildCard(entry) {
  const card = el("li", "rs-card");
  const head = el("div", "rs-head");
  const heading = el("h2", "rs-name");
  if (isHttps(entry.root_url)) {
    heading.append(externalLink(entry.root_url, entry.name));
  } else {
    heading.textContent = entry.name;
  }
  head.append(iconNode(entry), heading);
  card.append(head, el("p", "rs-relation", entry.relation));
  const steward = labelled("Steward", stewardNode(entry));
  if (isHttps(entry.steward_source)) steward.append(" (", externalLink(entry.steward_source, "source"), ")");
  card.append(steward);

  const description = el("p", "rs-description");
  description.textContent = entry.description === NOT_STATED
    ? "No description stated by the steward."
    : `“${entry.description}”`;
  if (isHttps(entry.description_source)) {
    description.append(" (", externalLink(entry.description_source, "source"), ")");
  }
  card.append(description);

  // UX-11: show what the steward states; one badge replaces the repeated "not stated" fields.
  if (entry.update_model && entry.update_model !== NOT_STATED) card.append(labelled("Updates", entry.update_model));
  if (entry.terms_status === "recorded" && entry.terms) card.append(labelled("Terms", entry.terms));
  else if (entry.terms_status !== "recorded") card.append(el("p", "rs-badge", "Reuse terms not recorded"));

  // A link-out can carry a disclosure, e.g. that the Atlas owner is a listed contributor. Shown as text.
  const disclosure = typeof entry.disclosure === "string" ? entry.disclosure.trim() : "";
  if (disclosure) card.append(el("p", "rs-disclosure", `Disclosure: ${disclosure}`));
  return card;
}

export function renderList(list, entries, query) {
  const shown = entries.filter((entry) => matchesQuery(entry, query));
  list.replaceChildren(...shown.map(buildCard));
  return shown.length;
}

export async function mountResources(root = document.getElementById("resources-root")) {
  if (!root) return;
  const status = el("p", "result-count", "Loading related resources…");
  status.setAttribute("role", "status");
  root.replaceChildren(status);

  let entries;
  try {
    const payload = await loadJson("linkouts.json");
    entries = Array.isArray(payload?.entries) ? payload.entries : [];
  } catch {
    status.textContent = "Related resources could not be loaded.";
    return;
  }

  const filterId = "resources-filter";
  const label = el("label", "", "Filter resources");
  label.htmlFor = filterId;
  const input = el("input");
  input.id = filterId;
  input.type = "search";
  input.autocomplete = "off";
  input.placeholder = "Name, steward or description";
  const form = el("form", "rs-filter");
  form.setAttribute("role", "search");
  form.addEventListener("submit", (event) => event.preventDefault());
  form.append(label, input);

  const count = el("p", "result-count");
  count.setAttribute("aria-live", "polite");
  const list = el("ul", "rs-list");
  const note = el("p", "data-note", "Links are checked weekly for HTTP status.");

  const update = () => {
    const shown = renderList(list, entries, input.value);
    count.textContent = `Showing ${shown} of ${entries.length} resources.`;
  };
  input.addEventListener("input", update);

  root.replaceChildren(form, count, list, note);
  update();
}
