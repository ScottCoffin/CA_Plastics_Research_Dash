import {attachMapGestures} from "./world_map.js";
import {siteRoot} from "./atlas.js";

const esc = (value) => String(value ?? "").replace(/[&<>\"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;"}[c]));
const fmt = (value) => Number.isFinite(+value) ? new Intl.NumberFormat("en-US").format(+value) : "0";
const REGIONAL_ATLASES = {
  california: {key: "california", label: "California", country: "US"},
  norway: {key: "norway", label: "Norway", country: "NO"},
  belgium: {key: "belgium", label: "Belgium", country: "BE"},
};

function scopeLabel(scope) { return scope?.label || (scope?.kind === "world" ? "World" : scope?.key || "World"); }

// Groups scope map: the shared Natural Earth country geometry, shared explore country metadata,
// and the same cooperative zoom/pan behavior as /explore.
export function mountGroupsScopeMap(root, {world, scopes, explore, coverage, onScope = () => {}} = {}) {
  const entries = Array.isArray(scopes?.scopes) ? scopes.scopes : [];
  const countries = Array.isArray(world?.countries) ? world.countries : [];
  const metadata = new Map((explore?.countries || []).map((c) => [c.iso, c]));
  const valid = entries.length ? entries : [{key: "world", kind: "world", label: "World", group_ids: []}];
  const byKey = new Map(valid.map((s) => [s.key, s]));
  const get = (key) => byKey.get(key) || byKey.get("world") || valid[0];
  const atlasFor = (scope) => {
    if (scope.kind === "region") return REGIONAL_ATLASES[String(scope.key).replace(/^region:/, "")] || null;
    if (scope.kind === "country" && ["NO", "BE"].includes(scope.iso)) return Object.values(REGIONAL_ATLASES).find((atlas) => atlas.country === scope.iso) || null;
    return null;
  };
  const listeners = new AbortController();
  let disposed = false;
  const currentHash = () => new URLSearchParams(location.hash.replace(/^#/, ""));
  let selected = get(currentHash().get("scope") || "world");
  let appliedKey = null;
  let view = [0, 0, +(world?.w || 1000), +(world?.h || 520)];
  let map, gestures;
  const frame = [0, 0, +(world?.w || 1000), +(world?.h || 520)];

  const childrenFor = (scope) => valid.filter((item) => item.parent === scope.key);
  const countriesFor = (scope) => {
    if (scope.kind === "country") return [scope.iso];
    if (scope.kind === "region") {
      const country = byKey.get(scope.parent);
      return country?.iso ? [country.iso] : [];
    }
    if (scope.kind === "continent" || scope.kind === "cont") return (explore?.countries || []).filter((c) => c.continent === scope.label || c.continent === scope.name).map((c) => c.iso);
    return (explore?.countries || []).map((c) => c.iso);
  };
  const resize = () => {
    if (!map) return;
    map.setAttribute("viewBox", view.join(" "));
  };
  const setScope = (next, {writeHash = true, focus = false} = {}) => {
    const candidate = get(next.key);
    if (appliedKey === candidate.key) return;
    selected = candidate;
    appliedKey = selected.key;
    const allowed = new Set(countriesFor(selected));
    root.querySelectorAll("[data-iso]").forEach((path) => {
      path.classList.toggle("is-muted", !allowed.has(path.dataset.iso));
      const selectedIso = selected.kind === "region" ? byKey.get(selected.parent)?.iso : selected.iso;
      const isSelected = (selected.kind === "country" || selected.kind === "region") && path.dataset.iso === selectedIso;
      path.classList.toggle("is-selected", isSelected);
      path.setAttribute("aria-pressed", String(isSelected));
    });
    const title = root.querySelector("[data-scope-title]");
    const count = root.querySelector("[data-scope-count]");
    if (title) title.textContent = scopeLabel(selected);
    const groupCount = selected.kind === "world" ? (coverage?.roster_total ?? selected.group_ids?.length ?? 0) : (selected.group_ids?.length ?? 0);
    if (count) count.textContent = `${fmt(groupCount)} groups in this scope`;
    const live = root.querySelector("[data-live]");
    if (live) live.textContent = `Scope: ${scopeLabel(selected)}. ${fmt(groupCount)} groups.`;
    const related = root.querySelector("[data-related-links]");
    const regionalAtlas = atlasFor(selected);
    if (related) {
      related.hidden = !regionalAtlas;
      if (regionalAtlas) {
        const base = siteRoot();
        const prefix = `${regionalAtlas.key}/`;
        related.innerHTML = `<span>Related regional Atlas views</span><a href="${new URL(prefix, base).href}">${esc(regionalAtlas.label)} atlas</a><a href="${new URL(`${prefix}institutions`, base).href}">Institutions</a><a href="${new URL(`${prefix}evidence`, base).href}">Evidence map and works</a>`;
      }
    }
    const parent = root.querySelector("[data-scope-ladder]");
    if (parent) {
      const trail = [get("world")];
      let cursor = selected;
      const chain = [];
      while (cursor && cursor.key !== "world") { chain.unshift(cursor); cursor = byKey.get(cursor.parent); }
      trail.push(...chain);
      parent.innerHTML = trail.map((item, i) => `<button type="button" class="gm-step${item.key === selected.key ? " is-current" : ""}" data-key="${esc(item.key)}"${item.key === selected.key ? ' aria-current="location"' : ""}>${esc(scopeLabel(item))}${item.group_ids ? `<span>${fmt(item.group_ids.length)}</span>` : ""}</button>`).join("");
    }
    const choices = root.querySelector("[data-scope-choices]");
    if (choices) {
      const children = childrenFor(selected);
      choices.innerHTML = children.length ? children.map((item) => `<button type="button" data-key="${esc(item.key)}" class="gm-choice">${esc(scopeLabel(item))}<span>${fmt(item.group_ids?.length ?? coverage?.by_country?.[item.iso]?.roster ?? 0)}</span></button>`).join("") : `<span class="gm-hint">No narrower scopes are available here.</span>`;
    }
    const fit = (boxes) => {
      if (!boxes.length) return;
      const x0 = Math.min(...boxes.map((b) => b.x)), y0 = Math.min(...boxes.map((b) => b.y));
      const x1 = Math.max(...boxes.map((b) => b.x + b.width)), y1 = Math.max(...boxes.map((b) => b.y + b.height));
      const pad = Math.max(8, Math.max(x1 - x0, y1 - y0) * 0.12);
      const left = Math.max(0, x0 - pad), top = Math.max(0, y0 - pad);
      const right = Math.min(frame[2], x1 + pad), bottom = Math.min(frame[3], y1 + pad);
      let w = right - left, h = bottom - top;
      const ratio = frame[2] / frame[3];
      w = Math.min(frame[2], Math.max(w, h * ratio));
      h = w / ratio;
      const x = Math.max(0, Math.min(frame[2] - w, (left + right - w) / 2));
      const y = Math.max(0, Math.min(frame[3] - h, (top + bottom - h) / 2));
      view = [x, y, w, h];
      resize();
    };
    if (selected.kind === "world") { view = frame.slice(); resize(); }
    else {
      let iso = selected.iso;
      if (!iso && selected.kind === "region") iso = byKey.get(selected.parent)?.iso;
      const target = iso ? root.querySelector(`[data-iso="${CSS.escape(iso)}"]`) : null;
      if (target) fit([target.getBBox()]);
      else if (selected.kind === "continent" || selected.kind === "cont") {
        const countrySet = new Set(countriesFor(selected));
        fit([...root.querySelectorAll("[data-iso]")].filter((el) => countrySet.has(el.dataset.iso)).map((el) => el.getBBox()));
      }
    }
    if (writeHash && currentHash().get("scope") !== selected.key) {
      const params = currentHash();
      params.set("scope", selected.key);
      history.pushState(null, "", `${location.pathname}${location.search}#${params}`);
    }
    root.setAttribute("aria-label", `Community groups map. Scope: ${scopeLabel(selected)}. ${fmt(groupCount)} groups.`);
    onScope(selected);
    if (focus) root.querySelector(`[data-key="${CSS.escape(selected.key)}"]`)?.focus();
  };

  root.innerHTML = `<section class="gm-map-panel" aria-labelledby="gm-title">
    <div class="gm-map-head"><div><h2 id="gm-title">Groups by place</h2><p><span data-scope-title>World</span> · <span data-scope-count>Loading scope counts…</span></p></div><div class="gm-map-actions"><button type="button" data-zoom="in" aria-label="Zoom in">+</button><button type="button" data-zoom="out" aria-label="Zoom out">−</button><button type="button" data-zoom="reset">Reset map</button></div></div>
    <nav class="gm-ladder" aria-label="Group map scope" data-scope-ladder></nav>
    <div class="gm-legend" aria-label="Groups listed by country">
      <span>Groups listed by country</span><i class="gm-swatch gm-swatch--zero"></i><span>0</span><i class="gm-swatch gm-swatch--few"></i><span>1–4</span><i class="gm-swatch gm-swatch--some"></i><span>5–24</span><i class="gm-swatch gm-swatch--many"></i><span>25+</span>
    </div>
    <div class="gm-map-wrap"><svg class="gm-map" viewBox="0 0 ${frame[2]} ${frame[3]}" tabindex="0" role="group" aria-label="Interactive map of community group counts by country. Select a country to scope; plus and minus zoom, arrows pan, zero resets.">
      <path class="gm-sphere" d="${world?.sphere || ""}" />
      ${countries.map((country) => {
        const meta = metadata.get(country.iso_a2) || {};
        const countryScope = valid.find((item) => item.kind === "country" && item.iso === country.iso_a2);
        const rosterCount = countryScope?.group_ids?.length ?? coverage?.by_country?.[country.iso_a2]?.roster;
        const tier = rosterCount == null ? "unknown" : rosterCount === 0 ? "zero" : rosterCount < 5 ? "few" : rosterCount < 25 ? "some" : "many";
        return `<path class="gm-country gm-country--${tier}" data-iso="${esc(country.iso_a2)}" d="${country.d}" tabindex="0" role="button" aria-pressed="false" aria-label="${esc(meta.name || country.name)}: ${rosterCount == null ? "group count unavailable" : `${fmt(rosterCount)} groups in the roster`}. Select country scope" />`;
      }).join("")}
      ${world?.disputed ? `<path class="gm-boundary" d="${world.disputed}" aria-hidden="true"/>` : ""}
    </svg><p class="gm-map-hint" data-hint>Hold Ctrl and scroll, or click the map first, to zoom. Drag to pan; on touch, use two fingers. Keyboard: +/− zoom, arrows pan, 0 reset.</p></div>
    <div class="gm-subscopes" data-scope-choices aria-label="Narrow this scope"></div>
    <nav class="gm-related" data-related-links aria-label="Related regional Atlas views" hidden></nav>
    <p class="gm-live" aria-live="polite" data-live></p>
  </section>`;
  map = root.querySelector(".gm-map");
  gestures = attachMapGestures(map, {frame, view: () => view, apply: (next) => { view = next; resize(); }, reset: () => { view = frame.slice(); resize(); }, hint: root.querySelector("[data-hint]")});
  root.addEventListener("click", (event) => {
    const choice = event.target.closest("[data-key]");
    if (choice) { const next = get(choice.dataset.key); setScope(next); return; }
    const zoom = event.target.closest("[data-zoom]")?.dataset.zoom;
    if (zoom === "in") gestures.zoomBy(1.5);
    if (zoom === "out") gestures.zoomBy(1 / 1.5);
    if (zoom === "reset") setScope(get("world"));
  }, {signal: listeners.signal});
  const activateCountry = (path) => {
    const iso = path.dataset.iso;
    const entry = valid.find((item) => item.kind === "country" && item.iso === iso);
    if (entry) setScope(entry);
    else {
      const continent = metadata.get(iso)?.continent;
      const parent = valid.find((item) => (item.kind === "continent" || item.kind === "cont") && (item.label === continent || item.name === continent));
      if (parent) setScope(parent);
    }
  };
  map.addEventListener("click", (event) => { if (!gestures.dragged()) { const path = event.target.closest("[data-iso]"); if (path) activateCountry(path); } }, {signal: listeners.signal});
  map.addEventListener("keydown", (event) => {
    const path = event.target.closest("[data-iso]");
    if (path && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); activateCountry(path); }
  }, {signal: listeners.signal});
  const syncScope = () => {
    if (!root.isConnected) { api.dispose(); return; }
    setScope(get(currentHash().get("scope") || "world"), {writeHash: false});
  };
  addEventListener("hashchange", syncScope, {signal: listeners.signal});
  addEventListener("popstate", syncScope, {signal: listeners.signal});
  setScope(selected, {writeHash: false});
  const api = {
    setScope: (key) => setScope(get(key)),
    get scope() { return selected; },
    dispose() {
      if (disposed) return;
      disposed = true;
      listeners.abort();
      gestures.dispose();
    },
  };
  return api;
}
