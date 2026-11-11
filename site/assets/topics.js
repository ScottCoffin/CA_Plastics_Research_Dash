// Shared topic labels and colours for every Atlas page (Experts, Institutions, SEM).
// One fixed hue per research topic (validated categorical palette, light surface;
// never cycled). Hues fill marks and dots only; text stays in ink colours.
// Matrix facets ("matrix:*") are a second dimension and use neutral outlined chips.
(function (global) {
  "use strict";
  const TOPICS = {
    occurrence_and_monitoring: { label: "Occurrence & monitoring", color: "#2a78d6", order: 1 },
    fate_transport_and_sorption: { label: "Fate & transport", color: "#eb6834", order: 2 },
    soil_and_agriculture: { label: "Soil & agriculture", color: "#1baf7a", order: 3 },
    analytical_methods: { label: "Analytical methods", color: "#eda100", order: 4 },
    ecotoxicology_and_trophic_transfer: { label: "Ecotoxicology & food webs", color: "#e87ba4", order: 5 },
    wastewater_and_treatment: { label: "Wastewater & treatment", color: "#008300", order: 6 },
    human_exposure_and_health_risk: { label: "Human exposure & health", color: "#6250d6", order: 7 },
    air: { label: "Air & atmosphere", color: "#e34948", order: 8 }
  };
  const MATRICES = {
    marine: "Marine",
    freshwater: "Freshwater",
    soil_and_agriculture: "Soil",
    food_and_drink: "Food & drink",
    air: "Air",
    wastewater: "Wastewater",
    sediment: "Sediment",
    biota: "Biota"
  };
  const OTHER = "#8a9499";

  function isMatrix(tag) {
    return String(tag).startsWith("matrix:");
  }
  function titleCase(text) {
    const words = String(text).replace(/[_:]+/g, " ").trim().split(/\s+/);
    return words.map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w === "and" ? "&" : w)).join(" ");
  }
  function label(tag) {
    const key = String(tag || "");
    if (TOPICS[key]) return TOPICS[key].label;
    if (isMatrix(key)) {
      const name = key.slice("matrix:".length);
      return MATRICES[name] || titleCase(name);
    }
    return titleCase(key);
  }
  function color(tag) {
    const key = String(tag || "");
    return TOPICS[key] ? TOPICS[key].color : OTHER;
  }
  function order(tag) {
    const key = String(tag || "");
    if (TOPICS[key]) return TOPICS[key].order;
    return isMatrix(key) ? 100 : 50;
  }
  function sortTags(tags) {
    return [...new Set(tags || [])].sort((a, b) => order(a) - order(b) || label(a).localeCompare(label(b)));
  }
  function escapeText(value) {
    return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }
  // Chip markup: topic chips carry a colour dot and a tinted fill; matrix chips are outlined.
  function chip(tag, count) {
    const text = escapeText(label(tag)) + (count === undefined || count === null ? "" : ` <span class="topic-count">${Number(count)}</span>`);
    if (isMatrix(tag)) return `<span class="topic-chip matrix" data-tag="${escapeText(tag)}">${text}</span>`;
    const hue = color(tag);
    return `<span class="topic-chip" data-tag="${escapeText(tag)}" style="--topic:${hue}"><span class="topic-dot" aria-hidden="true"></span>${text}</span>`;
  }
  // Counts per tag from a list of works with domain_tags / facet_tags.
  function weights(works, { matrices = false } = {}) {
    const counts = new Map();
    (works || []).forEach((work) => {
      const tags = [...(work.domain_tags || []), ...(matrices ? work.facet_tags || [] : [])];
      new Set(tags).forEach((tag) => counts.set(tag, (counts.get(tag) || 0) + 1));
    });
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || order(a[0]) - order(b[0]));
  }
  const CSS = `
.topic-chip{display:inline-flex;align-items:center;gap:.35rem;padding:.2rem .6rem;border-radius:999px;font-size:.82rem;line-height:1.3;font-weight:600;color:#1d2a33;background:color-mix(in srgb,var(--topic,#8a9499) 14%,#fff);border:1px solid color-mix(in srgb,var(--topic,#8a9499) 45%,#fff);white-space:nowrap}
.topic-chip .topic-dot{width:.6rem;height:.6rem;border-radius:999px;background:var(--topic,#8a9499);flex:none}
.topic-chip.matrix{background:#fff;border:1px dashed #8a9499;color:#3b4850;font-weight:500}
.topic-chip .topic-count{font-weight:700;color:#4a5860}
.topic-chips{display:flex;flex-wrap:wrap;gap:.35rem}`;
  function injectCss(doc) {
    const d = doc || global.document;
    if (!d || d.getElementById("atlas-topic-css")) return;
    const style = d.createElement("style");
    style.id = "atlas-topic-css";
    style.textContent = CSS;
    d.head.appendChild(style);
  }
  const api = { TOPICS, MATRICES, label, color, order, sortTags, chip, weights, isMatrix, injectCss };
  global.AtlasTopics = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (global.document) injectCss(global.document);
})(typeof window !== "undefined" ? window : globalThis);
