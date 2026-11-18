// Plastiverse Live global landing: the scroll story and the sections after it (PLAT-2).
// A readable port of the owner-approved prototype engine (.impeccable/sketches/src/story_engine7.js).
// Spec: docs/PLAT_2_LANDING_SPEC.md. Plain canvas 2D, no animation library (ADR-VD30).
//
// Data and assets (all same-origin):
//   data/trend_global.json              works per year (chart, beat 8-9)
//   data/global/evidence_cells.json     live works per cell for the grid and #evidence (optional, PLAT-2b)
//   data/global/world_raster.json       world and California pixel rasters (beats 12-13, #regions)
//   assets/landing/picnic.json          picnic layout, item atlas rects and Voronoi seeds (offline,
//                                       scripts/build_landing_assets.py); the browser cuts the shards
//   assets/landing/papers.json          CC BY paper first pages (beat 5)
//   assets/world/world.json             country outlines for the #regions map (loaded lazily)
// Captions are real DOM text in the stage; the canvas is aria-hidden. Text never overlaps a visual:
// layout() measures the caption text boxes and places every visual in a safe zone (spec 4.10).
import {siteRoot} from "./atlas.js";

// ---- timeline -----------------------------------------------------------------------------
// Positions in scroll units (one unit is about 95% of a viewport height). TOT is the story length.
// This table is the one place to tune dwell. Pairs are [in, done]; quadruples are [in, full, fade, out].
export const TOT = 31.5;
export const TU = {
  move: [0.25, 0.75], pop: [1.3, 1.9], gdis: [2.5, 3.0], U: [2.95, 3.7],
  stack: [5.6, 6.4], papersOut: [7.0, 7.3],
  K: [7.3, 8.1], Kl: [8.3, 8.7, 10.3, 10.5], B: [10.5, 11.2], glow: [12.1, 12.6], burst: [12.6, 13.2],
  C: [13.4, 15.6], Cax: [17.4, 17.7, 20.5, 20.65], Ann: [17.85, 18.75],
  Ev: [20.7, 21.4], Evg: [21.2, 21.45, 23.3, 23.45],
  Nw: [23.5, 24.2], Nwl: [24, 24.3, 26, 26.15], spring: [23.8, 24.2, 25.9, 26.25],
  Mp: [26.25, 26.9], Mpu: [26.7, 27, 28.4, 28.55], Z: [28.55, 29.2], Zu: [29, 29.3],
};
// Reduced motion: one still per beat, at these positions (units).
export const STILLS = [
  ["picnic", 1.0], ["cloud", 4.7], ["papers", 6.7], ["mandala", 9.9], ["bulb", 12.5],
  ["chart", 20.2], ["grid", 22.9], ["network", 25.6], ["map", 28.0], ["california", 31.2],
];
const T = Object.fromEntries(Object.entries(TU).map(([k, v]) => [k, v.map((u) => u / TOT)]));
const POP = 0.4 / TOT;          // one item's pop
const HAIRLINE = 0.06 / TOT;    // cracks open
const FLY = 0.45 / TOT;         // shards fly out
const CRUMBLE = 0.35 / TOT;     // shards crumble into particles
const FADE = 0.25 / TOT;        // caption fade

// ---- colours (logo palette; the --pv-* tokens hold the same values) ---------------------------
const SLATE = [67, 100, 135], SLATE2 = [134, 169, 191], MINT = [197, 234, 223], CORAL = [250, 107, 104];
const SUN = [255, 244, 154], GOLD = [226, 183, 20], LIGHT = [246, 248, 249], NIGHT = [0, 0, 0];
const INK = "#17263d", INK2 = "#4d5d73", CORAL_INK = "#c53e39", GRID_LINE = "#c4d0d6";
const MAP_COLOURS = {"0": [233, 241, 239], "1": MINT, "2": SLATE2, "3": SLATE, c: CORAL};
const FONT = "'Schibsted Grotesk',system-ui,sans-serif", MONO = "'Martian Mono',ui-monospace,monospace";

// ---- small helpers ----------------------------------------------------------------------------
/** Deterministic LCG, identical to the prototype and scripts/build_landing_assets.py. */
export const rng = (seed) => () => {
  seed = (seed * 1664525 + 1013904223) >>> 0;
  return seed / 4294967296;
};
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const seg = (p, a, b) => clamp((p - a) / (b - a), 0, 1);
const win = (p, w) => seg(p, w[0], w[1]) * (1 - seg(p, w[2], w[3]));
const easeOut = (t) => 1 - Math.pow(1 - t, 3);
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const css = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const lum = (c) => 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2];
const fitContain = (nw, nh, box) => {
  const s = Math.min(box.w / nw, box.h / nh), w = nw * s, h = nh * s;
  return {x: box.x + (box.w - w) / 2, y: box.y + (box.h - h) / 2, w, h};
};
/** Filled size of a pixel-map cell: a 1 px gap on big cells, a proportional one on phones. */
const ink = (cell) => Math.max(cell * 0.78, cell - 1);
const lerpRect = (a, b, m) => ({x: a.x + (b.x - a.x) * m, y: a.y + (b.y - a.y) * m, w: a.w + (b.w - a.w) * m, h: a.h + (b.h - a.h) * m});
/** Hue for the mandala's colour order; greys sort after every hue, by lightness. */
function hue([r, g, b]) {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  if (d < 22) return 400 + mx;
  let h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  h *= 60;
  return h < 0 ? h + 360 : h;
}
function canvas(w, h) {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  return c;
}
async function json(path) {
  const response = await fetch(new URL(path, siteRoot()), {cache: "no-cache"});
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
  return response.json();
}
/** A fully decoded bitmap (decoded off the main thread, so the first drawImage is cheap). */
async function image(path) {
  const response = await fetch(new URL(path, siteRoot()), {cache: "no-cache"});
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
  return createImageBitmap(await response.blob());
}

// ---- the picnic: cells and Voronoi shards -------------------------------------------------------
/** Cells of a sprite on a grid of `f` px: [gx, gy, r, g, b] where alpha > 110, plus the empty
 *  cells that touch them (shards include those so their edges are not ragged). */
function spriteCells(sprite, f, test) {
  const gw = Math.ceil(sprite.width / f), gh = Math.ceil(sprite.height / f);
  const small = canvas(gw, gh), x = small.getContext("2d", {willReadFrequently: true});
  x.drawImage(sprite, 0, 0, gw, gh);
  const d = x.getImageData(0, 0, gw, gh).data, inside = new Uint8Array(gw * gh), cells = [], extra = [];
  for (let j = 0; j < gw * gh; j++) {
    const k = j * 4;
    if (test(d[k], d[k + 1], d[k + 2], d[k + 3])) {
      inside[j] = 1;
      cells.push([j % gw, (j / gw) | 0, d[k], d[k + 1], d[k + 2]]);
    }
  }
  for (const q of cells) {
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const X = q[0] + dx, Y = q[1] + dy;
      if (X < 0 || Y < 0 || X >= gw || Y >= gh) continue;
      const j = Y * gw + X;
      if (!inside[j]) { inside[j] = 2; extra.push([X, Y, 0, 0, 0]); }
    }
  }
  return {cells, extra};
}

/** Split one picture (an item or the blanket) into Voronoi shards cut from its own pixels.
 *  Seeds come from picnic.json (sprite-local grid units). Crack lines are cut per 2 px, never on
 *  the sampling grid, so fracture edges come out straight and clean (spec 4.2). */
const TIMINGS = [];
let taskStart = 0, taskLabel = "start";
/** Yield to the event loop; records how long the task that just ended ran (debug timings). */
const yieldTask = (label = "") => {
  const now = performance.now();
  if (taskStart) TIMINGS.push([taskLabel, Math.round(now - taskStart)]);
  return new Promise((resolve) => setTimeout(() => { taskStart = performance.now(); taskLabel = label; resolve(); }, 0));
};

async function fracture(c, cells, extra, f, seeds, rr) {
  const near = (gx, gy) => {
    let bi = 0, bd = 1e18;
    for (let k = 0; k < seeds.length; k++) {
      const dx = seeds[k][0] - gx, dy = seeds[k][1] - gy, dd = dx * dx + dy * dy;
      if (dd < bd) { bd = dd; bi = k; }
    }
    return bi;
  };
  const groups = seeds.map(() => ({cells: [], gx0: 1e9, gy0: 1e9, gx1: -1, gy1: -1, sx: 0, sy: 0}));
  const add = (q, core) => {
    const s = groups[near(q[0], q[1])];
    if (core) { s.cells.push(q); s.sx += q[0]; s.sy += q[1]; }
    s.gx0 = Math.min(s.gx0, q[0]); s.gx1 = Math.max(s.gx1, q[0]);
    s.gy0 = Math.min(s.gy0, q[1]); s.gy1 = Math.max(s.gy1, q[1]);
  };
  // Grouping is cells x seeds distance tests; chunk it so the blanket does not block for long.
  for (let i = 0; i < cells.length; i++) { add(cells[i], true); if (i % 4000 === 3999) await yieldTask("group cells"); }
  for (let i = 0; i < extra.length; i++) { add(extra[i], false); if (i % 4000 === 3999) await yieldTask("group extra"); }
  const local = (gx, gy) => [(gx + 0.5) * f - c.bw / 2, (gy + 0.5) * f - c.bh / 2];
  c.shards = [];
  for (const [s, k] of groups.map((g2, i) => [g2, i]).filter(([g2]) => g2.cells.length)) {
    // One shard per task keeps the main thread responsive (Lighthouse TBT) while the stage
    // still shows the first-paint picnic.
    await yieldTask(c.ground ? "blanket shard" : `item ${c.k} shard`);
    const gx0 = s.gx0 - 1, gy0 = s.gy0 - 1, w = (s.gx1 + 1 - gx0 + 1) * f, h = (s.gy1 + 1 - gy0 + 1) * f;
    const R2 = 2, mw = Math.ceil(w / R2), mh = Math.ceil(h / R2);
    const maskCanvas = canvas(mw, mh), m = maskCanvas.getContext("2d"), id = m.createImageData(mw, mh);
    let work = 0;  // distance tests since the last yield
    for (let my = 0; my < mh; my++) {
      for (let mx = 0; mx < mw; mx++) {
        const px = gx0 * f + (mx + 0.5) * R2, py = gy0 * f + (my + 0.5) * R2;
        if (near(px / f - 0.5, py / f - 0.5) === k) id.data[(my * mw + mx) * 4 + 3] = 255;
      }
      work += mw * seeds.length;
      if (work > 250000) { work = 0; await yieldTask("mask rows"); }
    }
    m.putImageData(id, 0, 0);
    const sx = gx0 * f, sy = gy0 * f, piece = canvas(w, h), x2 = piece.getContext("2d");
    x2.drawImage(c.sp, sx, sy, w, h, 0, 0, w, h);
    x2.globalCompositeOperation = "destination-in";
    x2.imageSmoothingEnabled = true;
    x2.drawImage(maskCanvas, 0, 0, w, h);
    const [cx, cy] = local(s.sx / s.cells.length, s.sy / s.cells.length);
    const len = Math.hypot(cx, cy) || 1, dir = Math.atan2(cy, cx) + (rr() - 0.5) * 0.9;
    const dist = c.ground ? 18 + rr() * 60 : (70 + rr() * 190) * (0.6 + 0.4 * Math.min(1, len / 120));
    c.shards.push({
      sp: piece, w, h, lx0: sx - c.bw / 2, ly0: sy - c.bh / 2, cx, cy,
      ox: Math.cos(dir) * dist, oy: Math.sin(dir) * dist, rs: (rr() - 0.5) * (c.ground ? 0.6 : 3.2),
      thr: rr(), cells: s.cells,
    });
  }
  const owner = new Map();
  c.shards.forEach((s, i) => s.cells.forEach((q) => owner.set(q, i)));
  c.pts = cells.map((q) => [c.shards[owner.get(q)], ...local(q[0], q[1]), q[2], q[3], q[4]]);
}

// ---- particles ----------------------------------------------------------------------------
const KINDS = ["frag", "frag", "fiber", "film", "bead", "grain", "flake"];
function makeParticles(n) {
  const r = rng(42), out = [];
  for (let i = 0; i < n; i++) {
    const kind = KINDS[Math.floor(r() * KINDS.length)], verts = [], nv = kind === "film" ? 5 : 4;
    for (let v = 0; v < nv; v++) {
      const a = (v / nv) * Math.PI * 2 + r() * 0.6;
      verts.push([Math.cos(a) * (0.6 + r() * 0.6), Math.sin(a) * (0.6 + r() * 0.6)]);
    }
    out.push({kind, rgb: [200, 200, 200], rot: r() * 6.28, spin: (r() - 0.5) * 6, size: 1.7 + r() * 1.9, verts, seed: r(), ur: r(), ua: r() * 6.28});
  }
  return out;
}

// ---- chart annotations (spec 4.5) -------------------------------------------------------------
function annotations(lastYear, lastValue) {
  return [
    {y: 1972, head: "Carpenter et al. 1972", sub: "“Polystyrene spherules in coastal waters”"},
    {y: 2004, head: "Thompson et al. 2004", sub: "“Lost at sea: where is all the plastic?”"},
    {y: lastYear, head: "Hartmann et al. 2026", sub: "“Lost in a sea of information: the microplastics publication deluge”", note: `${lastYear} to date: ${lastValue.toLocaleString("en-US")} works`},
  ];
}

// =============================================================================================
/** Mount the story inside `root` (the .plv element). Resolves once the first frame is drawn. */
export async function mountLandingStory(root) {
  const $ = (sel) => root.querySelector(sel);
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const story = $("#plv-story"), stage = $("#plv-stage"), cv = $("#plv-cv"), g = cv.getContext("2d");
  const hdr = $(".plv-top"), cue = $("#plv-cue"), stackEl = $("#plv-stack"), firstPaint = $("#plv-firstpaint");
  const debug = (window.__landingDebug = {ready: false, rects: [], collect: false, beats: {...TU}, TOT});

  // The first-paint picnic is the LCP image: fetch the story's heavier assets only after load.
  // Wait for load, a painted frame and an idle moment, so nothing here delays the first paint.
  if (document.readyState !== "complete") await new Promise((resolve) => addEventListener("load", resolve, {once: true}));
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  await new Promise((resolve) => (window.requestIdleCallback ? requestIdleCallback(resolve, {timeout: 1500}) : setTimeout(resolve, 200)));
  const [trend, picnic, papers, raster, evidence] = await Promise.all([
    json("data/trend_global.json"), json("assets/landing/picnic.json"),
    json("assets/landing/papers.json"), json("data/global/world_raster.json"),
    evidenceCells(),
  ]);
  // Footnote under the grid (canvas): live counts name their date; the illustrative grid says so.
  const liveDate = String(evidence?.fetched_at || "").slice(0, 10);
  const evidenceNote = evidence
    ? {wide: `worldwide; works per cell, OpenAlex${liveDate ? `, ${liveDate}` : ""}`, narrow: "works per cell"}
    : {wide: "worldwide; illustrative cell counts until the live counts are built", narrow: "illustrative counts"};

  // Chart data: 1970 to the latest year in the trend file.
  const byYear = trend.by_year || {};
  const lastYear = Math.min(new Date().getUTCFullYear(), Math.max(...Object.keys(byYear).map(Number)));
  const YEARS = Array.from({length: lastYear - 1969}, (_, i) => 1970 + i);
  const VALS = YEARS.map((y) => Number(byYear[String(y)] || 0));
  const total = VALS.reduce((a, b) => a + b, 0);
  const UNIT = Math.max(50, Math.round(total / 900 / 10) * 10);
  const colDots = VALS.map((v) => Math.round(v / UNIT));
  const N = colDots.reduce((a, b) => a + b, 0);
  root.querySelectorAll("[data-plv='unit']").forEach((el) => (el.textContent = UNIT.toLocaleString("en-US")));
  root.querySelectorAll("[data-plv='query']").forEach((el) => (el.textContent = trend.query_version || "unknown"));
  root.querySelectorAll("[data-plv='fetched']").forEach((el) => (el.textContent = String(trend.fetched_at || "").slice(0, 10)));
  root.querySelectorAll("[data-plv='map-fetched']").forEach((el) => (el.textContent = String(raster.fetched_at || "").slice(0, 10)));
  const ANN = annotations(lastYear, VALS[VALS.length - 1]);
  const annList = $("#plv-ann-list");
  if (annList) annList.innerHTML = ANN.map((a) => `<li>${a.head}, ${a.sub}${a.note ? `; ${a.note}` : ""}</li>`).join("");

  // Papers (beat 5): real CC BY first pages.
  stackEl.innerHTML = "";
  const paperImgs = papers.map((p) => {
    const img = document.createElement("img");
    img.alt = "";
    img.decoding = "async";
    img.dataset.src = new URL(`assets/landing/${p.src}`, siteRoot()).href;
    stackEl.append(img);
    return img;
  });

  const RAS = String(raster.world).split("|"), RC = RAS[0].length, RR = RAS.length;
  const ZR = String(raster.ca).split("|");
  const P = makeParticles(N);
  let W = 0, H = 0;
  const CH = {};
  let DUST = [], KL = [], NL = [], MAPU = null, ZU = {cell: 1}, DEB = [];
  const SC = {comps: []};
  const PAPERS = [];

  // Caption text box relative to the stage (DOM ranges, so the box hugs the text).
  const capBox = (sel) => {
    const el = root.querySelector(sel);
    if (!el) return {r: 0, b: 0, t: H};
    let r = 0, b = 0, t = 1e9;
    el.querySelectorAll("h1,h2,p").forEach((k) => {
      const range = document.createRange();
      range.selectNodeContents(k);
      const q = range.getBoundingClientRect();
      r = Math.max(r, q.right); b = Math.max(b, q.bottom); t = Math.min(t, q.top);
    });
    const s = stage.getBoundingClientRect();
    return {r: r - s.left, b: b - s.top, t: t - s.top};
  };

  // --- compose the picnic from the offline atlas -------------------------------------------
  const [blanketImg, atlasImg] = await Promise.all([
    image(`assets/landing/${picnic.blanket.src}`), image(`assets/landing/${picnic.atlas.src}`),
  ]);
  async function compose() {
    const f = picnic.grid || 4, fr = rng(91), items = [];
    for (const spec of picnic.items) {
      await yieldTask(`item ${spec.k} cells`);
      const sp = canvas(spec.w, spec.h);
      sp.getContext("2d").drawImage(atlasImg, spec.x, spec.y, spec.w, spec.h, 0, 0, spec.w, spec.h);
      const it = {sp, bw: spec.w, bh: spec.h, tx: spec.tx, ty: spec.ty, r0: spec.r0, sc: spec.sc, k: spec.k, area: spec.area, up: spec.up, vx: spec.vx, spin: spec.spin, ord: spec.ord};
      const {cells, extra} = spriteCells(sp, f, (r, g2, b, a) => a > 110);
      if (!cells.length) continue;
      await fracture(it, cells, extra, f, spec.seeds, fr);
      items.push(it);
    }
    items.sort((a, b) => a.k - b.k);
    const nw = picnic.blanket.w, nh = picnic.blanket.h, kc = canvas(nw, nh);
    kc.getContext("2d").drawImage(blanketImg, 0, 0, nw, nh);
    const ground = {sp: kc, bw: nw, bh: nh, tx: nw / 2, ty: nh / 2, r0: 0, sc: 1, ground: true, up: 0, vx: 0, spin: 0, ord: -1, k: -1};
    const F = picnic.blanket.grid || 8;
    const gcells = spriteCells(kc, F, (r, g2, b, a) => a > 40 && lum([r, g2, b]) > 40);
    await fracture(ground, gcells.cells, gcells.extra, F, picnic.blanket.seeds, fr);
    SC.comps = [ground, ...items];
    // Data particles: sampled from the items' pixels; about 18% come from the blanket as fibres.
    const pr = rng(3), pool = [];
    items.forEach((c) => c.pts.forEach((q) => pool.push([c, q])));
    for (const p of P) {
      let c, q;
      if (pr() < 0.18) { c = ground; q = ground.pts[Math.floor(pr() * ground.pts.length)]; p.kind = "fiber"; }
      else [c, q] = pool[Math.floor(pr() * pool.length)];
      p.c = c; p.sh = q[0]; p.lx = q[1] + (pr() - 0.5) * 4; p.ly = q[2] + (pr() - 0.5) * 4;
      p.rgb = [q[3], q[4], q[5]]; p.thr = pr();
      p.ea = Math.atan2(p.ly - p.sh.cy, p.lx - p.sh.cx) + (pr() - 0.5) * 2;
      p.edist = c.ground ? 0.2 + pr() * 0.5 : 0.3 + pr() * 1.1;
    }
    // Crumbs: one spray per shard, in its own colours; they swirl into the cloud and fade.
    const dr = rng(13), all = [];
    SC.comps.forEach((c) => c.pts.forEach((q) => all.push([c, q])));
    DEB = [];
    for (let i = 0; i < 3800; i++) {
      const [c, q] = all[Math.floor(dr() * all.length)];
      const a = Math.atan2(q[2] - q[0].cy, q[1] - q[0].cx) + (dr() - 0.5) * 2.4;
      const dd = (c.ground ? 10 : 25) + dr() * (c.ground ? 50 : 120);
      DEB.push({c, sh: q[0], lx: q[1] + (dr() - 0.5) * 6, ly: q[2] + (dr() - 0.5) * 6, rgb: css([q[3], q[4], q[5]]), thr: dr(), dx: Math.cos(a) * dd, dy: Math.sin(a) * dd + dr() * 20, s: 0.8 + dr() * 1.8, ua: dr() * 6.28, ur: Math.pow(dr(), 0.6)});
    }
  }

  // --- per-frame picnic transforms ---------------------------------------------------------
  function phaseOf(c, p, nI) {
    let s0, c0;
    if (c.ground) { c0 = T.gdis[0]; s0 = c0; }
    else { s0 = T.pop[0] + (c.ord / Math.max(1, nI - 1)) * (T.pop[1] - T.pop[0]); c0 = s0 + POP * 0.85; }
    return {tt: c.ground ? 0 : easeOut(seg(p, s0, s0 + POP)), c0, k0: c0 + HAIRLINE + FLY * 0.55,
      st: 0.03 * seg(p, c0, c0 + HAIRLINE) + 0.97 * easeOut(seg(p, c0 + HAIRLINE, c0 + HAIRLINE + FLY))};
  }
  function itemXf(c, R) {
    const s = R.w / picnic.blanket.w, tt = c.ph ? c.ph.tt : 0, k = c.sc * (1 + 0.3 * tt), r = c.r0 + c.spin * 0.35 * tt;
    return {s, k, r, co: Math.cos(r), si: Math.sin(r), X: R.x + c.tx * s + c.vx * W * 0.015 * tt, Y: R.y + c.ty * s - H * 0.07 * c.up * tt, tt};
  }
  function shardFrame(c) {
    const st = c.ph.st;
    for (const s of c.shards) {
      const a = s.rs * st;
      s.co = Math.cos(a); s.si = Math.sin(a); s.px = s.cx + s.ox * st; s.py = s.cy + s.oy * st;
    }
  }
  function shardPt(c, s, lx, ly) {
    const f = c.xf, ux = lx - s.cx, uy = ly - s.cy, X1 = s.px + ux * s.co - uy * s.si, Y1 = s.py + ux * s.si + uy * s.co, K = f.k * f.s;
    return [f.X + (X1 * f.co - Y1 * f.si) * K, f.Y + (X1 * f.si + Y1 * f.co) * K];
  }

  // --- layout: every target position, recomputed on resize -------------------------------------
  function placeStack(box) {
    const pr = rng(21), n = paperImgs.length, ph = Math.min(box.h * 0.62, box.w * 0.5), pw = ph * 0.773, y = box.y + box.h / 2;
    PAPERS.length = 0;
    paperImgs.forEach((im, i) => {
      const t = n > 1 ? i / (n - 1) : 0.5;
      const cx = box.x + pw / 2 + 12 + t * (box.w - pw - 24) + (pr() - 0.5) * 16, cy = y + (pr() - 0.5) * box.h * 0.06, rot = (pr() - 0.5) * 0.3;
      // Each page keeps its own aspect ratio (0.71-0.77); until it loads, assume 0.755.
      const aspect = im.naturalWidth ? im.naturalWidth / im.naturalHeight : 0.755;
      const pp = {el: im, cx, cy, w: ph * aspect, h: ph, rot};
      im.style.width = `${pp.w}px`;
      im.style.height = `${ph}px`;
      if (!im.naturalWidth) {
        im.addEventListener("load", () => { pp.w = ph * (im.naturalWidth / im.naturalHeight); im.style.width = `${pp.w}px`; }, {once: true});
      }
      PAPERS.push(pp);
    });
  }

  // Layout runs as steps: the first time with a yield between beats (keeps the main thread free
  // during load), on resize all at once.
  function layout() { for (const _ of layoutSteps()); }
  async function layoutYielding() { let i = 0; for (const _ of layoutSteps()) await yieldTask(`layout ${i++}`); }
  function* layoutSteps() {
    const r = stage.getBoundingClientRect();
    W = r.width; H = r.height;
    const dpr = Math.min(2, devicePixelRatio || 1);
    cv.width = W * dpr; cv.height = H * dpr;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const gut = Math.max(16, Math.min(48, W * 0.034)), narrow = W <= 860;
    CH.narrow = narrow;
    // Safe zone: right of the widest side caption on desktop; between the captions on phones.
    const tops = [".c1", ".c1n", ".c2", ".cb", ".c5", ".c4", ".c7"];
    const side = [...tops, ".c2b"].map(capBox), bottom = [".c2b"].map(capBox);
    const textR = Math.max(...side.map((o) => o.r)) + 40, capB = Math.max(...tops.map(capBox).map((o) => o.b)) + 20;
    const VX0 = narrow ? gut : Math.max(textR, W * 0.4), VX1 = W - gut;
    const VY0 = narrow ? capB : H * 0.14, VY1 = narrow ? Math.min(...bottom.map((o) => o.t)) - 16 : H * 0.94;
    Object.assign(CH, {VX0, VY0, VX1, VY1});
    // Phones: each beat's visual sits between its own caption and the screen bottom (or its own
    // bottom caption), not below the tallest caption of the whole story (spec 4.10).
    const zone = (tops, bottomSel) => {
      if (!narrow) return [VY0, VY1];
      const y0 = Math.max(...tops.map(capBox).map((o) => o.b)) + 20;
      const y1 = bottomSel ? capBox(bottomSel).t - 16 : H - 52;
      return [y0, Math.max(y0 + 80, y1)];
    };
    const order = P.map((p, i) => [p.seed, i]).sort((a, b) => a[0] - b[0]);
    // Picnic: nearly full screen on load; just below the title once it arrives.
    const c0 = capBox(".c0"), nw = picnic.blanket.w, nh = picnic.blanket.h;
    CH.sceneBig = fitContain(nw, nh, narrow ? {x: -W * 0.25, y: H * 0.2, w: W * 1.5, h: H * 0.6} : {x: gut, y: 60 + H * 0.02, w: W - 2 * gut, h: H - 60 - H * 0.06});
    CH.sceneT = fitContain(nw, nh, narrow ? {x: -W * 0.25, y: c0.b + 24, w: W * 1.5, h: H - c0.b - 24 - H * 0.08} : {x: gut, y: c0.b + 20, w: W - 2 * gut, h: H - c0.b - 20 - H * 0.04});
    if (firstPaint) Object.assign(firstPaint.style, {left: `${CH.sceneBig.x}px`, top: `${CH.sceneBig.y}px`, width: `${CH.sceneBig.w}px`, height: `${CH.sceneBig.h}px`});
    const [py0, py1] = zone([".c1n"]);
    placeStack({x: VX0, y: py0, w: VX1 - VX0, h: py1 - py0});
    const sc = W / 1440 + 0.35;
    P.forEach((p) => (p.eo = [Math.cos(p.ea) * p.edist * 130 * sc, Math.sin(p.ea) * p.edist * 130 * sc]));
    yield;
    // U: the loose cloud.
    const [uy0, uy1] = zone([".c1", ".c1n"]);
    const cx = (VX0 + VX1) / 2, cy = (uy0 + uy1) / 2, RXu = (VX1 - VX0) / 2, RYu = (uy1 - uy0) / 2;
    Object.assign(CH, {ucx: cx, ucy: cy, uRX: RXu * 0.9, uRY: RYu * 0.9});
    P.forEach((p) => {
      const rr = Math.pow(p.ur, 0.6);
      p.U = [cx + Math.cos(p.ua) * rr * RXu * 0.9, cy + Math.sin(p.ua) * rr * RYu * 0.9];
    });
    yield;
    // K: the mandala. Concentric rings, colours sorted around the circle, every piece radial (spec 4.3).
    const [ky0, ky1] = zone([".c2"], ".c2b"), kcy = (ky0 + ky1) / 2;
    const R = (Math.min(VX1 - VX0, ky1 - ky0) / 2) * 0.84;
    CH.K = [cx, kcy, R];
    const s0 = R * Math.sqrt(Math.PI / N) * 0.97, slots = [];
    for (let rr = s0 * 0.75, ring = 0; slots.length < N; rr += s0, ring++) {
      const n = Math.min(Math.max(1, Math.round((2 * Math.PI * rr) / s0)), N - slots.length), off = ring * 0.37;
      for (let k = 0; k < n; k++) slots.push([rr, ((k / n) * Math.PI * 2 + off) % (Math.PI * 2)]);
    }
    slots.sort((a, b) => a[1] - b[1] || a[0] - b[0]);
    [...P].sort((a, b) => hue(a.rgb) - hue(b.rgb) || lum(a.rgb) - lum(b.rgb)).forEach((p, j) => {
      const [r2, th] = slots[j];
      p.K = [cx + Math.cos(th) * r2, kcy + Math.sin(th) * r2];
      p.kr = r2 / R; p.kth = th;
      p.ksz = ((s0 * 0.36) / p.size) * (1.25 - 0.4 * Math.min(1, p.kr));
    });
    KL = [];
    const NWG = 48, wedges = Array.from({length: NWG}, () => []);
    P.forEach((p) => wedges[Math.floor((p.kth / (Math.PI * 2)) * NWG) % NWG].push(p));
    wedges.forEach((w) => {
      w.sort((a, b) => a.kr - b.kr);
      for (let i = 1; i < w.length; i++) if (w[i].kr - w[i - 1].kr < (s0 * 1.6) / R) KL.push([w[i - 1], w[i]]);
    });
    const dr = rng(17);
    DUST = [];
    for (let i = 0; i < 3000; i++) {
      const q = P[Math.floor(dr() * N)].rgb, a = dr() * 6.28, r3 = R * (1.06 + 0.75 * Math.pow(dr(), 1.4));
      const x = cx + Math.cos(a) * r3 * 1.2, y = kcy + Math.sin(a) * r3;
      // Fade the halo out over 40 px towards the edges of its area instead of cutting it straight.
      const xMin = narrow ? 0 : VX0, yMin = narrow ? ky0 : 60, yMax = narrow ? ky1 : H;
      const edge = clamp(Math.min(x - xMin, W - x, y - yMin, yMax - y) / 40, 0, 1);
      if (edge <= 0) continue;
      DUST.push([x, y, 0.6 + dr() * 1.2, q, dr(), edge]);
    }
    yield;
    // B: the light bulb, filled with the particles in mandala-angle order (spec 4.4).
    CH.bulbPaths = [...root.querySelectorAll("#plv-bulbsrc path")].map((q) => new Path2D(q.getAttribute("d")));
    const [bz0, bz1] = zone([".cb"]);
    const bh = Math.min(H * 0.7, (bz1 - bz0) * 0.96, (VX1 - VX0) * 1.4), bsc = bh / 270, bcx = (VX0 + VX1) / 2;
    const bx0 = bcx - 100 * bsc, by0 = (bz0 + bz1) / 2 - 135 * bsc;
    CH.bulb = [bcx, by0 + 100 * bsc, bh, bsc, bx0, by0];
    // Bulb glass as a 200x270 alpha mask, read once (isPointInPath per candidate was the slowest part).
    if (!CH.bulbMask) {
      const mc = canvas(200, 270), mx = mc.getContext("2d", {willReadFrequently: true});
      mx.fill(CH.bulbPaths[0]);
      CH.bulbMask = mx.getImageData(0, 0, 200, 270).data;
    }
    const inside = (x, y) => CH.bulbMask[((y | 0) * 200 + (x | 0)) * 4 + 3] > 127 || (x > 68 && x < 132 && y > 208 && y < 258);
    let dd = Math.sqrt(26500 / N), bs = [];
    for (let it = 0; it < 30; it++) {
      bs = [];
      for (let y = 12, row = 0; y < 258; y += dd * 0.88, row++) for (let x = 16 + ((row % 2) * dd) / 2; x < 186; x += dd) if (inside(x, y)) bs.push([x, y]);
      if (bs.length >= N) break;
      dd *= 0.97;
    }
    bs = bs.map((b) => [...b, (Math.atan2(b[1] - 110, b[0] - 100) + Math.PI * 2.5) % (Math.PI * 2)]).sort((a, b) => a[2] - b[2]);
    const step = bs.length / N;
    [...P].sort((a, b) => a.kth - b.kth).forEach((p, j) => {
      const b = bs[Math.floor(j * step)];
      p.B = [bx0 + b[0] * bsc, by0 + b[1] * bsc];
      p.bsz = (dd * bsc * 0.42) / p.size;
    });
    yield;
    // C: the unit chart. Desktop: headline middle-left over the empty early years; phones: below.
    const c3 = capBox(".c3"), c3s = root.querySelector(".c3s"), srcH = c3s.getBoundingClientRect().height;
    const x0 = Math.max(24, W * 0.06), x1 = W - x0, chartTop = 60 + H * 0.07;
    const base = narrow ? c3.t - 28 - srcH - 30 : H * 0.95 - srcH - 30, stride = (x1 - x0) / YEARS.length;
    c3s.style.top = `${base + 30}px`;
    c3s.style.left = `${x0}px`;
    Object.assign(CH, {x0, x1, base, stride, chartTop});
    annMeasure();
    const head = ANN[2].h + 26;
    let gap = Math.max(1.6, Math.min(6.2, stride / 3.3, (base - chartTop - head) / Math.ceil(Math.max(...colDots) / 3)));
    CH.txt = narrow ? null : {l: 0, t: c3.t - 12, r: c3.r + 16, b: c3.b + 14};
    if (CH.txt) colDots.forEach((n, i) => {
      const X = x0 + i * stride + stride / 2;
      if (X <= CH.txt.r && n > 0) gap = Math.min(gap, (base - CH.txt.b) / Math.ceil(n / 3));
    });
    CH.gap = gap;
    const cs = [];
    colDots.forEach((n, ci) => { for (let k = 0; k < n; k++) cs.push([x0 + ci * stride + stride / 2 + ((k % 3) - 1) * gap, base - (Math.floor(k / 3) + 0.5) * gap, ci]); });
    order.forEach(([, i], j) => { const s = cs[j] || cs[cs.length - 1]; P[i].C = [s[0], s[1]]; P[i].cj = j / N; });
    annLayout();
    yield;
    // Ev: the evidence grid. Live works per cell when evidence_cells.json is valid (PLAT-2b); until
    // then, illustrative weights. The dot allocation below normalises either.
    const ROWS = narrow ? ["occur.", "effects", "methods", "fate", "solutions"] : ["occurrence", "effects", "methods", "fate and transport", "solutions"];
    const COLS = narrow ? ["ocean", "fresh", "soil", "air", "biota", "people"] : ["ocean", "freshwater", "soil", "air", "food and biota", "people"];
    const WTS = evidence ? evidence.counts : [[30, 20, 8, 5, 12, 4], [18, 10, 4, 1, 16, 6], [10, 6, 3, 2, 3, 1], [8, 6, 3, 2, 1, 0], [4, 2, 0, 0, 1, 0]];
    const sw = WTS.flat().reduce((a, b) => a + b, 0), cnt = WTS.map((row) => row.map((v) => Math.floor((v / sw) * N)));
    cnt[0][0] += N - cnt.flat().reduce((a, b) => a + b, 0);
    const [ez0, ez1] = zone([".c5"]);
    const gx0 = VX0 + (narrow ? 56 : 120), gy0 = ez0 + 28, cw = (VX1 - gx0) / COLS.length, chh = Math.min(narrow ? 90 : 1e9, (ez1 - gy0 - 24) / ROWS.length);
    Object.assign(CH, {ROWS, COLS, gx0, gy0, cw, chh});
    let idx = 0;
    cnt.forEach((row, ri) => row.forEach((c, ci) => {
      const sp = Math.max(3.2, Math.min(6, Math.sqrt(((cw - 14) * (chh - 14)) / Math.max(c, 1)))), per = Math.max(1, Math.floor((cw - 14) / sp));
      for (let k = 0; k < c && idx < N; k++, idx++) {
        const p = P[order[idx][1]];
        p.Ev = [gx0 + ci * cw + 8 + (k % per) * sp + sp / 2, gy0 + ri * chh + 8 + Math.floor(k / per) * sp + sp / 2];
        p.evsp = sp;
      }
    }));
    yield;
    // Nw: an illustrative collaboration network, 7 communities.
    const [nz0, nz1] = zone([".c4"]);
    const nr = rng(11), NCOM = 7, coms = [];
    for (let k = 0; k < NCOM; k++) {
      const a = (k / NCOM) * 6.28 + nr() * 0.5;
      coms.push([(VX0 + VX1) / 2 + Math.cos(a) * (VX1 - VX0) * 0.32, (nz0 + nz1) / 2 + Math.sin(a) * (nz1 - nz0) * 0.3]);
    }
    CH.coms = coms;
    const members = coms.map(() => []);
    order.forEach(([, i], j) => {
      const k = j % NCOM, p = P[i], s = Math.sqrt(-2 * Math.log(nr() + 1e-6)) * Math.min(W, H) * 0.045, a = nr() * 6.28;
      p.Nw = [coms[k][0] + Math.cos(a) * s, coms[k][1] + Math.sin(a) * s];
      p.com = k;
      members[k].push(p);
    });
    NL = [];
    members.forEach((ms, k) => ms.forEach((p) => {
      for (let e = 0; e < 2; e++) { const q = ms[Math.floor(nr() * ms.length)]; if (q !== p) NL.push([p, q]); }
      if (nr() < 0.04) { const o = members[(k + 1 + Math.floor(nr() * (NCOM - 1))) % NCOM]; NL.push([p, o[Math.floor(nr() * o.length)]]); }
    }));
    yield;
    // Mp: the world pixel map, below its caption.
    const c6 = capBox(".c6"), my0 = c6.b + 24, mw = Math.min(W - 2 * gut, ((H * 0.96 - my0) * RC) / RR), cell = mw / RC, mx0 = (W - mw) / 2;
    MAPU = {mx0, my0, cell, mw, mh: cell * RR};
    const land = [];
    for (let r4 = 0; r4 < RR; r4++) for (let cc = 0; cc < RC; cc++) {
      const ch = RAS[r4][cc];
      if (ch === ".") continue;
      land.push([cc, r4, ch, ch === "c" ? 40 : ch === "3" ? 4 : ch === "2" ? 2 : ch === "1" ? 1 : 0.3]);
    }
    const mr = rng(5), pick = land.map((l) => [Math.pow(mr(), 1 / l[3]), l]).sort((a, b) => b[0] - a[0]).slice(0, N).map((x) => x[1]);
    order.forEach(([, i], j) => { const l = pick[j % pick.length]; P[i].Mp = [mx0 + (l[0] + 0.5) * cell, my0 + (l[1] + 0.5) * cell]; P[i].mch = l[2]; });
    yield;
    // Z: California at local scale.
    const [zz0, zz1] = zone([".c7"]);
    const zc = Math.min((zz1 - zz0) / ZR.length, (VX1 - VX0) / ZR[0].length), zx0 = (VX0 + VX1) / 2 - (zc * ZR[0].length) / 2, zy0 = zz0;
    ZU = {zx0, zy0, cell: zc};
    const zl = [];
    ZR.forEach((row, r4) => { for (let cc = 0; cc < row.length; cc++) if (row[cc] !== ".") zl.push([cc, r4, row[cc]]); });
    const zr = rng(9);
    for (let k = zl.length - 1; k > 0; k--) { const j = Math.floor(zr() * (k + 1)); [zl[k], zl[j]] = [zl[j], zl[k]]; }
    order.forEach(([, i], j) => {
      const l = zl[j % zl.length];
      P[i].Z = [zx0 + (l[0] + 0.5) * zc, zy0 + (l[1] + 0.5) * zc];
      P[i].zc = (l[2] === "w" ? zr() < 0.5 : zr() < 0.12) ? CORAL : zr() < 0.5 ? SLATE : SLATE2;
    });
  }

  // --- chart annotations: wrapped labels clear of the dots and the headline, with arrows --------
  function wrapText(text, font, maxW) {
    g.font = font;
    const out = [];
    let line = "";
    for (const w of text.split(" ")) {
      const t = line ? `${line} ${w}` : w;
      if (g.measureText(t).width > maxW && line) { out.push(line); line = w; } else line = t;
    }
    if (line) out.push(line);
    return out;
  }
  const annFont = (weight, fs) => (weight === "mono" ? `400 ${fs - 2}px ${MONO}` : `${weight} ${fs}px ${FONT}`);
  function annMeasure() {
    const fs = CH.narrow ? 11.5 : 13, lh = fs + 4, maxW = CH.narrow ? 136 : Math.min(250, W * 0.18);
    for (const a of ANN) {
      a.lines = [...wrapText(a.head, annFont(600, fs), maxW).map((t) => [t, 600]), ...wrapText(a.sub, annFont(400, fs), maxW).map((t) => [t, 400])];
      if (a.note) wrapText(a.note, annFont("mono", fs), maxW).forEach((l) => a.lines.push([l, "mono"]));
      a.h = a.lines.length * lh;
      a.w = Math.min(maxW, Math.max(...a.lines.map((l) => { g.font = annFont(l[1], fs); return g.measureText(l[0]).width; })));
      a.fs = fs; a.lh = lh;
    }
  }
  function annLayout() {
    const {x0, x1, base, stride, gap, chartTop} = CH;
    const X = (i) => x0 + i * stride + stride / 2, top = (i) => base - Math.ceil(colDots[i] / 3) * gap;
    const hitTxt = (x, y, w, h) => { const t = CH.txt; return t && x < t.r && x + w > t.l && y < t.b && y + h > t.t; };
    const fits = (x, y, w, h) => {
      if (x < x0 - 4 || x + w > x1 || hitTxt(x, y, w, h)) return false;
      for (let i = 0; i < YEARS.length; i++) { const xi = X(i); if (xi >= x - 8 && xi <= x + w + 8 && top(i) < y + h + 10) return false; }
      return true;
    };
    for (const a of ANN) { a.i = Math.max(0, YEARS.indexOf(a.y)); a.tx = X(a.i); a.ty = top(a.i) - 6; }
    const [c72, t04, h26] = ANN;
    h26.y0 = chartTop; h26.x0 = Math.max(x0, Math.min(x1 - h26.w, h26.tx - stride * 0.9 - h26.w));
    c72.y0 = base - 62 - c72.h; c72.x0 = c72.tx + stride * 2.5;
    t04.y0 = base - 90 - t04.h; t04.x0 = Math.max(x0, t04.tx - stride * 2 - t04.w);
    if (c72.x0 < t04.x0 + t04.w + 12 && c72.x0 + c72.w > t04.x0 - 12) t04.y0 = Math.min(t04.y0, c72.y0 - t04.h - 20);
    while (!fits(t04.x0, t04.y0, t04.w, t04.h) && t04.y0 < base - t04.h - 30) t04.y0 += 8;
    for (const a of ANN) {
      const left = a.tx > a.x0 + a.w / 2;
      a.ax = left ? a.x0 + a.w + 6 : a.x0 - 6;
      a.ay = a.y0 + Math.min(a.h - a.lh * 0.5, a.lh * 1.2);
      a.cxp = a.tx; a.cyp = a.ay;
    }
  }
  function drawAnn(a, f) {
    if (f <= 0) return;
    g.save();
    g.globalAlpha = Math.min(1, f * 2);
    g.textAlign = "left"; g.textBaseline = "top";
    a.lines.forEach((l, k) => { g.font = annFont(l[1], a.fs); g.fillStyle = l[1] === 600 ? INK : INK2; g.fillText(l[0], a.x0, a.y0 + k * a.lh + 1); });
    const q = Math.min(1, f * 1.4), pt = (s) => { const u = 1 - s; return [u * u * a.ax + 2 * u * s * a.cxp + s * s * a.tx, u * u * a.ay + 2 * u * s * a.cyp + s * s * a.ty]; };
    g.globalAlpha = 1; g.strokeStyle = CORAL_INK; g.lineWidth = 1.4; g.lineCap = "round";
    g.beginPath();
    for (let k = 0; k <= 24; k++) { const [x, y] = pt((q * k) / 24); k ? g.lineTo(x, y) : g.moveTo(x, y); }
    g.stroke();
    if (q > 0.98) {
      const [x, y] = pt(1), [xp, yp] = pt(0.92), an = Math.atan2(y - yp, x - xp);
      g.beginPath();
      g.moveTo(x, y); g.lineTo(x - Math.cos(an - 0.45) * 8, y - Math.sin(an - 0.45) * 8);
      g.moveTo(x, y); g.lineTo(x - Math.cos(an + 0.45) * 8, y - Math.sin(an + 0.45) * 8);
      g.stroke();
    }
    g.restore();
    if (debug.collect) debug.rects.push(["annotation", a.x0, a.y0, a.x0 + a.w, a.y0 + a.h]);
  }

  // --- drawing --------------------------------------------------------------------------------
  function shape(p, x, y, s, a, rgb, alpha, straight) {
    g.save();
    g.translate(x, y); g.rotate(a); g.globalAlpha = alpha;
    const col = css(rgb);
    if (p.kind === "fiber") {
      g.strokeStyle = col; g.lineWidth = Math.max(1.1, s * 0.45); g.lineCap = "round"; g.beginPath();
      if (straight) { g.moveTo(-s * 1.7, 0); g.lineTo(s * 1.7, 0); }
      else { g.moveTo(-s * 2.4, 0); g.quadraticCurveTo(-s, -s * 1.6, 0, 0); g.quadraticCurveTo(s, s * 1.6, s * 2.4, 0); }
      g.stroke();
    } else if (p.kind === "bead") { g.fillStyle = col; g.beginPath(); g.arc(0, 0, s * 0.9, 0, 7); g.fill(); }
    else if (p.kind === "grain") { g.fillStyle = col; g.fillRect(-s * 0.7, -s * 0.7, s * 1.4, s * 1.4); }
    else {
      g.fillStyle = col;
      if (p.kind === "film") g.globalAlpha = alpha * 0.65;
      g.beginPath();
      p.verts.forEach((v, i) => {
        const X = v[0] * s * (p.kind === "flake" ? 1.6 : 1.2), Y = v[1] * s * (p.kind === "flake" ? 0.7 : 1.2);
        i ? g.lineTo(X, Y) : g.moveTo(X, Y);
      });
      g.closePath(); g.fill();
    }
    g.restore();
  }
  const mark = (kind, x, y, r) => { if (debug.collect) debug.rects.push([kind, x - r, y - r, x + r, y + r]); };

  const fades = [...stage.querySelectorAll("[data-a]")].map((el) => ({el, a: +el.dataset.a / TOT, b: el.dataset.b ? +el.dataset.b / TOT : 9, cap: el.classList.contains("cap")}));
  const RAYS = (() => { const r = rng(42); return Array.from({length: 40}, (_, i) => [(i / 40) * Math.PI * 2 + r() * 0.08, 0.6 + r() * 0.6]); })();
  let lastPluck = 0;
  const progress = () => { const r = story.getBoundingClientRect(); return clamp(-r.top / (r.height - innerHeight), 0, 1); };

  /** Draw one frame. `t` is a timestamp (ms); `pAt` forces a story position (0..1) for stills. */
  function frame(t, pAt) {
    const still = pAt !== undefined, p = still ? pAt : progress();
    if (debug.collect) debug.rects = [];
    const bp = seg(p, ...T.burst), lit = bp >= 1;
    stage.style.background = css(lit ? LIGHT : NIGHT);
    stage.classList.toggle("lit", lit);
    if (!still) hdr.classList.toggle("on-dark", bp < 0.8 && story.getBoundingClientRect().bottom > 60);
    g.clearRect(0, 0, W, H);
    const nI = SC.comps.length - 1;
    if (!still) cue.style.opacity = String(1 - seg(p, 0.05 / TOT, 0.25 / TOT));
    // The picnic: full screen, then just below the title; it shatters in place.
    const R = lerpRect(CH.sceneBig, CH.sceneT, easeInOut(seg(p, ...T.move)));
    for (const c of SC.comps) { c.ph = phaseOf(c, p, nI); c.xf = itemXf(c, R); if (p >= c.ph.c0) shardFrame(c); }
    const drawOrder = [SC.comps[0], ...SC.comps.slice(1).sort((a, b) => a.ph.tt - b.ph.tt || a.k - b.k)];
    for (const c of drawOrder) {
      const f = c.xf, ph = c.ph, K = f.k * f.s;
      if (p < ph.c0) {
        g.save();
        if (!c.ground) {
          g.shadowColor = `rgba(0,0,0,${0.45 - 0.15 * f.tt})`; g.shadowBlur = (16 + 30 * f.tt) * f.s;
          g.shadowOffsetX = (5 + 14 * f.tt) * f.s; g.shadowOffsetY = (7 + 40 * f.tt) * f.s;
        }
        g.translate(f.X, f.Y); g.rotate(f.r);
        g.drawImage(c.sp, (-c.bw * K) / 2, (-c.bh * K) / 2, c.bw * K, c.bh * K);
        g.restore();
        if (debug.collect) {
          // Bounding box of the rotated sprite (tighter than a circle for the wide blanket).
          const hw = (c.bw * K) / 2, hh = (c.bh * K) / 2, ex = Math.abs(hw * f.co) + Math.abs(hh * f.si), ey = Math.abs(hw * f.si) + Math.abs(hh * f.co);
          debug.rects.push(["picnic", f.X - ex, f.Y - ey, f.X + ex, f.Y + ey]);
        }
        continue;
      }
      for (const s of c.shards) {
        const sa = 1 - seg(p, ph.k0 + s.thr * CRUMBLE * 0.5, ph.k0 + CRUMBLE);
        if (sa <= 0.004) continue;
        g.save();
        g.globalAlpha = sa;
        if (!c.ground) { g.shadowColor = "rgba(0,0,0,.4)"; g.shadowBlur = 10 * f.s; g.shadowOffsetY = (10 + 30 * f.tt) * f.s; }
        g.translate(f.X, f.Y); g.rotate(f.r); g.scale(K, K); g.translate(s.px, s.py); g.rotate(s.rs * ph.st);
        g.drawImage(s.sp, s.lx0 - s.cx, s.ly0 - s.cy, s.w, s.h);
        g.restore();
        if (debug.collect) { const [x, y] = shardPt(c, s, s.cx, s.cy); mark("shard", x, y, (Math.max(s.w, s.h) * K) / 2); }
      }
    }
    g.globalAlpha = 1;
    // Papers drop in one by one, fanned (beat 5).
    PAPERS.forEach((pp, i) => {
      const n = PAPERS.length, span = T.stack[1] - T.stack[0], a0 = T.stack[0] + (span * i) / n;
      const o = easeOut(seg(p, a0, a0 + (span / n) * 1.6)) * (1 - seg(p, ...T.papersOut));
      pp.el.style.opacity = o;
      pp.el.style.transform = `translate(${pp.cx - pp.w / 2}px,${pp.cy - pp.h / 2 - (1 - o) * 60}px) rotate(${pp.rot}rad)`;
      if (o > 0.01 && debug.collect) debug.rects.push(["paper", pp.cx - pp.w * 0.6, pp.cy - pp.h * 0.6, pp.cx + pp.w * 0.6, pp.cy + pp.h * 0.6]);
    });
    for (const f of fades) {
      const o = seg(p, f.a, f.a + FADE) * (1 - seg(p, f.b - FADE, f.b));
      f.el.style.opacity = o;
      if (f.cap) { f.el.style.transform = `translateY(${(1 - o) * 12}px)`; f.el.style.visibility = o > 0 ? "visible" : "hidden"; }
    }
    // Glow, then a radial light burst from the bulb (beat 7).
    const gl = seg(p, ...T.glow);
    if (CH.bulb) {
      const [bx, by, bh] = CH.bulb;
      if (gl > 0 && bp < 1) {
        const gr = g.createRadialGradient(bx, by, 0, bx, by, bh * (0.4 + 0.25 * gl));
        gr.addColorStop(0, `rgba(255,236,170,${0.7 * gl})`); gr.addColorStop(1, "rgba(255,236,170,0)");
        g.fillStyle = gr; g.fillRect(0, 0, W, H);
      }
      if (bp > 0 && bp < 1) {
        const maxR = Math.max(Math.hypot(bx, by), Math.hypot(W - bx, by), Math.hypot(bx, H - by), Math.hypot(W - bx, H - by)) * 1.05, rr = maxR * easeOut(bp);
        g.save(); g.lineCap = "round";
        for (const [a, l] of RAYS) {
          g.strokeStyle = `rgba(255,226,150,${0.55 * (1 - bp)})`; g.lineWidth = 2 + 6 * (1 - bp);
          g.beginPath(); g.moveTo(bx + Math.cos(a) * rr * 0.6, by + Math.sin(a) * rr * 0.6);
          g.lineTo(bx + Math.cos(a) * rr * (1 + 0.6 * l), by + Math.sin(a) * rr * (1 + 0.6 * l)); g.stroke();
        }
        g.restore();
        g.fillStyle = css(LIGHT); g.beginPath(); g.arc(bx, by, rr, 0, 7); g.fill();
        const ring = g.createRadialGradient(bx, by, rr * 0.82, bx, by, rr * 1.08);
        ring.addColorStop(0, "rgba(255,244,200,0)"); ring.addColorStop(0.7, `rgba(255,226,140,${0.8 * (1 - bp * 0.6)})`); ring.addColorStop(1, "rgba(255,226,140,0)");
        g.fillStyle = ring; g.fillRect(0, 0, W, H);
      }
    }
    const tU = easeInOut(seg(p, ...T.U)), tK = easeInOut(seg(p, ...T.K)), tB = easeInOut(seg(p, ...T.B));
    const tV = easeInOut(seg(p, ...T.Ev)), tN = easeInOut(seg(p, ...T.Nw)), tM = easeInOut(seg(p, ...T.Mp)), tZ = easeInOut(seg(p, ...T.Z));
    const rotU = still ? 0 : (t / 1000) * 0.02 * (1 - tK), ucx = CH.ucx, ucy = CH.ucy, kOn = tK * (1 - tB);
    // Dust halo beyond the mandala, twinkling gently.
    if (kOn > 0) {
      const tw = t / 1000;
      for (const [x, y, s, c, k, edge] of DUST) { g.globalAlpha = kOn * edge * (0.2 + 0.5 * k) * (0.75 + 0.25 * Math.sin(tw * 1.3 + k * 40)); g.fillStyle = css(c); g.fillRect(x, y, s, s); }
      g.globalAlpha = 1;
      mark("mandala", CH.K[0], CH.K[1], CH.K[2] * 1.2);
    }
    // Underlays: evidence grid, world map, California.
    const ev = win(p, T.Evg);
    if (ev > 0) {
      const {ROWS, COLS, gx0, gy0, cw, chh} = CH;
      g.globalAlpha = ev; g.strokeStyle = GRID_LINE; g.lineWidth = 1;
      g.font = `${CH.narrow ? 9 : 10}px ${MONO}`; g.fillStyle = INK2;
      for (let i = 0; i <= ROWS.length; i++) { g.beginPath(); g.moveTo(gx0, gy0 + i * chh); g.lineTo(gx0 + cw * COLS.length, gy0 + i * chh); g.stroke(); }
      for (let j = 0; j <= COLS.length; j++) { g.beginPath(); g.moveTo(gx0 + j * cw, gy0); g.lineTo(gx0 + j * cw, gy0 + chh * ROWS.length); g.stroke(); }
      g.textAlign = "right"; g.textBaseline = "alphabetic";
      ROWS.forEach((r2, i) => g.fillText(r2, gx0 - 8, gy0 + i * chh + chh / 2 + 3));
      g.textAlign = "center";
      COLS.forEach((c2, j) => g.fillText(c2, gx0 + j * cw + cw / 2, gy0 - 10));
      g.textAlign = "right";
      g.fillText(CH.narrow ? evidenceNote.narrow : evidenceNote.wide, gx0 + cw * COLS.length, gy0 + chh * ROWS.length + 18);
      g.globalAlpha = 1;
      if (debug.collect) debug.rects.push(["grid", gx0 - 120, gy0 - 22, gx0 + cw * COLS.length, gy0 + chh * ROWS.length + 22]);
    }
    const mu = win(p, T.Mpu);
    if (mu > 0 && MAPU) {
      const {mx0, my0, cell} = MAPU;
      g.globalAlpha = mu * 0.9;
      for (let r4 = 0; r4 < RR; r4++) { const row = RAS[r4]; for (let cc = 0; cc < RC; cc++) { const ch = row[cc]; if (ch === ".") continue; g.fillStyle = css(MAP_COLOURS[ch] || SLATE); g.fillRect(mx0 + cc * cell, my0 + r4 * cell, ink(cell), ink(cell)); } }
      g.globalAlpha = 1;
      if (debug.collect) debug.rects.push(["map", mx0, my0, mx0 + MAPU.mw, my0 + MAPU.mh]);
    }
    const zu = seg(p, ...T.Zu);
    if (zu > 0) {
      const {zx0, zy0, cell} = ZU;
      g.globalAlpha = zu;
      for (let r4 = 0; r4 < ZR.length; r4++) { const row = ZR[r4]; for (let cc = 0; cc < row.length; cc++) { const ch = row[cc]; if (ch === ".") continue; g.fillStyle = ch === "w" ? "#e7f2f1" : "#cfe9e6"; g.fillRect(zx0 + cc * cell, zy0 + r4 * cell, ink(cell), ink(cell)); } }
      g.globalAlpha = 1;
      if (debug.collect) debug.rects.push(["california", zx0, zy0, zx0 + cell * ZR[0].length, zy0 + cell * ZR.length]);
    }
    // Bulb outline and filament: faint glass first, yellow once it turns on.
    const bo = seg(p, T.B[0] + 0.3 / TOT, T.B[1]) * (1 - seg(p, T.C[0] - 0.1 / TOT, T.C[0] + 0.2 / TOT));
    if (bo > 0 && CH.bulbPaths) {
      const [, , bh, bsc, bx0, by0] = CH.bulb;
      g.save(); g.translate(bx0, by0); g.scale(bsc, bsc); g.lineWidth = 1.3 / bsc; g.lineJoin = "round"; g.lineCap = "round";
      g.strokeStyle = css(mix([215, 222, 235], mix(SUN, GOLD, bp), Math.max(gl, bp)), 0.55 * bo + 0.35 * bo * gl);
      CH.bulbPaths.forEach((pa) => g.stroke(pa));
      g.restore();
      mark("bulb", CH.bulb[0], by0 + 135 * bsc, bh / 2);
    }
    // Springy network: nodes chase their targets on damped springs; a community is plucked now and then.
    const spr = reduce || still ? 0 : win(p, T.spring);
    if (spr > 0.5 && t - lastPluck > 2300) {
      lastPluck = t;
      const k = Math.floor(Math.random() * CH.coms.length), [kx, ky] = CH.coms[k];
      for (const q of P) if (q.com === k && q.sOn) { q.vx += (q.sx - kx) * 0.09 + (Math.random() - 0.5) * 2; q.vy += (q.sy - ky) * 0.09 + (Math.random() - 0.5) * 2; }
    }
    // Crumbs: each shard sprays small pieces of its own colours, which swirl into the cloud and fade.
    if (tU < 1 && p > T.pop[0] && DEB.length) {
      for (const d of DEB) {
        const c = d.c, ph = c.ph, a0 = ph.k0 + d.thr * CRUMBLE * 0.8;
        if (p < a0) continue;
        const al = seg(p, a0, a0 + 0.04 / TOT) * (1 - tU);
        if (al <= 0.01) continue;
        let [x, y] = shardPt(c, d.sh, d.lx, d.ly);
        const dm = easeOut(seg(p, a0, a0 + 0.7 / TOT));
        x += d.dx * dm; y += d.dy * dm;
        x += (CH.ucx + Math.cos(d.ua) * d.ur * CH.uRX - x) * tU; y += (CH.ucy + Math.sin(d.ua) * d.ur * CH.uRY - y) * tU;
        g.globalAlpha = al; g.fillStyle = d.rgb; g.fillRect(x, y, d.s, d.s);
        if (al > 0.2) mark("crumb", x, y, d.s);
      }
      g.globalAlpha = 1;
    }
    // Data particles through every beat.
    const pos = new Map(), yel = Math.max(gl, bp);
    for (const q of P) {
      if (!q.c) continue;
      const st = q.cj * (1.4 / TOT), ph = q.c.ph, a0 = ph.k0 + q.thr * CRUMBLE * 0.7;
      let x, y;
      if (p >= ph.c0) [x, y] = shardPt(q.c, q.sh, q.lx, q.ly);
      else { const f = q.c.xf, K = f.k * f.s; x = f.X + (q.lx * f.co - q.ly * f.si) * K; y = f.Y + (q.lx * f.si + q.ly * f.co) * K; }
      const dm = easeOut(seg(p, a0, a0 + 0.7 / TOT)) * 0.55;
      x += q.eo[0] * dm; y += q.eo[1] * dm;
      const ux = q.U[0] - ucx, uy = q.U[1] - ucy, a2 = rotU * (1 + q.seed), cr = Math.cos(a2), sr = Math.sin(a2);
      x += (ucx + ux * cr - uy * sr - x) * tU; y += (ucy + ux * sr + uy * cr - y) * tU;
      x += (q.K[0] - x) * tK; y += (q.K[1] - y) * tK;
      x += (q.B[0] - x) * tB; y += (q.B[1] - y) * tB;
      const tC = easeInOut(seg(p - st, ...T.C));
      x += (q.C[0] - x) * tC; y += (q.C[1] - y) * tC;
      if (q.Ev) { x += (q.Ev[0] - x) * tV; y += (q.Ev[1] - y) * tV; }
      x += (q.Nw[0] - x) * tN; y += (q.Nw[1] - y) * tN;
      if (spr > 0) {
        const tx = x + Math.sin(t / 900 + q.seed * 20) * 2.5, ty = y + Math.cos(t / 1100 + q.seed * 30) * 2.5;
        if (!q.sOn) { q.sx = x; q.sy = y; q.vx = 0; q.vy = 0; q.sOn = true; }
        q.vx = (q.vx + (tx - q.sx) * 0.05) * 0.88; q.vy = (q.vy + (ty - q.sy) * 0.05) * 0.88;
        q.sx += q.vx; q.sy += q.vy;
        x += (q.sx - x) * spr; y += (q.sy - y) * spr;
      } else q.sOn = false;
      x += (q.Mp[0] - x) * tM; y += (q.Mp[1] - y) * tM;
      x += (q.Z[0] - x) * tZ; y += (q.Z[1] - y) * tZ;
      pos.set(q, [x, y]);
      const show = seg(p, a0, a0 + 0.05 / TOT);
      if (show <= 0) continue;
      let rgb = mix(q.rgb, mix(SUN, GOLD, bp), yel * (1 - tC));
      rgb = mix(rgb, SLATE, tC); rgb = mix(rgb, SLATE, tV);
      rgb = mix(rgb, q.com === 2 ? CORAL : SLATE, tN);
      rgb = mix(rgb, MAP_COLOURS[q.mch] || SLATE, tM);
      rgb = mix(rgb, q.zc, tZ);
      let radius;
      if (tM > 0.5) {
        const cc = MAPU.cell + (ZU.cell - MAPU.cell) * tZ;
        g.globalAlpha = show; g.fillStyle = css(rgb); g.fillRect(x - cc / 2, y - cc / 2, ink(cc), ink(cc));
        radius = cc / 2;
      } else if (tC > 0.65) {
        radius = tN > 0.5 ? 2.6 : tV > 0.5 ? Math.max(1.2, (q.evsp || 4) * 0.34) : Math.max(1.3, CH.gap * 0.38);
        g.globalAlpha = show; g.fillStyle = css(rgb); g.beginPath(); g.arc(x, y, radius, 0, 7); g.fill();
      } else {
        let f = (1 + 0.5 * tU * (1 - tK)) * (1 + 1.2 * (1 - seg(p, a0, a0 + 0.35 / TOT)));
        f += (q.ksz - f) * tK; f += (q.bsz - f) * tB;
        const r0 = q.rot + q.spin * (dm + tU), ord = Math.max(kOn, tB * (1 - tC));
        shape(q, x, y, q.size * f, r0 + (q.kth - r0) * ord, rgb, show, ord > 0.5);
        radius = q.size * f * 2.4;
      }
      if (show > 0.2) mark("particle", x, y, radius);
    }
    g.globalAlpha = 1;
    const kl = win(p, T.Kl);
    if (kl > 0) {
      g.lineWidth = 0.5; g.strokeStyle = `rgba(225,228,236,${0.2 * kl})`; g.beginPath();
      for (const [a, b] of KL) { const A = pos.get(a), B = pos.get(b); g.moveTo(A[0], A[1]); g.lineTo(B[0], B[1]); }
      g.stroke();
    }
    const ax = win(p, T.Cax);
    if (ax > 0) {
      const {x0, x1, base, stride} = CH;
      g.globalAlpha = ax; g.strokeStyle = INK2; g.fillStyle = INK2; g.lineWidth = 1;
      g.beginPath(); g.moveTo(x0, base + 3); g.lineTo(x1, base + 3); g.stroke();
      g.font = `10px ${MONO}`; g.textAlign = "center"; g.textBaseline = "alphabetic";
      YEARS.forEach((y, i) => {
        if (y % 10 === 0 || y === lastYear) {
          const X = x0 + i * stride + stride / 2;
          g.beginPath(); g.moveTo(X, base + 3); g.lineTo(X, base + 8); g.stroke(); g.fillText(y, X, base + 20);
        }
      });
      g.globalAlpha = 1;
      const n = ANN.length, aw = (T.Ann[1] - T.Ann[0]) / n, out = 1 - seg(p, T.Cax[2], T.Cax[3]);
      ANN.forEach((a, i) => drawAnn(a, seg(p, T.Ann[0] + i * aw, T.Ann[0] + (i + 1) * aw) * out));
    }
    const nl = win(p, T.Nwl);
    if (nl > 0) {
      g.lineWidth = 0.5; g.strokeStyle = `rgba(23,38,61,${0.22 * nl})`; g.beginPath();
      for (const [a, b] of NL) { const A = pos.get(a), B = pos.get(b); g.moveTo(A[0], A[1]); g.lineTo(B[0], B[1]); }
      g.stroke();
    }
  }

  // --- start ------------------------------------------------------------------------------------
  if (document.fonts && document.fonts.ready) await document.fonts.ready;
  await compose();
  // Paper pages are needed from beat 5 on; load them once the picnic is ready.
  paperImgs.forEach((img) => (img.src = img.dataset.src));
  await layoutYielding();
  await yieldTask("after layout");
  if (reduce) {
    await renderStills();
    if (firstPaint) firstPaint.hidden = true;
  } else {
    runLoop();
  }
  addEventListener("resize", () => { layout(); if (reduce) renderStills(); });
  await yieldTask("end");
  debug.timings = TIMINGS;
  debug.ready = true;
  debug.frame = (pUnits) => frame(performance.now(), pUnits / TOT);
  debug.enable = () => { debug.collect = true; };
  debug.visualRects = () => debug.rects.map(([kind, x0, y0, x1, y1]) => ({kind, x0, y0, x1, y1}));
  debug.captionRects = () => {
    const s = stage.getBoundingClientRect(), out = [];
    stage.querySelectorAll(".cap").forEach((cap) => {
      if (cap.style.visibility === "hidden" || Number(cap.style.opacity || 0) < 0.05) return;
      cap.querySelectorAll("h1,h2,p").forEach((k) => {
        if (Number(getComputedStyle(k).opacity) < 0.05) return;
        const range = document.createRange();
        range.selectNodeContents(k);
        for (const q of range.getClientRects()) out.push({cls: cap.className, x0: q.left - s.left, y0: q.top - s.top, x1: q.right - s.left, y1: q.bottom - s.top});
      });
    });
    return out;
  };

  // Render loop: only while the story is on screen and the tab is visible. At the very top the
  // first-paint image already shows frame 0, so the canvas takes over on the first scroll.
  function runLoop() {
    if (progress() <= 0) {
      cue.style.opacity = "1";
      addEventListener("scroll", () => { if (firstPaint) firstPaint.hidden = true; startLoop(); }, {once: true, passive: true});
      return;
    }
    if (firstPaint) firstPaint.hidden = true;
    startLoop();
  }
  function startLoop() {
    let onScreen = true, raf = 0;
    const tick = (t) => { raf = 0; frame(t); schedule(); };
    const schedule = () => { if (!raf && onScreen && !document.hidden) raf = requestAnimationFrame(tick); };
    new IntersectionObserver((entries) => { onScreen = entries[0].isIntersecting; schedule(); }).observe(story);
    document.addEventListener("visibilitychange", schedule);
    frame(performance.now());
    schedule();
  }

  // Reduced motion: one static figure per beat, each with its caption, as a vertical sequence.
  async function renderStills() {
    await Promise.all(paperImgs.map((i) => i.decode().catch(() => {})));
    const holder = root.querySelector("#plv-stills");
    holder.innerHTML = "";
    const dpr = Math.min(2, devicePixelRatio || 1);
    for (const [name, units] of STILLS) {
      frame(0, units / TOT);
      const fig = document.createElement("figure");
      fig.className = `plv-still${units >= TU.burst[1] ? " lit" : ""}`;
      fig.dataset.beat = name;
      const img = document.createElement("img");
      img.className = "plv-still-img";
      img.alt = "";
      const copy = canvas(W * dpr, H * dpr);
      copy.getContext("2d").drawImage(cv, 0, 0);
      img.src = copy.toDataURL("image/webp", 0.85);
      fig.append(img);
      // Papers are DOM images in the stage; draw the visible ones into the still too.
      if (name === "papers") {
        const x = copy.getContext("2d");
        x.scale(dpr, dpr);
        for (const pp of PAPERS) {
          x.save(); x.translate(pp.cx, pp.cy); x.rotate(pp.rot);
          x.drawImage(pp.el, -pp.w / 2, -pp.h / 2, pp.w, pp.h);
          x.restore();
        }
        img.src = copy.toDataURL("image/webp", 0.85);
      }
      stage.querySelectorAll(".cap").forEach((cap) => {
        if (Number(cap.style.opacity || 0) < 0.5) return;
        const clone = cap.cloneNode(true);
        clone.style.opacity = "1"; clone.style.transform = "none"; clone.style.visibility = "visible";
        clone.querySelectorAll("[data-a]").forEach((el) => { if (Number(el.style.opacity || 0) < 0.5) el.remove(); else el.style.opacity = "1"; });
        clone.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));
        if (units >= TU.burst[1]) clone.classList.remove("dk");
        fig.append(clone);
      });
      holder.append(fig);
    }
    root.classList.add("reduced");
  }
}

// ---- header and region pickers ----------------------------------------------------------------
const PICKER_HTML = `<div class="plv-pk-h">Pick a region <span>2 regions</span></div>
<a class="plv-row live" href="./california/"><div class="plv-sw l"></div><div><b>California</b><br><small>live atlas, daily build</small></div><div class="plv-go">Open atlas <svg width="14" height="10" viewBox="0 0 14 10" aria-hidden="true"><path d="M1 5h11M8 1l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></div></a>
<a class="plv-row" href="./ambassadors"><div class="plv-sw s"></div><div>Norway<br><small>in preparation</small></div><div class="plv-go quiet">Help build it</div></a>
<a class="plv-row" href="./ambassadors"><div class="plv-sw r"></div><div>Your region<br><small>opens on request</small></div><div class="plv-go quiet">Request</div></a>
<p class="plv-pk-note">Regions open where people ask for them. Each needs local researchers to guide the sources and check the data before it goes live.</p>`;

export function mountPickers(root) {
  root.querySelectorAll("[data-plv='picker']").forEach((el) => (el.innerHTML = PICKER_HTML));
  const button = root.querySelector("#plv-regions-btn"), panel = root.querySelector("#plv-hdr-picker");
  if (!button || !panel) return;
  const set = (open) => { panel.hidden = !open; button.setAttribute("aria-expanded", String(open)); };
  button.addEventListener("click", () => set(panel.hidden));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) { set(false); button.focus(); } });
  document.addEventListener("click", (e) => { if (!panel.hidden && !panel.contains(e.target) && !button.contains(e.target)) set(false); });
}

// ---- #regions: the world pixel map with country outlines --------------------------------------
export function mountRegionsMap(root) {
  const box = root.querySelector("#plv-mapbox");
  if (!box) return;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let started = false;
  const start = async () => {
    if (started) return;
    started = true;
    const [raster, world] = await Promise.all([json("data/global/world_raster.json"), json("assets/world/world.json")]);
    const rows = String(raster.world).split("|"), cols = rows[0].length, cell = raster.cell || 7;
    const mw = cols * cell, mh = rows.length * cell;
    box.style.aspectRatio = `${mw} / ${mh}`;
    const px = box.querySelector("canvas"), pg = px.getContext("2d");
    const token = (name) => getComputedStyle(root).getPropertyValue(name).trim();
    const colour = {"0": token("--pv-wash"), "1": token("--pv-mint"), "2": token("--pv-slate-2"), "3": token("--pv-slate"), c: token("--pv-coral")};
    // The canvas matches the box's real size, so cells are never shrunk by CSS (that caused moire
    // on phones). Small cells get no gutter.
    let size = 0, step = 0, pd = 1;
    const fit = () => {
      pd = Math.min(2, devicePixelRatio || 1);
      size = box.clientWidth;
      px.width = Math.round(size * pd); px.height = Math.round(((size * mh) / mw) * pd);
      pg.setTransform(pd, 0, 0, pd, 0, 0);
      step = size / cols;
    };
    const draw = (n) => {
      const gap = step >= 4 ? 1 : 0;
      for (let r = 0; r < rows.length; r++) {
        const row = rows[r];
        for (let c = 0; c < Math.min(n, row.length); c++) {
          const ch = row[c];
          if (ch === ".") continue;
          pg.fillStyle = colour[ch] || colour["0"];
          pg.fillRect(c * step, r * step, step - gap, step - gap);
        }
      }
    };
    fit();
    new ResizeObserver(() => { if (box.clientWidth && Math.abs(box.clientWidth - size) > 1) { fit(); draw(cols); } }).observe(box);
    // Outlines over the pixels: every country, Norway dashed, California breathing (CSS).
    const [c0, c1] = world.crop, svg = box.querySelector("svg"), ns = "http://www.w3.org/2000/svg";
    svg.setAttribute("viewBox", `0 ${c0} ${world.w} ${c1 - c0}`);
    svg.setAttribute("preserveAspectRatio", "none");
    const clip = document.createElementNS(ns, "clipPath"), sphere = document.createElementNS(ns, "path");
    clip.id = "plv-sph"; sphere.setAttribute("d", world.sphere); clip.append(sphere);
    const defs = document.createElementNS(ns, "defs"); defs.append(clip);
    const outline = document.createElementNS(ns, "g");
    outline.setAttribute("class", "o"); outline.setAttribute("clip-path", "url(#plv-sph)");
    for (const c of world.countries) { const path = document.createElementNS(ns, "path"); path.setAttribute("d", c.d); outline.append(path); }
    const norway = world.countries.find((c) => c.id === "578");
    const no = document.createElementNS(ns, "path"); no.setAttribute("class", "no"); if (norway) no.setAttribute("d", norway.d);
    const ca = document.createElementNS(ns, "path"); ca.setAttribute("class", "ca"); ca.setAttribute("d", world.ca);
    svg.replaceChildren(defs, outline, no, ca);
    if (reduce) { draw(cols); return; }
    const t0 = performance.now();
    let k = 0;
    const reveal = (t) => {
      const q = Math.min(1, (t - t0) / 1400), n = Math.round((1 - Math.pow(1 - q, 3)) * cols);
      if (n > k) { pg.save(); pg.beginPath(); pg.rect(k * step, 0, (n - k) * step, px.height); pg.clip(); draw(n); pg.restore(); k = n; }
      if (q < 1) requestAnimationFrame(reveal);
    };
    requestAnimationFrame(reveal);
  };
  new IntersectionObserver((entries, ob) => { if (entries[0].isIntersecting) { ob.disconnect(); start(); } }, {rootMargin: "400px"}).observe(box);
}

// ---- #evidence: live works per cell (PLAT-2b) -------------------------------------------------
// The build writes data/global/evidence_cells.json. When it is valid, the grid on the canvas and the
// #evidence table show its counts; otherwise both keep the illustrative numbers. One shared request.
const LEDE_ILLUSTRATIVE = "Rebuilt daily from OpenAlex once the cell definitions are agreed.";
let liveCells = null;
/** The live cell counts, or null when the file is missing, unreadable or invalid. Never rejects. */
function evidenceCells() {
  if (!liveCells) liveCells = json("data/global/evidence_cells.json").then(validCells, () => null);
  return liveCells;
}
/** The file when it is plat2b.v1: 5 rows of 6 non-negative integers, max > 0, and some work counted. */
function validCells(data) {
  if (!data || data.schema_version !== "plat2b.v1" || !Array.isArray(data.counts) || data.counts.length !== 5) return null;
  const shapeOk = data.counts.every((row) => Array.isArray(row) && row.length === 6 && row.every((n) => Number.isInteger(n) && n >= 0));
  if (!shapeOk || typeof data.max !== "number" || !(data.max > 0)) return null;
  return data.counts.flat().some((n) => n > 0) ? data : null;
}
/** Rewrites the #evidence table, its caption, lede and source line from the live counts. Without valid
 *  counts it changes nothing, so the illustrative markup stays. */
async function mountEvidenceMap() {
  const section = document.getElementById("evidence");
  const table = section?.querySelector("[data-plv='evidence-table']");
  const data = table ? await evidenceCells() : null;
  if (!data) return;
  const {max, counts} = data, gapBelow = (Number(data.gap_share) || 0) * max, date = String(data.fetched_at || "").slice(0, 10);
  table.querySelectorAll("tbody tr").forEach((tr, r) => tr.querySelectorAll("td").forEach((td, c) => {
    const n = counts[r]?.[c];
    if (n === undefined) return;
    const v = Math.min(1, n / max);
    td.style.setProperty("--v", v.toFixed(2));
    td.classList.toggle("dk", v >= 0.6);
    td.classList.toggle("gap", n < gapBelow);
    const span = td.querySelector("span");
    if (span) span.textContent = n.toLocaleString("en-US");
  }));
  const caption = table.querySelector("[data-plv='evidence-caption']");
  if (caption) caption.textContent = "Works per cell by topic and setting, worldwide, from OpenAlex";
  const lede = section.querySelector("[data-plv='evidence-lede']");
  if (lede) lede.textContent = lede.textContent.replace(LEDE_ILLUSTRATIVE, "Rebuilt daily from OpenAlex.");
  const source = section.querySelector("[data-plv='evidence-src']");
  const how = data.row_field === "title.search" ? "the topic named in the title and the setting in the title or abstract, among works matching the reviewed plastics query" : "title and abstract matches of the reviewed plastics query";
  if (source) source.textContent = `Works per cell: ${how}, OpenAlex${date ? `, updated ${date}` : ""}. A work can count in several cells.`;
}
// Set up at module start, not behind the story's load waits, so the table updates even if the story is skipped.
const startEvidenceMap = () => mountEvidenceMap().catch((error) => console.error("evidence map:", error));
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startEvidenceMap, {once: true});
else startEvidenceMap();
