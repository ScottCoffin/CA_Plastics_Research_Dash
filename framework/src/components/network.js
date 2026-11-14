// Collaboration network page. sigma.js (WebGL) draws a graphology graph; ForceAtlas2 re-runs the
// layout on request. Every filter change rebuilds the graph from the model and keeps each expert
// where it was. Without WebGL, or when sigma fails to start, the table view opens instead.
// Pure logic lives in network_model.js.
import Graph from "npm:graphology@0.26.0";
import Sigma from "npm:sigma@3.0.3";
import forceAtlas2 from "npm:graphology-layout-forceatlas2@0.10.1";
import "./shared/topics.js";
import {classicUrl, escapeHtml, formatCount, loadJson} from "./atlas.js";
import {
  colourGroups,
  emptyNetworkState,
  formatNetworkHash,
  graphAttributes,
  groupCounts,
  legendGroups,
  matchingNodeIds,
  normalizeNetworkState,
  parseNetworkHash,
  sectorLabel,
  sectorOptions,
  shownEdgeWeights,
  sortByCollaborators,
  tagOptions,
  topCoauthors,
  yearBounds
} from "./network_model.js";

const DIM_NODE_COLOUR = "#dfe5e8";
const DIM_EDGE_COLOUR = "#eef1f2";
const FOCUS_EDGE_COLOUR = "#1d2a33";
const GRAPH_BUTTONS = ["zoomIn", "zoomOut", "resetView", "fullscreen", "layout", "restore"];

function labelFor(tag) {
  const api = window.AtlasTopics;
  return api ? api.label(tag) : String(tag);
}

function topicColour(tag) {
  const api = window.AtlasTopics;
  return api ? api.color(tag) : null;
}

function expertUrl(id) {
  return classicUrl(`expert.html#author=${encodeURIComponent(id)}`);
}

// Profile link for the side panel: the Framework experts page with the author in the hash.
function profileUrl(id) {
  return new URL(`experts#author=${encodeURIComponent(id)}`, document.baseURI).href;
}

function textEl(tag, text, className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function fillSelect(select, pairs) {
  for (const [value, text] of pairs) select.append(new Option(text, value));
}

function webglAvailable() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

function sharedWorksText(weight) {
  return weight === 1 ? "1 shared work" : `${formatCount(weight)} shared works`;
}

export async function mountNetwork() {
  const chart = document.getElementById("network-chart");
  if (!chart) return;
  const stage = document.getElementById("network-stage");
  const message = document.getElementById("network-message");
  const panel = document.getElementById("network-panel");
  const legend = document.getElementById("network-legend");
  const rowsBody = document.getElementById("network-rows");
  const caption = document.getElementById("network-table-caption");
  const tableDetails = document.getElementById("network-table");
  const status = document.getElementById("network-status");
  const search = document.getElementById("net-search");
  const searchList = document.getElementById("net-search-list");
  const colourSelect = document.getElementById("net-colour");
  const sizeSelect = document.getElementById("net-size");
  const buttons = {
    zoomIn: document.getElementById("net-zoom-in"),
    zoomOut: document.getElementById("net-zoom-out"),
    resetView: document.getElementById("net-reset-view"),
    fullscreen: document.getElementById("net-fullscreen"),
    layout: document.getElementById("net-layout"),
    restore: document.getElementById("net-restore")
  };
  const controls = {
    topic: document.getElementById("net-topic"),
    sector: document.getElementById("net-sector"),
    institution: document.getElementById("net-institution"),
    yearFrom: document.getElementById("net-year-from"),
    yearTo: document.getElementById("net-year-to"),
    minWorks: document.getElementById("net-min"),
    minOut: document.getElementById("net-min-out"),
    currentOnly: document.getElementById("net-current"),
    form: document.getElementById("network-filters"),
    reset: document.getElementById("network-reset")
  };
  const required = [
    stage, message, panel, legend, rowsBody, caption, tableDetails, status, search, searchList,
    colourSelect, sizeSelect, ...Object.values(buttons), ...Object.values(controls)
  ];
  if (required.some((item) => !item)) return;

  let data;
  try {
    data = await loadJson("network.json");
  } catch (error) {
    message.textContent = "The collaboration network could not be loaded. Try again later.";
    status.textContent = "Network unavailable.";
    return;
  }
  const nodes = (Array.isArray(data?.nodes) ? data.nodes : []).filter((node) => node && typeof node.id === "string");
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = (Array.isArray(data?.edges) ? data.edges : []).filter(
    (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target) && edge.source !== edge.target
  );
  if (!nodes.length) {
    message.textContent = "The network export has no experts.";
    status.textContent = "No network data.";
    return;
  }

  // Filter options come from the data; a hash value that no option matches is dropped.
  const topics = tagOptions(nodes);
  const sectors = sectorOptions(nodes);
  fillSelect(controls.topic, topics.map((tag) => [tag, labelFor(tag)]));
  fillSelect(controls.sector, sectors.map((sector) => [sector, sectorLabel(sector)]));
  if (!topics.length) {
    controls.topic.disabled = true;
    controls.topic.title = "This export has no topic tags.";
  }
  const bounds = yearBounds(edges);
  if (bounds.min !== null) {
    controls.yearFrom.placeholder = String(bounds.min);
    controls.yearTo.placeholder = String(bounds.max);
  }

  // Search: one entry per name (first expert wins when two share a name).
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const idByName = new Map();
  for (const node of [...nodes].sort((a, b) => String(a.name).localeCompare(String(b.name)))) {
    if (!idByName.has(node.name)) idByName.set(node.name, node.id);
  }
  searchList.replaceChildren(
    ...[...idByName.keys()].map((name) => {
      const option = document.createElement("option");
      option.value = name;
      return option;
    })
  );

  function fromHash() {
    const parsed = parseNetworkHash(window.location.hash);
    if (!topics.includes(parsed.topic)) parsed.topic = "";
    if (!sectors.includes(parsed.sector)) parsed.sector = "";
    return normalizeNetworkState(parsed);
  }

  function writeControls(value) {
    controls.topic.value = value.topic;
    controls.sector.value = value.sector;
    controls.institution.value = value.institution;
    controls.yearFrom.value = value.yearFrom ?? "";
    controls.yearTo.value = value.yearTo ?? "";
    controls.minWorks.value = String(value.minWorks);
    controls.minOut.textContent = String(value.minWorks);
    controls.currentOnly.checked = value.currentOnly;
  }

  // Year fields are read raw so typing a year is not cleared mid-entry; normalizing happens in the model.
  function readControls() {
    return normalizeNetworkState({
      topic: controls.topic.value,
      sector: controls.sector.value,
      institution: controls.institution.value,
      yearFrom: controls.yearFrom.value,
      yearTo: controls.yearTo.value,
      minWorks: controls.minWorks.value,
      currentOnly: controls.currentOnly.checked
    });
  }

  // Graph state. The graphology graph is always kept in memory; sigma draws it when WebGL works.
  let state = emptyNetworkState();
  let colourMode = "cluster";
  let sizeMode = "works";
  let colours = colourGroups(nodes, colourMode, topicColour);
  const hiddenGroups = new Set();
  const positions = new Map(); // id -> {x, y} for experts moved by drag or by the layout
  const graph = new Graph({type: "undirected"});
  let renderer = null;
  let model = {matching: new Set(), weights: [], visible: new Set()};
  let selectedId = null;
  let hoveredId = null;
  let activeId = null;
  let activeSet = null;
  let dragId = null;
  let layoutRunning = false;
  let layoutFrame = 0;
  let layoutSettings = null;

  // Keep the current drawn positions so a rebuild does not move anyone.
  function savePositions() {
    graph.forEachNode((key, attrs) => positions.set(key, {x: attrs.x, y: attrs.y}));
  }

  // Hover wins over selection: the active expert and its neighbours stay bright, the rest dim.
  function refreshHighlight() {
    const candidate = hoveredId ?? selectedId;
    activeId = candidate !== null && graph.hasNode(candidate) ? candidate : null;
    activeSet = activeId === null ? null : new Set([activeId, ...graph.neighbors(activeId)]);
    if (renderer) renderer.refresh();
  }

  const nodeReducer = (key, data) => {
    const res = {...data};
    if (key === activeId) {
      res.highlighted = true;
      res.forceLabel = true;
    } else if (activeSet && !activeSet.has(key)) {
      res.color = DIM_NODE_COLOUR;
      res.label = null;
    }
    if (key === selectedId) res.highlighted = true;
    return res;
  };

  const edgeReducer = (key, data) => {
    const res = {...data};
    if (activeId !== null) {
      const [a, b] = graph.extremities(key);
      if (a === activeId || b === activeId) res.color = FOCUS_EDGE_COLOUR;
      else res.color = DIM_EDGE_COLOUR;
    }
    return res;
  };

  // Cluster numbers in the table follow the legend: largest cluster is Cluster 1.
  const clusterRank = new Map([...groupCounts(nodes, "cluster").keys()].map((key, i) => [key, i + 1]));

  function renderTable(visible) {
    const rows = sortByCollaborators(nodes, visible);
    rowsBody.innerHTML = rows
      .map((node) => {
        const degree = Number(node.degree) || 0;
        const works = Number(node.plastic_works) || 0;
        const rank = clusterRank.get(String(node.community));
        const clusterCell = rank ? `Cluster ${rank}` : "Other clusters";
        return (
          `<tr><th scope="row"><a href="${escapeHtml(expertUrl(node.id))}">${escapeHtml(node.name)}</a></th>` +
          `<td>${escapeHtml(clusterCell)}</td><td>${degree}</td><td>${works}</td></tr>`
        );
      })
      .join("");
    caption.textContent = `${formatCount(rows.length)} experts shown, most collaborators first.`;
  }

  function addFact(list, term, detail) {
    list.append(textEl("dt", term), textEl("dd", detail));
  }

  // Side panel for the selected expert. Co-author buttons select that co-author.
  function renderPanel() {
    panel.replaceChildren();
    const node = selectedId === null ? null : byId.get(selectedId);
    if (!node) {
      panel.append(textEl("p", "Select a dot on the chart, or search for a name, to see that expert's collaborations here.", "net-panel-note"));
      return;
    }
    panel.append(textEl("h2", node.name));
    if (!model.visible.has(node.id)) {
      panel.append(textEl("p", "This expert is hidden by the current filters or legend. Reset the filters to see them on the chart.", "net-panel-note"));
    }
    const facts = document.createElement("dl");
    facts.className = "net-facts";
    addFact(facts, "Primary affiliation", (node.primary_affiliations || [])[0] || "Affiliation not listed");
    addFact(facts, "Institutions", (node.institutions || []).join("; ") || "Not listed");
    addFact(facts, "Plastic-related works", formatCount(Number(node.plastic_works) || 0));
    addFact(facts, "Collaborators", formatCount(Number(node.degree) || 0));
    addFact(facts, "Topics", (node.topics || []).map(labelFor).join(", ") || "None listed");
    panel.append(facts);

    const coauthors = topCoauthors(edges, model.weights, node.id, 8);
    panel.append(textEl("h3", "Top co-authors"));
    if (!coauthors.length) {
      panel.append(textEl("p", "No co-authors with shown links.", "net-panel-note"));
    } else {
      const list = document.createElement("ul");
      list.className = "net-coauthors";
      for (const {id, weight} of coauthors) {
        const other = byId.get(id);
        const item = document.createElement("li");
        const button = textEl("button", `${other ? other.name : id} (${sharedWorksText(weight)})`, "net-link-button");
        button.type = "button";
        button.addEventListener("click", () => select(id, {pan: true}));
        item.append(button);
        list.append(item);
      }
      panel.append(list);
    }
    const link = textEl("a", "Open expert profile", "net-profile-link");
    link.href = profileUrl(node.id);
    panel.append(link);
  }

  function panTo(id) {
    if (!renderer || !graph.hasNode(id)) return;
    const point = renderer.getNodeDisplayData(id);
    if (point) renderer.getCamera().animate({x: point.x, y: point.y, ratio: 0.25}, {duration: 600});
  }

  function select(id, {pan = false} = {}) {
    selectedId = id !== null && byId.has(id) ? id : null;
    refreshHighlight();
    renderPanel();
    if (pan && selectedId !== null) panTo(selectedId);
  }

  // Legend: one toggle per group, aria-pressed shows whether the group is drawn.
  function renderLegend() {
    const groups = legendGroups(nodes, colourMode, colours, labelFor);
    legend.replaceChildren(
      ...groups.map((group) => {
        const item = document.createElement("li");
        const button = document.createElement("button");
        button.type = "button";
        button.className = "net-legend-item";
        button.setAttribute("aria-pressed", String(!hiddenGroups.has(group.key)));
        const swatch = textEl("span", "", "net-swatch");
        swatch.style.background = group.colour;
        button.append(swatch, textEl("span", `${group.label} (${formatCount(group.count)} experts)`));
        button.addEventListener("click", () => {
          if (hiddenGroups.has(group.key)) hiddenGroups.delete(group.key);
          else hiddenGroups.add(group.key);
          renderLegend();
          render();
        });
        item.append(button);
        return item;
      })
    );
  }

  // Rebuilds the graph from the model, then refreshes status, table and panel.
  function render() {
    savePositions();
    const attrs = graphAttributes(nodes, edges, state, colourMode, sizeMode, {colours, hiddenGroups, positions});
    graph.clear();
    for (const row of attrs.nodes) {
      const {key, ...rest} = row;
      graph.addNode(key, rest);
    }
    for (const row of attrs.edges) {
      graph.addEdgeWithKey(row.key, row.source, row.target, {size: row.size, color: row.color, weight: row.weight});
    }
    const matching = matchingNodeIds(nodes, state);
    model = {
      matching,
      weights: shownEdgeWeights(edges, matching, state),
      visible: new Set(attrs.nodes.map((row) => row.key))
    };
    const experts = attrs.nodes.length;
    const links = attrs.edges.length;
    status.textContent =
      experts === 0
        ? "No experts match these filters. Use Reset filters to see the whole network."
        : `${formatCount(experts)} experts, ${formatCount(links)} links shown`;
    renderTable(model.visible);
    refreshHighlight();
    if (selectedId !== null) renderPanel();
  }

  // Controls are not rewritten here, so a half-typed year is never cleared mid-entry.
  function commit(next) {
    state = next;
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${formatNetworkHash(state)}`);
    render();
  }

  // ForceAtlas2 in short synchronous bursts per animation frame, until stopped.
  function stepLayout() {
    if (!layoutRunning) return;
    if (!stage.isConnected) {
      stopLayout();
      return;
    }
    forceAtlas2.assign(graph, {iterations: 3, settings: layoutSettings});
    if (renderer) renderer.refresh();
    layoutFrame = window.requestAnimationFrame(stepLayout);
  }

  function setLayoutButton() {
    buttons.layout.setAttribute("aria-pressed", String(layoutRunning));
    buttons.layout.textContent = layoutRunning ? "Stop layout" : "Re-run layout";
  }

  function stopLayout() {
    if (!layoutRunning) return;
    layoutRunning = false;
    window.cancelAnimationFrame(layoutFrame);
    savePositions();
    setLayoutButton();
  }

  function showFallback(text) {
    renderer = null;
    message.hidden = false;
    message.textContent = text;
    tableDetails.open = true;
    for (const key of GRAPH_BUTTONS) buttons[key].disabled = true;
  }

  function bindRenderer() {
    renderer.on("enterNode", (event) => {
      hoveredId = event.node;
      refreshHighlight();
    });
    renderer.on("leaveNode", () => {
      hoveredId = null;
      refreshHighlight();
    });
    renderer.on("clickNode", (event) => select(event.node));
    renderer.on("clickStage", () => select(null));
    // Drag a dot to move it; the camera stays put while a dot is held.
    renderer.on("downNode", (event) => {
      dragId = event.node;
    });
    const captor = renderer.getMouseCaptor();
    captor.on("mousemovebody", (event) => {
      if (dragId === null || !graph.hasNode(dragId)) return;
      const point = renderer.viewportToGraph(event);
      graph.setNodeAttribute(dragId, "x", point.x);
      graph.setNodeAttribute(dragId, "y", point.y);
      event.preventSigmaDefault();
      event.original.preventDefault();
      event.original.stopPropagation();
    });
    captor.on("mouseup", () => {
      if (dragId === null) return;
      dragId = null;
      savePositions();
    });
  }

  function createRenderer() {
    if (!webglAvailable()) throw new Error("WebGL is unavailable");
    renderer = new Sigma(graph, stage, {
      renderEdgeLabels: false,
      labelDensity: 0.07,
      labelGridCellSize: 70,
      labelRenderedSizeThreshold: 8,
      minCameraRatio: 0.02,
      maxCameraRatio: 5,
      nodeReducer,
      edgeReducer
    });
    bindRenderer();
  }

  // Controls.
  controls.form.addEventListener("input", () => commit(readControls()));
  controls.form.addEventListener("change", () => commit(readControls()));
  controls.reset.addEventListener("click", () => {
    writeControls(emptyNetworkState());
    commit(emptyNetworkState());
  });
  window.addEventListener("hashchange", () => {
    state = fromHash();
    writeControls(state);
    render();
  });

  colourSelect.addEventListener("change", () => {
    colourMode = colourSelect.value;
    colours = colourGroups(nodes, colourMode, topicColour);
    hiddenGroups.clear();
    renderLegend();
    render();
  });
  sizeSelect.addEventListener("change", () => {
    sizeMode = sizeSelect.value;
    render();
  });

  search.addEventListener("change", () => {
    const id = idByName.get(search.value.trim());
    if (id === undefined) return;
    select(id, {pan: true});
  });

  buttons.zoomIn.addEventListener("click", () => renderer?.getCamera().animatedZoom({duration: 250}));
  buttons.zoomOut.addEventListener("click", () => renderer?.getCamera().animatedUnzoom({duration: 250}));
  buttons.resetView.addEventListener("click", () => renderer?.getCamera().animatedReset({duration: 250}));

  if (!chart.requestFullscreen) buttons.fullscreen.hidden = true;
  buttons.fullscreen.addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await chart.requestFullscreen();
    } catch {
      status.textContent = "Full screen is not available in this browser.";
    }
  });
  document.addEventListener("fullscreenchange", () => {
    const on = document.fullscreenElement === chart;
    buttons.fullscreen.textContent = on ? "Exit full screen" : "Full screen";
    if (renderer) {
      renderer.resize();
      renderer.refresh();
    }
  });

  buttons.layout.addEventListener("click", () => {
    if (layoutRunning) {
      stopLayout();
      return;
    }
    if (graph.order < 2) return;
    layoutSettings = forceAtlas2.inferSettings(graph);
    layoutRunning = true;
    setLayoutButton();
    layoutFrame = window.requestAnimationFrame(stepLayout);
  });
  buttons.restore.addEventListener("click", () => {
    stopLayout();
    positions.clear();
    render();
    renderer?.getCamera().animatedReset({duration: 400});
  });

  // First paint: the model and table first, then the sigma view if WebGL and sigma start.
  state = fromHash();
  writeControls(state);
  renderLegend();
  render();
  try {
    createRenderer();
    message.hidden = true;
  } catch (error) {
    showFallback(
      "The network graphic could not start in this browser, so the table below lists the same experts."
    );
  }
}
