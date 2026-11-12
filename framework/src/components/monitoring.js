// Monitoring page logic (AT-5c). Lift-and-shift of the classic Monitoring tab in site/index.html
// (filteredMonitoringSamples, drawMonitoringMap, renderMonitoringMapDetails, facet state, renderMonitoring
// and the event bindings). Markup lives in src/monitoring.md; pure helpers in monitoring_view.js and
// shared map code in svg_map.js. Nothing touches the DOM until mountMonitoring() runs.
import {loadJson, escapeHtml} from "./atlas.js";
import {monitoringView} from "./monitoring_view.js";
import {monitoringMap, attachMapInteractions, ensureCaBasemap, caBasemapFeatures, caBasemapState} from "./svg_map.js";

const $ = (id) => document.getElementById(id);
const MONITORING_PAGE_SIZE = 50;
const FACET_IDS = ["facet-filters", "facet-sources", "facet-map", "facet-gaps", "facet-samples"];
// The classic page stores facet state in sessionStorage (not localStorage); the key is kept as-is.
const FACET_STORAGE_KEY = "monitoring-facets";
// Evidence labels from the classic work-dataset helpers (linked-works line in the source table).
const EVIDENCE_LABELS = {"DataCite-relation": "DataCite relation", "DAS-match": "Data availability statement"};

// Page state (classic: state.monitoringFilters, state.monitoringPage and the monitoringMap* variables).
const state = {
  data: null, // monitoring.json payload
  filters: {tier: "", search: "", contributor: "", matrix: "", year: "", region: ""},
  page: 0,
  samples: [], // samples passing the filters
  extent: "statewide",
  view: null, // null means the extent's own view; otherwise the user's zoom and pan
  hidden: new Set(), // matrix labels hidden with the legend toggles
  selection: null, // { rows } for the selected marker
  rendered: [], // clusters from the last draw; markers index into this
  frame: 0
};

function evidenceLabel(type) {
  return EVIDENCE_LABELS[type] || "Unrecognized evidence";
}

function linkedWorksHtml(row) {
  const linked = Array.isArray(row?.linked_works) ? row.linked_works : [];
  if (!linked.length) return "";
  const works = new Set(linked.map((item) => item.work_id)).size;
  const types = [...new Set(linked.map((item) => evidenceLabel(item.evidence_type)))].sort();
  return `<br><small>Linked works: ${works} (${escapeHtml(types.join(", "))})</small>`;
}

function filteredSamples() {
  const payload = state.data;
  const f = state.filters;
  const eligible = new Set((payload.datasets || []).filter((row) => {
    if (f.tier && row.access_tier !== f.tier) return false;
    const text = `${row.name} ${row.steward}`.toLowerCase();
    if (f.search && !text.includes(f.search.toLowerCase())) return false;
    if (f.contributor && String(row.contributor_in_ca) !== f.contributor) return false;
    return true;
  }).map((row) => row.id));
  return monitoringView.filterSamples(payload.samples || [], eligible, f);
}

function currentMapView() {
  return state.view || monitoringMap.viewBox(state.extent);
}

function scheduleMapDraw() {
  if (state.frame) return;
  state.frame = window.requestAnimationFrame(() => { state.frame = 0; drawMonitoringMap(); });
}

function drawMonitoringMap() {
  ensureCaBasemap(() => drawMonitoringMap());
  const key = state.extent;
  const extent = monitoringMap.extents[key];
  const samples = state.samples;
  const located = monitoringView.locatedSamples(samples);
  const container = $("monitoring-map");
  document.querySelectorAll("[data-map-extent]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.mapExtent === key)));
  if (!located.length) {
    container.innerHTML = '<p class="empty">No valid sample coordinates are available for this filter.</p>';
    $("monitoring-map-legend").innerHTML = "";
    $("monitoring-map-note").textContent = `${samples.length} observations match; 0 have valid coordinate pairs.`;
    $("facet-map-count").textContent = "0 samples in extent";
    state.rendered = [];
    return;
  }
  const view = currentMapView();
  // The legend counts follow the filters only; hiding a matrix does not change them.
  const legend = monitoringMap.legend(located, key);
  const inExtent = legend.reduce((total, [, count]) => total + count, 0);
  const clusters = monitoringMap.clusters(monitoringMap.visibleSamples(located, state.hidden), key, view);
  state.rendered = clusters;
  const position = new Map(samples.map((row, index) => [row, index]));
  const selected = new Set(state.selection ? state.selection.rows : []);
  const focused = document.activeElement && container.contains(document.activeElement) ? document.activeElement.getAttribute("data-cluster-key") : null;
  // Marker radius and font scale with the view width, so they keep the same on-screen size.
  const radius = view.width * 0.026;
  const fontSize = view.width * 0.024;
  const markers = clusters.map((cluster, index) => {
    const clustered = cluster.rows.length > 1;
    const [first] = cluster.rows;
    const label = clustered
      ? `${cluster.rows.length} samples; ${cluster.mixed ? "mixed matrices: " : "matrix: "}${[...cluster.matrices].map(([name, count]) => `${name} ${count}`).join(", ")}`
      : `${monitoringView.matrix(first) || monitoringMap.unknownLabel}; ${monitoringView.year(first) ? first.date : "Unknown date"}; ${first.method || "method unknown"}`;
    const isSelected = cluster.rows.some((row) => selected.has(row));
    const clusterKey = String(Math.min(...cluster.rows.map((row) => position.get(row))));
    // Mixed clusters: a ring split by matrix share, so colour still shows the matrices.
    let ring = "";
    if (cluster.mixed) {
      const ringR = radius * 1.18;
      const circumference = 2 * Math.PI * ringR;
      let offset = 0;
      ring = [...cluster.matrices].map(([name, count]) => {
        const length = (count / cluster.rows.length) * circumference;
        const arc = `<circle cx="${cluster.x}" cy="${cluster.y}" r="${ringR}" style="fill:none;stroke:${monitoringMap.colorFor(name)};stroke-width:${radius * 0.42};vector-effect:none" stroke-dasharray="${length} ${circumference - length}" stroke-dashoffset="${-offset}" transform="rotate(-90 ${cluster.x} ${cluster.y})"/>`;
        offset += length;
        return arc;
      }).join("");
    }
    const halo = isSelected ? `<circle class="marker-halo" cx="${cluster.x}" cy="${cluster.y}" r="${radius * 1.5}"/>` : "";
    return `<g class="monitoring-marker${cluster.mixed ? " mixed" : ""}${isSelected ? " selected" : ""}" role="button" tabindex="0" aria-pressed="${isSelected}" aria-label="${escapeHtml(`${label}. Select for details.`)}" data-cluster-index="${index}" data-cluster-key="${clusterKey}"><title>${escapeHtml(label)}</title>${ring}<circle class="marker-body" cx="${cluster.x}" cy="${cluster.y}" r="${radius}" fill="${cluster.color}"/>${halo}<text x="${cluster.x}" y="${cluster.y}" font-size="${fontSize}" text-anchor="middle" dominant-baseline="central">${cluster.rows.length}</text></g>`;
  }).join("");
  const basemapFeatures = caBasemapFeatures();
  const basemap = basemapFeatures
    ? `<path class="map-state-waters" fill-rule="evenodd" d="${basemapFeatures.state_waters}"/><path class="map-land" fill-rule="evenodd" d="${basemapFeatures.land}"/>`
    : "";
  container.innerHTML = `<svg class="monitoring-map-svg" viewBox="${view.x} ${view.y} ${view.width} ${view.height}" preserveAspectRatio="xMidYMid meet" role="group" aria-label="${escapeHtml(`${extent.label} sample map: ${inExtent} samples, ${clusters.length} markers`)}"><rect class="map-sea" x="${view.x}" y="${view.y}" width="${view.width}" height="${view.height}"/>${basemap}${monitoringMap.placeLabels(view, clusters.map((cluster) => ({ x: cluster.x, y: cluster.y, r: radius })))}<g class="monitoring-markers">${markers}</g></svg>`;
  if (focused !== null) {
    const marker = container.querySelector(`[data-cluster-key="${focused}"]`);
    (marker || container).focus({ preventScroll: true });
  }
  $("monitoring-map-legend").innerHTML = legend.length
    ? `<ul>${legend.map(([label, count]) => { const shown = !state.hidden.has(label); return `<li><button type="button" class="monitoring-legend-toggle" data-matrix="${escapeHtml(label)}" aria-pressed="${shown}"><span class="monitoring-swatch" style="background:${monitoringMap.colorFor(label)}"></span>${escapeHtml(label)} (${count})</button></li>`; }).join("")}${clusters.some((cluster) => cluster.mixed) ? '<li><span class="monitoring-swatch mixed"></span>Mixed-matrix cluster: ring segments show each matrix\'s share</li>' : ""}</ul>`
    : "";
  const basemapNote = caBasemapState() === "failed" ? "Basemap unavailable; markers only." : basemapFeatures ? "" : "Basemap loading.";
  const hiddenCount = state.hidden.size;
  $("facet-map-count").textContent = `${inExtent} sample${inExtent === 1 ? "" : "s"} in extent`;
  $("monitoring-map-note").textContent = `${samples.length} observations match; ${located.length} have valid coordinate pairs; ${inExtent} fall inside the ${extent.label} extent. Zoom ${monitoringMap.zoomScale(view).toFixed(1)}x${hiddenCount ? `; ${hiddenCount} matrix${hiddenCount === 1 ? "" : "es"} hidden from the map` : ""}. Dots are coloured by matrix, and nearby samples are grouped into numbered clusters that split as you zoom in. The basemap is a simplified outline of California land and state waters. ${basemapNote}`.trim();
}

function renderMapDetails() {
  const panel = $("monitoring-map-details");
  const rows = state.selection ? state.selection.rows : [];
  if (!rows.length) {
    panel.innerHTML = "";
    return;
  }
  const payload = state.data;
  const shown = rows.slice(0, 25);
  panel.innerHTML = `<div class="map-details-card"><div class="map-details-head"><h4>${rows.length} sample${rows.length === 1 ? "" : "s"} selected</h4><div class="map-details-actions"><button type="button" data-map-fit>Zoom to these</button><button type="button" data-map-close>Close</button></div></div><div class="monitoring-table-wrap"><table class="monitoring-table"><thead><tr><th>Date</th><th>Matrix</th><th>Region</th><th>Method</th><th>Particle count</th><th>Concentration</th><th>Citation</th></tr></thead><tbody>${shown.map((row) => { const source = (payload.datasets || []).find((dataset) => dataset.id === row.dataset_id); return `<tr><td>${escapeHtml(monitoringView.year(row) ? row.date : "Unknown date")}</td><td>${escapeHtml(monitoringView.matrix(row) || "Unknown matrix")}</td><td>${escapeHtml(monitoringView.region(row).replaceAll("_", " "))}</td><td>${escapeHtml(row.method || "unknown")}</td><td>${escapeHtml(monitoringView.displayValue(row.particle_count, "unknown"))}</td><td>${escapeHtml(monitoringView.displayValue(row.concentration_value, "not available"))} ${escapeHtml(row.concentration_unit || "")}</td><td>${escapeHtml(row.citation || source?.citation || "Citation unavailable")}</td></tr>`; }).join("")}</tbody></table></div>${rows.length > 25 ? `<p class="data-note">+${rows.length - 25} more</p>` : ""}</div>`;
}

function selectCluster(index) {
  const cluster = state.rendered[index];
  if (!cluster) return;
  state.selection = { rows: cluster.rows.slice() };
  renderMapDetails();
  drawMonitoringMap();
}

function fitMapToSelection() {
  const rows = state.selection ? state.selection.rows : [];
  const points = rows.map((row) => monitoringView.coordinates(row)).filter(Boolean).map(([lat, lon]) => monitoringMap.project(lon, lat));
  const fitted = monitoringMap.fitView(points, currentMapView());
  if (!fitted) return;
  state.view = fitted;
  drawMonitoringMap();
}

function readFacetState() {
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(FACET_STORAGE_KEY) || "{}");
    return saved && typeof saved === "object" ? saved : {};
  } catch (error) {
    return {};
  }
}

function saveFacetState() {
  const snapshot = {};
  FACET_IDS.forEach((id) => { snapshot[id] = $(id).open; });
  try {
    window.sessionStorage.setItem(FACET_STORAGE_KEY, JSON.stringify(snapshot));
  } catch (error) {
    // Storage can be blocked; the sections then keep their default state.
  }
}

function restoreFacetState() {
  const saved = readFacetState();
  FACET_IDS.forEach((id) => { if (typeof saved[id] === "boolean") $(id).open = saved[id]; });
}

function setAllFacets(open) {
  FACET_IDS.forEach((id) => { $(id).open = open; });
  saveFacetState();
}

function render() {
  const payload = state.data;
  const localPreview = payload.publication_mode === "private_preview";
  const f = state.filters;
  $("monitoring-tier").value = f.tier;
  $("monitoring-search").value = f.search;
  $("monitoring-contributor").value = f.contributor;
  const datasets = (payload.datasets || []).filter((row) => (!f.tier || row.access_tier === f.tier) && (!f.search || `${row.name} ${row.steward}`.toLowerCase().includes(f.search.toLowerCase())) && (!f.contributor || String(row.contributor_in_ca) === f.contributor));
  const filterOptions = monitoringView.filterOptions(payload.samples || []);
  const { matrices, years, hasUnknownMatrix, hasUnknownYear } = filterOptions;
  $("monitoring-matrix").innerHTML = '<option value="">All matrices</option>' + matrices.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("") + (hasUnknownMatrix ? `<option value="${monitoringView.unknownMatrix}">Unknown matrix</option>` : "");
  $("monitoring-year").innerHTML = '<option value="">All years</option>' + years.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("") + (hasUnknownYear ? `<option value="${monitoringView.unknownYear}">Unknown date</option>` : "");
  $("monitoring-matrix").value = f.matrix;
  $("monitoring-year").value = f.year;
  $("monitoring-region").value = f.region;
  $("monitoring-status").textContent = localPreview
    ? `Private local preview · ${payload.sample_count} observations · rights remain unresolved; this payload must not be published.`
    : `Public catalogue · ${(payload.datasets || []).filter((row) => row.seed_eligible).length} verified seed entries and ${(payload.datasets || []).filter((row) => !row.seed_eligible).length} discovery records · ${payload.sample_count} cleared sample observations.`;
  const publishedSources = (payload.datasets || []).filter((row) => row.measurement_status === "published_rights_cleared");
  $("monitoring-quality-note").textContent = localPreview
    ? "Local QC rows are shown only for private review. Coordinate points and values describe this single source sample; they do not establish statewide monitoring coverage or comparable concentrations."
    : payload.publication_mode === "public_cleared"
      ? `Observations come only from rights-cleared sources: ${publishedSources.map((row) => `${row.name} (${row.publication_license ? row.publication_license.id : "licence recorded"})`).join("; ")}. They describe those projects' samples, not statewide monitoring coverage, and concentrations from different methods are not directly comparable. Blank cells are not evidence of a data gap. Cite: ${publishedSources.map((row) => row.citation).join("; ")}.`
      : "Registry entries describe sources and programs, not confirmed sample coverage. No cleared monitoring observations are available for this public snapshot, so absence here is not evidence of a data gap.";
  $("monitoring-source-count").textContent = `${datasets.length} source record${datasets.length === 1 ? "" : "s"} shown · contributor location is unknown unless explicitly recorded`;
  const activeFilters = Object.values(f).filter(Boolean).length;
  $("facet-filters-count").textContent = activeFilters ? `${activeFilters} filter${activeFilters === 1 ? "" : "s"} active` : "No filters set";
  $("facet-sources-count").textContent = `${datasets.length} source${datasets.length === 1 ? "" : "s"}`;
  $("monitoring-sources").innerHTML = datasets.length ? `<table class="monitoring-table"><thead><tr><th>Source</th><th>Steward / tier</th><th>Matrix and region</th><th>Format / cadence</th><th>License</th><th>Checked</th><th>Citations</th></tr></thead><tbody>${datasets.map((row) => `<tr><th scope="row">${escapeHtml(row.name)}<br><small>${row.seed_eligible ? "Verified registry seed" : "Discovery record; not in seed count"} · ${escapeHtml(row.entity_type)} · ${escapeHtml(row.status)}</small>${linkedWorksHtml(row)}</th><td>${escapeHtml(row.steward)}<br>Tier ${escapeHtml(row.access_tier)} · contributor in CA: ${row.contributor_in_ca === true ? "yes" : row.contributor_in_ca === false ? "no" : "unknown"}</td><td>${escapeHtml((row.sample_matrix || []).join(", "))}<br>${escapeHtml(row.region)}</td><td>${escapeHtml((row.format || []).join(", "))}<br>${escapeHtml(row.cadence)}</td><td>${escapeHtml(row.license)}</td><td>${escapeHtml(row.last_checked || "unknown")}</td><td><a href="${escapeHtml(row.url)}" target="_blank" rel="noreferrer">Source</a> · <a href="${escapeHtml(row.provenance_url)}" target="_blank" rel="noreferrer">Evidence</a><br>${escapeHtml(row.citation)}</td></tr>`).join("")}</tbody></table>` : '<p class="empty">No source records match these filters.</p>';
  const samples = filteredSamples();
  state.samples = samples;
  if (state.selection) {
    const available = new Set(samples);
    const rows = state.selection.rows.filter((row) => available.has(row));
    state.selection = rows.length ? { rows } : null;
    renderMapDetails();
  }
  drawMonitoringMap();
  $("monitoring-gaps-note").textContent = samples.length
    ? `Observed sample counts in the ${localPreview ? "private local preview" : "public data"} only. Blank cells do not imply absence of monitoring.`
    : "No sample rows are available for a measurement-based gap assessment. Registry topic/region descriptions are not counted as observations.";
  const counts = new Map();
  samples.forEach((row) => { const year = monitoringView.year(row) || "Unknown date"; const matrix = monitoringView.matrix(row) || "Unknown matrix"; const key = `${matrix}\u0000${monitoringView.region(row)}\u0000${year}`; counts.set(key, (counts.get(key) || 0) + 1); });
  const keys = [...counts.keys()].sort();
  $("facet-gaps-count").textContent = `${keys.length} coverage cell${keys.length === 1 ? "" : "s"}`;
  $("monitoring-gaps").innerHTML = keys.length ? `<table class="gaps-table"><thead><tr><th>Matrix</th><th>Region</th><th>Year</th><th>Samples</th></tr></thead><tbody>${keys.map((key) => { const [matrix, region, year] = key.split("\u0000"); return `<tr><th scope="row">${escapeHtml(matrix)}</th><td>${escapeHtml(region.replaceAll("_", " "))}</td><td>${escapeHtml(year)}</td><td class="gaps-cell">${counts.get(key)}</td></tr>`; }).join("")}</tbody></table>` : '<p class="empty">No sample-derived coverage cells are available.</p>';
  const monitoringPages = Math.max(1, Math.ceil(samples.length / MONITORING_PAGE_SIZE));
  state.page = Math.min(Math.max(state.page, 0), monitoringPages - 1);
  const monitoringPageStart = state.page * MONITORING_PAGE_SIZE;
  $("facet-samples-count").textContent = `${samples.length} row${samples.length === 1 ? "" : "s"}`;
  $("monitoring-samples").innerHTML = samples.length ? `<table class="monitoring-table"><thead><tr><th>Date</th><th>Matrix / region</th><th>Method</th><th>Count / concentration</th><th>Citation</th></tr></thead><tbody>${samples.slice(monitoringPageStart, monitoringPageStart + MONITORING_PAGE_SIZE).map((row) => { const source = payload.datasets.find((dataset) => dataset.id === row.dataset_id); const dateLabel = monitoringView.year(row) ? row.date : "Unknown date"; const matrixLabel = monitoringView.matrix(row) || "Unknown matrix"; return `<tr><td>${escapeHtml(dateLabel)}</td><td>${escapeHtml(matrixLabel)} / ${escapeHtml(monitoringView.region(row).replaceAll("_", " "))}</td><td>${escapeHtml(row.method || "unknown")}</td><td>${escapeHtml(monitoringView.displayValue(row.particle_count, "unknown"))} particles · ${escapeHtml(monitoringView.displayValue(row.concentration_value, "not available"))} ${escapeHtml(row.concentration_unit || "")}${row.deposition_rate_value === null || row.deposition_rate_value === undefined ? "" : ` · deposition ${escapeHtml(String(row.deposition_rate_value))} ${escapeHtml(row.deposition_rate_unit || "")}`}</td><td>${escapeHtml(row.citation || source?.citation || "Citation unavailable")}${source ? ` · <a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">source</a>` : ""}</td></tr>`; }).join("")}</tbody></table>${samples.length > MONITORING_PAGE_SIZE ? `<p class="data-note monitoring-pager">Rows ${monitoringPageStart + 1}–${Math.min(monitoringPageStart + MONITORING_PAGE_SIZE, samples.length)} of ${samples.length} <button type="button" data-monitoring-page="-1" ${monitoringPageStart === 0 ? "disabled" : ""}>◀ Previous</button> <button type="button" data-monitoring-page="1" ${monitoringPageStart + MONITORING_PAGE_SIZE >= samples.length ? "disabled" : ""}>Next ▶</button></p>` : ""}` : '<p class="empty">No sample observations are available in this snapshot.</p>';
}

// Filter controls: any change resets the sample page to the first one (classic input/change handlers).
function onFilterInput() {
  const f = state.filters;
  f.tier = $("monitoring-tier").value;
  f.search = $("monitoring-search").value.trim();
  f.contributor = $("monitoring-contributor").value;
  f.matrix = $("monitoring-matrix").value;
  f.year = $("monitoring-year").value;
  f.region = $("monitoring-region").value;
  state.page = 0;
  render();
}

function bindEvents() {
  ["monitoring-tier", "monitoring-search", "monitoring-contributor", "monitoring-matrix", "monitoring-year", "monitoring-region"].forEach((id) => {
    $(id).addEventListener("input", onFilterInput);
    $(id).addEventListener("change", onFilterInput);
  });
  document.querySelectorAll("[data-map-extent]").forEach((button) => button.addEventListener("click", () => { state.extent = button.dataset.mapExtent; state.view = null; scheduleMapDraw(); }));
  const zoomMapBy = (factor) => { state.view = monitoringMap.zoomView(currentMapView(), factor); scheduleMapDraw(); };
  $("monitoring-zoom-in").addEventListener("click", () => zoomMapBy(1.5));
  $("monitoring-zoom-out").addEventListener("click", () => zoomMapBy(1 / 1.5));
  $("monitoring-zoom-reset").addEventListener("click", () => { state.view = null; scheduleMapDraw(); });
  const mapContainer = $("monitoring-map");
  attachMapInteractions(mapContainer, { getView: currentMapView, setView: (view) => { state.view = view; scheduleMapDraw(); }, select: selectCluster });
  // Keyboard arrows pan the map when it is focused; attachMapInteractions handles those keys.
  $("monitoring-map-legend").addEventListener("click", (event) => {
    const button = event.target.closest("[data-matrix]");
    if (!button) return;
    const label = button.dataset.matrix;
    if (state.hidden.has(label)) state.hidden.delete(label); else state.hidden.add(label);
    drawMonitoringMap();
    const again = [...$("monitoring-map-legend").querySelectorAll("[data-matrix]")].find((item) => item.dataset.matrix === label);
    if (again) again.focus();
  });
  $("monitoring-map-details").addEventListener("click", (event) => {
    if (event.target.closest("[data-map-fit]")) fitMapToSelection();
    if (event.target.closest("[data-map-close]")) {
      state.selection = null;
      renderMapDetails();
      drawMonitoringMap();
      mapContainer.focus({ preventScroll: true });
    }
  });
  FACET_IDS.forEach((id) => $(id).addEventListener("toggle", () => { saveFacetState(); if (id === "facet-map" && $(id).open) scheduleMapDraw(); }));
  $("monitoring-facets-expand").addEventListener("click", () => setAllFacets(true));
  $("monitoring-facets-collapse").addEventListener("click", () => setAllFacets(false));
  $("monitoring-samples").addEventListener("click", (event) => {
    const button = event.target.closest("[data-monitoring-page]");
    if (!button) return;
    state.page += Number(button.dataset.monitoringPage);
    render();
    $("monitoring-samples-heading").scrollIntoView({ block: "start" });
  });
}

// Entry point for src/monitoring.md. Loads monitoring.json, then renders and binds the page.
export async function mountMonitoring() {
  try {
    const payload = await loadJson("monitoring.json");
    if (!payload || payload.schema_version !== "s7.5") throw new Error("monitoring.json does not match the S7.5 contract");
    state.data = payload;
    restoreFacetState();
    bindEvents();
    render();
  } catch (error) {
    $("monitoring-status").textContent = "Monitoring data unavailable.";
    $("monitoring-sources").innerHTML = `<p class="empty">${escapeHtml(error.message)}<br>Run the site through a web server and rebuild the S7.5 data export.</p>`;
  }
}
