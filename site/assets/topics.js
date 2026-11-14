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
    air: { label: "Air & atmosphere", color: "#e34948", order: 8 },
    // A 9th category never gets a generated hue: it reuses the related violet with a
    // 45-degree hatch and a diamond marker (composite encoding; dataviz rule).
    risk_assessment: { label: "Risk assessment", color: "#6250d6", order: 9, pattern: "hatch" },
    // Owner request 2026-11-11: life on plastic (biofilms, microbial communities,
    // rafting). Hatched ecotoxicology pink, the closest biological topic.
    plastisphere: { label: "Plastisphere", color: "#e87ba4", order: 10, pattern: "hatch" },
    // Owner decision 2026-11-13: BPA, phthalate and 6PPD studies admitted only by a
    // chemicals-in-plastics term. Auxiliary: neutral grey hatch, listed last, with a note.
    plastic_associated_chemicals: {
      label: "Plastic-associated chemicals",
      color: "#6f7b82",
      order: 11,
      pattern: "hatch",
      auxiliary: true
    }
  };
  // Shown wherever an auxiliary topic appears (chip tooltip, glossary, Evidence map).
  const AUXILIARY_NOTE =
    "Auxiliary topic: studies of chemicals associated with plastics (such as BPA, phthalates " +
    "and 6PPD) that the search found through those chemical names. The Atlas searches for " +
    "plastics terms, so coverage of these chemical studies is less complete than for studies " +
    "of plastic particles and debris.";
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
  function pattern(tag) {
    const key = String(tag || "");
    return TOPICS[key] && TOPICS[key].pattern ? TOPICS[key].pattern : "";
  }
  // CSS background for a solid or hatched topic fill (chips, bars drawn with HTML).
  function cssFill(tag, alpha) {
    const hue = color(tag);
    if (pattern(tag) !== "hatch") return hue;
    return `repeating-linear-gradient(45deg, ${hue} 0 3px, #ffffff 3px 5px)`;
  }
  // SVG fill: a solid colour, or url(#atlas-hatch-<tag>) when svgDefs() is in the SVG.
  // Each hatched topic gets its own pattern in its own hue.
  function svgFill(tag) {
    return pattern(tag) === "hatch" ? `url(#atlas-hatch-${String(tag)})` : color(tag);
  }
  function svgDefs() {
    const patterns = Object.keys(TOPICS)
      .filter((key) => TOPICS[key].pattern === "hatch")
      .map((key) => `<pattern id="atlas-hatch-${key}" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">`
        + `<rect width="5" height="5" fill="#ffffff"/><rect width="3" height="5" fill="${TOPICS[key].color}"/></pattern>`);
    return `<defs>${patterns.join("")}</defs>`;
  }
  function sortTags(tags) {
    return [...new Set(tags || [])].sort((a, b) => order(a) - order(b) || label(a).localeCompare(label(b)));
  }
  function escapeText(value) {
    return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }
  function isAuxiliary(tag) {
    const key = String(tag || "");
    return Boolean(TOPICS[key] && TOPICS[key].auxiliary);
  }
  function note(tag) {
    return isAuxiliary(tag) ? AUXILIARY_NOTE : "";
  }
  // Chip markup: topic chips carry a colour dot and a tinted fill; matrix chips are outlined.
  // Auxiliary topics add a dashed border and a title with the coverage note.
  function chip(tag, count) {
    const text = escapeText(label(tag)) + (count === undefined || count === null ? "" : ` <span class="topic-count">${Number(count)}</span>`);
    if (isMatrix(tag)) return `<span class="topic-chip matrix" data-tag="${escapeText(tag)}">${text}</span>`;
    const hue = color(tag);
    const hatch = pattern(tag) === "hatch" ? " hatch" : "";
    const aux = isAuxiliary(tag) ? ` auxiliary" title="${escapeText(AUXILIARY_NOTE)}` : "";
    return `<span class="topic-chip${hatch}${aux}" data-tag="${escapeText(tag)}" style="--topic:${hue}"><span class="topic-dot" aria-hidden="true"></span>${text}</span>`;
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
.topic-chips{display:flex;flex-wrap:wrap;gap:.35rem}
.topic-chip.hatch{background:repeating-linear-gradient(45deg,color-mix(in srgb,var(--topic) 22%,#fff) 0 3px,#fff 3px 6px)}
.topic-chip.hatch .topic-dot{border-radius:1px;transform:rotate(45deg);width:.55rem;height:.55rem}
.topic-chip.auxiliary{border-style:dashed;font-style:italic}`;
  function injectCss(doc) {
    const d = doc || global.document;
    if (!d || d.getElementById("atlas-topic-css")) return;
    const style = d.createElement("style");
    style.id = "atlas-topic-css";
    style.textContent = CSS;
    d.head.appendChild(style);
    // One shared, hidden <defs> for patterned topic fills (avoids duplicate ids per chart).
    const addDefs = () => {
      if (d.getElementById("atlas-topic-defs") || !d.body) return;
      const holder = d.createElement("div");
      holder.innerHTML = `<svg id="atlas-topic-defs" width="0" height="0" aria-hidden="true" focusable="false" style="position:absolute">${svgDefs()}</svg>`;
      d.body.appendChild(holder.firstChild);
    };
    if (d.body) addDefs(); else d.addEventListener("DOMContentLoaded", addDefs);
  }
  const api = { TOPICS, MATRICES, AUXILIARY_NOTE, label, color, order, pattern, cssFill, svgFill, svgDefs, sortTags, chip, weights, isMatrix, isAuxiliary, note, injectCss };
  global.AtlasTopics = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (global.document) injectCss(global.document);
})(typeof window !== "undefined" ? window : globalThis);
