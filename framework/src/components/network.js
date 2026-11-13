// Collaboration network page. The SVG is built once; filter changes toggle classes and attributes
// and rebuild only the table. Hover or focus highlights a node and its links; Enter or click opens
// the expert's page in the same tab. Pure logic lives in network_model.js.
import "./shared/topics.js";
import {classicUrl, escapeHtml, formatCount, loadJson} from "./atlas.js";
import {
  OTHER_COLOUR,
  VIEW_SIZE,
  communityColourMap,
  connectedIds,
  edgeStroke,
  emptyNetworkState,
  formatNetworkHash,
  layoutToView,
  matchingNodeIds,
  neighbourIds,
  networkSummary,
  nodeRadius,
  normalizeNetworkState,
  parseNetworkHash,
  sectorLabel,
  sectorOptions,
  shownEdgeWeights,
  sortByCollaborators,
  tagOptions,
  yearBounds
} from "./network_model.js";

const SVG_NS = "http://www.w3.org/2000/svg";

function labelFor(tag) {
  const api = window.AtlasTopics;
  return api ? api.label(tag) : String(tag);
}

function svgEl(tag, attrs) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return node;
}

function textEl(tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}

function expertUrl(id) {
  return classicUrl(`expert.html#author=${encodeURIComponent(id)}`);
}

function fillSelect(select, pairs) {
  for (const [value, text] of pairs) select.append(new Option(text, value));
}

export async function mountNetwork() {
  const chart = document.getElementById("network-chart");
  if (!chart) return;
  const status = document.getElementById("network-status");
  const message = document.getElementById("network-message");
  const legend = document.getElementById("network-legend");
  const rowsBody = document.getElementById("network-rows");
  const caption = document.getElementById("network-table-caption");
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
  if (Object.values(controls).some((item) => !item) || !status || !rowsBody || !caption) return;

  let data;
  try {
    data = await loadJson("network.json");
  } catch (error) {
    if (message) message.textContent = "The collaboration network could not be loaded. Try again later.";
    status.textContent = "Network unavailable.";
    return;
  }
  const nodes = (Array.isArray(data?.nodes) ? data.nodes : []).filter((node) => node && typeof node.id === "string");
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = (Array.isArray(data?.edges) ? data.edges : []).filter(
    (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target) && edge.source !== edge.target
  );
  if (!nodes.length) {
    if (message) message.textContent = "The network export has no experts.";
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

  // Build the SVG once. Edges sit under nodes; node order matches the data array.
  const positions = layoutToView(nodes);
  const centre = {x: VIEW_SIZE / 2, y: VIEW_SIZE / 2};
  const at = (id) => positions.get(id) || centre;
  const colours = communityColourMap(nodes);
  const clusterRank = new Map([...colours.keys()].map((community, i) => [community, i + 1]));
  const clusterName = (community) =>
    clusterRank.has(community) ? `Cluster ${clusterRank.get(community)}` : "Other clusters";
  const maxWorks = Math.max(1, ...nodes.map((node) => Number(node.plastic_works) || 0));
  const nodeIndex = new Map(nodes.map((node, j) => [node.id, j]));

  const svg = svgEl("svg", {
    class: "net-svg",
    viewBox: `0 0 ${VIEW_SIZE} ${VIEW_SIZE}`,
    role: "group",
    "aria-label": "Collaboration network of California experts. The table below lists the same experts."
  });
  const edgeLayer = svgEl("g", {class: "net-edges"});
  const nodeLayer = svgEl("g", {class: "net-nodes"});
  const edgeEls = edges.map((edge) => {
    const from = at(edge.source);
    const to = at(edge.target);
    const line = svgEl("line", {class: "net-edge", x1: from.x.toFixed(1), y1: from.y.toFixed(1), x2: to.x.toFixed(1), y2: to.y.toFixed(1)});
    edgeLayer.append(line);
    return line;
  });
  const nodeEls = nodes.map((node) => {
    const point = at(node.id);
    const degree = Number(node.degree) || 0;
    const circle = svgEl("circle", {
      class: "net-node",
      cx: point.x.toFixed(1),
      cy: point.y.toFixed(1),
      r: nodeRadius(node.plastic_works, maxWorks).toFixed(1),
      fill: colours.get(node.community) || OTHER_COLOUR,
      tabindex: 0,
      role: "link",
      "aria-label": `${node.name}, ${degree} collaborators`,
      "data-id": node.id
    });
    nodeLayer.append(circle);
    return circle;
  });
  svg.append(edgeLayer, nodeLayer);

  const tip = document.createElement("div");
  tip.className = "net-tooltip";
  tip.hidden = true;
  tip.setAttribute("aria-hidden", "true");
  chart.replaceChildren(svg, tip);

  if (legend) {
    const items = [...colours.keys()].map((community) => {
      const count = nodes.filter((node) => node.community === community).length;
      const item = document.createElement("li");
      const swatch = textEl("span", "");
      swatch.className = "net-swatch";
      swatch.style.background = colours.get(community);
      item.append(swatch, textEl("span", `${clusterName(community)} (${formatCount(count)} experts)`));
      return item;
    });
    const other = document.createElement("li");
    const grey = textEl("span", "");
    grey.className = "net-swatch";
    grey.style.background = OTHER_COLOUR;
    other.append(grey, textEl("span", "Other clusters"));
    legend.replaceChildren(...items, other);
  }

  let state = fromHash();
  let model = {matching: new Set(), weights: []};
  let lit = {nodes: [], edges: []};

  function clearHighlight() {
    svg.classList.remove("has-focus");
    for (const j of lit.nodes) nodeEls[j].classList.remove("is-focus", "is-linked");
    for (const i of lit.edges) edgeEls[i].classList.remove("is-linked");
    lit = {nodes: [], edges: []};
  }

  function showTooltip(j) {
    const node = nodes[j];
    const affiliation = (node.primary_affiliations || [])[0] || "Affiliation not listed";
    tip.replaceChildren(
      textEl("strong", node.name),
      textEl("span", affiliation),
      textEl("span", `Plastic-related works: ${formatCount(Number(node.plastic_works) || 0)}`),
      textEl("span", `Collaborators: ${Number(node.degree) || 0}`)
    );
    tip.hidden = false;
    const dot = nodeEls[j].getBoundingClientRect();
    const box = chart.getBoundingClientRect();
    const half = tip.offsetWidth / 2;
    const x = dot.left - box.left + dot.width / 2;
    const left = Math.min(Math.max(x, half + 4), Math.max(half + 4, box.width - half - 4));
    const y = dot.top - box.top;
    const below = y < 110;
    tip.classList.toggle("is-below", below);
    tip.style.left = `${left}px`;
    tip.style.top = `${below ? y + dot.height : y}px`;
  }

  function highlight(j) {
    clearHighlight();
    const id = nodes[j].id;
    if (!model.matching.has(id)) return;
    svg.classList.add("has-focus");
    lit.nodes.push(j);
    nodeEls[j].classList.add("is-focus");
    for (const other of neighbourIds(edges, model.weights, id)) {
      const k = nodeIndex.get(other);
      if (k === undefined) continue;
      nodeEls[k].classList.add("is-linked");
      lit.nodes.push(k);
    }
    edges.forEach((edge, i) => {
      if (model.weights[i] > 0 && (edge.source === id || edge.target === id)) {
        edgeEls[i].classList.add("is-linked");
        lit.edges.push(i);
      }
    });
    showTooltip(j);
  }

  function hideHighlight() {
    clearHighlight();
    tip.hidden = true;
  }

  nodeEls.forEach((circle, j) => {
    circle.addEventListener("pointerenter", () => highlight(j));
    circle.addEventListener("pointerleave", hideHighlight);
    circle.addEventListener("focus", () => highlight(j));
    circle.addEventListener("blur", hideHighlight);
    circle.addEventListener("click", () => window.location.assign(expertUrl(nodes[j].id)));
    circle.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      window.location.assign(expertUrl(nodes[j].id));
    });
  });

  function renderTable(matching) {
    const rows = sortByCollaborators(nodes, matching);
    rowsBody.innerHTML = rows
      .map((node) => {
        const degree = Number(node.degree) || 0;
        const works = Number(node.plastic_works) || 0;
        return (
          `<tr><th scope="row"><a href="${escapeHtml(expertUrl(node.id))}">${escapeHtml(node.name)}</a></th>` +
          `<td>${escapeHtml(clusterName(node.community))}</td><td>${degree}</td><td>${works}</td></tr>`
        );
      })
      .join("");
    caption.textContent = `${formatCount(rows.length)} experts shown, most collaborators first.`;
  }

  // Filter change: toggle classes and attributes on the existing elements, then refresh status and table.
  function render() {
    clearHighlight();
    const matching = matchingNodeIds(nodes, state);
    const weights = shownEdgeWeights(edges, matching, state);
    const connected = connectedIds(edges, weights);
    edges.forEach((_edge, i) => {
      const weight = weights[i];
      edgeEls[i].classList.toggle("is-hidden", !(weight > 0));
      if (weight > 0) edgeEls[i].setAttribute("stroke-width", edgeStroke(weight).toFixed(2));
    });
    nodes.forEach((node, j) => {
      const shown = matching.has(node.id);
      nodeEls[j].classList.toggle("is-hidden", !shown);
      nodeEls[j].classList.toggle("is-dim", shown && !connected.has(node.id));
    });
    model = {matching, weights};
    const summary = networkSummary(matching, weights);
    status.textContent =
      summary.experts === 0
        ? "No experts match these filters. Use Reset filters to see the whole network."
        : `${formatCount(summary.experts)} experts, ${formatCount(summary.links)} links shown`;
    renderTable(matching);
  }

  // Controls are not rewritten here, so a half-typed year is never cleared mid-entry.
  function commit(next) {
    state = next;
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${formatNetworkHash(state)}`);
    render();
  }

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

  writeControls(state);
  render();
}
