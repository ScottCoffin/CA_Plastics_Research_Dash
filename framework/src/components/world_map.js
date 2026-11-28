// Shared world-map pieces (AMB-1): the Natural Earth I frame, the place index and its search, the zoom and
// gesture rules, and the boundary layers of world.json. /explore (components/explore.js) and the ambassadors
// page (components/ambassadors.js) both import this module, so one projection, one minimum zoom box and one
// set of gestures serve every global map. Pure helpers are exported for the node runtime tests; the DOM
// helpers are attachMapGestures and mountPlaceSearch.

// ---- projection ------------------------------------------------------------------------------
// Natural Earth I (d3 geoNaturalEarth1), the one projection for every global map. world.json, the raster in
// explore.json and the places index are all in this frame, so markers and places are projected here with the
// same polynomial and the same frame as scripts/build_world_map.py.
// Natural Earth I in radians on the unit sphere (Patterson, 2007), as scripts/build_world_map.py.
function neRad(lam, phi) {
  const p2 = phi * phi, p4 = p2 * p2;
  const x = lam * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)));
  const y = phi * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)));
  return [x, y];
}
// Frame: x from 0 at longitude -180 to 1000 at +180; y from 0 at latitude 90 down. Same as world.json's viewBox.
const NE = {XM: neRad(Math.PI, 0)[0], YM: neRad(0, Math.PI / 2)[1], W: 1000};
NE.SCALE = NE.W / (2 * NE.XM);
export const FRAME_WIDTH = NE.W;
export function frameXY(lon, lat) {
  const [x, y] = neRad((lon * Math.PI) / 180, (lat * Math.PI) / 180);
  return [(x + NE.XM) * NE.SCALE, (NE.YM - y) * NE.SCALE];
}

// ---- zoom boxes ------------------------------------------------------------------------------
// The smallest zoom extent, in kilometres. Most places zoom to a 300 km box; island states (owner 2026-11-25) to
// 120 km, so their main islands fill more of the view. ISLAND_ISO is the list of island states on the maps.
export const MIN_EXTENT_KM = 300;
export const ISLAND_MIN_EXTENT_KM = 120;
export const ISLAND_ISO = new Set(["FJ", "FM", "KI", "MH", "NR", "PW", "SB", "TO", "TV", "VU", "WS"]);
export function minKmFor(iso) {
  return ISLAND_ISO.has(iso) ? ISLAND_MIN_EXTENT_KM : MIN_EXTENT_KM;
}
// The box that holds a [west, south, east, north] box at least minKm big, centred on the original box.
export function minimumBox(bbox, minKm = MIN_EXTENT_KM) {
  const [w, s, e, n] = bbox;
  const midLat = (s + n) / 2, kmDegLat = 111.32;
  const kmDegLon = kmDegLat * Math.max(Math.cos((midLat * Math.PI) / 180), 0.05);
  const cx = (w + e) / 2, cy = (s + n) / 2;
  const width = Math.max(e - w, minKm / kmDegLon), height = Math.max(n - s, minKm / kmDegLat);
  return [cx - width / 2, Math.max(cy - height / 2, -90), cx + width / 2, Math.min(cy + height / 2, 90)];
}
// A place's geometry is a [west, south, east, north] box or a [lon, lat] point.
export function boxOf(geom) {
  return geom.length === 4 ? geom : [geom[0], geom[1], geom[0], geom[1]];
}
// A place's extent in frame units: the projected bounds of its box, sampled along each edge.
export function frameExtent(bbox) {
  const [w, s, e, n] = bbox;
  const pts = [];
  for (let i = 0; i <= 8; i++) {
    const f = i / 8;
    pts.push([w + (e - w) * f, s], [w + (e - w) * f, n], [w, s + (n - s) * f], [e, s + (n - s) * f]);
  }
  const xy = pts.map(([lon, lat]) => frameXY(lon, lat));
  return [Math.min(...xy.map((p) => p[0])), Math.min(...xy.map((p) => p[1])), Math.max(...xy.map((p) => p[0])), Math.max(...xy.map((p) => p[1]))];
}
// The zoom extent of a place (frame units): its minimum box for its country's size class.
export function placeExtent(geom, iso) {
  return frameExtent(minimumBox(boxOf(geom), minKmFor(iso)));
}

// ---- zoom and pan (pure; tested by tests/framework_explore_zoom_runtime.mjs) -------------------
// Zoom 1 is the whole frame; ZOOM_MAX is the closest zoom. A view is [x, y, w, h] in frame units.
export const ZOOM_MAX = 60;
export function clampWidth(width, frameWidth) {
  return Math.min(frameWidth, Math.max(frameWidth / ZOOM_MAX, width));
}
// Scale factor for one wheel event (deltaMode 0 pixels, 1 lines, 2 pages). Each event is capped so a fast wheel cannot jump.
export function wheelFactor(deltaY, deltaMode = 0) {
  const px = Math.max(-200, Math.min(200, deltaY * (deltaMode === 1 ? 16 : deltaMode === 2 ? 400 : 1)));
  return Math.exp(-px * 0.002);
}
// Zoom a view by factor (above 1 zooms in) and keep the point (ax, ay) where it is on screen. The aspect is kept.
export function zoomView(view, factor, ax, ay, frameWidth) {
  const [x, y, w, h] = view;
  const nw = clampWidth(w / factor, frameWidth), k = nw / w;
  return [ax - (ax - x) * k, ay - (ay - y) * k, nw, h * k];
}
// Keep a view inside the frame. A view bigger than the frame in one direction is centred on it.
export function clampView(view, frame) {
  const [fx, fy, fw, fh] = frame, [x, y, w, h] = view;
  const cx = w >= fw ? fx + (fw - w) / 2 : Math.max(fx, Math.min(x, fx + fw - w));
  const cy = h >= fh ? fy + (fh - h) / 2 : Math.max(fy, Math.min(y, fy + fh - h));
  return [cx, cy, w, h];
}

// ---- gestures (pure; tested by tests/framework_explore_zoom_runtime.mjs) ---------------------
// The how-to-zoom hint stays on screen until the map is activated (owner 2026-11-25), so it is never a timed flash.
export const WHEEL_HINT = "Hold Ctrl and scroll to zoom, or click the map first";
export const TOUCH_HINT = "Use two fingers to move the map";
// A wheel zooms the map only with Ctrl or Cmd held, or while the map is active; otherwise the page scrolls.
export function wheelZooms(event, active) {
  return Boolean(event.ctrlKey || event.metaKey || active);
}
// The map is active after a press or focus inside it, and inactive after Escape, focus leaving it or a press outside.
export function nextActive(active, kind) {
  if (kind === "inside") return true;
  if (kind === "escape" || kind === "leave" || kind === "outside") return false;
  return active;
}
// One finger on touch scrolls the page (hint only); a mouse, or two or more fingers, pan the map.
export function dragMode(pointerType, pointerCount) {
  return pointerType === "touch" && pointerCount < 2 ? "hint" : "pan";
}

// ---- places (pure) ---------------------------------------------------------------------------
// Entries of places.json (schema places-v1) as objects; the compact arrays are documented in docs/SITE_DATA.md.
export function placeRows(payload) {
  if (payload?.schema !== "places-v1" || !Array.isArray(payload.entries)) return [];
  const aliases = payload.aliases || {};
  return payload.entries.map(([name, k, p, iso, geom, population]) => ({
    name, kind: payload.kinds[k], parent: payload.parents[p], iso, geom, population,
    key: foldName(name), alt: (aliases[iso] || []).map(foldName),
  }));
}
export function foldName(s) {
  return String(s ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}
const KIND_RANK = {country: 0, admin1: 1, city: 2};
export const KIND_LABEL = {country: "Country", admin1: "Region", city: "City"};
// Matches ranked by how well the name matches (exact, then word start, then inside), then kind, then population.
export function searchPlaces(rows, query, limit = 8) {
  const q = foldName(query);
  if (!q) return [];
  const scored = [];
  for (const r of rows) {
    const names = [r.key, ...r.alt];
    let score = -1;
    for (const n of names) {
      if (n === q) { score = 0; break; }
      if (n.startsWith(q)) score = score < 0 || score > 1 ? 1 : score;
      else if (n.split(/[\s,.()'-]+/).some((word) => word.startsWith(q))) score = score < 0 || score > 2 ? 2 : score;
      else if (n.includes(q)) score = score < 0 || score > 3 ? 3 : score;
    }
    if (score >= 0) scored.push({r, score});
  }
  scored.sort((a, b) => a.score - b.score || KIND_RANK[a.r.kind] - KIND_RANK[b.r.kind] || (b.r.population || 0) - (a.r.population || 0) || a.r.name.localeCompare(b.r.name));
  return scored.slice(0, limit).map((s) => s.r);
}

// ---- boundary layers (world.json) ------------------------------------------------------------
// Natural Earth disputed boundary lines (dashed) and Pacific grouping lines (dotted), in the world.json frame.
export function boundaryPaths(world) {
  return {disputed: world?.disputed || "", pacific: world?.pacific_groups || ""};
}

// ---- DOM: place search -----------------------------------------------------------------------
export const SEARCH_ICON = '<svg class="i" viewBox="0 0 14 14" aria-hidden="true"><circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M9.5 9.5L13 13" stroke="currentColor" stroke-width="1.4"/></svg>';
const escapeText = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
// A combobox over place rows. Choosing a row calls onPick(row). sub(row) gives the line under the name and
// count(row) the figure at the end; listClass and optClass let a page keep its own styles.
export function mountPlaceSearch(host, {id, rows, onPick, sub, count = () => "", listClass = "pop", optClass = "opt", placeholder = "Find a country or place"}) {
  const subline = sub || ((r) => (r.kind === "country" ? "Country" : `${KIND_LABEL[r.kind]}, ${r.parent}`));
  host.innerHTML = `${SEARCH_ICON}<input type="search" id="${id}" placeholder="${escapeText(placeholder)}" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="${id}-list" aria-autocomplete="list"><div class="${listClass}" id="${id}-list" role="listbox" hidden></div>`;
  const input = host.querySelector("input"), list = host.querySelector(`.${listClass}`);
  let hits = [], active = -1;
  const paint = () => {
    list.innerHTML = hits.length
      ? hits.map((r, i) => `<div role="option" class="${optClass}" id="${id}-o${i}" data-i="${i}" aria-selected="${i === active}"><span></span><span>${escapeText(r.name)}<small>${escapeText(subline(r))}</small></span><span class="n">${escapeText(count(r))}</span></div>`).join("")
      : `<p class="pop-note" style="border:0">No place matches “${escapeText(input.value)}”.</p>`;
    input.setAttribute("aria-activedescendant", active >= 0 ? `${id}-o${active}` : "");
    list.querySelectorAll(`.${optClass}`).forEach((o, i) => o.style.background = i === active ? "color-mix(in srgb, var(--pv-slate) 10%, var(--pv-paper))" : "");
  };
  const open = (v) => { list.hidden = !v; input.setAttribute("aria-expanded", String(v)); };
  const pick = (r) => { input.value = ""; open(false); onPick(r); };
  input.addEventListener("input", () => {
    hits = searchPlaces(rows, input.value);
    active = hits.length ? 0 : -1;
    paint(); open(!!input.value.trim());
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); if (hits.length) { active = (active + (e.key === "ArrowDown" ? 1 : -1) + hits.length) % hits.length; paint(); } }
    else if (e.key === "Enter" && hits[active]) { e.preventDefault(); pick(hits[active]); }
    else if (e.key === "Escape") { open(false); }
  });
  input.addEventListener("blur", () => setTimeout(() => open(false), 150));
  list.addEventListener("mousedown", (e) => { const o = e.target.closest("[data-i]"); if (o) { e.preventDefault(); pick(hits[+o.dataset.i]); } });
  return input;
}

// ---- DOM: gestures ---------------------------------------------------------------------------
// A press anywhere else deactivates the map. Only the most recent map's listener is kept.
let outsideTap = null;
let outsideSvg = null;
// Cooperative gestures for one map svg (spec section 10). The wheel zooms with Ctrl or Cmd, or once the map is
// active (click, tap or focus); otherwise the page scrolls and the hint explains how. One finger scrolls the page
// on touch; two fingers pan and pinch. Options:
//   frame: [x, y, w, h] of the whole map; view(): the current view; apply(view): show a view (already clamped);
//   reset(): show the whole map; hint: element that shows the how-to text (shown while the map is inactive);
//   drag: an object whose moved flag is set by a drag, so the click that ends a drag can be ignored;
//   before(): run before each user gesture (for example to cancel an animation).
// Returns zoomBy(factor, ax?, ay?) for on-map buttons.
export function attachMapGestures(svg, {frame, view, apply, reset, hint, drag = {moved: false}, before = () => {}}) {
  const pts = new Map();
  let press = {x: 0, y: 0}, active = false, hintText = WHEEL_HINT;
  const paintHint = () => {
    if (!hint) return;
    hint.textContent = hintText;
    hint.classList.toggle("show", !active);
  };
  const setHint = (text) => { hintText = text; paintHint(); };
  const setActive = (kind) => {
    const next = nextActive(active, kind);
    if (next === active) return;
    active = next;
    paintHint();
  };
  if (outsideTap) document.removeEventListener("pointerdown", outsideTap);
  outsideTap = (e) => {
    if (!svg.isConnected) { document.removeEventListener("pointerdown", outsideTap); outsideTap = null; outsideSvg = null; return; }
    if (!svg.contains(e.target)) setActive("outside");
  };
  document.addEventListener("pointerdown", outsideTap);
  outsideSvg = svg;
  paintHint();
  const mid = () => {
    const v = [...pts.values()], n = v.length;
    const x = v.reduce((s, p) => s + p.x, 0) / n, y = v.reduce((s, p) => s + p.y, 0) / n;
    return {x, y, d: n > 1 ? Math.hypot(v[0].x - v[1].x, v[0].y - v[1].y) : 0};
  };
  const toView = (x, y) => {
    const ctm = svg.getScreenCTM();
    if (!ctm) return null;
    const p = svg.createSVGPoint();
    p.x = x; p.y = y;
    const q = p.matrixTransform(ctm.inverse());
    return [q.x, q.y];
  };
  // A user gesture replaces any running animation and keeps the view inside the frame.
  const show = (next) => { before(); apply(clampView(next, frame)); };
  const zoomBy = (factor, ax, ay) => {
    const v = view();
    show(zoomView(v, factor, ax ?? v[0] + v[2] / 2, ay ?? v[1] + v[3] / 2, frame[2]));
  };
  const panBy = (dx, dy) => { const v = view(); show([v[0] + dx, v[1] + dy, v[2], v[3]]); };
  svg.addEventListener("wheel", (e) => {
    if (!wheelZooms(e, active)) { setHint(WHEEL_HINT); return; }
    e.preventDefault();
    const at = toView(e.clientX, e.clientY);
    if (at) zoomBy(wheelFactor(e.deltaY, e.deltaMode), at[0], at[1]);
  }, {passive: false});
  svg.addEventListener("dblclick", (e) => {
    const at = toView(e.clientX, e.clientY);
    if (at) zoomBy(2, at[0], at[1]);
  });
  svg.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    setActive("inside");
    if (pts.size === 0) { press = {x: e.clientX, y: e.clientY}; drag.moved = false; before(); }
    pts.set(e.pointerId, {x: e.clientX, y: e.clientY});
  });
  const release = (e) => { pts.delete(e.pointerId); };
  svg.addEventListener("pointerup", release);
  svg.addEventListener("pointercancel", release);
  svg.addEventListener("pointerleave", release);
  svg.addEventListener("pointermove", (e) => {
    if (!pts.has(e.pointerId)) return;
    const prev = mid();
    pts.set(e.pointerId, {x: e.clientX, y: e.clientY});
    const now = mid();
    const travelled = Math.hypot(now.x - press.x, now.y - press.y);
    if (dragMode(e.pointerType, pts.size) === "hint") {
      if (travelled > 4) setHint(TOUCH_HINT);
      return;
    }
    if (!drag.moved && (pts.size > 1 || travelled > 4)) {
      drag.moved = true;
      try { svg.setPointerCapture(e.pointerId); } catch { /* the pointer may already be released */ }
    }
    if (!drag.moved) return;
    const ctm = svg.getScreenCTM();
    if (!ctm) return;
    // Pan with the midpoint, then pinch-zoom by the change in finger spacing, about the midpoint.
    const v = view();
    let next = [v[0] - (now.x - prev.x) / ctm.a, v[1] - (now.y - prev.y) / ctm.d, v[2], v[3]];
    if (pts.size > 1 && prev.d > 0 && now.d > 0) {
      const at = toView(now.x, now.y);
      if (at) next = zoomView(next, now.d / prev.d, at[0], at[1], frame[2]);
    }
    show(next);
  });
  svg.addEventListener("focusin", () => setActive("inside"));
  svg.addEventListener("focusout", (e) => { if (!svg.contains(e.relatedTarget)) setActive("leave"); });
  svg.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { setActive("escape"); return; }
    if (e.target !== svg || e.altKey || e.ctrlKey || e.metaKey) return;
    const step = view()[2] * 0.1;
    const keys = {
      "+": () => zoomBy(1.5), "=": () => zoomBy(1.5), "-": () => zoomBy(1 / 1.5), "_": () => zoomBy(1 / 1.5),
      ArrowLeft: () => panBy(-step, 0), ArrowRight: () => panBy(step, 0), ArrowUp: () => panBy(0, -step), ArrowDown: () => panBy(0, step),
      "0": () => { before(); reset(); },
    };
    if (!keys[e.key]) return;
    e.preventDefault();
    keys[e.key]();
  });
  return {
    zoomBy,
    dragged: () => drag.moved,
    dispose: () => {
      if (outsideSvg === svg && outsideTap) {
        document.removeEventListener("pointerdown", outsideTap);
        outsideTap = null;
        outsideSvg = null;
      }
    },
  };
}
