// Map helpers shared by the Monitoring and Institutions pages (AT-5c).
// monitoringMap is pure geometry (ported from site/index.html). The interaction and basemap
// functions touch the DOM or the network only when called, so Node tests can import this file.
import {classicUrl} from "./atlas.js";
import {monitoringView} from "./monitoring_view.js";

export const monitoringMap = Object.freeze({
  extents: Object.freeze({
    statewide: Object.freeze({ label: "Statewide", lon: [-124.6, -114], lat: [32.4, 42.1] }),
    sf_bay: Object.freeze({ label: "SF Bay", lon: [-123.1, -121.7], lat: [37.3, 38.3] })
  }),
  // One x-scale for every extent: equirectangular, cos(mid-latitude of California).
  cosMid: Math.cos((37.25 * Math.PI) / 180),
  unknownLabel: "Unknown matrix",
  palette: Object.freeze({
    "surface water": "#1f5fa8",
    stormwater: "#6b3fa0",
    sediment: "#8a5a1c",
    "wastewater effluent": "#b35900",
    fish: "#2e7d32",
    "snow (fresh snowfall)": "#0f7490",
    "snow (snowpack pit layer)": "#4b5fc0",
    "atmospheric deposition (dry, passive sampler)": "#b3245c",
    "Unknown matrix": "#6b7177"
  }),
  otherColor: "#6b7177",
  mixedColor: "#ffffff",
  project(lon, lat) {
    return [lon * monitoringMap.cosMid, -lat];
  },
  // Static place names drawn under the data markers. priority 1 shows statewide; higher numbers appear as the view zooms in.
  places: [
    { name: "San Francisco", lon: -122.42, lat: 37.77, priority: 1, kind: "city" },
    { name: "Los Angeles", lon: -118.24, lat: 34.05, priority: 1, kind: "city" },
    { name: "San Diego", lon: -117.16, lat: 32.72, priority: 1, kind: "city" },
    { name: "Sacramento", lon: -121.49, lat: 38.58, priority: 1, kind: "city" },
    { name: "Fresno", lon: -119.79, lat: 36.74, priority: 1, kind: "city" },
    { name: "San Jose", lon: -121.89, lat: 37.34, priority: 1, kind: "city" },
    { name: "Bakersfield", lon: -119.02, lat: 35.37, priority: 1, kind: "city" },
    { name: "Redding", lon: -122.39, lat: 40.59, priority: 1, kind: "city" },
    { name: "Eureka", lon: -124.16, lat: 40.8, priority: 1, kind: "city" },
    { name: "Riverside", lon: -117.4, lat: 33.95, priority: 2, kind: "city" },
    { name: "Oakland", lon: -122.27, lat: 37.8, priority: 2, kind: "city" },
    { name: "Santa Barbara", lon: -119.7, lat: 34.42, priority: 2, kind: "city" },
    { name: "Stockton", lon: -121.29, lat: 37.96, priority: 2, kind: "city" },
    { name: "Chico", lon: -121.84, lat: 39.73, priority: 2, kind: "city" },
    { name: "Long Beach", lon: -118.19, lat: 33.77, priority: 3, kind: "city" },
    { name: "Monterey", lon: -121.89, lat: 36.6, priority: 3, kind: "city" },
    { name: "Santa Cruz", lon: -122.03, lat: 36.97, priority: 3, kind: "city" },
    { name: "San Bernardino", lon: -117.29, lat: 34.11, priority: 3, kind: "city" },
    { name: "Modesto", lon: -121.0, lat: 37.64, priority: 3, kind: "city" },
    { name: "Palm Springs", lon: -116.55, lat: 33.83, priority: 3, kind: "city" },
    { name: "San Luis Obispo", lon: -120.66, lat: 35.28, priority: 3, kind: "city" },
    { name: "Irvine", lon: -117.83, lat: 33.68, priority: 4, kind: "city" },
    { name: "Davis", lon: -121.74, lat: 38.54, priority: 4, kind: "city" },
    { name: "Berkeley", lon: -122.27, lat: 37.87, priority: 4, kind: "city" },
    { name: "Merced", lon: -120.48, lat: 37.3, priority: 4, kind: "city" },
    { name: "Sierra Nevada", lon: -118.9, lat: 37.2, priority: 1, kind: "landmark" },
    { name: "Central Valley", lon: -120.1, lat: 36.3, priority: 1, kind: "landmark" },
    { name: "Mojave Desert", lon: -116.8, lat: 35.1, priority: 1, kind: "landmark" },
    { name: "Salton Sea", lon: -115.85, lat: 33.3, priority: 2, kind: "landmark" },
    { name: "Lake Tahoe", lon: -120.04, lat: 39.09, priority: 2, kind: "landmark" },
    { name: "San Francisco Bay", lon: -122.28, lat: 37.62, priority: 3, kind: "landmark" },
    { name: "Channel Islands", lon: -119.7, lat: 33.96, priority: 2, kind: "landmark" },
    { name: "Monterey Bay", lon: -121.95, lat: 36.78, priority: 4, kind: "landmark" },
    { name: "Point Conception", lon: -120.47, lat: 34.45, priority: 3, kind: "landmark" }
  ],
  placeMinZoom: { 1: 0, 2: 1.8, 3: 3.5, 4: 7 },
  // avoid: [{ x, y, r }] marker discs in view units; labels that would sit under a marker are skipped so they stay legible.
  placeLabels(view, avoid = []) {
    const zoom = monitoringMap.zoomScale(view);
    const fs = view.width * 0.019;
    const charW = fs * 0.56;
    const boxes = avoid.map((m) => ({ x0: m.x - m.r, x1: m.x + m.r, y0: m.y - m.r, y1: m.y + m.r, marker: m }));
    const hit = (a, b) => a.x0 < b.x1 && a.x1 > b.x0 && a.y0 < b.y1 && a.y1 > b.y0;
    const out = [];
    const ordered = monitoringMap.places.filter((place) => zoom >= (monitoringMap.placeMinZoom[place.priority] ?? 0)).sort((a, b) => a.priority - b.priority);
    for (const place of ordered) {
      const [x, y] = monitoringMap.project(place.lon, place.lat);
      const pad = fs * 0.6;
      if (x < view.x + pad || x > view.x + view.width - pad || y < view.y + pad || y > view.y + view.height - pad) continue;
      const city = place.kind === "city";
      const width = place.name.length * charW;
      const dot = fs * 0.28;
      // A city sitting under a data marker gets no dot; its name is set beside that marker instead.
      const cover = city ? avoid.filter((m) => Math.hypot(m.x - x, m.y - y) < m.r + dot).sort((a, b) => b.r - a.r)[0] : null;
      const ox = cover ? cover.x : x;
      const oy = cover ? cover.y : y;
      const gap = city ? (cover ? cover.r : dot) + fs * 0.25 : 0;
      const candidates = city
        ? [{ anchor: "start", x0: ox + gap, x1: ox + gap + width, dy: 0 }, { anchor: "end", x0: ox - gap - width, x1: ox - gap, dy: 0 }, { anchor: "middle", x0: ox - width / 2, x1: ox + width / 2, dy: -(gap + fs * 0.6) }, { anchor: "middle", x0: ox - width / 2, x1: ox + width / 2, dy: gap + fs * 0.6 }]
        : [{ anchor: "middle", x0: x - width / 2, x1: x + width / 2, dy: 0 }];
      const dotBox = { x0: x - dot, x1: x + dot, y0: y - dot, y1: y + dot };
      let chosen = null;
      for (const cand of candidates) {
        const cy = oy + (cand.dy || 0);
        const box = { x0: cand.x0, x1: cand.x1, y0: cy - fs * 0.6, y1: cy + fs * 0.6 };
        if (box.x0 < view.x + pad * 0.3 || box.x1 > view.x + view.width - pad * 0.3) continue;
        if (boxes.some((other) => other.marker !== cover && (hit(box, other) || (city && !cover && hit(dotBox, other))))) continue;
        chosen = { cand, box, cy };
        break;
      }
      if (!chosen) continue;
      boxes.push(chosen.box);
      if (city && !cover) boxes.push(dotBox);
      const tx = chosen.cand.anchor === "start" ? ox + gap : chosen.cand.anchor === "end" ? ox - gap : ox;
      out.push(`<g class="place-${place.kind}">${city && !cover ? `<circle class="place-dot" cx="${x}" cy="${y}" r="${dot}"/>` : ""}<text x="${tx}" y="${chosen.cy}" font-size="${fs}" text-anchor="${chosen.cand.anchor}" dominant-baseline="central" style="stroke-width:${fs * 0.3}">${place.name}</text></g>`);
    }
    return `<g class="map-places" aria-hidden="true">${out.join("")}</g>`;
  },
  viewBox(key) {
    const extent = monitoringMap.extents[key];
    if (!extent) throw new Error(`unknown map extent: ${key}`);
    const [x0, y0] = monitoringMap.project(extent.lon[0], extent.lat[1]);
    const [x1, y1] = monitoringMap.project(extent.lon[1], extent.lat[0]);
    return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
  },
  inView(key, lat, lon) {
    const view = monitoringMap.viewBox(key);
    const [x, y] = monitoringMap.project(lon, lat);
    return x >= view.x && x <= view.x + view.width && y >= view.y && y <= view.y + view.height;
  },
  // Interactive view: 1x (statewide width) up to maxZoom, centred within the statewide extent.
  maxZoom: 40,
  clampView(view) {
    const bounds = monitoringMap.viewBox("statewide");
    const aspect = view.height / view.width;
    const width = Math.min(bounds.width, Math.max(bounds.width / monitoringMap.maxZoom, view.width));
    const height = width * aspect;
    const cx = Math.min(bounds.x + bounds.width, Math.max(bounds.x, view.x + view.width / 2));
    const cy = Math.min(bounds.y + bounds.height, Math.max(bounds.y, view.y + view.height / 2));
    return { x: cx - width / 2, y: cy - height / 2, width, height };
  },
  zoomScale(view) {
    return monitoringMap.viewBox("statewide").width / view.width;
  },
  // factor > 1 zooms in; the anchor point (view units) stays under the pointer when given.
  zoomView(view, factor, anchor = null) {
    const width = view.width / factor;
    const ax = anchor ? anchor.x : view.x + view.width / 2;
    const ay = anchor ? anchor.y : view.y + view.height / 2;
    const scale = width / view.width;
    return monitoringMap.clampView({ x: ax - (ax - view.x) * scale, y: ay - (ay - view.y) * scale, width, height: view.height * scale });
  },
  panView(view, dx, dy) {
    return monitoringMap.clampView({ ...view, x: view.x + dx, y: view.y + dy });
  },
  // Centre and zoom so that projected points fit with margin; a single point gets a close view.
  fitView(points, view) {
    if (!points.length) return null;
    const bounds = monitoringMap.viewBox("statewide");
    const aspect = view.height / view.width;
    const xs = points.map(([x]) => x);
    const ys = points.map(([, y]) => y);
    const maxX = Math.max(...xs);
    const minX = Math.min(...xs);
    const maxY = Math.max(...ys);
    const minY = Math.min(...ys);
    const width = Math.max(bounds.width / 16, Math.max(maxX - minX, (maxY - minY) / aspect) * 1.5);
    const height = width * aspect;
    return monitoringMap.clampView({ x: (maxX + minX) / 2 - width / 2, y: (maxY + minY) / 2 - height / 2, width, height });
  },
  inRect(view, lat, lon) {
    const [x, y] = monitoringMap.project(lon, lat);
    return x >= view.x && x <= view.x + view.width && y >= view.y && y <= view.y + view.height;
  },
  // Drops samples whose matrix the legend has switched off.
  visibleSamples(located, hidden) {
    return located.filter(({ row }) => !hidden.has(monitoringView.matrix(row) || monitoringMap.unknownLabel));
  },
  colorFor(label) {
    return monitoringMap.palette[label] || monitoringMap.otherColor;
  },
  // GeoJSON MultiPolygon -> SVG path data in projected units, rounded to ~0.01 degree.
  pathData(geometry) {
    if (!geometry || geometry.type !== "MultiPolygon") throw new Error("basemap feature must be a MultiPolygon");
    const round = (value) => Math.round(value * 100) / 100;
    const parts = [];
    geometry.coordinates.forEach((polygon) => polygon.forEach((ring) => {
      const points = [];
      ring.forEach(([lon, lat]) => {
        const [x, y] = monitoringMap.project(lon, lat).map(round);
        const last = points[points.length - 1];
        if (!last || last[0] !== x || last[1] !== y) points.push([x, y]);
      });
      if (points.length >= 3) parts.push(`M${points.map(([x, y]) => `${x} ${y}`).join("L")}Z`);
    }));
    return parts.join("");
  },
  // Grid clustering in projected space on an absolute grid; cell size is 1/12 of the view width.
  // Zooming in shrinks cells and splits clusters; panning leaves cluster membership unchanged.
  clusters(located, key, view = monitoringMap.viewBox(key)) {
    const cell = view.width / 12;
    const groups = new Map();
    located.forEach(({ row, coordinates }) => {
      const [lat, lon] = coordinates;
      if (!monitoringMap.inRect(view, lat, lon)) return;
      const [x, y] = monitoringMap.project(lon, lat);
      const cellKey = `${Math.floor(x / cell)}:${Math.floor(y / cell)}`;
      const group = groups.get(cellKey) || { rows: [], x: 0, y: 0, matrices: new Map() };
      const label = monitoringView.matrix(row) || monitoringMap.unknownLabel;
      group.rows.push(row);
      group.x += x;
      group.y += y;
      group.matrices.set(label, (group.matrices.get(label) || 0) + 1);
      groups.set(cellKey, group);
    });
    return [...groups.values()].map((group) => {
      const labels = [...group.matrices.keys()];
      const mixed = labels.length > 1;
      return {
        rows: group.rows,
        x: group.x / group.rows.length,
        y: group.y / group.rows.length,
        matrices: group.matrices,
        mixed,
        color: mixed ? monitoringMap.mixedColor : monitoringMap.colorFor(labels[0])
      };
    });
  },
  // Generic grid clustering for weighted points {x, y, weight, item} already in projected space.
  // Same absolute grid as clusters(): cell size is 1/12 of the view width.
  clusterPoints(points, view) {
    const cell = view.width / 12;
    const groups = new Map();
    points.forEach((point) => {
      if (point.x < view.x || point.x > view.x + view.width || point.y < view.y || point.y > view.y + view.height) return;
      const cellKey = `${Math.floor(point.x / cell)}:${Math.floor(point.y / cell)}`;
      const group = groups.get(cellKey) || { items: [], x: 0, y: 0, weight: 0 };
      group.items.push(point.item);
      group.x += point.x;
      group.y += point.y;
      group.weight += point.weight || 0;
      groups.set(cellKey, group);
    });
    return [...groups.values()].map((group) => ({ items: group.items, x: group.x / group.items.length, y: group.y / group.items.length, weight: group.weight }));
  },
  // Matrix counts for samples inside the extent, palette order first, then other labels.
  legend(located, key) {
    const counts = new Map();
    located.forEach(({ row, coordinates }) => {
      if (!monitoringMap.inView(key, coordinates[0], coordinates[1])) return;
      const label = monitoringView.matrix(row) || monitoringMap.unknownLabel;
      counts.set(label, (counts.get(label) || 0) + 1);
    });
    const ordered = Object.keys(monitoringMap.palette).filter((label) => counts.has(label));
    const others = [...counts.keys()].filter((label) => !(label in monitoringMap.palette)).sort();
    return [...ordered, ...others].map((label) => [label, counts.get(label)]);
  }
});

export function mapScreen(view, container) {
  const svg = container.querySelector("svg.monitoring-map-svg");
  if (!svg) return null;
  const rect = svg.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const scale = Math.min(rect.width / view.width, rect.height / view.height);
  return { rect, scale, offsetX: (rect.width - view.width * scale) / 2, offsetY: (rect.height - view.height * scale) / 2 };
}
export function clientToMapView(clientX, clientY, view, container) {
  const screen = mapScreen(view, container);
  if (!screen) return null;
  return { x: view.x + (clientX - screen.rect.left - screen.offsetX) / screen.scale, y: view.y + (clientY - screen.rect.top - screen.offsetY) / screen.scale };
}
// Pointer, wheel and keyboard behaviour shared by the Monitoring and Institutions maps.
// hooks: getView(), setView(view), select(clusterIndex).
export function attachMapInteractions(container, hooks) {
  let gesture = null;
  let suppressClick = false;
  const zoomBy = (factor) => hooks.setView(monitoringMap.zoomView(hooks.getView(), factor));
  const panBy = (dx, dy) => hooks.setView(monitoringMap.panView(hooks.getView(), dx, dy));
  container.addEventListener("pointerdown", (event) => {
    suppressClick = false;
    if (event.button !== 0) return;
    gesture = { id: event.pointerId, x: event.clientX, y: event.clientY, dragging: false };
  });
  container.addEventListener("pointermove", (event) => {
    if (!gesture || event.pointerId !== gesture.id) return;
    const dx = event.clientX - gesture.x;
    const dy = event.clientY - gesture.y;
    if (!gesture.dragging) {
      // Below 4px the gesture is still a click, so markers keep working.
      if (Math.hypot(dx, dy) < 4) return;
      gesture.dragging = true;
      container.setPointerCapture(event.pointerId);
      container.classList.add("is-panning");
    }
    const view = hooks.getView();
    const screen = mapScreen(view, container);
    if (!screen) return;
    hooks.setView(monitoringMap.panView(view, -dx / screen.scale, -dy / screen.scale));
    gesture.x = event.clientX;
    gesture.y = event.clientY;
  });
  const endGesture = (event) => {
    if (!gesture || event.pointerId !== gesture.id) return;
    suppressClick = gesture.dragging;
    gesture = null;
    container.classList.remove("is-panning");
  };
  container.addEventListener("pointerup", endGesture);
  container.addEventListener("pointercancel", endGesture);
  container.addEventListener("click", (event) => {
    if (suppressClick) { suppressClick = false; return; }
    const marker = event.target.closest(".monitoring-marker");
    if (marker) hooks.select(Number(marker.dataset.clusterIndex));
  });
  container.addEventListener("wheel", (event) => {
    event.preventDefault();
    const view = hooks.getView();
    const anchor = clientToMapView(event.clientX, event.clientY, view, container);
    const delta = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaY;
    hooks.setView(monitoringMap.zoomView(view, Math.exp(-delta * 0.0015), anchor));
  }, { passive: false });
  container.addEventListener("keydown", (event) => {
    const marker = event.target.closest(".monitoring-marker");
    if (marker && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      hooks.select(Number(marker.dataset.clusterIndex));
      return;
    }
    if (event.target !== container) return;
    const step = hooks.getView().width * 0.15;
    const actions = { ArrowLeft: () => panBy(-step, 0), ArrowRight: () => panBy(step, 0), ArrowUp: () => panBy(0, -step), ArrowDown: () => panBy(0, step), "+": () => zoomBy(1.25), "=": () => zoomBy(1.25), "-": () => zoomBy(0.8), _: () => zoomBy(0.8) };
    const action = actions[event.key];
    if (!action) return;
    event.preventDefault();
    action();
  });
}

// CA basemap loader (ported from ensureCaBasemap). The first call starts the fetch; onSettled runs
// once it succeeds or fails, so the caller can redraw. Later calls are no-ops, as in the classic site.
let caBasemap = null;
let caBasemapStatus = "idle";
export function caBasemapFeatures() {
  return caBasemap;
}
export function caBasemapState() {
  return caBasemapStatus;
}
export function ensureCaBasemap(onSettled = () => {}) {
  if (caBasemapStatus !== "idle") return;
  caBasemapStatus = "loading";
  fetch(classicUrl("assets/ca_boundaries.geojson"))
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((geojson) => {
      const features = {};
      (geojson.features || []).forEach((feature) => {
        const boundary = feature.properties && feature.properties.boundary;
        if (boundary === "land" || boundary === "state_waters") features[boundary] = monitoringMap.pathData(feature.geometry);
      });
      if (!features.land || !features.state_waters) throw new Error("basemap lacks land or state_waters");
      caBasemap = features;
      caBasemapStatus = "ready";
    })
    .catch(() => { caBasemapStatus = "failed"; })
    .then(() => onSettled());
}
