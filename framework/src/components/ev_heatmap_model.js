// Pure helpers for the Evidence Map heatmap (EV-HEATMAP). No DOM access; labels are added by the view.
// Rows are topic tags (from domain_tags). Columns are matrix tags (from facet_tags) plus a
// "No matrix tag" column, or 5-year publication bins. A work counts once per cell it falls in.

export const MODES = ["topic-matrix", "topic-year"];
export const NO_MATRIX_KEY = "__no_matrix__";
export const NO_MATRIX_LABEL = "No matrix tag";
export const BIN_WIDTH = 5;

const TOPIC_ORDER = [
  "occurrence_and_monitoring",
  "fate_transport_and_sorption",
  "soil_and_agriculture",
  "analytical_methods",
  "ecotoxicology_and_trophic_transfer",
  "wastewater_and_treatment",
  "human_exposure_and_health_risk",
  "air",
  "risk_assessment",
  "plastisphere"
];
const MATRIX_ORDER = [
  "matrix:marine",
  "matrix:freshwater",
  "matrix:soil_and_agriculture",
  "matrix:food_and_drink",
  "matrix:air",
  "matrix:wastewater"
];

const EMPTY_FILL = "#f4f7f6";
const LOW_FILL = "#d3ece6";
const HIGH_FILL = "#0b4d48";
const INK_DARK = "#000000";
const INK_LIGHT = "#ffffff";

// Fallback label for a matrix tag without a shared label; the view prefers the shared topic label helper.
function titleFromKey(key) {
  const words = String(key).replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function isMatrix(tag) {
  return String(tag).startsWith("matrix:");
}

function uniqueSorted(values, canonical) {
  const extras = [...new Set(values)].filter((v) => !canonical.includes(v)).sort();
  return [...canonical, ...extras];
}

function yearOf(row) {
  const raw = row ? row.year : null;
  if (raw === null || raw === undefined || raw === "") return null;
  const year = Number(raw);
  return Number.isInteger(year) ? year : null;
}

// Five-year bins aligned to multiples of 5, from the bin holding the earliest year to the bin holding
// the latest. The last bin is labelled up to the latest year present (e.g. "2025–2026").
export function yearBins(years) {
  if (!years.length) return [];
  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);
  const bins = [];
  for (let start = Math.floor(minYear / BIN_WIDTH) * BIN_WIDTH; start <= maxYear; start += BIN_WIDTH) {
    const end = Math.min(start + BIN_WIDTH - 1, maxYear);
    bins.push({key: String(start), start, end, label: end > start ? `${start}–${end}` : String(start)});
  }
  return bins;
}

function binIndexFor(year, bins) {
  if (year === null) return -1;
  return bins.findIndex((bin) => year >= bin.start && year <= bin.end);
}

function addId(store, row, col, id) {
  const key = `${row}\u0000${col}`;
  if (!store.has(key)) store.set(key, new Set());
  store.get(key).add(id);
}

// heatmapCells(rows, mode) -> {rows:[tag], cols:[{key,label}], cells:[{row,col,count,ids}], max}
// rows: [{work_id, year, domain_tags, facet_tags}]. Every row x column pair gets a cell (zeros included)
// so the grid keeps its shape as filters change. `col` is the column key.
export function heatmapCells(rows, mode) {
  if (!MODES.includes(mode)) throw new Error(`Unknown heatmap mode: ${mode}`);
  const input = Array.isArray(rows) ? rows : [];
  const topicTags = uniqueSorted(
    input.flatMap((r) => (Array.isArray(r.domain_tags) ? r.domain_tags : [])).filter((t) => !isMatrix(t)),
    TOPIC_ORDER
  );

  let cols;
  let colsFor;
  if (mode === "topic-matrix") {
    const matrixTags = uniqueSorted(
      input.flatMap((r) => (Array.isArray(r.facet_tags) ? r.facet_tags : [])).filter(isMatrix),
      MATRIX_ORDER
    );
    cols = [
      ...matrixTags.map((key) => ({key, label: titleFromKey(key.slice("matrix:".length))})),
      {key: NO_MATRIX_KEY, label: NO_MATRIX_LABEL}
    ];
    colsFor = (r) => {
      const matrices = (Array.isArray(r.facet_tags) ? r.facet_tags : []).filter(isMatrix);
      return matrices.length ? [...new Set(matrices)] : [NO_MATRIX_KEY];
    };
  } else {
    const years = input.map(yearOf).filter((y) => y !== null);
    const bins = yearBins(years);
    cols = bins.map((bin) => ({key: bin.key, label: bin.label}));
    colsFor = (r) => {
      const index = binIndexFor(yearOf(r), bins);
      return index < 0 ? [] : [bins[index].key];
    };
  }

  const store = new Map();
  input.forEach((r, i) => {
    const id = r && r.work_id !== undefined && r.work_id !== null ? r.work_id : `row-${i}`;
    const topics = (Array.isArray(r && r.domain_tags) ? r.domain_tags : []).filter((t) => !isMatrix(t));
    const targets = colsFor(r);
    for (const topic of new Set(topics)) {
      for (const col of targets) addId(store, topic, col, id);
    }
  });

  const cells = [];
  let max = 0;
  for (const row of topicTags) {
    for (const col of cols) {
      const ids = store.has(`${row}\u0000${col.key}`) ? [...store.get(`${row}\u0000${col.key}`)] : [];
      max = Math.max(max, ids.length);
      cells.push({row, col: col.key, count: ids.length, ids});
    }
  }
  return {rows: topicTags, cols, cells, max};
}

function hexToRgb(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function toHex([r, g, b]) {
  return "#" + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
}

// Sequential single-hue scale. 0 (or no maximum) is the near-white empty fill; any positive count is
// a teal from light (LOW_FILL) to dark (HIGH_FILL), linear in count / max, so darker means more works.
export function colorFor(count, max) {
  if (!(count > 0) || !(max > 0)) return EMPTY_FILL;
  const t = Math.min(1, count / max);
  const lo = hexToRgb(LOW_FILL);
  const hi = hexToRgb(HIGH_FILL);
  return toHex(lo.map((v, i) => v + (hi[i] - v) * t));
}

function luminance(rgb) {
  const [r, g, b] = rgb.map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(a, b) {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

// Text ink for a fill: black or white, whichever gives the higher contrast. Pure black and white are
// used because no single dark grey reaches 4.5:1 on every mid-tone; black and white together do.
export function textInk(fill) {
  const rgb = hexToRgb(fill);
  if (!rgb) return INK_DARK;
  return contrastRatio(rgb, hexToRgb(INK_LIGHT)) >= contrastRatio(rgb, hexToRgb(INK_DARK))
    ? INK_LIGHT
    : INK_DARK;
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
