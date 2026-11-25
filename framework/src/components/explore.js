// Explore the data (GA-2b): the GA-1 prototype's script (.impeccable/sketches/global_app.html) as a
// module. The markup is static in explore.md, inside <div class="gx">; this module fetches
// explore.json, then fills the scope bar, the statement, the tabs and the panels, and keeps the
// #scope= and &view= hash state. Every query runs inside root, so ids stay unique per page.
import {globalDataUrl, siteRoot} from "./atlas.js";
import {denominatorShare, readDenominators} from "./v4_trend_model.js";

// Pure helpers over countries.json (PLAT-4 slice 4: unscreened query hits, schema plat4b-v1). Exported for the
// Node runtime test. A country absent from the file gives null, and the page keeps its sample or preview.
const COUNTRIES_SCHEMA = "plat4b-v1";
export function countrySeries(payload, iso) {
  if (payload?.schema_version !== COUNTRIES_SCHEMA || !Array.isArray(payload.countries)) return null;
  const entry = payload.countries.find((c) => c.iso === iso);
  if (!entry) return null;
  const years = payload.years || {};
  const rows = [];
  let partial = null;
  for (const g of entry.works_by_year || []) {
    if (g.partial) partial = [g.year, g.count];
    else rows.push([g.year, g.count]);
  }
  rows.sort((a, b) => a[0] - b[0]);
  return {entry, from: years.first ?? rows[0]?.[0] ?? null, last: years.last_complete ?? null, partial, rows};
}
export function tierNote(entry) {
  return entry?.tier === "C" ? "Few works (under 50); treat as indicative." : null;
}
export function topTopics(entry, n = 3) {
  return (entry?.top_primary_topics || []).slice(0, n);
}

// ---- places and zoom (AMB-1) -----------------------------------------------------------------
// Natural Earth I (d3 geoNaturalEarth1), the one projection for every global map. world.json, the
// raster in explore.json and the places index are all in this frame, so markers and places are
// projected here with the same polynomial and the same frame as scripts/build_world_map.py.
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
export function frameXY(lon, lat) {
  const [x, y] = neRad((lon * Math.PI) / 180, (lat * Math.PI) / 180);
  return [(x + NE.XM) * NE.SCALE, (NE.YM - y) * NE.SCALE];
}
// The smallest zoom extent, in kilometres, and the box that holds a [west, south, east, north] box at least that big.
export const MIN_EXTENT_KM = 300;
export function minimumBox(bbox, minKm = MIN_EXTENT_KM) {
  const [w, s, e, n] = bbox;
  const midLat = (s + n) / 2, kmDegLat = 111.32;
  const kmDegLon = kmDegLat * Math.max(Math.cos((midLat * Math.PI) / 180), 0.05);
  const cx = (w + e) / 2, cy = (s + n) / 2;
  const width = Math.max(e - w, minKm / kmDegLon), height = Math.max(n - s, minKm / kmDegLat);
  return [cx - width / 2, Math.max(cy - height / 2, -90), cx + width / 2, Math.min(cy + height / 2, 90)];
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

export async function mountExplore(root) {
  const [response, placesResponse, worldResponse] = await Promise.all([
    fetch(globalDataUrl("explore.json"), {cache: "no-cache"}),
    fetch(globalDataUrl("places.json"), {cache: "no-cache"}).catch(() => null),
    fetch(new URL("assets/world/world.json", siteRoot()), {cache: "no-cache"}).catch(() => null),
  ]);
  if (!response.ok) throw new Error(`explore.json returned HTTP ${response.status}`);
  const D = await response.json();
  // places.json is optional: without it the search falls back to the countries in explore.json.
  const PLACES = placesResponse?.ok ? await placesResponse.json().catch(() => null) : null;
  const PLACE_ROWS = placeRows(PLACES);
  const PLACE_GEO = Object.fromEntries(PLACE_ROWS.filter((r) => r.kind === "country").map((r) => [r.iso, r.geom]));
  const PLACE_NAME = Object.fromEntries(PLACE_ROWS.filter((r) => r.kind === "country").map((r) => [r.iso, r.name]));
  const MARKERS = Array.isArray(PLACES?.markers) ? PLACES.markers : [];
  // The boundary layers come from world.json (same frame as the raster). Without it the map has no boundary lines.
  const WORLD = worldResponse?.ok ? await worldResponse.json().catch(() => null) : null;
  const BOUNDARY = {disputed: WORLD?.disputed || "", pacific: WORLD?.pacific_groups || ""};
  const G = D.grid, S = D.sample.scopes;
  const fmt = (n) => Number(n).toLocaleString("en-US");
  const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0) + "%";
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  const $ = (s, r = root) => r.querySelector(s);
  const ARROW = '<svg class="i" viewBox="0 0 14 10" aria-hidden="true"><path d="M1 5h11M8 1l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';
  const CHEV = '<svg width="10" height="7" viewBox="0 0 10 7" aria-hidden="true"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>';
  const SEARCH = '<svg class="i" viewBox="0 0 14 14" aria-hidden="true"><circle cx="6" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M9.5 9.5L13 13" stroke="currentColor" stroke-width="1.4"/></svg>';
  const MENU = '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M2 4h12M2 8h12M2 12h12" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>';
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  // Global listeners outlive the page when Framework's router swaps pages; they stop once root is gone.
  const attached = () => root.isConnected;

  // ---- model ----------------------------------------------------------------------------
  const C = Object.fromEntries(D.countries.map((c) => [c.iso, c]));
  const COUNTRIES = D.countries.filter((c) => c.works > 0).sort((a, b) => b.works - a.works);
  COUNTRIES.forEach((c, i) => (c.rank = i + 1));
  const CONTS = ["Asia", "Europe", "North America", "South America", "Africa", "Oceania"].map((name) => {
    const list = COUNTRIES.filter((c) => c.continent === name);
    return {name, list, works: list.reduce((s, c) => s + c.works, 0), week: list.reduce((s, c) => s + c.week, 0)};
  }).sort((a, b) => b.works - a.works);
  const contOf = (name) => CONTS.find((c) => c.name === name);
  const ATLAS = {
    US: {name: "California", status: "live", works: D.california.works, href: "./california/"},
    NO: {name: "Norway", status: "prep", href: "./norway/"},
  };
  const PREVIEW = ["US", "CN", "NO"];
  const NOW_Y = new Date().getFullYear();
  const years = Object.entries(D.trend_world).map(([y, n]) => [+y, n]).filter(([y]) => y <= NOW_Y);
  const lastYear = Math.max(...years.map((y) => y[0]));
  const recentWorld = years.filter(([y]) => y > lastYear - 5).reduce((s, [, n]) => s + n, 0);
  const totalWorld = D.totals.works_all;
  const fetched = new Date(D.fetched_at).toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric"});
  const SRC = `OpenAlex, plastics query ${D.query_version}, fetched ${fetched}.`;

  // scope: {kind: "world"} | {kind: "cont", name} | {kind: "country", iso}
  let scope = {kind: "world"}, tab = "countries";
  // A place picked from search (a region or city) zooms to its box inside its country's scope; null otherwise.
  let focusGeo = null;
  const scopeKey = (s) => (s.kind === "world" ? "world" : s.kind === "cont" ? "cont:" + s.name : s.iso);
  const parseScope = (k) => (!k || k === "world" ? {kind: "world"} : k.startsWith("cont:") && contOf(k.slice(5)) ? {kind: "cont", name: k.slice(5)} : C[k] && C[k].works ? {kind: "country", iso: k} : {kind: "world"});
  const THE = new Set(["US", "GB", "NL", "AE", "PH", "DO", "CF", "BS", "GM", "MV", "KM", "SB", "SC", "CD", "CG", "CZ"]);
  const inName = (iso) => (THE.has(iso) ? "the " : "") + C[iso].name;
  const scopeName = (s = scope) => (s.kind === "world" ? "World" : s.kind === "cont" ? s.name : C[s.iso].name);
  const scopeWorks = (s = scope) => (s.kind === "world" ? totalWorld : s.kind === "cont" ? contOf(s.name).works : C[s.iso].works);
  const sampleOf = (s = scope) => (s.kind === "world" ? S.world : s.kind === "country" ? S[s.iso] : null);
  // countries.json, fetched once when a country scope first needs it. undefined: not loaded yet; null: absent.
  let countryFile;
  let countryLoad = null;
  function loadCountryFile() {
    if (!countryLoad) {
      countryLoad = fetch(globalDataUrl("countries.json"), {cache: "no-cache"})
        .then((r) => (r.ok ? r.json() : null))
        .then((p) => (countryFile = p?.schema_version === COUNTRIES_SCHEMA ? p : null))
        .catch(() => (countryFile = null));
    }
    return countryLoad;
  }

  // ---- popovers -------------------------------------------------------------------------
  let openPop = null;
  function closePop(focusBack = true) {
    if (!openPop) return;
    const {el, btn, temp} = openPop;
    if (temp) el.remove(); else el.hidden = true;
    btn?.setAttribute("aria-expanded", "false");
    if (focusBack) btn?.focus();
    openPop = null;
  }
  function showPop(btn, el, temp) {
    closePop(false);
    el.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    openPop = {el, btn, temp};
    el.querySelector("a, button")?.focus();
  }
  document.addEventListener("click", (e) => {
    if (attached() && openPop && !openPop.el.contains(e.target) && !openPop.btn.contains(e.target)) closePop(false);
  });
  document.addEventListener("keydown", (e) => {
    if (!attached()) return;
    if (e.key === "Escape") { if (openPop) closePop(); else if ($("#drawer").classList.contains("open")) closeDrawer(); }
    if (openPop && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      const items = [...openPop.el.querySelectorAll(".opt")];
      const i = items.indexOf(document.activeElement);
      if (i < 0) return;
      e.preventDefault();
      items[(i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length].focus();
    }
  });
  const regionsBtn = $("#regions-btn");
  regionsBtn.addEventListener("click", () => (openPop?.btn === regionsBtn ? closePop() : showPop(regionsBtn, $("#regions-pop"))));

  function optHTML(o) {
    return `<button type="button" class="opt" data-scope="${esc(o.key)}"${o.cur ? ' aria-current="true"' : ""}><span></span><span>${esc(o.label)}</span><span class="n">${fmt(o.works)}</span></button>`;
  }
  function listPop(btn, title, note, opts) {
    const el = document.createElement("div");
    el.className = "pop";
    el.innerHTML = `<div class="pop-h">${esc(title)}<span>${note}</span></div><div class="pop-list">${opts.map(optHTML).join("")}</div>`;
    const r = btn.getBoundingClientRect();
    el.style.position = "fixed";
    el.style.left = Math.min(r.left, innerWidth - 376) + "px";
    el.style.top = r.bottom + 6 + "px";
    root.append(el); // inside root, so the .gx rules apply to the list
    el.addEventListener("click", (e) => { const b = e.target.closest("[data-scope]"); if (b) { closePop(false); go(parseScope(b.dataset.scope)); } });
    showPop(btn, el, true);
  }

  // ---- the ladder -----------------------------------------------------------------------
  function ladderSteps() {
    const steps = [{label: "World", works: totalWorld, kind: "world"}];
    const cont = scope.kind === "cont" ? scope.name : scope.kind === "country" ? C[scope.iso].continent : null;
    steps.push(cont ? {label: cont, works: contOf(cont).works, kind: "cont", name: cont} : {label: "Choose a continent", ghost: true, kind: "cont"});
    if (cont) steps.push(scope.kind === "country" ? {label: C[scope.iso].name, works: C[scope.iso].works, kind: "country", iso: scope.iso} : {label: "Choose a country", ghost: true, kind: "country", cont});
    return steps;
  }
  function renderLadder() {
    const steps = ladderSteps(), last = steps.filter((s) => !s.ghost).length - 1;
    const ol = $("#ladder");
    ol.innerHTML = steps.map((s, i) => `<li><button type="button" class="step${s.ghost ? " ghost" : ""}${i === last ? " cur" : ""}" data-i="${i}" aria-haspopup="true" aria-expanded="false"${i === last ? ' aria-current="location"' : ""}>${esc(s.label)}${s.works ? ` <span class="n">${fmt(s.works)}</span>` : ""}${CHEV}</button></li>`).join("");
    const at = scope.kind === "country" && ATLAS[scope.iso];
    if (at) {
      ol.insertAdjacentHTML("beforeend", at.status === "live"
        ? `<li><a class="step atlas" href="${at.href}"><i class="sw live"></i>${at.name} <span class="n">${fmt(at.works)}</span><span class="go">Open live atlas ${ARROW}</span></a></li>`
        : `<li><a class="step prep" href="${at.href}"><i class="sw prep"></i>${at.name} atlas, in preparation</a></li>`);
    }
    ol.querySelectorAll("button.step").forEach((b) => b.addEventListener("click", () => {
      if (openPop?.btn === b) return closePop();
      const s = steps[+b.dataset.i];
      if (s.kind === "world") listPop(b, "World", "continent counts sum their countries", [{key: "world", label: "Whole world", works: totalWorld, cur: scope.kind === "world"}, ...CONTS.map((c) => ({key: "cont:" + c.name, label: c.name, works: c.works}))]);
      else if (s.kind === "cont") listPop(b, "Continents", "sums of country counts", CONTS.map((c) => ({key: "cont:" + c.name, label: c.name, works: c.works, cur: c.name === s.name})));
      else { const cont = s.cont || C[s.iso].continent; const list = contOf(cont).list; listPop(b, cont, `${list.length} countries`, list.map((c) => ({key: c.iso, label: c.name, works: c.works, cur: c.iso === s.iso}))); }
    }));
    paintMenuBtn();
  }
  // On phones this button is the menu: it names the current view and scope, then the scope's works.
  function paintMenuBtn() {
    const sb = $("#scope-btn"), label = viewLabel(tab);
    sb.innerHTML = `${MENU}<span class="menu-t">${esc(label)} · ${esc(scopeName())}</span><span class="n">${fmt(scopeWorks())}</span>`;
    sb.setAttribute("aria-label", `Menu: ${label}, ${scopeName()}. Open views and scope`);
  }

  // Choosing a place. A country with works scopes the page to it; a region or city scopes to its country and zooms
  // to its own box; a place with no works in explore.json only zooms the map, and the scope stays the world.
  function selectPlace(iso, box = null) {
    if (C[iso]?.works > 0) go({kind: "country", iso}, {focus: box});
    else go({kind: "world"}, {focus: box || PLACE_GEO[iso] || null});
  }

  // ---- find a place (combobox): countries, first-level regions and cities ----------------------
  // A place is offered when its country has works to scope to. Without places.json the list is the countries.
  const KIND_LABEL = {country: "Country", admin1: "Region", city: "City"};
  // A place whose country has no works in explore.json still zooms the map (see selectPlace).
  const SEARCH_ROWS = PLACE_ROWS.length
    ? PLACE_ROWS
    : COUNTRIES.map((c) => ({name: c.name, kind: "country", parent: "", iso: c.iso, geom: null, key: foldName(c.name), alt: [], population: c.works}));
  function mountFind(host, id) {
    host.innerHTML = `${SEARCH}<input type="search" id="${id}" placeholder="Find a country or place" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="${id}-list" aria-autocomplete="list"><div class="pop" id="${id}-list" role="listbox" hidden></div>`;
    const input = host.querySelector("input"), list = host.querySelector(".pop");
    let hits = [], active = -1;
    const sub = (r) => (r.kind === "country" ? C[r.iso]?.continent || "Country" : `${KIND_LABEL[r.kind]}, ${r.parent}`);
    const paint = () => {
      list.innerHTML = hits.length
        ? hits.map((r, i) => `<div role="option" class="opt" id="${id}-o${i}" data-i="${i}" aria-selected="${i === active}"><span></span><span>${esc(r.name)}<small>${esc(sub(r))}</small></span><span class="n">${r.kind === "country" && C[r.iso] ? fmt(C[r.iso].works) : ""}</span></div>`).join("")
        : `<p class="pop-note" style="border:0">No place matches “${esc(input.value)}”.</p>`;
      input.setAttribute("aria-activedescendant", active >= 0 ? `${id}-o${active}` : "");
      list.querySelectorAll(".opt").forEach((o, i) => o.style.background = i === active ? "color-mix(in srgb, var(--pv-slate) 10%, var(--pv-paper))" : "");
    };
    const open = (v) => { list.hidden = !v; input.setAttribute("aria-expanded", String(v)); };
    input.addEventListener("input", () => {
      hits = searchPlaces(SEARCH_ROWS, input.value);
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
    const pick = (r) => { input.value = ""; open(false); closeDrawer(false); selectPlace(r.iso, r.kind === "country" ? null : r.geom); };
  }

  // ---- mobile drawer ---------------------------------------------------------------------
  function renderDrawer() {
    const cont = scope.kind === "cont" ? scope.name : scope.kind === "country" ? C[scope.iso].continent : null;
    const row = (key, label, works, d, on) => `<li><button type="button" class="opt${on ? " on" : ""}" style="--d:${d}" data-scope="${esc(key)}"${on ? ' aria-current="true"' : ""}><span></span><span>${esc(label)}</span><span class="n">${fmt(works)}</span></button></li>`;
    let h = row("world", "World", totalWorld, 0, scope.kind === "world");
    for (const c of CONTS) {
      h += row("cont:" + c.name, c.name, c.works, 1, scope.kind === "cont" && scope.name === c.name);
      if (c.name === cont) for (const k of c.list.slice(0, 40)) h += row(k.iso, k.name, k.works, 2, scope.kind === "country" && scope.iso === k.iso);
    }
    h += `<li class="lab">Regional atlases</li>
    <li><a class="opt live" href="${ATLAS.US.href}"><i class="sw live"></i><span>California<small>live atlas, daily build</small></span><span class="go">Open ${ARROW}</span></a></li>
    <li><a class="opt" href="${ATLAS.NO.href}"><i class="sw prep"></i><span>Norway<small>in preparation</small></span><span class="go quiet">Help build it</span></a></li>`;
    $("#views").innerHTML = TABS.map(([id]) => `<li><button type="button" class="opt${id === tab ? " on" : ""}" data-view="${id}"${id === tab ? ' aria-current="page"' : ""}><span></span><span>${esc(viewLabel(id))}</span></button></li>`).join("");
    $("#vlad").innerHTML = h;
  }
  $("#vlad").addEventListener("click", (e) => { const b = e.target.closest("[data-scope]"); if (b) { closeDrawer(false); go(parseScope(b.dataset.scope)); } });
  $("#views").addEventListener("click", (e) => { const b = e.target.closest("[data-view]"); if (b) chooseView(b.dataset.view); });
  // A view picked from the menu: show it, then move focus to its panel and scroll it below the sticky bars.
  function chooseView(id) {
    closeDrawer(false);
    setTab(id);
    const panel = $("#panel-" + id);
    panel.focus({preventScroll: true});
    panel.scrollIntoView({block: "start"});
  }
  function openDrawer() { renderDrawer(); $("#drawer").classList.add("open"); $("#scope-btn").setAttribute("aria-expanded", "true"); $("#drawer-x").focus(); }
  function closeDrawer(focus = true) { $("#drawer").classList.remove("open"); $("#scope-btn").setAttribute("aria-expanded", "false"); if (focus) $("#scope-btn").focus(); }
  $("#scope-btn").addEventListener("click", openDrawer);
  $("#drawer-x").addEventListener("click", () => closeDrawer());
  $("#drawer .scrim").addEventListener("click", () => closeDrawer());

  // ---- head ----------------------------------------------------------------------------
  function renderHead() {
    const h1 = $("#h1"), st = $("#statement");
    if (scope.kind === "world") {
      h1.textContent = "Plastics research, worldwide.";
      st.innerHTML = `<span class="m">${fmt(totalWorld)}</span> works under the plastics query, with authors in <span class="m">${COUNTRIES.length}</span> countries. <span class="m">${pct(recentWorld, totalWorld)}</span> were published in the last five years; <span class="m">${fmt(D.totals.works_week)}</span> arrived this week.`;
    } else if (scope.kind === "cont") {
      const c = contOf(scope.name), lead = c.list[0];
      h1.textContent = scope.name;
      st.innerHTML = `<span class="m">${c.list.length}</span> countries with plastics research. <b>${esc(inName(lead.iso)).replace(/^the /, "The ")}</b> leads with <span class="m">${fmt(lead.works)}</span> works, followed by ${esc(inName(c.list[1].iso))} and ${esc(inName(c.list[2].iso))}.`;
    } else {
      const c = C[scope.iso];
      h1.textContent = c.name;
      st.innerHTML = `<span class="m">${fmt(c.works)}</span> works with at least one author in ${esc(inName(c.iso))}, <b>${ordinal(c.rank)}</b> of ${COUNTRIES.length} countries. <span class="m">${pct(c.recent5, c.works)}</span> appeared in the last five years; <span class="m">${fmt(c.week)}</span> this week.`;
    }
  }
  const ordinal = (n) => n + (["th", "st", "nd", "rd"][(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10] || "th");

  // ---- tabs ----------------------------------------------------------------------------
  const TABS = [["countries", "Countries"], ["evidence", "Evidence map"], ["trend", "Trend"], ["experts", "Authors"], ["institutions", "Institutions"], ["network", "Network"], ["works", "Works"]];
  const viewLabel = (id) => (id === "countries" && scope.kind === "country" ? "Overview" : TABS.find((t) => t[0] === id)[1]);
  function renderTabs() {
    $("#tabs").innerHTML = TABS.map(([id]) => `<button type="button" role="tab" class="tab" id="tab-${id}" aria-controls="panel-${id}" aria-selected="${id === tab}" tabindex="${id === tab ? 0 : -1}">${viewLabel(id)}</button>`).join("");
    $("#panels").innerHTML = TABS.map(([id]) => `<section class="panel" role="tabpanel" id="panel-${id}" aria-labelledby="tab-${id}" tabindex="0"${id === tab ? "" : " hidden"}></section>`).join("");
  }
  $("#tabs").addEventListener("click", (e) => { const t = e.target.closest(".tab"); if (t) setTab(t.id.slice(4)); });
  $("#tabs").addEventListener("keydown", (e) => {
    const ids = TABS.map((t) => t[0]), i = ids.indexOf(tab);
    const j = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? ids.length - 1 : null;
    if (j === null) return;
    e.preventDefault();
    setTab(ids[(j + ids.length) % ids.length]);
    $("#tab-" + tab).focus();
  });
  function setTab(id) {
    tab = id;
    root.querySelectorAll(".tab").forEach((t) => { const on = t.id === "tab-" + id; t.setAttribute("aria-selected", on); t.tabIndex = on ? 0 : -1; });
    root.querySelectorAll(".panel").forEach((p) => (p.hidden = p.id !== "panel-" + id));
    writeHash();
    paintMenuBtn();
    renderPanel();
  }

  // ---- the map -------------------------------------------------------------------------
  // The world frame carries an empty Arctic band above the first raster row, so labels never sit on land at the top.
  const BAND = 12 * G.v, H = G.rows * G.v, FULL = [0, G.y0 - BAND, G.w, H + BAND], ASPECT = G.w / (H + BAND), CELL = G.u * 0.8;
  // Narrow cards (under 640 px): a single map for a continent or country is portrait; a world scope is two panes over the raster.
  const PORTRAIT = 3 / 5;
  const PAIR = [["Americas", [0, G.y0, 78 * G.u, H]], ["Europe, Africa, Asia and Oceania", [76 * G.u, G.y0, 108 * G.u, H]]];
  const step = (w) => (w >= 3000 ? "s3" : w >= 300 ? "s2" : w >= 30 ? "s1" : w > 0 ? "s0" : "sx");
  const cellD = (cells) => cells.map(([c, r]) => `M${(c * G.u).toFixed(1)} ${(G.y0 + r * G.v).toFixed(1)}h${CELL.toFixed(2)}v${CELL.toFixed(2)}h-${CELL.toFixed(2)}z`).join("");
  const runsCells = (runs) => runs.flatMap(([c, r, n]) => Array.from({length: n}, (_, k) => [c + k, r]));
  const caCells = D.california.cells;
  const bboxCells = (cells) => cells.reduce((b, [c, r]) => [Math.min(b[0], c), Math.min(b[1], r), Math.max(b[2], c + 1), Math.max(b[3], r + 1)], [1e9, 1e9, -1e9, -1e9]);
  // The dashed "in preparation" mark traces the region's own cells, so it stays on the pixel grid at every zoom.
  function cellOutline(cells) {
    const has = new Set(cells.map(([c, r]) => c + "," + r)), o = 0.1, segs = [];
    const X = (c) => ((c - o) * G.u).toFixed(2), Y = (r) => (G.y0 + (r - o) * G.v).toFixed(2);
    for (const [c, r] of cells) {
      if (!has.has(c + "," + (r - 1))) segs.push(`M${X(c)} ${Y(r)}H${X(c + 1)}`);
      if (!has.has(c + "," + (r + 1))) segs.push(`M${X(c)} ${Y(r + 1)}H${X(c + 1)}`);
      if (!has.has(c - 1 + "," + r)) segs.push(`M${X(c)} ${Y(r)}V${Y(r + 1)}`);
      if (!has.has(c + 1 + "," + r)) segs.push(`M${X(c + 1)} ${Y(r)}V${Y(r + 1)}`);
    }
    return segs.join("");
  }
  let vb = FULL.slice(), vbAspect = ASPECT, mapEl = null, tween = 0;
  // Set on pointerdown and kept until the next one: a drag must not also count as a click on a country.
  const drag = {moved: false};

  // Small countries: one dot each at its centroid, focusable and clickable when the country has works.
  function markerSvg() {
    return MARKERS.map(([iso, lon, lat]) => {
      const c = C[iso], name = c?.name || PLACE_NAME[iso] || iso, on = c?.works > 0;
      const [x, y] = frameXY(lon, lat);
      const at = `cx="${x.toFixed(1)}" cy="${y.toFixed(1)}"`;
      const works = on ? `${fmt(c.works)} works` : "no works counted";
      return `<g class="sm${on ? "" : " none"}" data-iso="${iso}" tabindex="0" role="button" aria-label="${esc(name)}, ${works}. Select to zoom the map to it."><circle class="sm-hit" ${at} r="8"/><circle class="sm-dot" ${at} r="3"/></g>`;
    }).join("");
  }
  // Dots and hit areas keep a constant size on screen: their radius follows the viewBox width.
  function sizeMarkers() {
    const k = vb[2];
    mapEl?.querySelectorAll(".sm-dot").forEach((d) => d.setAttribute("r", (k * 0.005).toFixed(3)));
    mapEl?.querySelectorAll(".sm-hit").forEach((d) => d.setAttribute("r", (k * 0.014).toFixed(3)));
  }
  function mapHTML() {
    const paths = D.countries.filter((c) => c.runs.length).map((c) => `<path class="c ${step(c.works)}" data-iso="${c.iso}" d="${cellD(runsCells(c.runs))}"/>`).join("");
    const body = `${paths}<path class="ca" d="${cellD(caCells)}"/><path class="no" d="${cellOutline(runsCells(C.NO.runs))}"/><path class="pg" d="${BOUNDARY.pacific}"/><path class="bd" d="${BOUNDARY.disputed}"/>`;
    // Each pane repeats the country paths in its own svg; the viewBox clips it to its part of the raster.
    const pane = ([label, [x, y, w, h]]) => `<figure class="mp"><figcaption class="mcap">${label}</figcaption><div class="mp-box" style="aspect-ratio:${w} / ${h}"><svg class="map" viewBox="${x} ${y} ${w} ${h}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${label}: plastics works by country.">${body}</svg></div></figure>`;
    return `<div class="mapcard"><div class="map-tools" id="map-tools"></div><div class="mapbox" id="mapbox" style="--ga-ar:${G.w} / ${(H + BAND).toFixed(1)}">
    <svg class="map" id="map" tabindex="0" viewBox="${vb.join(" ")}" preserveAspectRatio="xMidYMid meet" role="group" aria-label="World map of plastics works by country. Every country is also listed in the table below. Small countries are buttons. Hold Ctrl and scroll, or click the map first, to zoom; drag to pan; with the map focused, plus and minus zoom, arrow keys pan and 0 resets.">${body}${markerSvg()}<rect class="extent" id="extent" x="0" y="0" width="0" height="0" style="display:none"/></svg>
    <div class="panes" id="panes">${PAIR.map(pane).join("")}</div>
    <svg class="leaders" id="leaders" aria-hidden="true"></svg>
    <a class="callout live" id="co-ca" href="${ATLAS.US.href}"><b><i class="sw live"></i>California</b><small>live atlas · <span class="m">${fmt(D.california.works)}</span> works</small><span class="go">Open atlas ${ARROW}</span></a>
    <a class="callout" id="co-no" href="${ATLAS.NO.href}"><b><i class="sw prep"></i>Norway</b><span class="go quiet">Atlas in preparation ${ARROW}</span></a>
    <div class="maptip" id="tip" hidden></div>
    <div class="map-zoom" role="group" aria-label="Map zoom">
      <button type="button" class="btn" id="zoom-in" aria-label="Zoom in" title="Zoom in">+</button>
      <button type="button" class="btn" id="zoom-out" aria-label="Zoom out" title="Zoom out">&minus;</button>
      <button type="button" class="btn" id="zoom-reset" aria-label="Reset map view" title="Reset map view">Reset</button>
    </div>
    <div class="map-hint" id="map-hint" aria-live="polite"></div>
  </div>
  <div class="astrip"><a class="opt live" href="${ATLAS.US.href}"><i class="sw live"></i><span>California<small>live regional atlas</small></span><span class="go">Open ${ARROW}</span></a><a class="opt" href="${ATLAS.NO.href}"><i class="sw prep"></i><span>Norway<small>atlas in preparation</small></span><span class="go quiet">Help build it</span></a></div>
  <div class="legend"><div class="ramp">works per country <i style="background:var(--pv-wash)"></i><i style="background:var(--pv-mint)"></i><i style="background:var(--pv-slate-2)"></i><i style="background:var(--pv-slate)"></i> under 30 · 30–299 · 300–2,999 · 3,000+</div><p>Select a country to scope every view to it. Countries too small for this map are in the table.</p><p class="keys"><span><svg width="26" height="8" aria-hidden="true"><line x1="0" y1="4" x2="26" y2="4" stroke="var(--pv-ink-2)" stroke-width="1" stroke-dasharray="4 3"/></svg>Disputed boundary, as drawn by Natural Earth</span><span><svg width="26" height="8" aria-hidden="true"><line x1="0" y1="4" x2="26" y2="4" stroke="var(--pv-slate-2)" stroke-width="1.2" stroke-linecap="round" stroke-dasharray="0 3.2"/></svg>Pacific grouping</span></p><p class="credit">Boundaries: Natural Earth, including its disputed-area lines. Hold Ctrl and scroll to zoom (or click the map first); two fingers pan and pinch on touch; double-click to zoom in; with the map focused, + and &minus; zoom, arrow keys pan, 0 resets.</p></div></div>`;
  }
  function wireMap() {
    mapEl = $("#map");
    const tip = $("#tip"), box = $("#mapbox");
    let hov = null;
    // The panes repeat each country, so hover lights every copy of it.
    const hover = (iso) => {
      if (iso === hov) return;
      hov = iso;
      box.querySelectorAll(".c.hov").forEach((el) => el.classList.remove("hov"));
      if (iso) box.querySelectorAll(`.c[data-iso="${iso}"]`).forEach((el) => el.classList.add("hov"));
    };
    box.querySelectorAll("svg.map").forEach((svg) => {
      svg.addEventListener("pointermove", (e) => {
        const p = e.target.closest?.(".c, .sm");
        hover(p && p.classList.contains("c") ? p.dataset.iso : null);
        if (!p) { tip.hidden = true; return; }
        const iso = p.dataset.iso, c = C[iso], r = box.getBoundingClientRect();
        tip.innerHTML = `${esc(c?.name || PLACE_NAME[iso] || iso)}<br><span class="m">${c?.works ? fmt(c.works) + " works · " + pct(c.recent5, c.works) + " last 5 y" : "no works counted"}</span>`;
        tip.hidden = false;
        const x = e.clientX - r.left, y = e.clientY - r.top;
        tip.style.left = Math.min(x + 14, r.width - tip.offsetWidth - 6) + "px";
        tip.style.top = Math.max(y - tip.offsetHeight - 12, 6) + "px";
      });
      svg.addEventListener("pointerleave", () => { hover(null); tip.hidden = true; });
      svg.addEventListener("click", (e) => {
        if (drag.moved) return;
        const p = e.target.closest?.(".c");
        if (p) { if (C[p.dataset.iso].works) go({kind: "country", iso: p.dataset.iso}); return; }
        const m = e.target.closest?.(".sm");
        if (m) selectPlace(m.dataset.iso, PLACE_GEO[m.dataset.iso] || null);
      });
      svg.addEventListener("keydown", (e) => {
        const m = e.target.closest?.(".sm");
        if (m && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); selectPlace(m.dataset.iso, PLACE_GEO[m.dataset.iso] || null); }
      });
    });
    sizeMarkers();
    paintMapScope(false);
    wireZoom();
  }
  // Zoom and pan inside the map. A wheel zooms only with Ctrl or Cmd held, or while the map is active (wheelZooms);
  // otherwise the page scrolls. One finger scrolls the page (touch-action: pan-y); two fingers pan and pinch-zoom.
  let outsideTap = null;
  function wireZoom() {
    const svg = mapEl, pts = new Map(), hintEl = $("#map-hint");
    let press = {x: 0, y: 0}, active = false, hintTimer = 0;
    const hint = (text) => {
      if (!hintEl) return;
      hintEl.textContent = text;
      hintEl.classList.add("show");
      clearTimeout(hintTimer);
      hintTimer = setTimeout(() => hintEl.classList.remove("show"), 1500);
    };
    const setActive = (kind) => {
      const next = nextActive(active, kind);
      if (next === active) return;
      active = next;
      if (!active) { clearTimeout(hintTimer); hintEl?.classList.remove("show"); }
    };
    // A press anywhere else deactivates the map. Only the current render's listener is kept.
    if (outsideTap) document.removeEventListener("pointerdown", outsideTap);
    outsideTap = (e) => {
      if (!svg.isConnected) { document.removeEventListener("pointerdown", outsideTap); outsideTap = null; return; }
      if (!svg.contains(e.target)) setActive("outside");
    };
    document.addEventListener("pointerdown", outsideTap);
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
    // A user gesture replaces any running scope animation and keeps the view inside the frame.
    const setUserView = (next) => { cancelAnimationFrame(tween); vb = clampView(next, FULL); mapEl.setAttribute("viewBox", vb.join(" ")); sizeMarkers(); placeCallouts(); };
    const zoomAt = (factor, ax = vb[0] + vb[2] / 2, ay = vb[1] + vb[3] / 2) => setUserView(zoomView(vb, factor, ax, ay, FULL[2]));
    const panBy = (dx, dy) => setUserView([vb[0] + dx, vb[1] + dy, vb[2], vb[3]]);
    svg.addEventListener("wheel", (e) => {
      if (!wheelZooms(e, active)) { hint(WHEEL_HINT); return; }
      e.preventDefault();
      const at = toView(e.clientX, e.clientY);
      if (at) zoomAt(wheelFactor(e.deltaY, e.deltaMode), at[0], at[1]);
    }, {passive: false});
    svg.addEventListener("dblclick", (e) => {
      const at = toView(e.clientX, e.clientY);
      if (at) zoomAt(2, at[0], at[1]);
    });
    svg.addEventListener("pointerdown", (e) => {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      setActive("inside");
      if (pts.size === 0) { press = {x: e.clientX, y: e.clientY}; drag.moved = false; cancelAnimationFrame(tween); }
      pts.set(e.pointerId, {x: e.clientX, y: e.clientY});
    });
    const release = (e) => { pts.delete(e.pointerId); };
    svg.addEventListener("pointerup", release);
    svg.addEventListener("pointercancel", release);
    svg.addEventListener("pointerleave", release);
    svg.addEventListener("pointermove", (e) => {
      if (!pts.has(e.pointerId)) return;
      const before = mid();
      pts.set(e.pointerId, {x: e.clientX, y: e.clientY});
      const now = mid();
      const travelled = Math.hypot(now.x - press.x, now.y - press.y);
      if (dragMode(e.pointerType, pts.size) === "hint") {
        if (travelled > 4) hint(TOUCH_HINT);
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
      let next = [vb[0] - (now.x - before.x) / ctm.a, vb[1] - (now.y - before.y) / ctm.d, vb[2], vb[3]];
      if (pts.size > 1 && before.d > 0 && now.d > 0) {
        const at = toView(now.x, now.y);
        if (at) next = zoomView(next, now.d / before.d, at[0], at[1], FULL[2]);
      }
      setUserView(next);
    });
    svg.addEventListener("focusin", () => setActive("inside"));
    svg.addEventListener("focusout", (e) => { if (!svg.contains(e.relatedTarget)) setActive("leave"); });
    svg.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { setActive("escape"); return; }
      if (e.target !== svg || e.altKey || e.ctrlKey || e.metaKey) return;
      const step = vb[2] * 0.1;
      const keys = {
        "+": () => zoomAt(1.5), "=": () => zoomAt(1.5), "-": () => zoomAt(1 / 1.5), "_": () => zoomAt(1 / 1.5),
        ArrowLeft: () => panBy(-step, 0), ArrowRight: () => panBy(step, 0), ArrowUp: () => panBy(0, -step), ArrowDown: () => panBy(0, step),
        "0": () => paintMapScope(true),
      };
      if (!keys[e.key]) return;
      e.preventDefault();
      keys[e.key]();
    });
    $("#zoom-in")?.addEventListener("click", () => zoomAt(1.6));
    $("#zoom-out")?.addEventListener("click", () => zoomAt(1 / 1.6));
    $("#zoom-reset")?.addEventListener("click", () => paintMapScope(true));
  }
  const CONT_BOX = {"Europe": [76, 2, 114, 26], "Asia": [108, 2, 176, 46], "North America": [22, 0, 78, 40], "South America": [44, 34, 78, 72], "Africa": [80, 12, 120, 68], "Oceania": [138, 38, 184, 72]};
  // A country's main body for framing: the contiguous US without Alaska and Hawaii; elsewhere drop cells far from
  // the median (French Guiana for France, outlying islands).
  const MAIN = {US: ([c, r]) => c > 22 && r > 9};
  function mainCells(cells, iso) {
    if (MAIN[iso]) return cells.filter(MAIN[iso]);
    const med = (a) => a.slice().sort((x, y) => x - y)[a.length >> 1];
    const mc = med(cells.map((c) => c[0])), mr = med(cells.map((c) => c[1]));
    const keep = cells.filter(([c, r]) => Math.hypot(c - mc, r - mr) <= 16);
    return keep.length ? keep : cells;
  }
  // The whole world in a box of the given aspect: the desktop frame itself, or centred on the raster when portrait.
  const worldFrame = (aspect) => (aspect === ASPECT ? FULL : [0, FULL[1] + FULL[3] / 2 - G.w / aspect / 2, G.w, G.w / aspect]);
  // A box of the given aspect around (cx, cy) that holds w by h. Desktop boxes stay inside the frame; a portrait box
  // may run past the raster, which is blank, so it keeps its centre.
  function frameOf(cx, cy, w, h, aspect) {
    w = Math.min(Math.max(w, h * aspect), FULL[2]); h = w / aspect;
    const x = Math.max(Math.min(cx - w / 2, G.w - w), 0);
    const y = aspect === ASPECT ? Math.max(Math.min(cy - h / 2, FULL[1] + FULL[3] - h), FULL[1]) : cy - h / 2;
    return [x, y, w, h];
  }
  // A place's geometry is a [west, south, east, north] box or a [lon, lat] point. Its zoom box is the minimum
  // box (about 300 km) projected into the frame, with the usual padding and at least 120 units wide.
  const boxOf = (g) => (g.length === 4 ? g : [g[0], g[1], g[0], g[1]]);
  const placeExtent = (g) => frameExtent(minimumBox(boxOf(g)));
  function geoFrame(g, aspect) {
    const [x0, y0, x1, y1] = placeExtent(g);
    const w = Math.max((x1 - x0) * 1.3, 120);
    return frameOf((x0 + x1) / 2, (y0 + y1) / 2, w, w / aspect, aspect);
  }
  // The dashed outline of a zoomed place that has no raster cells (its minimum box), or null.
  function extentBox() {
    if (focusGeo) return placeExtent(focusGeo);
    if (scope.kind === "country" && !C[scope.iso].runs.length && PLACE_GEO[scope.iso]) return placeExtent(PLACE_GEO[scope.iso]);
    return null;
  }
  function targetBox(aspect = ASPECT) {
    if (focusGeo) return geoFrame(focusGeo, aspect);
    if (scope.kind === "world") return worldFrame(aspect);
    if (scope.kind === "country" && !C[scope.iso].runs.length && PLACE_GEO[scope.iso]) return geoFrame(PLACE_GEO[scope.iso], aspect);
    const cells = scope.kind === "cont" ? null : runsCells(C[scope.iso].runs);

    if (cells && !cells.length) return worldFrame(aspect);
    const [c0, r0, c1, r1] = cells ? bboxCells(mainCells(cells, scope.iso)) : CONT_BOX[scope.name];
    const pad = cells ? 1.3 : 1.08;
    const cx = ((c0 + c1) / 2) * G.u, cy = G.y0 + ((r0 + r1) / 2) * G.v;
    const w = Math.max((c1 - c0) * G.u * pad, scope.kind === "cont" ? 260 : 120), h = Math.max((r1 - r0) * G.v * pad, w / aspect);
    return frameOf(cx, cy, w, h, aspect);
  }
  function paintMapScope(animate = true) {
    if (!mapEl) return;
    const inScope = scope.kind === "world" ? null : new Set(scope.kind === "cont" ? contOf(scope.name).list.map((c) => c.iso) : [scope.iso]);
    const box = $("#mapbox");
    box.querySelectorAll("svg.map").forEach((s) => s.classList.toggle("scoped", !!inScope));
    box.querySelectorAll(".c, .sm").forEach((p) => p.classList.toggle("out", !!inScope && !inScope.has(p.dataset.iso)));
    const ex = box.querySelector("#extent"), ext = extentBox();
    if (ex) {
      ex.style.display = ext ? "" : "none";
      if (ext) { ex.setAttribute("x", ext[0]); ex.setAttribute("y", ext[1]); ex.setAttribute("width", ext[2] - ext[0]); ex.setAttribute("height", ext[3] - ext[1]); }
    }
    const mode = layoutMap();
    const tools = $("#map-tools");
    tools.innerHTML = scope.kind === "world" ? "" : `<button type="button" class="btn" id="map-up">${scope.kind === "country" ? "Back to " + esc(C[scope.iso].continent) : "Whole world"}</button>`;
    $("#map-up")?.addEventListener("click", () => go(scope.kind === "country" ? {kind: "cont", name: C[scope.iso].continent} : {kind: "world"}));
    cancelAnimationFrame(tween);
    // Pair mode shows fixed panes and leaves the desktop viewBox alone.
    if (mode === "pair") { placeCallouts(); return; }
    const aspect = mode === "portrait" ? PORTRAIT : ASPECT;
    const to = targetBox(aspect), from = vbAspect === aspect ? vb.slice() : worldFrame(aspect);
    vbAspect = aspect;
    if (!animate || reduced.matches) { vb = to.slice(); mapEl.setAttribute("viewBox", vb.join(" ")); sizeMarkers(); placeCallouts(); return; }
    hideCallouts();
    const t0 = performance.now(), dur = 450, ease = (t) => 1 - Math.pow(1 - t, 3);
    const frame = (now) => {
      const t = Math.min((now - t0) / dur, 1), k = ease(t);
      vb = from.map((v, i) => v + (to[i] - v) * k);
      mapEl.setAttribute("viewBox", vb.join(" "));
      sizeMarkers();
      if (t < 1) tween = requestAnimationFrame(frame); else placeCallouts();
    };
    tween = requestAnimationFrame(frame);
  }
  function hideCallouts() { root.querySelectorAll(".callout, .leader").forEach((el) => el.classList.add("hide")); }
  // Card width sets the layout: desktop; narrow with a world scope (two panes); narrow otherwise (one portrait map).
  function layoutMap() {
    const box = $("#mapbox"), card = box?.closest(".mapcard");
    if (!card) return "desktop";
    const narrow = box.getBoundingClientRect().width < 640;
    const mode = !narrow ? "desktop" : scope.kind === "world" ? "pair" : "portrait";
    card.classList.toggle("narrow", narrow);
    card.classList.toggle("pair", mode === "pair");
    card.classList.toggle("portrait", mode === "portrait");
    return mode;
  }
  function placeCallouts() {
    const box = $("#mapbox"); if (!box) return;
    if (layoutMap() !== "desktop") return;
    const R = box.getBoundingClientRect(), W = R.width, Hh = R.height;
    const px = (x) => ((x - vb[0]) / vb[2]) * W, py = (y) => ((y - vb[1]) / vb[3]) * Hh;
    box.closest(".mapcard").classList.toggle("compact", W < 1100);
    const L = $("#leaders"), lines = [], taken = [];
    const hit = (a, b, m = 6) => a.x0 < b.x1 + m && a.x1 > b.x0 - m && a.y0 < b.y1 + m && a.y1 > b.y0 - m;
    // Try each side in order; take the first box that stays inside the map and clears its anchor and the other label.
    const place = (id, cells, order, cls, show) => {
      const el = $(id); el.classList.toggle("hide", !show);
      if (!show) return;
      const [c0, r0, c1, r1] = bboxCells(cells);
      const a = {x0: px(c0 * G.u), x1: px(c1 * G.u), y0: py(G.y0 + r0 * G.v), y1: py(G.y0 + r1 * G.v)};
      const ax = (a.x0 + a.x1) / 2, ay = (a.y0 + a.y1) / 2, w = el.offsetWidth, h = el.offsetHeight, g = W < 1100 ? 14 : 32;
      const at = {left: [a.x0 - g - w, ay - h / 2], right: [a.x1 + g, ay - h / 2], above: [ax - w / 2, a.y0 - g - h], below: [ax - w / 2, a.y1 + g],
        "below-left": [a.x0 - g - w, a.y1 + g / 2], "above-left": [a.x0 - g - w, a.y0 - g / 2 - h], "below-right": [a.x1 + g, a.y1 + g / 2]};
      let pick = null;
      for (const k of order) {
        const [x, y] = at[k], r = {x0: x, y0: y, x1: x + w, y1: y + h};
        if (x >= 8 && y >= 8 && x + w <= W - 8 && y + h <= Hh - 8 && !hit(r, a) && !taken.some((t) => hit(r, t))) { pick = r; break; }
      }
      if (!pick) { const [x, y] = at[order[0]]; const cx = Math.max(8, Math.min(x, W - w - 8)), cy = Math.max(8, Math.min(y, Hh - h - 8)); pick = {x0: cx, y0: cy, x1: cx + w, y1: cy + h}; }
      taken.push(pick);
      el.style.left = pick.x0 + "px"; el.style.top = pick.y0 + "px";
      const cl = (v, lo, hi) => Math.max(lo, Math.min(v, hi));
      const bx = cl((pick.x0 + pick.x1) / 2, a.x0, a.x1), by = cl((pick.y0 + pick.y1) / 2, a.y0, a.y1);
      const ex = cl(bx, pick.x0, pick.x1), ey = cl(by, pick.y0, pick.y1);
      lines.push(`<line class="leader ${cls}" x1="${bx.toFixed(1)}" y1="${by.toFixed(1)}" x2="${ex.toFixed(1)}" y2="${ey.toFixed(1)}"/><circle cx="${bx.toFixed(1)}" cy="${by.toFixed(1)}" r="2.5" fill="${cls ? "var(--pv-coral-ink)" : "var(--pv-ink)"}"/>`);
    };
    const showCA = scope.kind === "world" || (scope.kind === "cont" && scope.name === "North America") || (scope.kind === "country" && scope.iso === "US");
    const showNO = scope.kind === "world" || (scope.kind === "cont" && scope.name === "Europe") || (scope.kind === "country" && scope.iso === "NO");
    place("#co-ca", caCells, ["left", "above-left", "below-left", "below", "right"], "", showCA);
    place("#co-no", runsCells(C.NO.runs), ["above", "above-left", "left", "below-left", "right", "below"], "prep", showNO);
    L.innerHTML = lines.join("");
  }
  addEventListener("resize", () => { if (attached() && tab === "countries" && mapEl) paintMapScope(false); });

  // ---- panels --------------------------------------------------------------------------
  const TH = (label, key, sort, num) => `<th class="${num ? "n " : ""}col-${key}"${sort.key === key ? ` aria-sort="${sort.dir > 0 ? "ascending" : "descending"}"` : ""}><button type="button" data-sort="${key}">${label}${sort.key === key ? `<svg class="arr" viewBox="0 0 8 8" aria-hidden="true"><path d="${sort.dir > 0 ? "M1 6l3-4 3 4" : "M1 2l3 4 3-4"}" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>` : ""}</button></th>`;
  const tableState = {q: "", cont: "", sort: {key: "works", dir: -1}, all: false};

  function countriesPanel(el) {
    const country = scope.kind === "country";
    el.innerHTML = `<div class="sec">${mapHTML()}<p class="src">${SRC} A work counts once for every country among its authors, so country totals overlap.${PLACE_ROWS.length ? " Place names: GeoNames (CC BY 4.0) and Natural Earth." : ""}</p></div>
    <div class="sec" id="below"></div>`;
    wireMap();
    if (country) overview($("#below")); else countryTable($("#below"));
  }
  function countryTable(el) {
    const st = tableState, inCont = scope.kind === "cont" ? scope.name : st.cont;
    let rows = COUNTRIES.filter((c) => (!inCont || c.continent === inCont) && (!st.q || c.name.toLowerCase().includes(st.q.toLowerCase())));
    const k = st.sort.key, val = (c) => (k === "name" ? c.name : k === "cont" ? c.continent : k === "share" ? c.recent5 / c.works : c[k]);
    rows.sort((a, b) => (val(a) < val(b) ? -1 : val(a) > val(b) ? 1 : 0) * st.sort.dir || b.works - a.works);
    const shown = st.all ? rows : rows.slice(0, 25), max = COUNTRIES[0].works;
    const body = shown.map((c) => {
      const at = ATLAS[c.iso];
      const badge = at?.status === "prep" ? `<span class="badge"><i class="sw prep"></i><span class="bt">atlas in preparation</span></span>` : at ? `<span class="badge"><i class="sw live"></i><span class="bt">live atlas below</span></span>` : "";
      let h = `<tr class="row" data-iso="${c.iso}"><td class="rk">${c.rank}</td><td><button type="button" class="namebtn">${esc(c.name)}</button>${badge}</td><td class="cont col-cont">${esc(c.continent)}</td><td class="n">${fmt(c.works)}</td><td class="barcell col-bar"><div class="bar" style="width:${Math.max((c.works / max) * 100, 0.6)}%"><i style="width:${(c.recent5 / c.works) * 100}%"></i></div></td><td class="n col-share">${pct(c.recent5, c.works)}</td><td class="n col-week">${fmt(c.week)}</td></tr>`;
      if (at?.status === "live") h += `<tr class="atlas"><td></td><td colspan="6"><div class="atlas-cell"><i class="sw live"></i><b>California</b><small>live regional atlas · daily build · <span class="m">${fmt(at.works)}</span> works</small><a class="go" href="${at.href}">Open atlas ${ARROW}</a></div></td></tr>`;
      return h;
    }).join("");
    el.innerHTML = `<h2>${scope.kind === "cont" ? "Countries in " + esc(scope.name) : "Every country, ranked."}</h2>
    <p class="lede">Bars show all works; the darker part is the last five years. Select a country to open its profile.</p>
    <div class="toolbar"><label class="sr" for="cq">Filter countries</label><input class="field" id="cq" type="search" placeholder="Filter countries" value="${esc(st.q)}" style="width:min(280px,100%)">
    ${scope.kind === "cont" ? "" : `<label class="sr" for="cc">Continent</label><select class="field" id="cc"><option value="">All continents</option>${CONTS.map((c) => `<option${c.name === st.cont ? " selected" : ""}>${c.name}</option>`).join("")}</select>`}
    <span class="count">${rows.length} ${rows.length === 1 ? "country" : "countries"}</span></div>
    <div class="tw"><table class="t"><caption class="sr">Countries by plastics works</caption><thead><tr><th><span>#</span></th>${TH("country", "name", st.sort)}${TH("continent", "cont", st.sort)}${TH("works", "works", st.sort, 1)}<th class="col-bar"><span>all years / last 5</span></th>${TH("last 5 y", "share", st.sort, 1)}${TH("this week", "week", st.sort, 1)}</tr></thead>
    <tbody>${body || `<tr><td colspan="7" class="empty"><b>No country matches “${esc(st.q)}”.</b><button type="button" class="linkbtn" id="clear">Clear the filter</button></td></tr>`}</tbody></table></div>
    ${rows.length > 25 ? `<button type="button" class="btn more" id="all">${st.all ? "Show the top 25" : `Show all ${rows.length} countries`}</button>` : ""}`;
    const re = () => countryTable(el);
    $("#cq", el).addEventListener("input", (e) => { st.q = e.target.value; const pos = e.target.selectionStart; re(); const i = $("#cq", el); i.focus(); i.setSelectionRange(pos, pos); });
    $("#cc", el)?.addEventListener("change", (e) => { st.cont = e.target.value; re(); });
    $("#clear", el)?.addEventListener("click", () => { st.q = ""; re(); $("#cq", el).focus(); });
    $("#all", el)?.addEventListener("click", () => { st.all = !st.all; re(); });
    el.querySelectorAll("[data-sort]").forEach((b) => b.addEventListener("click", () => {
      const key = b.dataset.sort; st.sort = {key, dir: st.sort.key === key ? -st.sort.dir : key === "name" || key === "cont" ? 1 : -1}; re(); el.querySelector(`[data-sort="${key}"]`).focus();
    }));
    el.querySelectorAll("tr.row").forEach((tr) => tr.addEventListener("click", (e) => { if (!e.target.closest("a")) go({kind: "country", iso: tr.dataset.iso}); }));
  }

  function hbars(items, {max, link} = {}) {
    const m = max || Math.max(...items.map((i) => i.count), 1);
    return items.map((i) => {
      const inner = `<span class="nm">${esc(i.name)}</span><span class="bar" style="width:${Math.max((i.count / m) * 100, 1)}%"></span><span class="n">${fmt(i.count)}</span>`;
      return link && i.iso ? `<button type="button" class="hb" data-iso="${i.iso}">${inner}</button>` : `<div class="hb">${inner}</div>`;
    }).join("");
  }
  function previewNotice(what) {
    return `<div class="notice"><p><b>${what} for ${esc(scopeName())} arrive with the global build.</b> This preview carries full profiles for three countries.</p><div class="row2">${PREVIEW.map((i) => `<button type="button" class="btn" data-go="${i}">${C[i].name}</button>`).join("")}</div></div>`;
  }
  function wireGo(el) { el.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => go({kind: "country", iso: b.dataset.go}))); el.querySelectorAll("button.hb[data-iso]").forEach((b) => b.addEventListener("click", () => go({kind: "country", iso: b.dataset.iso}))); }

  function partnersOf(iso) {
    const s = S[iso]; if (!s?.countries) return null;
    return s.countries.filter((g) => g.key !== iso && C[g.key]).slice(0, 10).map((g) => ({name: C[g.key].name, count: g.count, iso: g.key}));
  }
  // Unscreened totals and top primary topics from countries.json; the first load re-renders the overview.
  function factsBox(entry) {
    const note = tierNote(entry);
    return `<div class="box"><h3>Works and topics, unscreened</h3><p class="lede">Query hits with at least one author in ${esc(inName(entry.iso))}. Not a relevance-screened count.</p>
    <p><span class="m">${fmt(entry.works_total)}</span> works, the first in ${entry.first_year}.${note ? ` ${note}` : ""}</p>
    ${hbars(topTopics(entry, 3).map((t) => ({name: t.name, count: t.count})))}</div>`;
  }
  function overview(el) {
    if (countryFile === undefined) loadCountryFile().then(() => { if (el.isConnected && tab === "countries" && scope.kind === "country") overview(el); });
    const series = countryFile ? countrySeries(countryFile, scope.iso) : null;
    const c = C[scope.iso], s = S[scope.iso], partners = partnersOf(scope.iso), at = ATLAS[scope.iso];
    const atlas = at ? (at.status === "live"
      ? `<a class="atlasbox" href="${at.href}"><i class="sw live"></i><span><b>California has a live regional atlas.</b><small>Authors, institutions, monitoring, funding and policy, rebuilt daily · <span class="m">${fmt(at.works)}</span> works</small></span><span class="go">Open atlas ${ARROW}</span></a>`
      : `<a class="atlasbox prep" href="${at.href}"><i class="sw prep"></i><span><b>A Norway atlas is in preparation.</b><small>Local researchers check institutions, monitoring and policy before it goes live.</small></span><span class="go quiet">Help build it ${ARROW}</span></a>`) : "";
    // Yearly counts: the countries.json series when the country is in the file (the same series as the Trend
    // tab); otherwise the fixed-seed sample, labelled as a sample.
    const ovSeries = series ? [...series.rows, ...(series.partial ? [series.partial] : [])] : null;
    const ovSample = !series && s?.years ? Object.fromEntries(s.years.map((g) => [+g.key, g.count])) : null;
    const ovPartial = series ? (series.partial ? series.partial[0] : null) : lastYear;
    const yearsLede = series
      ? `Works under the plastics query with an author in ${esc(inName(c.iso))}, unscreened query hits; the hatched year is to date.`
      : `Sample counts for ${esc(inName(c.iso))}, a fixed-seed preview; ${lastYear} is the year to date.`;
    el.innerHTML = `<h2>${esc(inName(c.iso)).replace(/^the /, "The ")} at a glance.</h2><p class="lede">Every panel below counts works with at least one author in ${esc(inName(c.iso))}.</p><div class="grid2">
    ${series ? factsBox(series.entry) : ""}
    <div class="box"><h3>Works per year</h3><p class="lede">${yearsLede}</p>${ovSeries?.length || ovSample ? `<div class="chart" id="ov-chart"></div>` : previewNotice("Yearly counts")}</div>
    <div class="box"><h3>Who they publish with</h3><p class="lede">Co-author countries on the same works. Select one to open it.</p>${partners ? hbars(partners, {link: true}) : previewNotice("Co-author countries")}</div>
    <div class="box"><h3>Most frequent topics</h3><p class="lede">OpenAlex primary topic of each work.</p>${s?.topics ? hbars(s.topics.slice(0, 8).map((t) => ({name: t.name, count: t.count}))) : previewNotice("Topics")}</div>
    <div class="box"><h3>Where it sits</h3><p class="lede">Rank among ${COUNTRIES.length} countries by works.</p>${hbars(COUNTRIES.slice(Math.max(c.rank - 3, 0), c.rank + 2).map((k) => ({name: `${k.rank}. ${k.name}`, count: k.works, iso: k.iso === c.iso ? null : k.iso})), {link: true})}${atlas}</div>
  </div><p class="src">${SRC}</p>`;
    if (ovSeries?.length) columns($("#ov-chart"), ovSeries, {h: 220, partial: ovPartial});
    else if (ovSample) columns($("#ov-chart"), Object.entries(ovSample).map(([y, n]) => [+y, n]).filter(([y]) => y >= 1990 && y <= lastYear), {h: 220});
    wireGo(el);
  }

  // Column chart: real years, last year hatched as "to date".
  // partial: the year to hatch (null for none); the default is the world view's last year.
  function columns(el, data, {h = 300, ann, partial} = {}) {
    const part = partial === undefined ? lastYear : partial;
    const W = Math.max(el.clientWidth || 900, 300); h = W < 560 ? Math.round(h * 0.7) : h;
    const pad = {l: 52, r: 8, t: 16, b: 28}, iw = W - pad.l - pad.r, ih = h - pad.t - pad.b;
    const max = Math.max(...data.map((d) => d[1])), mag = Math.pow(10, Math.floor(Math.log10(max))), top = Math.ceil(max / mag) * mag;
    const ticks = [0, top / 4, top / 2, (3 * top) / 4, top];
    const bw = iw / data.length;
    const y = (v) => pad.t + ih - (v / top) * ih;
    const every = data.length > 40 || W < 560 ? 10 : 5;
    let s = `<svg viewBox="0 0 ${W} ${h}" role="img" aria-label="Works per year, ${data[0][0]} to ${data.at(-1)[0]}"><defs><pattern id="ga-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--pv-paper)"/><rect width="3" height="6" fill="var(--pv-slate-2)"/></pattern></defs><g class="ax">`;
    for (const t of ticks) s += `<line class="gl" x1="${pad.l}" x2="${W - pad.r}" y1="${y(t)}" y2="${y(t)}"/><text x="${pad.l - 8}" y="${y(t) + 3.5}" text-anchor="end">${fmt(t)}</text>`;
    data.forEach(([yr], i) => { if (yr % every === 0) s += `<text x="${pad.l + i * bw + bw / 2}" y="${h - 8}" text-anchor="middle">${yr}</text>`; });
    s += `</g>`;
    data.forEach(([yr, n], i) => { s += `<rect class="col${yr === part ? " part" : ""}" x="${(pad.l + i * bw + bw * 0.12).toFixed(1)}" y="${y(n).toFixed(1)}" width="${(bw * 0.76).toFixed(1)}" height="${(ih - (y(n) - pad.t)).toFixed(1)}"><title>${yr}${yr === part ? " (to date)" : ""}: ${fmt(n)} works</title></rect>`; });
    s += `<line class="base" x1="${pad.l}" x2="${W - pad.r}" y1="${pad.t + ih}" y2="${pad.t + ih}"/>`;
    if (ann) { const i = data.findIndex((d) => d[0] === ann.year); if (i >= 0) { const x = pad.l + i * bw + bw / 2; s += `<g class="ann"><line x1="${x}" x2="${x}" y1="${pad.t + ih - 4}" y2="${pad.t + ih * 0.45}"/><text x="${x + 6}" y="${pad.t + ih * 0.45 + 4}">${esc(ann.text)}</text></g>`; } }
    el.innerHTML = s + `</svg>`;
  }
  function trendPanel(el) {
    if (scope.kind === "country" && countryFile === undefined) {
      el.innerHTML = `<h2>Works per year</h2><p class="lede">Loading the yearly counts for ${esc(scopeName())}.</p>`;
      return void loadCountryFile().then(() => { if (el.isConnected && tab === "trend") trendPanel(el); });
    }
    const series = scope.kind === "country" && countryFile ? countrySeries(countryFile, scope.iso) : null;
    if (series) return countryTrend(el, series);
    const s = sampleOf();
    const data = scope.kind === "world" ? years : s?.years ? s.years.map((g) => [+g.key, g.count]).sort((a, b) => a[0] - b[0]) : null;
    if (!data) { el.innerHTML = `<h2>Works per year</h2><p class="lede">How fast research grows in ${esc(scopeName())}.</p>${previewNotice("Yearly counts")}`; return wireGo(el); }
    const view = trendPanel.view || "chart", from = scope.kind === "world" ? 1970 : 1990, rows = data.filter(([y]) => y >= from && y <= lastYear);
    el.innerHTML = `<div class="toolbar"><div><h2>Works per year</h2><p class="lede" style="margin:0">Works under the plastics query${scope.kind === "world" ? "" : " with an author in " + esc(scope.kind === "country" ? inName(scope.iso) : scopeName())}, ${from} to ${lastYear}; the hatched year is to date.</p></div>
    <div class="seg" style="margin-left:auto" role="group" aria-label="Show as"><button type="button" class="btn" aria-pressed="${view === "chart"}" data-v="chart">Chart</button><button type="button" class="btn" aria-pressed="${view === "table"}" data-v="table">Table</button></div></div>
    <div class="box">${view === "chart" ? `<div class="chart" id="tr-chart"></div>` : `<div class="tw" style="max-height:420px;overflow:auto" tabindex="0" role="region" aria-label="Works per year table, scrollable"><table class="t"><thead><tr><th><span>year</span></th><th class="n"><span>works</span></th></tr></thead><tbody>${rows.slice().reverse().map(([y, n]) => `<tr><td class="m">${y}${y === lastYear ? " (to date)" : ""}</td><td class="n">${fmt(n)}</td></tr>`).join("")}</tbody></table></div>`}</div>
    <p class="src">${SRC}${scope.kind === "world" ? " Carpenter et al. (1972), Science 178:749, first described plastic spherules in coastal waters." : ""}</p>`;
    if (view === "chart") columns($("#tr-chart"), rows, {h: 340, ann: scope.kind === "world" ? {year: 1972, text: "1972: first ocean microplastics paper"} : null});
    el.querySelectorAll("[data-v]").forEach((b) => b.addEventListener("click", () => { trendPanel.view = b.dataset.v; trendPanel(el); }));
    if (scope.kind === "world") pollutionShare(el);
    // BQ-2.4: the pollution-core share (B/A) from denominators.json, fetched once when the Trend tab first
    // needs it. It is a line under the counts, with the same what-this-is-and-is-not text as the Evidence Map.
    async function pollutionShare(target) {
      if (!trendPanel.denoms) trendPanel.denoms = fetch(globalDataUrl("denominators.json"), {cache: "no-cache"}).then((r) => (r.ok ? r.json() : null)).then(readDenominators).catch(() => null);
      const denoms = await trendPanel.denoms;
      if (!denoms || !target.isConnected || scope.kind !== "world" || target.querySelector("[data-bq-share]")) return;
      const last = denominatorShare(denoms, "B", "A").at(-1);
      if (!last) return;
      const what = denoms.what_this_is_and_is_not || {};
      target.insertAdjacentHTML("beforeend", `<div class="box" data-bq-share><h3>Pollution-core share</h3>` +
        `<p class="lede">In ${last.year}, ${fmt(last.corpus)} of ${fmt(last.global)} works matching the plastics query (${(last.share * 100).toFixed(1)}%) also match the pollution-core terms.</p>` +
        `<p class="src"><b>What this is.</b> ${esc(what.is)} <b>What this is not.</b> ${esc(what.is_not)}</p></div>`);
    }
  }

  // Country scope with a countries.json entry: complete years from the file, the partial year hatched, and the
  // unscreened caption with the file's own what-this-is text. Chart/Table share the world view's controls.
  function countryTrend(el, {entry, from, last, partial, rows}) {
    const view = trendPanel.view || "chart";
    const data = partial ? [...rows, partial] : rows;
    const partialYear = partial ? partial[0] : null;
    const what = countryFile.what_this_is_and_is_not || {};
    const note = tierNote(entry);
    el.innerHTML = `<div class="toolbar"><div><h2>Works per year</h2><p class="lede" style="margin:0">Works under the plastics query with an author in ${esc(inName(entry.iso))}, unscreened query hits, ${from} to ${partialYear ?? last}; the hatched year is to date.</p></div>
    <div class="seg" style="margin-left:auto" role="group" aria-label="Show as"><button type="button" class="btn" aria-pressed="${view === "chart"}" data-v="chart">Chart</button><button type="button" class="btn" aria-pressed="${view === "table"}" data-v="table">Table</button></div></div>
    ${note ? `<p class="lede">${esc(note)}</p>` : ""}
    <div class="box">${view === "chart" ? `<div class="chart" id="tr-chart"></div>` : `<div class="tw" style="max-height:420px;overflow:auto" tabindex="0" role="region" aria-label="Works per year table, scrollable"><table class="t"><thead><tr><th><span>year</span></th><th class="n"><span>works</span></th></tr></thead><tbody>${data.slice().reverse().map(([y, n]) => `<tr><td class="m">${y}${y === partialYear ? " (to date)" : ""}</td><td class="n">${fmt(n)}</td></tr>`).join("")}</tbody></table></div>`}</div>
    <p class="src"><b>What this is.</b> ${esc(what.is)} <b>What this is not.</b> ${esc(what.is_not)} Source: OpenAlex, plastics query ${esc(countryFile.query_version)}.</p>`;
    if (view === "chart") columns($("#tr-chart"), data, {h: 340, partial: partialYear});
    el.querySelectorAll("[data-v]").forEach((b) => b.addEventListener("click", () => { trendPanel.view = b.dataset.v; trendPanel(el); }));
  }

  const EV_ROWS = ["occurrence", "effects", "methods", "fate and transport", "solutions"];
  const EV_COLS = ["ocean", "freshwater", "soil", "air", "food and biota", "people"];
  const EV_SH_R = ["occur.", "effects", "methods", "fate", "solut."], EV_SH_C = ["ocean", "fresh", "soil", "air", "food", "people"];
  const EV_BASE = [[3900, 2600, 1040, 650, 1560, 520], [2340, 1300, 520, 130, 2080, 780], [1300, 780, 390, 260, 390, 130], [1040, 780, 390, 260, 130, 0], [520, 260, 0, 0, 130, 0]];
  let evFilter = null;
  function evidencePanel(el) {
    const k = scopeWorks() / totalWorld, cells = EV_BASE.map((r) => r.map((v) => Math.round(v * k)));
    const max = Math.max(...cells.flat());
    el.innerHTML = `<h2>Where the evidence is, and where it is missing.</h2>
    <p class="lede">Studies sorted by what they examine and where. Hatched cells are gaps. Select a cell to list its works.</p>
    <div class="evwrap"><table class="evt"><caption class="sr">Evidence map for ${esc(scopeName())}</caption><thead><tr><td></td>${EV_COLS.map((c, j) => `<th scope="col"><span class="lg">${c}</span><span class="sh" aria-hidden="true">${EV_SH_C[j]}</span></th>`).join("")}</tr></thead><tbody>
    ${cells.map((r, i) => `<tr><th scope="row"><span class="lg">${EV_ROWS[i]}</span><span class="sh" aria-hidden="true">${EV_SH_R[i]}</span></th>${r.map((v, j) => { const gap = v < 1; let f = gap ? 0 : Math.sqrt(v / max) * 0.95; const dk = f > 0.68; if (dk) f = Math.max(f, 0.9); return `<td class="${gap ? "gap" : dk ? "dk" : ""}" style="--v:${f.toFixed(3)}"><button type="button" data-r="${i}" data-c="${j}" aria-label="${EV_ROWS[i]} in ${EV_COLS[j]}: ${gap ? "gap, no studies" : fmt(v) + " works"}">${gap ? "gap" : fmt(v)}</button></td>`; }).join("")}</tr>`).join("")}
    </tbody></table></div>
    <p class="src">Illustrative counts, scaled to ${esc(scopeName())}. The live map counts works per cell with the reviewed query and the agreed cell definitions.</p>`;
    el.querySelectorAll("[data-r]").forEach((b) => b.addEventListener("click", () => { evFilter = `${EV_ROWS[b.dataset.r]} × ${EV_COLS[b.dataset.c]}`; setTab("works"); }));
  }

  function rankTable(el, {title, lede, items, unit, note, linkBase, q}) {
    const max = Math.max(...items.map((i) => i.count), 1);
    const shown = items.filter((i) => !q.v || i.name.toLowerCase().includes(q.v.toLowerCase()));
    el.innerHTML = `<h2>${title}</h2><p class="lede">${lede}</p>
    <div class="toolbar"><label class="sr" for="rq">Filter</label><input class="field" id="rq" type="search" placeholder="Filter by name" value="${esc(q.v)}" style="width:min(280px,100%)"><span class="count">${shown.length} of ${items.length}</span></div>
    <div class="tw"><table class="t"><thead><tr><th><span>#</span></th><th><span>name</span></th><th class="n"><span>${unit}</span></th><th class="col-bar"><span>relative to the top</span></th><th class="n"><span>source</span></th></tr></thead><tbody>
    ${shown.map((i) => `<tr><td class="rk">${i.rank}</td><td>${esc(i.name)}</td><td class="n">${fmt(i.count)}</td><td class="barcell col-bar"><div class="bar" style="width:${(i.count / max) * 100}%;background:var(--pv-slate)"></div></td><td class="n"><a href="${linkBase}${i.key}" rel="noreferrer">OpenAlex</a></td></tr>`).join("") || `<tr><td colspan="5" class="empty"><b>Nothing matches “${esc(q.v)}”.</b><button type="button" class="linkbtn" id="rclear">Clear the filter</button></td></tr>`}
    </tbody></table></div><p class="src">${note} ${SRC}</p>`;
    const i = $("#rq", el);
    i.addEventListener("input", (e) => { q.v = e.target.value; const p = e.target.selectionStart; rankTable(el, arguments[1]); const n = $("#rq", el); n.focus(); n.setSelectionRange(p, p); });
    $("#rclear", el)?.addEventListener("click", () => { q.v = ""; rankTable(el, arguments[1]); $("#rq", el).focus(); });
  }
  const qExp = {v: ""}, qInst = {v: ""};
  function expertsPanel(el) {
    const s = sampleOf();
    if (!s?.authors) { el.innerHTML = `<h2>Authors</h2><p class="lede">The most published researchers in ${esc(scopeName())}.</p>${previewNotice("Author rankings")}`; return wireGo(el); }
    rankTable(el, {title: scope.kind === "world" ? "The most published researchers." : `Most published researchers on ${esc(scopeName())} works.`,
      lede: "Ranked by works under the plastics query. Counts are works, not citations or quality.",
      items: s.authors.map((a, i) => ({...a, rank: i + 1})), unit: "works", linkBase: "https://openalex.org/authors/", q: qExp,
      note: scope.kind === "world" ? "One person can hold more than one OpenAlex author record." : `Includes co-authors abroad on works with an author in ${esc(scopeName())}.`});
  }
  function institutionsPanel(el) {
    const s = sampleOf();
    if (!s?.institutions) { el.innerHTML = `<h2>Institutions</h2><p class="lede">Universities, agencies and institutes in ${esc(scopeName())}.</p>${previewNotice("Institution rankings")}`; return wireGo(el); }
    rankTable(el, {title: scope.kind === "world" ? "Institutions with the most plastics works." : `Institutions on ${esc(scopeName())} works.`,
      lede: "Ranked by works under the plastics query that list the institution.",
      items: s.institutions.map((a, i) => ({...a, rank: i + 1})), unit: "works", linkBase: "https://openalex.org/institutions/", q: qInst,
      note: scope.kind === "world" ? "" : `Includes partner institutions abroad; the global build keeps only institutions located in ${esc(scopeName())}.`});
  }

  function networkPanel(el) {
    const ego = scope.kind === "country" ? scope.iso : null;
    let nodes, links;
    if (ego) {
      const p = partnersOf(ego);
      if (!p) { el.innerHTML = `<h2>Collaboration network</h2>${previewNotice("Co-author networks")}`; return wireGo(el); }
      nodes = [{iso: ego, works: C[ego].works}, ...p.slice(0, 12).map((x) => ({iso: x.iso, works: C[x.iso].works, w: x.count}))];
      links = nodes.slice(1).map((n) => ({a: ego, b: n.iso, w: n.w}));
    } else {
      const set = Object.keys(S).filter((k) => k !== "world" && C[k]).filter((k) => scope.kind !== "cont" || C[k].continent === scope.name);
      if (set.length < 2) { el.innerHTML = `<h2>Collaboration network</h2>${previewNotice("Co-author networks")}`; return wireGo(el); }
      nodes = set.map((iso) => ({iso, works: C[iso].works}));
      const seen = new Map();
      for (const a of set) for (const g of S[a].countries || []) if (g.key !== a && set.includes(g.key)) { const key = [a, g.key].sort().join("-"); seen.set(key, Math.max(seen.get(key) || 0, g.count)); }
      links = [...seen].map(([k, w]) => { const [a, b] = k.split("-"); return {a, b, w}; });
    }
    const W = 760, Hh = 560, cx = W / 2, cy = Hh / 2, R = 220, maxW = Math.max(...nodes.map((n) => n.works)), maxL = Math.max(...links.map((l) => l.w));
    const order = ego ? nodes : nodes.slice().sort((a, b) => (C[a.iso].continent + a.iso < C[b.iso].continent + b.iso ? -1 : 1));
    const pos = {};
    order.forEach((n, i) => { if (ego && i === 0) pos[n.iso] = [cx, cy]; else { const k = ego ? i - 1 : i, N = ego ? order.length - 1 : order.length, t = ((k + (ego ? 0 : 0.5)) / N) * Math.PI * 2 - Math.PI / 2; pos[n.iso] = [cx + R * Math.cos(t), cy + R * Math.sin(t)]; } });
    const r = (n) => 6 + Math.sqrt(n.works / maxW) * 26;
    const mg = el.clientWidth < 600 ? 170 : 80;
    const svg = `<svg viewBox="${-mg} -18 ${W + 2 * mg} ${Hh + 36}" role="group" aria-label="Co-authorship network between countries">
    ${links.sort((a, b) => a.w - b.w).map((l) => { const [x1, y1] = pos[l.a], [x2, y2] = pos[l.b], mx = (x1 + x2) / 2 + (cx - (x1 + x2) / 2) * 0.35, my = (y1 + y2) / 2 + (cy - (y1 + y2) / 2) * 0.35; return `<path class="lk" data-a="${l.a}" data-b="${l.b}" d="M${x1.toFixed(1)} ${y1.toFixed(1)}Q${mx.toFixed(1)} ${my.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}" fill="none" stroke-width="${(0.8 + (l.w / maxL) * 9).toFixed(2)}" stroke-opacity="${(0.25 + (l.w / maxL) * 0.6).toFixed(2)}"/>`; }).join("")}
    ${nodes.map((n) => { const [x, y] = pos[n.iso], rr = r(n), out = !ego || n.iso !== ego, ang = Math.atan2(y - cy, x - cx), lx = out ? x + Math.cos(ang) * (rr + 8) : x, ly = out ? y + Math.sin(ang) * (rr + 8) : y + rr + 16, anchor = !out ? "middle" : Math.cos(ang) > 0.1 ? "start" : Math.cos(ang) < -0.1 ? "end" : "middle";
      return `<g class="nd${n.iso === ego ? " me" : ""}" data-iso="${n.iso}" tabindex="0" role="button" aria-label="${esc(C[n.iso].name)}, ${fmt(n.works)} works"><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${rr.toFixed(1)}"/><text x="${lx.toFixed(1)}" y="${(ly + 4).toFixed(1)}" text-anchor="${anchor}">${esc(C[n.iso].name)}</text></g>`; }).join("")}</svg>`;
    const ranked = links.slice().sort((a, b) => b.w - a.w).slice(0, 10);
    el.innerHTML = `<h2>${ego ? `Who ${esc(inName(ego))} works with.` : "Which countries publish together."}</h2>
    <p class="lede">${ego ? "Circle size shows a country's works; line width shows the works it shares with each partner." : "The largest research countries and their shared works. Circle size shows a country's works; line width shows works they share. Hover or focus a country to isolate its links; select it to open its profile."}</p>
    <div class="netgrid"><div class="net" id="net">${svg}</div>
    <div class="box"><h3>Strongest links</h3><p class="lede">Works co-authored by both countries.</p><div id="net-list">${hbars(ranked.map((l) => ({name: `${C[l.a].name} · ${C[l.b].name}`, count: l.w})))}</div></div></div>
    <p class="src">Co-author countries from OpenAlex group_by on each country's works. ${SRC}</p>`;
    const net = $("#net", el);
    net.style.setProperty("--fs", (12 * Math.min((760 + 2 * mg) / Math.max(net.clientWidth, 1), 3.2)).toFixed(1) + "px");
    const adj = (iso) => links.filter((l) => l.a === iso || l.b === iso);
    const focus = (iso) => {
      net.classList.toggle("focus", !!iso);
      net.querySelectorAll(".lk").forEach((p) => p.classList.toggle("on", !!iso && (p.dataset.a === iso || p.dataset.b === iso)));
      const nb = new Set(iso ? adj(iso).flatMap((l) => [l.a, l.b]) : []);
      net.querySelectorAll(".nd").forEach((g) => g.classList.toggle("on", nb.has(g.dataset.iso) || g.dataset.iso === iso));
      $("#net-list", el).innerHTML = hbars((iso ? adj(iso) : ranked).sort((a, b) => b.w - a.w).slice(0, 10).map((l) => ({name: `${C[l.a].name} · ${C[l.b].name}`, count: l.w})));
    };
    net.querySelectorAll(".nd").forEach((g) => {
      g.addEventListener("pointerenter", () => focus(g.dataset.iso)); g.addEventListener("focus", () => focus(g.dataset.iso));
      g.addEventListener("click", () => go({kind: "country", iso: g.dataset.iso}));
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go({kind: "country", iso: g.dataset.iso}); } });
    });
    net.addEventListener("pointerleave", () => focus(null));
    net.addEventListener("focusout", (e) => { if (!net.contains(e.relatedTarget)) focus(null); });
  }

  const qWorks = {v: ""};
  function worksPanel(el) {
    const s = sampleOf();
    if (!s?.recent) { el.innerHTML = `<h2>Newest works</h2>${previewNotice("Works lists")}`; return wireGo(el); }
    const rel = s.recent.filter((w) => /plastic|polymer|microfib|tyre|tire/i.test(w.title || ""));
    const shown = rel.filter((w) => !qWorks.v || (w.title + " " + (w.source || "")).toLowerCase().includes(qWorks.v.toLowerCase()));
    el.innerHTML = `<h2>The newest works.</h2><p class="lede">Most recent first${scope.kind === "world" ? "" : ", with at least one author in " + esc(scope.kind === "country" ? inName(scope.iso) : scopeName())}.</p>
    <div class="toolbar">${evFilter ? `<span class="chip">Evidence cell: ${esc(evFilter)}<button type="button" id="evx" aria-label="Remove the evidence cell filter"><svg class="i" viewBox="0 0 14 14" aria-hidden="true"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5"/></svg></button></span>` : ""}
    <label class="sr" for="wq">Filter works</label><input class="field" id="wq" type="search" placeholder="Filter titles and journals" value="${esc(qWorks.v)}" style="width:min(320px,100%)"><span class="count">${shown.length} works</span></div>
    ${evFilter ? `<p class="lede">The preview does not filter by evidence cell yet; the live map will list this cell's works here.</p>` : ""}
    <ol class="works">${shown.map((w) => `<li><a class="ti" href="${esc(w.doi || "https://openalex.org/" + w.id)}" rel="noreferrer">${esc(w.title)}</a><span class="dt">${esc(w.date)}</span><span class="meta">${esc(w.first_author || "Unknown author")}${w.n_authors > 1 ? " et al." : ""}${w.source ? " · " + esc(w.source) : ""}${w.countries.length ? `<span class="cc" aria-label="Author countries">${w.countries.slice(0, 5).map((c) => `<span>${esc(C[c]?.name || c)}</span>`).join("")}${w.countries.length > 5 ? `<span>+${w.countries.length - 5}</span>` : ""}</span>` : ""}</span></li>`).join("") || `<li class="empty"><b>No work matches “${esc(qWorks.v)}”.</b><button type="button" class="linkbtn" id="wclear">Clear the filter</button></li>`}</ol>
    <p class="src">Newest works under the plastics query. This preview hides titles that do not name plastic; the global build adds a relevance check. ${SRC}</p>`;
    $("#wq", el).addEventListener("input", (e) => { qWorks.v = e.target.value; const p = e.target.selectionStart; worksPanel(el); const n = $("#wq", el); n.focus(); n.setSelectionRange(p, p); });
    $("#wclear", el)?.addEventListener("click", () => { qWorks.v = ""; worksPanel(el); $("#wq", el).focus(); });
    $("#evx", el)?.addEventListener("click", () => { evFilter = null; worksPanel(el); $("#wq", el).focus(); });
  }

  const PANELS = {countries: countriesPanel, evidence: evidencePanel, trend: trendPanel, experts: expertsPanel, institutions: institutionsPanel, network: networkPanel, works: worksPanel};
  function renderPanel() {
    if (tab !== "countries") mapEl = null;
    const el = $("#panel-" + tab);
    PANELS[tab](el);
  }

  // ---- navigation ------------------------------------------------------------------------
  function writeHash() {
    const h = `#scope=${encodeURIComponent(scopeKey(scope))}${tab !== "countries" ? "&view=" + tab : ""}`;
    if (location.hash !== h) history.replaceState(null, "", h);
  }
  function go(next, {push = true, focus = null} = {}) {
    const prev = scope;
    scope = next;
    focusGeo = focus;
    if (scope.kind !== "country") tableState.q = "";
    if (push) history.pushState(null, "", `#scope=${encodeURIComponent(scopeKey(scope))}${tab !== "countries" ? "&view=" + tab : ""}`);
    renderLadder(); renderHead();
    root.querySelectorAll(".tab").forEach((t) => { if (t.id === "tab-countries") t.textContent = scope.kind === "country" ? "Overview" : "Countries"; });
    if (tab === "countries" && mapEl && prev) {
      // Keep the map node so the zoom can run; rebuild only what sits below it.
      paintMapScope(true);
      const below = $("#below");
      if (scope.kind === "country") overview(below); else countryTable(below);
    } else renderPanel();
    $("#live").textContent = `Scope: ${scopeName()}, ${fmt(scopeWorks())} works.`;
    document.title = `${scope.kind === "world" ? "Explore the data" : scopeName()} · Plastiverse Live`;
  }
  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    scope = parseScope(p.get("scope"));
    focusGeo = null;
    tab = TABS.some((t) => t[0] === p.get("view")) ? p.get("view") : "countries";
  }
  addEventListener("popstate", () => { if (!attached()) return; readHash(); renderAll(); });
  function renderAll() { renderLadder(); renderHead(); renderTabs(); renderPanel(); }

  mountFind($("#find-desk"), "fd");
  mountFind($("#find-mob"), "fm");
  readHash();
  renderAll();
  document.fonts?.ready.then(() => placeCallouts());
  window.__explore = {go, setTab, get scope() { return scope; }};
}
