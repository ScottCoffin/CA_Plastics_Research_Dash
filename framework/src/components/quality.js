// BQ-1.4: renders a quality.json payload (schema bq1-v1) on /quality (global) and
// /california/quality. Every word and figure comes from the payload; this module adds no numbers.
// An estimand shows a figure only when its status is "ok", which the builder writes only at a
// final checkpoint (scripts/build_quality_json.py). Text is set with textContent, never innerHTML.

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text) node.textContent = text;
  return node;
}

function percent(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : null;
}

export function statusSentence(payload) {
  const labels = payload.labels || {};
  if (payload.status === "ok") return `Validated estimates are published below. ${labels.text || ""}.`;
  return `${payload.status_text || "No validated estimate yet"}; ${labels.text || ""}.`;
}

export function estimandSentence(entry) {
  if (entry.status !== "ok") return "No validated estimate yet.";
  const point = percent(entry.point);
  if (point === null) {
    return entry.upper_bound !== undefined
      ? `Upper bound ${percent(entry.upper_bound)} (95% confidence), n = ${entry.n}.`
      : "Estimate published in the data file, with its interval and flags.";
  }
  const [low, high] = Array.isArray(entry.interval) ? entry.interval.map(percent) : [null, null];
  const interval = low !== null && high !== null ? ` (95% interval ${low} to ${high})` : "";
  return `${point}${interval}, n = ${entry.n}.`;
}

export function renderQuality(root, payload) {
  root.replaceChildren();
  root.setAttribute("data-quality-schema", payload.schema || "");
  root.append(el("p", {class: "qx-status", id: "quality-status-line"}, statusSentence(payload)));

  const whatBox = el("section", {class: "qx-block", "aria-labelledby": "quality-what"});
  whatBox.append(el("h2", {id: "quality-what"}, "What this is and is not"));
  for (const paragraph of payload.what_this_is_and_is_not || []) {
    whatBox.append(el("p", {}, paragraph));
  }
  root.append(whatBox);

  const design = payload.design || {};
  const designBox = el("section", {class: "qx-block", "aria-labelledby": "quality-design"});
  designBox.append(el("h2", {id: "quality-design"}, "The planned design"));
  if (design.text) designBox.append(el("p", {}, design.text));
  root.append(designBox);

  const list = el("section", {class: "qx-block", "aria-labelledby": "quality-measures"});
  list.append(el("h2", {id: "quality-measures"}, "What is measured"));
  const cards = el("div", {class: "qx-cards"});
  for (const entry of Object.values(payload.estimands || {})) {
    const card = el("article", {class: "qx-card", "data-estimand": entry.id || ""});
    card.append(el("h3", {}, entry.label || entry.id || ""));
    card.append(el("p", {}, entry.what || ""));
    card.append(el("p", {class: "qx-figure"}, estimandSentence(entry)));
    cards.append(card);
  }
  list.append(cards);
  root.append(list);

  if (payload.note) root.append(el("p", {class: "qx-note"}, payload.note));
  return root;
}

export async function mountQuality(root, load) {
  try {
    const payload = await load();
    renderQuality(root, payload);
  } catch (error) {
    root.replaceChildren(el("p", {class: "qx-status"}, "No validated estimate yet; the status could not be loaded."));
    console.error("quality:", error);
  }
}
