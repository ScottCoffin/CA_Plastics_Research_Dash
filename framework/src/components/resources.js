// Related resources page (EM-16, Add-on A2 §8): one card per link-out registry entry.
// Link, don't mirror: names, stewards and descriptions are quoted from site/data/linkouts.json
// as each steward states them; nothing is fetched from the linked resources. Pure helpers are
// exported for Node tests, and nothing touches `document` at module load.
import {loadJson} from "./atlas.js";

const NOT_STATED = "not stated";

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

function labelled(label, value) {
  const p = el("p", "rs-field");
  p.append(el("span", "rs-label", `${label}: `), document.createTextNode(String(value)));
  return p;
}

export function buildCard(entry) {
  const card = el("li", "rs-card");
  const heading = el("h3", "rs-name");
  if (isHttps(entry.root_url)) {
    heading.append(externalLink(entry.root_url, entry.name));
  } else {
    heading.textContent = entry.name;
  }
  card.append(heading, el("p", "rs-relation", entry.relation));
  card.append(labelled("Steward", entry.steward));

  const description = el("p", "rs-description");
  description.textContent = entry.description === NOT_STATED
    ? "No description stated by the steward."
    : `“${entry.description}”`;
  if (isHttps(entry.description_source)) {
    description.append(" (", externalLink(entry.description_source, "source"), ")");
  }
  card.append(description);

  card.append(labelled("Updates", entry.update_model));
  card.append(labelled("Terms", entry.terms ?? entry.terms_status));
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
