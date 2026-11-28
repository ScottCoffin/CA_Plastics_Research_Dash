// Composition views for the Community groups page: two heatmaps, a zoomable treemap and an evidence panel.
// The pure helpers take the public groups.json and precision_card.json shapes and have no DOM access, so
// Node tests can load them. mountGroupsComposition draws the views with the Framework's Plot and d3, which
// the caller passes in (no npm imports here).
import {GROUP_TAXONOMY} from "./ambassador_groups.js";
import {groupLabel, niceLabel} from "./group_labels.js";
import {CHROME, INK_DARK, INK_LIGHT, SEQ, rampFill} from "./shared/palette.js";

/** Groups with fewer cases than this are drawn muted; their counts still show. */
export const SMALL_CELL = 5;
export const TAGGED_STATUSES = Object.freeze(["ambassador_tagged", "reviewed", "group_confirmed"]);
export const EMPTY_MESSAGE = "No groups are tagged yet. These charts fill in as volunteers tag groups.";
export const NOT_RECORDED = "Not recorded";
/** Reasons that are never listed on the page (retired by owner decision A4-D27). */
export const NEVER_LISTED_REASONS = Object.freeze(["conflict_of_interest"]);
export const NO_IMPOSSIBLE_REASONS = "No group has been marked as impossible to tag yet.";
const LAYER_ORDER = ["core", "adjacent"];
const LAYER_LABELS = Object.freeze({core: "Core groups", adjacent: "Adjacent groups"});
/** Evidence table rows: the five main tagged fields, in the order the page shows them. */
export const EVIDENCE_FIELDS = Object.freeze([
  {key: "entity_type", label: "Organisation type"},
  {key: "sector", label: "Sector"},
  {key: "plastics_centrality", label: "How central are plastics?"},
  {key: "primary_activities", label: "Main activities"},
  {key: "geographic_scope", label: "Geographic scope"},
]);
/** Plain names and one-line tooltips for the agreement statistics. */
export const STATISTIC_NAMES = Object.freeze({
  weighted_kappa: {
    name: "Agreement between volunteers (Cohen's weighted kappa)",
    tip: "Agreement between two volunteers who tagged the same group, with near misses counting less than clear disagreements, corrected for chance.",
  },
  pabak: {
    name: "PABAK",
    tip: "Prevalence-adjusted, bias-adjusted kappa: agreement corrected for how often each answer is used.",
  },
  gwet_ac1: {
    name: "Gwet's AC1",
    tip: "Chance-corrected agreement that stays steady when some answers are far more common than others.",
  },
});

export const isTagged = (group) => TAGGED_STATUSES.includes(group?.status);
export const taggedGroups = (groups) => (Array.isArray(groups) ? groups : []).filter(isTagged);
const keyOf = (value) => (value === undefined || value === null ? "" : String(value));
/** The principal activity is the first listed; an empty key means none recorded. */
const firstActivity = (group) => keyOf(Array.isArray(group?.primary_activities) ? group.primary_activities[0] : "");
export const pct = (share) => `${Math.round(share * 100)}%`;
const finite = (value) => typeof value === "number" && Number.isFinite(value);

// ---- colour contrast (WCAG relative luminance) ----

const channelLinear = (v) => {
  const c = v / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
};
/** Relative luminance of a six-digit hex colour. */
export function luminance(hex) {
  const n = parseInt(String(hex).slice(1), 16);
  return 0.2126 * channelLinear((n >> 16) & 255) + 0.7152 * channelLinear((n >> 8) & 255) + 0.0722 * channelLinear(n & 255);
}
/** Contrast ratio between two hex colours, from 1 to 21. */
export function contrastRatio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}
/** Label ink (INK_DARK or INK_LIGHT) with the higher contrast against a fill. */
export function inkFor(fill) {
  return contrastRatio(fill, INK_DARK) >= contrastRatio(fill, INK_LIGHT) ? INK_DARK : INK_LIGHT;
}

// ---- axes and tables ----

/** Display label for one axis value. Kind null means the value is already a label (for example a region). */
export function labelFor(kind, value) {
  if (value === "") return NOT_RECORDED;
  if (kind === null) return value;
  if (kind === "layer") return LAYER_LABELS[value] || niceLabel(value);
  return groupLabel(kind, value);
}

/**
 * Axis values in display order. Taxonomy values come first in taxonomy order (all of them when includeAll,
 * otherwise only the observed ones); observed values outside the taxonomy follow, sorted; "" (not recorded) is last.
 */
export function orderedKeys(order, observed, {includeAll = false} = {}) {
  const seen = new Set(observed.filter((v) => v !== ""));
  const base = includeAll ? order.slice() : order.filter((k) => seen.has(k));
  const extras = [...seen].filter((k) => !order.includes(k)).sort();
  const keys = [...base, ...extras];
  return observed.includes("") ? [...keys, ""] : keys;
}

/**
 * Counts for a two-axis table. shareOver "row" or "col" sets the share denominator (the row or column total);
 * fills: zero cells the lightest step, cells under SMALL_CELL muted, the rest on the ramp.
 */
function crosstab(tagged, {rowOf, colOf, rowKind, colKind, rowOrder, colOrder, rowAll, colAll, shareOver}) {
  const rowKeys = orderedKeys(rowOrder, tagged.map(rowOf), {includeAll: rowAll});
  const colKeys = orderedKeys(colOrder, tagged.map(colOf), {includeAll: colAll});
  const counts = new Map();
  const totals = {row: new Map(rowKeys.map((r) => [r, 0])), col: new Map(colKeys.map((c) => [c, 0]))};
  for (const group of tagged) {
    const r = rowOf(group);
    const c = colOf(group);
    const key = JSON.stringify([r, c]);
    counts.set(key, (counts.get(key) || 0) + 1);
    totals.row.set(r, totals.row.get(r) + 1);
    totals.col.set(c, totals.col.get(c) + 1);
  }
  const raw = [];
  for (const r of rowKeys) {
    for (const c of colKeys) raw.push({r, c, n: counts.get(JSON.stringify([r, c])) || 0});
  }
  const max = Math.max(0, ...raw.map((cell) => cell.n));
  const cells = raw.map(({r, c, n}) => {
    const base = shareOver ? totals[shareOver].get(shareOver === "row" ? r : c) : null;
    const share = base > 0 ? n / base : null;
    const small = n < SMALL_CELL;
    const intensity = shareOver ? share ?? 0 : max > 0 ? n / max : 0;
    const x = labelFor(colKind, c);
    const y = labelFor(rowKind, r);
    const fill = n === 0 ? SEQ[0] : small ? CHROME.sunken : rampFill(intensity);
    const tip = `${y} and ${x}: ${n} ${n === 1 ? "group" : "groups"}${share === null ? "" : `, ${pct(share)} of ${shareOver === "row" ? y : x}`}`;
    return {
      row: r, col: c, x, y, n, share, base: base ?? null, small,
      // Counts only; a zero in a share table is left blank so no text crowds the empty cell.
      label: shareOver && n === 0 ? "" : String(n),
      tip, fill,
      ink: small ? CHROME.axis : inkFor(fill),
    };
  });
  return {
    total: tagged.length,
    shareOver,
    xDomain: colKeys.map((c) => labelFor(colKind, c)),
    yDomain: rowKeys.map((r) => labelFor(rowKind, r)),
    cells,
    smallCount: cells.filter((cell) => cell.small).length,
  };
}

/** Heatmap 1: plastics centrality (columns) by sector (rows), counts only. */
export function centralityBySector(groups) {
  return crosstab(taggedGroups(groups), {
    rowOf: (g) => keyOf(g.sector),
    colOf: (g) => keyOf(g.plastics_centrality),
    rowKind: "sector",
    colKind: "plastics_centrality",
    rowOrder: GROUP_TAXONOMY.sector,
    colOrder: GROUP_TAXONOMY.plastics_centrality,
    rowAll: true,
    colAll: true,
    shareOver: null,
  });
}

/**
 * Heatmap 2, transposed: regions as rows (only regions with a tagged group), main activities as columns.
 * Each cell's share is of its region's tagged groups.
 */
export function activityByRegion(groups) {
  return crosstab(taggedGroups(groups), {
    rowOf: (g) => keyOf(g.region),
    colOf: firstActivity,
    rowKind: null,
    colKind: "primary_activities",
    rowOrder: [],
    colOrder: GROUP_TAXONOMY.primary_activities,
    rowAll: false,
    colAll: true,
    shareOver: "row",
  });
}

/** Sum of the leaf values under a treemap node. */
export function treeTotal(node) {
  return node.children ? node.children.reduce((sum, child) => sum + treeTotal(child), 0) : node.value;
}

/**
 * Treemap data: layer, then sector, then principal activity. Leaves carry the group count, so the total
 * equals the number of tagged groups. Empty branches are left out.
 */
export function compositionTree(groups) {
  const tagged = taggedGroups(groups);
  const layers = orderedKeys(LAYER_ORDER, tagged.map((g) => keyOf(g.layer)));
  return {
    id: "all",
    label: "All tagged groups",
    children: layers.map((layer) => {
      const inLayer = tagged.filter((g) => keyOf(g.layer) === layer);
      const sectors = orderedKeys(GROUP_TAXONOMY.sector, inLayer.map((g) => keyOf(g.sector)));
      return {
        id: `layer:${layer}`,
        label: labelFor("layer", layer),
        children: sectors.map((sector) => {
          const inSector = inLayer.filter((g) => keyOf(g.sector) === sector);
          const activities = orderedKeys(GROUP_TAXONOMY.primary_activities, inSector.map(firstActivity));
          return {
            id: `sector:${layer}:${sector}`,
            label: labelFor("sector", sector),
            children: activities.map((activity) => ({
              id: `activity:${layer}:${sector}:${activity}`,
              label: labelFor("primary_activities", activity),
              value: inSector.filter((g) => firstActivity(g) === activity).length,
            })),
          };
        }),
      };
    }),
  };
}

/** A label is drawn inside a tile only when it fits (sizes in pixels). */
export function labelFits(width, height, text) {
  const charWidth = 6.5;
  return height >= 22 && width >= 40 && String(text).length * charWidth + 8 <= width;
}

const intervalOf = (ci) =>
  Array.isArray(ci) && ci.length === 2 && ci.every(finite) ? [ci[0], ci[1]] : null;

function agreementOf(facet) {
  const agreement = facet.agreement;
  const reason = facet.agreement_reason || "Not yet measured";
  if (!agreement) return {reason, statistics: [], pairs: null};
  const stats = agreement.statistics || {};
  const statistics = Object.keys(STATISTIC_NAMES)
    .filter((key) => stats[key])
    .map((key) => ({
      key,
      name: STATISTIC_NAMES[key].name,
      tip: STATISTIC_NAMES[key].tip,
      value: finite(stats[key].value) ? stats[key].value : null,
      interval: intervalOf(stats[key].ci95),
    }));
  return {
    reason: statistics.length ? "" : reason,
    statistics,
    pairs: finite(agreement.n_pairs) ? agreement.n_pairs : null,
  };
}

function reviewOf(facet) {
  const review = facet.review;
  if (!review) return null;
  return {
    audited: finite(review.audited_n) ? review.audited_n : 0,
    agree: finite(review.agree_n) ? review.agree_n : 0,
    share: finite(review.agree_share) ? review.agree_share : null,
    interval: intervalOf(review.ci95),
  };
}

/** One row per main tagged field, from the precision card. A null agreement becomes its plain reason. */
export function evidenceRows(precision) {
  const facets = precision?.facets || {};
  return EVIDENCE_FIELDS.map(({key, label}) => {
    const facet = facets[key] || {};
    const tagged = finite(facet.tagged_n) ? facet.tagged_n : 0;
    const withEvidence = finite(facet.with_evidence_n) ? facet.with_evidence_n : 0;
    const reviewed = finite(facet.reviewed_n) ? facet.reviewed_n : 0;
    return {
      field: key,
      label,
      tagged,
      withEvidence,
      evidenceShare: tagged > 0 ? withEvidence / tagged : null,
      reviewed,
      reviewedShare: tagged > 0 ? reviewed / tagged : null,
      agreement: agreementOf(facet),
      review: reviewOf(facet),
    };
  });
}

/** Reasons that groups could not be tagged: only those with a count above zero, never the retired ones. */
export function reasonRows(precision) {
  const reasons = precision?.cannot_determine_reasons || {};
  return Object.keys(reasons)
    .filter((key) => !NEVER_LISTED_REASONS.includes(key))
    .map((key) => ({
      key,
      label: labelFor("cannot_determine_reason", key),
      count: finite(reasons[key]) ? reasons[key] : 0,
    }))
    .filter((row) => row.count > 0);
}

/** Plain sentence for a heatmap: the total and its largest share (or largest count). */
export function heatmapSummary(matrix, {rowNoun, colNoun}) {
  const total = matrix.total;
  if (total === 0) return EMPTY_MESSAGE;
  const shaded = matrix.smallCount ? ` Cells with fewer than ${SMALL_CELL} groups are shaded grey.` : "";
  let largest = "";
  if (matrix.shareOver === "row") {
    const ranked = matrix.cells
      .filter((c) => c.n > 0 && c.share !== null)
      .sort((a, b) => b.share - a.share || b.n - a.n);
    const top = ranked[0];
    if (top) largest = ` In ${top.y}, the largest share is ${top.x}: ${pct(top.share)} of ${top.base} tagged groups there.`;
  } else {
    const top = matrix.cells.reduce((best, cell) => (cell.n > best.n ? cell : best), matrix.cells[0]);
    if (top && top.n > 0) largest = ` The largest cell is ${top.y} and ${top.x}, with ${top.n} of ${total} tagged groups.`;
  }
  return `${total} tagged groups, by ${rowNoun} and ${colNoun}.${largest}${shaded}`;
}

export function treemapSummary(tree) {
  const total = treeTotal(tree);
  if (total === 0) return EMPTY_MESSAGE;
  const leaves = [];
  const walk = (node) => (node.children ? node.children.forEach(walk) : leaves.push(node));
  walk(tree);
  const top = leaves.reduce((best, leaf) => (leaf.value > best.value ? leaf : best), leaves[0]);
  return `${total} tagged groups, grouped by layer, sector and main activity. The largest activity group is ${top.label} with ${top.value} groups. Select a group or box to zoom in; use the path above to zoom out.`;
}

/** The value and 95% interval of one statistic, as plain text (without its name). */
export function statisticText(s) {
  const value = s.value === null ? "not calculated" : s.value.toFixed(2);
  const interval = s.interval ? ` (95% interval ${s.interval[0].toFixed(2)} to ${s.interval[1].toFixed(2)})` : "";
  return `${value}${interval}`;
}

/** Plain text for an agreement block, one line per statistic (or the reason when none is available). */
export function agreementLines(agreement) {
  if (!agreement.statistics.length) return [agreement.reason];
  return agreement.statistics.map((s) => `${s.name}: ${statisticText(s)}`);
}

// ---- DOM rendering (mountGroupsComposition only) ----

const HEADER_PX = 24;
const TREEMAP_GAP = 3;
const LAYER_CLASSES = Object.freeze(["core", "adjacent"]);

function node(doc, tag, className, text) {
  const el = doc.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

const emptyNote = (doc) => node(doc, "p", "groups-composition__empty", EMPTY_MESSAGE);

function heatmapFigure(doc, Plot, matrix, {title, summary, width, marginLeft, marginTop, xLineWidth, yLineWidth}) {
  const figure = node(doc, "figure", "groups-composition__figure");
  const chart = node(doc, "div", "groups-composition__chart");
  // A scrollable region must be reachable by keyboard (WCAG 2.1.1; axe scrollable-region-focusable).
  chart.tabIndex = 0;
  chart.setAttribute("role", "region");
  chart.setAttribute("aria-label", title);
  const plot = Plot.plot({
    width,
    marginLeft,
    marginTop,
    x: {domain: matrix.xDomain},
    y: {domain: matrix.yDomain},
    color: {identity: true},
    // lineWidth (label wrapping, in ems) is an axis-mark option, so the axes are explicit marks.
    marks: [
      Plot.axisX({anchor: "top", label: null, tickSize: 0, lineWidth: xLineWidth, fontSize: 11}),
      Plot.axisY({label: null, tickSize: 0, lineWidth: yLineWidth, fontSize: 11}),
      Plot.cell(matrix.cells, {x: "x", y: "y", fill: "fill", inset: 1, title: "tip"}),
      Plot.text(matrix.cells, {x: "x", y: "y", text: "label", fill: "ink", fontSize: 11}),
    ],
  });
  plot.setAttribute("role", "img");
  plot.setAttribute("aria-label", `${title}. ${summary}`);
  chart.append(plot);
  figure.append(chart, node(doc, "figcaption", "groups-composition__summary", summary));
  return figure;
}

function heatmapSection(doc, groups, Plot, width) {
  const section = node(doc, "section", "groups-composition__section");
  section.append(node(doc, "h3", "", "Plastics focus by sector"));
  const sectorMatrix = centralityBySector(groups);
  const activityMatrix = activityByRegion(groups);
  if (sectorMatrix.total === 0) {
    section.append(emptyNote(doc));
    return section;
  }
  const sectorSummary = heatmapSummary(sectorMatrix, {rowNoun: "sector", colNoun: "how central plastics are"});
  const activitySummary = heatmapSummary(activityMatrix, {rowNoun: "region", colNoun: "main activity"});
  if (!Plot) {
    section.append(node(doc, "p", "groups-composition__summary", sectorSummary));
    section.append(node(doc, "h3", "", "Main activity by region"));
    section.append(node(doc, "p", "groups-composition__summary", activitySummary));
    return section;
  }
  section.append(heatmapFigure(doc, Plot, sectorMatrix, {
    title: "Groups by sector and how central plastics are",
    summary: sectorSummary,
    width,
    marginLeft: 150,
    marginTop: 64,
    xLineWidth: 8,
    yLineWidth: 10,
  }));
  section.append(node(doc, "h3", "", "Main activity by region"));
  section.append(heatmapFigure(doc, Plot, activityMatrix, {
    title: "Groups by region and main activity, with each region's share",
    summary: activitySummary,
    width,
    marginLeft: 150,
    marginTop: 120,
    xLineWidth: 5,
    yLineWidth: 12,
  }));
  return section;
}

function treemapSection(doc, groups, d3, width) {
  const section = node(doc, "section", "groups-composition__section");
  section.append(node(doc, "h3", "", "Groups by layer, sector and main activity"));
  const tree = compositionTree(groups);
  if (treeTotal(tree) === 0) {
    section.append(emptyNote(doc));
    return section;
  }
  const W = width;
  const H = width <= 600 ? 300 : 360;
  const crumbs = node(doc, "nav", "groups-composition__crumbs");
  crumbs.setAttribute("aria-label", "Zoom path");
  const stage = node(doc, "div", "groups-composition__stage");
  stage.style.height = `${H}px`;
  // The layout is W wide; pin the stage to it so no empty band shows beside the boxes.
  stage.style.width = `${W}px`;
  stage.setAttribute("role", "group");
  stage.setAttribute("aria-label", "Treemap of tagged groups");
  const status = node(doc, "p", "groups-composition__summary");
  status.setAttribute("aria-live", "polite");
  section.append(crumbs, stage, status, node(doc, "p", "groups-composition__summary", treemapSummary(tree)));

  const root = d3.hierarchy(tree, (d) => d.children).sum((d) => (d.children ? 0 : d.value));
  let focus = root;
  const layerOf = (n) => {
    const top = n.ancestors().find((a) => a.depth === 1);
    const key = top ? top.data.id.split(":")[1] : "";
    return LAYER_CLASSES.includes(key) ? key : "other";
  };
  const place = (el, x, y, w, h) => {
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
    el.style.width = `${Math.max(0, w)}px`;
    el.style.height = `${Math.max(0, h)}px`;
  };
  const zoomTo = (target) => {
    focus = target;
    render();
  };
  const describe = (n) => `${n.data.label}: ${n.value} ${n.value === 1 ? "group" : "groups"}${n.children ? ". Select to zoom in" : ""}`;
  // d3.treemap only works on a root node (it indexes padding by depth), so every level is laid out on a fresh
  // hierarchy built from the node's data. Children keep their data order, so index i maps back to node.children[i].
  const layoutOf = (n, w, h, pad) => {
    const fresh = d3.hierarchy(n.data, (d) => d.children).sum((d) => (d.children ? 0 : d.value));
    d3.treemap().size([Math.max(0, w), Math.max(0, h)]).paddingInner(pad).round(true)(fresh);
    return fresh.children || [];
  };
  const tileFor = (child, x, y, w, h) => {
    const tile = node(doc, "button", "groups-composition__tile");
    tile.type = "button";
    place(tile, x, y, w, h);
    const text = describe(child);
    tile.setAttribute("aria-label", text);
    tile.title = text;
    if (labelFits(w, h, child.data.label)) tile.append(node(doc, "span", "", child.data.label));
    if (child.children) tile.addEventListener("click", () => zoomTo(child));
    return tile;
  };

  function render() {
    crumbs.replaceChildren();
    focus.ancestors().reverse().forEach((ancestor) => {
      const crumb = node(doc, "button", "groups-composition__crumb", ancestor.data.label);
      crumb.type = "button";
      if (ancestor === focus) crumb.setAttribute("aria-current", "location");
      crumb.addEventListener("click", () => zoomTo(ancestor));
      crumbs.append(crumb);
    });
    stage.replaceChildren();
    const boxes = layoutOf(focus, W, H, TREEMAP_GAP);
    status.textContent = `${focus.value} tagged ${focus.value === 1 ? "group" : "groups"} in ${focus.data.label}.`;
    for (const [i, child] of (focus.children || []).entries()) {
      const box = boxes[i];
      const x = box.x0;
      const y = box.y0;
      const w = box.x1 - box.x0;
      const h = box.y1 - box.y0;
      if (!child.children) {
        stage.append(tileFor(child, x, y, w, h));
        continue;
      }
      // Two levels: this child is a labelled group; its own children are tiles inside it.
      const layer = layerOf(child);
      const group = node(doc, "div", `groups-composition__group groups-composition__group--${layer}`);
      place(group, x, y, w, h);
      const head = node(doc, "button", "groups-composition__group-head", `${child.data.label}: ${child.value}`);
      head.type = "button";
      head.title = describe(child);
      head.setAttribute("aria-label", describe(child));
      head.addEventListener("click", () => zoomTo(child));
      group.append(head);
      // Lay out the group's tiles below the header strip; the group's own box is already read above.
      const inner = layoutOf(child, w, h - HEADER_PX, 2);
      for (const [j, grand] of child.children.entries()) {
        const g = inner[j];
        group.append(tileFor(grand, g.x0, HEADER_PX + g.y0, g.x1 - g.x0, g.y1 - g.y0));
      }
      stage.append(group);
    }
  }
  render();
  return section;
}

function agreementCell(doc, agreement) {
  const cell = node(doc, "td");
  if (!agreement.statistics.length) {
    cell.textContent = agreement.reason;
    return cell;
  }
  for (const s of agreement.statistics) {
    const line = node(doc, "p");
    const abbr = node(doc, "abbr", "", s.name);
    abbr.title = s.tip;
    line.append(abbr, doc.createTextNode(`: ${statisticText(s)}`));
    cell.append(line);
  }
  if (agreement.pairs !== null) cell.append(node(doc, "p", "groups-composition__note", `From ${agreement.pairs} double-tagged pairs.`));
  return cell;
}

function reviewCell(doc, review) {
  const cell = node(doc, "td");
  if (!review || review.share === null) {
    cell.textContent = "Not yet checked";
    return cell;
  }
  const interval = review.interval ? `, 95% interval ${review.interval[0].toFixed(2)} to ${review.interval[1].toFixed(2)}` : "";
  cell.textContent = `${pct(review.share)} agree (${review.agree} of ${review.audited})${interval}`;
  return cell;
}

function evidenceSection(doc, precision, globalOnly = false) {
  const section = node(doc, "section", "groups-composition__section");
  section.append(node(doc, "h3", "", "How well are the tags supported?"));
  if (globalOnly) {
    section.append(node(doc, "p", "groups-composition__note", "Precision evidence is available for the global tagging sample only; it has not been calculated for this scope."));
    return section;
  }
  const rows = evidenceRows(precision);
  const reasons = reasonRows(precision);
  const tagged = rows.length ? rows[0].tagged : 0;
  if (tagged === 0) section.append(emptyNote(doc));
  const table = node(doc, "table", "groups-composition__table");
  table.append(node(doc, "caption", "", "Share of tagged groups with a quote for each field, and how far volunteers agree."));
  const head = node(doc, "tr");
  ["Field", "Tagged groups", "With a quote", "Reviewed", "Agreement between volunteers", "Reviewer agreement"]
    .forEach((text) => head.append(node(doc, "th", "", text)));
  const thead = node(doc, "thead");
  thead.append(head);
  table.append(thead);
  const body = node(doc, "tbody");
  for (const row of rows) {
    const tr = node(doc, "tr");
    tr.append(node(doc, "th", "", row.label));
    tr.append(node(doc, "td", "", String(row.tagged)));
    tr.append(node(doc, "td", "", row.evidenceShare === null ? "No groups yet" : `${pct(row.evidenceShare)} (${row.withEvidence})`));
    tr.append(node(doc, "td", "", row.reviewedShare === null ? "No groups yet" : `${row.reviewed} (${pct(row.reviewedShare)})`));
    tr.append(agreementCell(doc, row.agreement));
    tr.append(reviewCell(doc, row.review));
    body.append(tr);
  }
  table.append(body);
  // The wrapper scrolls sideways on narrow screens, so the page body never does.
  const scroll = node(doc, "div", "groups-composition__scroll");
  scroll.tabIndex = 0;
  scroll.setAttribute("role", "region");
  scroll.setAttribute("aria-label", "Evidence and agreement table");
  scroll.append(table);
  section.append(scroll);
  section.append(node(doc, "p", "groups-composition__note",
    "Agreement needs two volunteers who tagged the same group independently, so it appears only where such a sample exists. Intervals are 95% ranges around each estimate."));
  section.append(node(doc, "h4", "", "Reasons groups could not be tagged"));
  if (reasons.length) {
    const list = node(doc, "ul", "groups-composition__reasons");
    for (const reason of reasons) list.append(node(doc, "li", "", `${reason.label}: ${reason.count}`));
    section.append(list);
  } else {
    section.append(node(doc, "p", "groups-composition__note", NO_IMPOSSIBLE_REASONS));
  }
  if (precision?.denominator_note) section.append(node(doc, "p", "groups-composition__note", precision.denominator_note));
  return section;
}

/**
 * Draws the three composition sections into el. Plot and d3 are the Framework's globals, passed in by the caller.
 * Charts size to the container (280 to 720 px wide). Without Plot the heatmaps fall back to text summaries;
 * the treemap needs d3. Layout is computed at mount time; it does not re-flow on resize.
 */
export function mountGroupsComposition(el, {groups = [], precision = null, Plot = null, d3 = null, width = 720, precisionGlobalOnly = false} = {}) {
  if (!el) return;
  const doc = el.ownerDocument;
  const fit = Math.max(280, Math.min(width, el.clientWidth || width));
  el.replaceChildren();
  el.classList.add("groups-composition");
  el.append(
    heatmapSection(doc, groups, Plot, fit),
    d3 ? treemapSection(doc, groups, d3, fit) : node(doc, "section", "groups-composition__section"),
    evidenceSection(doc, precision, precisionGlobalOnly),
  );
}
