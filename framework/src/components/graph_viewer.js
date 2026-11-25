// Global graph viewer (BQ-V.3): one reusable component for the institution and author graphs
// (site/data/global/graphs/, docs/NETWORK_BUILD.md §16 and §16b). mountGraph(root, {graph, phone})
// draws a precomputed layout with sigma.js (WebGL) and offers the same information as a DOM details
// panel and a sortable table. The canvas is aria-hidden; the table and details carry the content.
// Pure helpers live in graph_viewer_model.js. Teardown runs when root leaves the document.
import Graph from "npm:graphology@0.26.0";
import Sigma from "npm:sigma@3.0.3";
import {formatCount, globalDataUrl} from "./atlas.js";
import {CHROME} from "./shared/palette.js";
import {
  buildAdjacency,
  colourGroups,
  colourOf,
  edgesFromRows,
  formatGraphHash,
  formatWorks,
  graphFileKey,
  graphName,
  labelIndices,
  LABEL_COUNT,
  maxWorks,
  matchNodes,
  decodeLayout,
  nodeSize,
  nodesFromRows,
  noteText,
  openAlexUrl,
  parseGraphHash,
  sortNodes,
  SEARCH_LIMIT,
  TABLE_LIMIT,
  topNeighbours,
  usePhone,
  ZOOM_TO_NODE
} from "./graph_viewer_model.js";

const HOME_VIEW = Object.freeze({x: 0.5, y: 0.5, ratio: 1, angle: 0});
const WHEEL_HINT = "Hold Ctrl (or Cmd) and scroll to zoom, or click the graph first.";
const TOUCH_HINT = "Use two fingers to move the graph. One finger scrolls the page.";
const GRAPH_TITLES = {institutions: "Institutions", authors: "Authors"};
const SORTABLE = {name: "Name", country: "Country or type", works: "Works", community: "Community"};

const reduceMotion = () => Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);

// Small DOM helper: text is always set with textContent, so names from the data are never parsed as HTML.
function el(tag, attrs = {}, text = null) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  if (text !== null && text !== undefined) node.textContent = text;
  return node;
}

function shell(name, phone) {
  const id = `gv-${name}-${phone ? "phone" : "desktop"}`;
  const colourOptions = name === "authors"
    ? '<option value="community">Collaboration community</option><option value="country">Primary country</option>'
    : '<option value="community">Collaboration community</option>';
  return `
<div class="gv-head">
  <p class="gv-note"><span class="gv-badge">Unscreened search hits</span> <span data-gv="note"></span></p>
</div>
<div class="gv-toolbar">
  <div class="gv-search">
    <label class="gv-label" for="${id}-search">Find a name</label>
    <input class="gv-input" id="${id}-search" data-gv="search" type="search" autocomplete="off" spellcheck="false" aria-controls="${id}-results" aria-describedby="${id}-search-status">
    <ul class="gv-results" id="${id}-results" data-gv="results" hidden></ul>
    <p class="gv-sr" id="${id}-search-status" role="status" aria-live="polite" data-gv="search-status"></p>
  </div>
  <div class="gv-controls">
    <label class="gv-label" for="${id}-colour">Colour by</label>
    <select class="gv-select" id="${id}-colour" data-gv="colour">${colourOptions}</select>
    <button class="gv-button" type="button" data-gv="zoom-in">Zoom in</button>
    <button class="gv-button" type="button" data-gv="zoom-out">Zoom out</button>
    <button class="gv-button" type="button" data-gv="reset">Reset view</button>
    <button class="gv-button" type="button" data-gv="table-toggle" aria-expanded="false" aria-controls="${id}-table">Show as table</button>
  </div>
</div>
<p class="gv-status" role="status" aria-live="polite" data-gv="status">Loading the graph.</p>
<div class="gv-main">
  <div class="gv-figure">
    <div class="gv-stage" data-gv="stage" aria-hidden="true"></div>
    <p class="gv-hint" data-gv="hint" aria-hidden="true" hidden></p>
    <div class="gv-legend" data-gv="legend"></div>
  </div>
  <aside class="gv-details" aria-labelledby="${id}-details-title" data-gv="details">
    <h2 class="gv-details__title" id="${id}-details-title">Selected</h2>
    <p data-gv="details-body">Select a dot on the graph, search for a name, or pick a row in the table.</p>
  </aside>
</div>
<section class="gv-table-wrap" id="${id}-table" data-gv="table" hidden aria-labelledby="${id}-table-title">
  <h2 class="gv-table-title" id="${id}-table-title">Table of nodes</h2>
  <div class="gv-table-tools">
    <label class="gv-label" for="${id}-filter">Filter the table</label>
    <input class="gv-input" id="${id}-filter" data-gv="filter" type="search" autocomplete="off">
    <p class="gv-table-count" data-gv="table-count" role="status" aria-live="polite"></p>
  </div>
  <div class="gv-table-scroll">
    <table class="gv-table">
      <thead><tr data-gv="sort-row"></tr></thead>
      <tbody data-gv="rows"></tbody>
    </table>
  </div>
</section>`;
}

export function mountGraph(root, options = {}) {
  if (!root) throw new Error("mountGraph needs an element to mount into");
  const name = graphName(options.graph, "institutions");
  const phone = usePhone(options.phone ?? "auto", window.innerWidth);
  const motionOff = reduceMotion();
  const abort = new AbortController();
  const {signal} = abort;

  root.classList.add("gv");
  root.dataset.graph = name;
  root.dataset.phone = String(phone);
  root.dataset.state = "loading";
  root.innerHTML = shell(name, phone);
  const q = (key) => root.querySelector(`[data-gv="${key}"]`);
  const ui = {
    note: q("note"), search: q("search"), results: q("results"), searchStatus: q("search-status"),
    colour: q("colour"), zoomIn: q("zoom-in"), zoomOut: q("zoom-out"), reset: q("reset"),
    tableToggle: q("table-toggle"), status: q("status"), stage: q("stage"), hint: q("hint"),
    legend: q("legend"), details: q("details"), detailsBody: q("details-body"), table: q("table"),
    filter: q("filter"), tableCount: q("table-count"), sortRow: q("sort-row"), rows: q("rows")
  };
  const initial = parseGraphHash(window.location.hash);
  // The hash belongs to a viewer whose graph matches it (or to a page with no graph named).
  const ownsHash = !initial.graph || initial.graph === name;

  let graph = null;
  let renderer = null;
  let camera = null;
  let nodes = [];
  let byId = new Map();
  let adjacency = [];
  let colourMode = "community";
  let colours = null;
  let labelSet = new Set();
  let selectedId = null;
  let neighbourIds = new Set();
  let sortKey = "works";
  let sortDir = "desc";
  let tableShown = false;
  let engaged = false;
  let hintTimer = 0;
  let hashFrame = 0;
  let disposed = false;
  let observer = null;
  let manifestNote = "";

  const setStatus = (text) => { ui.status.textContent = text; };

  function flash(text) {
    ui.hint.textContent = text;
    ui.hint.hidden = false;
    clearTimeout(hintTimer);
    hintTimer = window.setTimeout(() => { ui.hint.hidden = true; }, 2200);
  }

  // Teardown: sigma releases its WebGL context and listeners; our listeners go through the signal.
  function teardown() {
    if (disposed) return;
    disposed = true;
    abort.abort();
    observer?.disconnect();
    cancelAnimationFrame(hashFrame);
    clearTimeout(hintTimer);
    renderer?.kill();
    renderer = null;
    camera = null;
    root.dataset.state = "closed";
  }

  observer = new MutationObserver(() => { if (!root.isConnected) teardown(); });
  observer.observe(document.documentElement, {childList: true, subtree: true});

  // Camera moves: instant under reduced motion, a short animation otherwise.
  function moveCamera(target, duration = 350) {
    if (!camera) return;
    if (motionOff) camera.setState(target);
    else camera.animate(target, {duration});
  }

  function zoomBy(factor) {
    if (!camera) return;
    const state = camera.getState();
    moveCamera({...state, ratio: state.ratio / factor}, 250);
  }

  function writeHash() {
    if (disposed || !camera || !ownsHash) return;
    const state = camera.getState();
    const hash = formatGraphHash({graph: name, node: selectedId, zoom: state.ratio, x: state.x, y: state.y});
    const target = `${window.location.pathname}${window.location.search}${hash}`;
    if (`${window.location.pathname}${window.location.search}${window.location.hash}` === target) return;
    window.history.replaceState(window.history.state, "", target);
  }

  function scheduleHash() {
    if (hashFrame || disposed) return;
    hashFrame = requestAnimationFrame(() => { hashFrame = 0; writeHash(); });
  }

  // Wheel and touch: the page scrolls unless Ctrl or Cmd is held, or the graph was clicked first.
  // Two fingers always move the graph. Sigma listens on this same element, so a capture listener
  // here runs first and stops the event before sigma sees it.
  function gate(event) {
    if (event.ctrlKey || event.metaKey || engaged) return;
    if (event.type !== "wheel" && event.touches && event.touches.length > 1) return;
    event.stopImmediatePropagation();
    flash(event.type === "wheel" ? WHEEL_HINT : TOUCH_HINT);
  }

  function select(id, {pan = false, zoom = ZOOM_TO_NODE} = {}) {
    if (id !== null && !(graph && graph.hasNode(id))) return false;
    selectedId = id;
    neighbourIds = id === null ? new Set() : new Set(graph.neighbors(id));
    renderer?.refresh();
    renderDetails();
    renderTableRows();
    if (id !== null && pan && renderer) {
      const point = renderer.getNodeDisplayData(id);
      if (point) moveCamera({x: point.x, y: point.y, ratio: zoom, angle: camera.getState().angle});
    }
    scheduleHash();
    return true;
  }

  function nodeReducer(id, data) {
    if (selectedId === null) return data;
    if (id === selectedId) return {...data, highlighted: true, zIndex: 2};
    if (neighbourIds.has(id)) return {...data, zIndex: 1};
    return {...data, color: CHROME.sunken, label: null, zIndex: 0};
  }

  function edgeReducer(id, data) {
    if (selectedId === null) return data;
    const [a, b] = graph.extremities(id);
    if (a === selectedId || b === selectedId) return {...data, color: CHROME.axis};
    return {...data, color: CHROME.page};
  }

  function nodeColour(node) {
    if (colourMode === "country") return colourOf(colours.colours, node.country);
    return colourOf(colours.colours, node.community);
  }

  function applyColours() {
    const keys = nodes.map((node) => (colourMode === "country" ? node.country : node.community));
    colours = colourGroups(keys);
    for (const node of nodes) graph.setNodeAttribute(node.id, "color", nodeColour(node));
    renderLegend();
    renderer?.refresh();
  }

  function renderLegend() {
    const legend = ui.legend;
    legend.replaceChildren();
    const title = colourMode === "country" ? "Primary country" : "Collaboration community";
    const list = el("ul", {class: "gv-legend__list", "aria-label": `${title} colours`});
    for (const row of colours.legend) {
      const label = colourMode === "country" ? `Country ${row.key}` : `Community ${Number(row.key) + 1}`;
      const li = el("li", {class: "gv-legend__item"});
      const swatch = el("span", {class: "gv-swatch", "aria-hidden": "true"});
      swatch.style.background = row.colour;
      li.append(swatch, el("span", {}, `${label} (${formatCount(row.count)})`));
      list.append(li);
    }
    if (colours.otherCount > 0) {
      const li = el("li", {class: "gv-legend__item"});
      const swatch = el("span", {class: "gv-swatch", "aria-hidden": "true"});
      swatch.style.background = colours.otherColour;
      li.append(swatch, el("span", {}, `Other (${formatCount(colours.otherCount)})`));
      list.append(li);
    }
    const sizeTitle = el("p", {class: "gv-legend__title"}, "Dot size: works");
    const sizeKey = el("ul", {class: "gv-size-key", "aria-label": "Dot size key"});
    const top = maxWorks(nodes);
    for (const works of [1, Math.max(1, Math.round(top / 10)), top]) {
      const size = nodeSize(works, top);
      const li = el("li", {class: "gv-size-key__item"});
      const dot = el("span", {class: "gv-size-key__dot", "aria-hidden": "true"});
      dot.style.width = `${size * 2}px`;
      dot.style.height = `${size * 2}px`;
      li.append(dot, el("span", {}, formatWorks(works)));
      sizeKey.append(li);
    }
    legend.append(el("p", {class: "gv-legend__title"}, title), list, sizeTitle, sizeKey);
  }

  function detailRow(dl, term, value) {
    dl.append(el("dt", {}, term), el("dd", {}, value));
  }

  function renderDetails() {
    const body = ui.detailsBody;
    body.replaceChildren();
    const node = selectedId === null ? null : byId.get(selectedId);
    const heading = ui.details.querySelector(".gv-details__title");
    if (!node) {
      heading.textContent = "Selected";
      body.append(el("p", {}, "Select a dot on the graph, search for a name, or pick a row in the table."));
      return;
    }
    heading.textContent = node.name;
    const dl = el("dl", {class: "gv-facts"});
    detailRow(dl, "Works", formatWorks(node.works));
    if (name === "authors") {
      detailRow(dl, "Primary country", node.country ?? "Not recorded");
    } else {
      detailRow(dl, "Country", node.country ?? "Not recorded");
      detailRow(dl, "Type", node.type ?? "Not recorded");
    }
    detailRow(dl, "Community", node.community === null ? "Not assigned" : `Community ${Number(node.community) + 1}`);
    body.append(dl);

    const links = el("ul", {class: "gv-links"});
    const openalex = openAlexUrl(node.id);
    if (node.ror) links.append(linkItem("ROR record", node.ror));
    if (openalex) links.append(linkItem("OpenAlex record", openalex));
    if (links.children.length) body.append(links);

    const neighbours = topNeighbours(adjacency, node.index, 10);
    body.append(el("h3", {class: "gv-subhead"}, "Strongest links (shared works)"));
    if (!neighbours.length) {
      body.append(el("p", {}, "No links in this graph."));
      return;
    }
    const list = el("ul", {class: "gv-neighbours"});
    for (const {index, weight} of neighbours) {
      const other = nodes[index];
      const li = el("li");
      const button = el("button", {class: "gv-link", type: "button"}, other.name);
      button.addEventListener("click", () => select(other.id, {pan: true}), {signal});
      li.append(button, el("span", {class: "gv-muted"}, ` ${formatCount(weight)} shared`));
      list.append(li);
    }
    body.append(list);
  }

  function linkItem(label, href) {
    const li = el("li");
    const a = el("a", {href, target: "_blank", rel: "noopener noreferrer"}, label);
    li.append(a);
    return li;
  }

  function renderSortHeaders() {
    ui.sortRow.replaceChildren();
    for (const [key, label] of Object.entries(SORTABLE)) {
      const th = el("th", {scope: "col", "aria-sort": sortKey === key ? (sortDir === "asc" ? "ascending" : "descending") : "none"});
      const button = el("button", {class: "gv-sort", type: "button", "data-sort": key}, label);
      button.addEventListener("click", () => {
        if (sortKey === key) sortDir = sortDir === "asc" ? "desc" : "asc";
        else { sortKey = key; sortDir = key === "name" || key === "country" ? "asc" : "desc"; }
        renderSortHeaders();
        renderTableRows();
      }, {signal});
      th.append(button);
      ui.sortRow.append(th);
    }
  }

  function renderTableRows() {
    if (!tableShown || !nodes.length) return;
    const filtered = ui.filter.value.trim() ? matchNodes(nodes, ui.filter.value) : nodes;
    const ordered = sortNodes(filtered, sortKey, sortDir);
    const shown = ordered.slice(0, TABLE_LIMIT);
    ui.rows.replaceChildren();
    for (const node of shown) {
      const tr = el("tr", {class: node.id === selectedId ? "gv-row gv-row--selected" : "gv-row"});
      const nameCell = el("th", {scope: "row"});
      const button = el("button", {class: "gv-link", type: "button"}, node.name);
      button.addEventListener("click", () => select(node.id, {pan: true}), {signal});
      nameCell.append(button);
      const kind = name === "authors" ? (node.country ?? "No country") : [node.country, node.type].filter(Boolean).join(", ") || "Not recorded";
      tr.append(nameCell, el("td", {}, kind), el("td", {class: "gv-num"}, formatCount(node.works)),
        el("td", {}, node.community === null ? "Not assigned" : String(Number(node.community) + 1)));
      ui.rows.append(tr);
    }
    const total = filtered.length;
    ui.tableCount.textContent = total > shown.length
      ? `Showing the first ${formatCount(shown.length)} of ${formatCount(total)} matches. Use the filter to narrow the list.`
      : `${formatCount(total)} ${total === 1 ? "node" : "nodes"}.`;
  }

  function setTable(show) {
    tableShown = show;
    ui.table.hidden = !show;
    ui.stage.hidden = show;
    ui.tableToggle.setAttribute("aria-expanded", String(show));
    ui.tableToggle.textContent = show ? "Show the graph" : "Show as table";
    if (show) renderTableRows();
    else if (renderer) renderer.resize();
  }

  // Search: type-ahead over the node names; a chosen name is selected and brought to the centre.
  function renderResults() {
    const matches = matchNodes(nodes, ui.search.value, SEARCH_LIMIT);
    ui.results.replaceChildren();
    ui.results.hidden = matches.length === 0;
    for (const node of matches) {
      const li = el("li");
      const button = el("button", {class: "gv-result", type: "button", "data-id": node.id}, node.name);
      button.addEventListener("click", () => chooseFromSearch(node.id), {signal});
      li.append(button);
      ui.results.append(li);
    }
    ui.searchStatus.textContent = !ui.search.value.trim() ? ""
      : matches.length ? `${matches.length} matching ${matches.length === 1 ? "name" : "names"}` : "No matching names";
  }

  function chooseFromSearch(id) {
    ui.results.hidden = true;
    select(id, {pan: true});
    ui.search.focus({preventScroll: true});
  }

  function bindControls() {
    ui.search.addEventListener("input", renderResults, {signal});
    ui.search.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { ui.results.hidden = true; return; }
      if (event.key === "ArrowDown") {
        const first = ui.results.querySelector("button");
        if (first) { event.preventDefault(); first.focus(); }
        return;
      }
      if (event.key === "Enter") {
        const first = matchNodes(nodes, ui.search.value, 1)[0];
        if (first) { event.preventDefault(); chooseFromSearch(first.id); }
      }
    }, {signal});
    ui.results.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { ui.results.hidden = true; ui.search.focus(); }
    }, {signal});
    ui.colour.addEventListener("change", () => {
      colourMode = ui.colour.value === "country" ? "country" : "community";
      applyColours();
      renderTableRows();
    }, {signal});
    ui.zoomIn.addEventListener("click", () => zoomBy(1.5), {signal});
    ui.zoomOut.addEventListener("click", () => zoomBy(1 / 1.5), {signal});
    ui.reset.addEventListener("click", () => { select(null); moveCamera({...HOME_VIEW}, 300); }, {signal});
    ui.tableToggle.addEventListener("click", () => setTable(!tableShown), {signal});
    ui.filter.addEventListener("input", renderTableRows, {signal});
    document.addEventListener("pointerdown", (event) => {
      if (!root.contains(event.target)) {
        engaged = false;
        ui.results.hidden = true;
      }
    }, {signal, passive: true});
    ui.stage.addEventListener("pointerdown", (event) => { if (event.pointerType !== "touch") engaged = true; }, {signal, passive: true});
    ui.stage.addEventListener("wheel", gate, {capture: true, passive: true, signal});
    ui.stage.addEventListener("touchstart", gate, {capture: true, passive: true, signal});
    ui.stage.addEventListener("touchmove", gate, {capture: true, passive: true, signal});
    window.addEventListener("hashchange", () => {
      const next = parseGraphHash(window.location.hash);
      if (next.graph && next.graph !== name) return;
      const node = next.node ?? null;
      if (node !== selectedId) select(node, {pan: next.zoom === undefined && node !== null});
      if (camera && (next.zoom !== undefined || next.x !== undefined)) {
        moveCamera({x: next.x ?? HOME_VIEW.x, y: next.y ?? HOME_VIEW.y, ratio: next.zoom ?? HOME_VIEW.ratio, angle: 0}, 0);
      }
    }, {signal});
  }

  async function getJson(url) {
    const response = await fetch(url, {cache: "no-cache"});
    if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}`);
    return response.json();
  }

  async function getBuffer(url) {
    const response = await fetch(url, {cache: "no-cache"});
    if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}`);
    return response.arrayBuffer();
  }

  function buildGraph(json, layout) {
    nodes = nodesFromRows(json);
    const edges = edgesFromRows(json, nodes.length);
    adjacency = buildAdjacency(edges, nodes.length);
    const top = maxWorks(nodes);
    labelSet = labelIndices(nodes, phone ? LABEL_COUNT.phone : LABEL_COUNT.desktop);
    colours = colourGroups(nodes.map((node) => (colourMode === "country" ? node.country : node.community)));
    graph = new Graph({type: "undirected", multi: false, allowSelfLoops: false});
    byId = new Map();
    for (const node of nodes) {
      byId.set(node.id, node);
      graph.addNode(node.id, {
        x: layout[2 * node.index],
        y: layout[2 * node.index + 1],
        size: nodeSize(node.works, top),
        color: nodeColour(node),
        label: labelSet.has(node.index) ? node.name : undefined
      });
    }
    for (const {source, target} of edges) {
      const a = nodes[source].id;
      const b = nodes[target].id;
      if (!graph.hasEdge(a, b)) graph.addEdge(a, b, {size: 0.6, color: CHROME.grid});
    }
  }

  function createRenderer() {
    renderer = new Sigma(graph, ui.stage, {
      renderEdgeLabels: false,
      labelDensity: 0.07,
      labelGridCellSize: 70,
      labelRenderedSizeThreshold: 6,
      minCameraRatio: 0.02,
      maxCameraRatio: 5,
      defaultNodeColor: CHROME.axis,
      defaultEdgeColor: CHROME.grid,
      nodeReducer,
      edgeReducer
    });
    camera = renderer.getCamera();
    renderer.on("clickNode", ({node}) => select(node, {pan: false}));
    renderer.on("clickStage", () => select(null));
    camera.on("updated", scheduleHash);
  }

  async function start() {
    setStatus(`Loading ${GRAPH_TITLES[name].toLowerCase()} graph.`);
    const manifest = await getJson(globalDataUrl("graphs/graphs_manifest.json"));
    if (disposed) return;
    const entry = manifest.graphs?.[graphFileKey(name, phone)];
    if (!entry) throw new Error(`manifest has no entry for ${graphFileKey(name, phone)}`);
    manifestNote = noteText(name === "authors" ? manifest.author_graph?.what_this_is_and_is_not : manifest.what_this_is_and_is_not);
    ui.note.textContent = manifestNote;
    const [json, bytes] = await Promise.all([
      getJson(globalDataUrl(`graphs/${entry.file}`)),
      getBuffer(globalDataUrl(`graphs/${entry.layout_file}`))
    ]);
    if (disposed) return;
    const layout = decodeLayout(bytes, json.nodes.rows.length);
    buildGraph(json, layout);
    if (disposed) return;
    try {
      createRenderer();
    } catch {
      showFallback("The graphic could not start in this browser, so the table lists the same nodes.");
      return;
    }
    const at = parseGraphHash(window.location.hash);
    if (ownsHash && (at.zoom !== undefined || at.x !== undefined || at.y !== undefined)) {
      camera.setState({x: at.x ?? HOME_VIEW.x, y: at.y ?? HOME_VIEW.y, ratio: at.zoom ?? HOME_VIEW.ratio, angle: 0});
    }
    if (ownsHash && at.node !== undefined && graph.hasNode(at.node)) {
      select(at.node, {pan: at.zoom === undefined && at.x === undefined});
    }
    renderLegend();
    renderSortHeaders();
    root.dataset.state = "ready";
    root.dataset.readyMs = String(Math.round(performance.now()));
    setStatus(`${formatCount(nodes.length)} ${name === "authors" ? "authors" : "institutions"} and ${formatCount(graph.size)} links.`);
  }

  function showFallback(message) {
    root.dataset.state = "fallback";
    setStatus(message);
    renderSortHeaders();
    setTable(true);
  }

  bindControls();

  start().catch((error) => {
    if (disposed) return;
    root.dataset.state = "error";
    setStatus(`The graph could not be loaded. ${error.message}`);
    renderSortHeaders();
    console.error(error);
  });

  return {teardown, select, get state() { return root.dataset.state; }};
}
