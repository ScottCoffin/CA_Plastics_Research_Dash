// Colours for the Framework's JavaScript charts, maps and Sankey (VD-9). Every value here must equal
// the matching token in framework/src/design/tokens.css; tests/test_vd9_palette.py enforces that.
// Topic hues stay in shared/topics.js: they are the Atlas's identity colours for data.
// Note: framework/.gitignore ignores shared/ except force-tracked files, so this file needs `git add -f`.

// Secondary categorical set for agencies, sectors, monitoring matrices and network communities.
// Fixed order, never cycled. Anything beyond the named slots takes OTHER.
export const SECONDARY = Object.freeze(["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#7A4E9B"]);

// Maps and scatter plots (--pairs all): the first six slots. The seventh fails the CVD warn band.
export const SECONDARY_ALL_PAIRS = Object.freeze(SECONDARY.slice(0, 6));

// The one grey for every "Other" or unknown slot.
export const OTHER = "#8a969c";

// Sequential teal ramp, light to dark (--seq-100 to --seq-700), for every heatmap and choropleth.
export const SEQ = Object.freeze(["#e3f2ed", "#b9e0d3", "#86c7b2", "#4fa68c", "#23876d", "#0e6e56", "#043e32"]);

// Chart chrome. Gridlines use grid; axes and tick labels use axis; text stays in text or ink colours.
export const CHROME = Object.freeze({
  grid: "#d5e0dd",
  axis: "#4a5d6c",
  text: "#1d2a33",
  surface: "#ffffff",
  sunken: "#eaf1ef"
});

// Cell label ink: black or white, whichever contrasts more with the fill.
export const INK_DARK = "#000000";
export const INK_LIGHT = "#ffffff";

// Neutral blue-greys for Sankey sector nodes, in SECTOR_ORDER. Topics carry colour in the Sankey instead.
export const NEUTRAL_STEPS = Object.freeze(["#2f5d8a", "#5f8fb8", "#86a3bd", "#55616b", "#8b959d", "#a9b4bd", "#c3cbd1"]);
export const NEUTRAL_FUNDER = "#3d4f5c";
export const NEUTRAL_EDGE = "#7d8a90";

const channels = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};

// Colour at t in [0, 1] along SEQ. Neighbouring steps are interpolated, so the ramp darkens smoothly.
export function rampFill(t) {
  const x = Math.min(1, Math.max(0, Number(t) || 0)) * (SEQ.length - 1);
  const i = Math.min(SEQ.length - 2, Math.floor(x));
  const f = x - i;
  const a = channels(SEQ[i]);
  const b = channels(SEQ[i + 1]);
  return "#" + a.map((v, k) => Math.round(v + (b[k] - v) * f).toString(16).padStart(2, "0")).join("");
}

// Heatmap cell fill for a count. Zero is the sunken fill, and any non-zero count starts at seq-200,
// so one work never looks like an empty cell (seq-100 is too close to sunken); max reaches seq-700.
export function countFill(count, max) {
  const n = Number(count) || 0;
  if (n <= 0 || !(max > 0)) return CHROME.sunken;
  const t = Math.min(1, n / max);
  const start = 1 / (SEQ.length - 1);
  return rampFill(start + (1 - start) * t);
}
