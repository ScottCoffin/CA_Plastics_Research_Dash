// Community groups network view (CG-11 part B) for /groups. Draws the groups graph payload with sigma.js (WebGL)
// and offers the same information as a DOM list and details panel. The canvas is aria-hidden; the list, the
// details and the counts carry the content. Pure helpers live in groups_network_model.js. sigma starts only when
// there is something to draw and the stage is on screen; dispose runs when root leaves the document.
// mountGroupsNetwork(root, json, {onOpenGroup}) returns a dispose function.
import Graph from "npm:graphology@0.26.0";
import Sigma from "npm:sigma@3.0.3";
import {escapeHtml, formatCount} from "./atlas.js";
import {
  degreeMap,
  egoView,
  formatNetHash,
  isEmptyGraph,
  linkLabel,
  netHashState,
  nodeSize,
  prepareGraph,
  sectorLabel,
  sectorsOf,
  STATUS_LABELS,
  viewFor
} from "./groups_network_model.js";

// Colours are read from the --pv-* tokens at mount; the hex fallbacks are used only when a token is missing.
const SECTOR_TOKENS = [["--pv-slate", "#436487"], ["--pv-coral-ink", "#c53e39"], ["--pv-gold", "#e2b714"], ["--pv-slate-2", "#86a9bf"], ["--pv-ink-2", "#4d5d73"], ["--pv-mint", "#c5eadf"], ["--pv-ink", "#17263d"], ["--pv-line", "#c4d0d6"], ["--pv-wash", "#e9f1ef"]];
const TYPE_TOKENS = {group: "--pv-ink", activity: "--pv-slate", theme: "--pv-gold", place: "--pv-ink-2", external: "--pv-paper"};
const EDGE_TOKENS = {assignment: "--pv-line", affiliation: "--pv-coral-ink", co_occurrence: "--pv-slate-2"};
const FAINT_TOKEN = "--pv-grid";
const TYPE_LABELS = {group: "Group", activity: "Activity tag", theme: "Theme tag", place: "Place tag", external: "Outside the roster"};
const LAYER_LABEL = "Adjacent organisation (no stated plastics focus)";
const EMPTY_MESSAGE = 'No groups are tagged yet, so there is no network to draw. <a href="./ambassadors">Volunteer Ambassadors</a> can help tag groups.';
const MODE_NOTES = {
  assignments: "Each link joins a group to one of its tags. Links are tag assignments, not relationships between groups.",
  co_occurrence: "Links show co-occurrence of tags, not partnerships. A link joins two activity tags carried by the same groups; its thickness shows how many groups carry both."
};
const AFFILIATION_NOTE = "Stated affiliations come from each group's own public statements. Each one shows its quote and source in the details.";

// Only http(s) links are drawn; an evidence URL with any other scheme shows no link.
const isWebUrl = (value) => {
  try { return ["http:", "https:"].includes(new URL(String(value)).protocol); } catch { return false; }
};
const webglAvailable = () => {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
};

// Resolves the colour tokens once. The sigma canvas needs plain colour strings, so the values are read here.
function readColours(el) {
  const style = getComputedStyle(el);
  const read = (name, fallback = "#17263d") => style.getPropertyValue(name).trim() || fallback;
  return {
    sectors: SECTOR_TOKENS.map(([name, fallback]) => read(name, fallback)),
    type: Object.fromEntries(Object.entries(TYPE_TOKENS).map(([key, name]) => [key, read(name)])),
    edge: Object.fromEntries(Object.entries(EDGE_TOKENS).map(([key, name]) => [key, read(name, "#c4d0d6")])),
    faint: read(FAINT_TOKEN, "#e4eaee")
  };
}

function controlsHtml(state, sectors) {
  const statusOptions = Object.entries(STATUS_LABELS)
    .map(([value, label]) => `<option value="${value}"${state.status === value ? " selected" : ""}>${escapeHtml(label)}</option>`)
    .join("");
  const legend = sectors.map((sector, index) => `<li><span class="gv-net-swatch" style="background: var(${SECTOR_TOKENS[index % SECTOR_TOKENS.length][0]})" aria-hidden="true"></span>${escapeHtml(sectorLabel(sector))}</li>`).join("");
  return `<div class="gv-net-controls">
      <fieldset class="gv-net-mode">
        <legend>Show</legend>
        <label class="gv-tree-check"><input type="radio" name="gv-net-mode" value="assignments" data-net="mode"${state.mode === "assignments" ? " checked" : ""}> Groups and their tags</label>
        <label class="gv-tree-check"><input type="radio" name="gv-net-mode" value="co_occurrence" data-net="mode"${state.mode === "co_occurrence" ? " checked" : ""}> Tag co-occurrence</label>
      </fieldset>
      <div class="gv-net-toggles">
        <label class="gv-tree-check" data-net-only="assignments"><input type="checkbox" data-net="aff"${state.affiliations ? " checked" : ""}> Stated affiliations between groups</label>
        <label class="gv-tree-check" data-net-only="assignments"><input type="checkbox" data-net="ext"${state.externals ? " checked" : ""}> Organisations outside the roster</label>
        <label class="gv-tree-check"><input type="checkbox" data-net="adj"${state.adjacent ? " checked" : ""}> Adjacent organisations (no stated plastics focus)</label>
      </div>
      <label class="gv-field"><span>Status</span><select data-net="status"><option value="">All statuses</option>${statusOptions}</select></label>
      <label class="gv-field"><span>Find a name</span><input type="search" data-net="q" autocomplete="off" value="${escapeHtml(state.query)}"></label>
      <button type="button" class="gv-btn" data-net="full"${state.ego ? "" : " hidden"}>Show the whole network</button>
    </div>
    <ul class="gv-net-legend" aria-label="Sector colours">${legend}</ul>
    <p class="gv-caption">Colour shows the sector. Size shows the number of tags, not importance.</p>`;
}

export function mountGroupsNetwork(root, json, options = {}) {
  if (!root) throw new Error("mountGroupsNetwork needs an element to mount into");
  const graph = prepareGraph(json);
  if (isEmptyGraph(graph) || graph.edges.length === 0) {
    root.innerHTML = `<p class="gv-status gv-net-empty">${EMPTY_MESSAGE}</p>`;
    return () => {};
  }

  const abort = new AbortController();
  const {signal} = abort;
  const sectors = sectorsOf(graph);
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const gx = new Graph({type: "undirected", multi: true, allowSelfLoops: false});
  let state = netHashState(location.hash);
  let view = {nodes: [], edges: [], counts: {nodes: 0, edges: 0}};
  let edgeByKey = new Map();
  let degrees = new Map();
  let neighbours = new Set();
  let selected = null; // {kind: "node" | "edge", id}
  let colours = null;
  let renderer = null;
  let disposed = false;
  let stageWatch = null;
  let rootWatch = null;

  root.classList.add("gv");
  root.innerHTML = `<div class="gv-net">
    ${graph.caution ? `<p class="gv-caption gv-net-caution">${escapeHtml(graph.caution)}</p>` : ""}
    ${graph.denominatorNote ? `<p class="gv-caption gv-net-denominator">${escapeHtml(graph.denominatorNote)}</p>` : ""}
    ${controlsHtml(state, sectors)}
    <p class="gv-net-counts" data-net="counts" aria-live="polite"></p>
    <p class="gv-net-note" data-net="note"></p>
    <p class="gv-caption" data-net="empty" hidden></p>
    <div class="gv-net-body">
      <div class="gv-net-stage" data-net="stage" aria-hidden="true"></div>
      <div class="gv-net-details" data-net="details" aria-live="polite"></div>
    </div>
    <div class="gv-net-list-wrap">
      <h3>Items in this view</h3>
      <ul class="gv-net-list" data-net="list"></ul>
    </div>
  </div>`;
  const q = (key) => root.querySelector(`[data-net="${key}"]`);
  const ui = {
    counts: q("counts"), note: q("note"), empty: q("empty"), stage: q("stage"),
    details: q("details"), list: q("list"), search: q("q"), status: q("status"), full: q("full")
  };
  colours = readColours(root);

  const writeHash = () => {
    history.replaceState(null, "", `${location.pathname}${location.search}${formatNetHash(state, location.hash)}`);
  };

  function refreshView() {
    const scoped = viewFor(graph, state);
    const focused = state.ego && scoped.nodes.some((node) => node.id === state.ego);
    const next = focused ? egoView(scoped, state.ego) : scoped;
    view = {...next, counts: {nodes: next.nodes.length, edges: next.edges.length}};
    edgeByKey = new Map(view.edges.map((edge) => [edge.key, edge]));
    degrees = degreeMap(view.edges);
    if (selected?.kind === "node" && !degrees.has(selected.id)) selected = null;
    if (selected?.kind === "edge" && !edgeByKey.has(selected.id)) selected = null;
    neighbours = new Set();
    if (selected?.kind === "node") {
      for (const edge of view.edges) {
        if (edge.source === selected.id) neighbours.add(edge.target);
        if (edge.target === selected.id) neighbours.add(edge.source);
      }
    }
  }

  function renderControls() {
    root.querySelectorAll("[data-net-only]").forEach((label) => {
      label.hidden = label.dataset.netOnly !== state.mode;
    });
    ui.full.hidden = !state.ego;
  }

  function renderText() {
    ui.counts.textContent = `Nodes shown: ${formatCount(view.counts.nodes)}. Links shown: ${formatCount(view.counts.edges)}.`;
    const base = MODE_NOTES[state.mode] ?? MODE_NOTES.assignments;
    ui.note.textContent = state.affiliations && state.mode === "assignments" ? `${base} ${AFFILIATION_NOTE}` : base;
    const empty = view.counts.nodes === 0;
    ui.empty.hidden = !empty;
    ui.empty.textContent = empty ? "No links match these filters. Try another option or clear the search." : "";
  }

  function renderList() {
    ui.list.innerHTML = view.nodes
      .slice()
      .sort((a, b) => a.label.localeCompare(b.label, "en") || a.id.localeCompare(b.id))
      .map((node) => {
        const current = selected?.kind === "node" && selected.id === node.id;
        return `<li><button type="button" class="gv-net-item" data-net-node="${escapeHtml(node.id)}" aria-pressed="${current}"><span>${escapeHtml(node.label)}</span><span class="gv-net-kind">${escapeHtml(TYPE_LABELS[node.type] ?? "Item")} · ${formatCount(degrees.get(node.id) ?? 0)} links</span></button></li>`;
      })
      .join("");
  }

  function renderDetails() {
    if (selected?.kind === "edge") {
      const edge = edgeByKey.get(selected.id);
      const a = byId.get(edge.source)?.label ?? edge.source;
      const b = byId.get(edge.target)?.label ?? edge.target;
      let extra = "";
      if (edge.edge_type === "affiliation") {
        extra = `<blockquote><q>${escapeHtml(edge.quote)}</q></blockquote>${isWebUrl(edge.url) ? `<p><a href="${escapeHtml(edge.url)}" rel="noopener nofollow">Source page</a></p>` : ""}`;
      } else if (edge.edge_type === "co_occurrence") {
        extra = `<p class="gv-meta">Co-occurrence of tags, not partnerships. ${formatCount(edge.weight)} groups carry both tags.</p>`;
      }
      ui.details.innerHTML = `<h3>${escapeHtml(linkLabel(edge))}</h3><p><b>${escapeHtml(a)}</b> and <b>${escapeHtml(b)}</b></p>${extra}`;
      return;
    }
    if (selected?.kind === "node") {
      const node = byId.get(selected.id);
      const rows = [
        `<div class="gv-fact"><dt>Type</dt><dd>${escapeHtml(TYPE_LABELS[node.type] ?? "Item")}</dd></div>`,
        `<div class="gv-fact"><dt>Links shown</dt><dd>${formatCount(degrees.get(node.id) ?? 0)}</dd></div>`,
        node.type === "group" ? `<div class="gv-fact"><dt>Sector</dt><dd>${escapeHtml(sectorLabel(node.sector))}</dd></div>` : "",
        node.type === "group" && node.layer === "adjacent" ? `<div class="gv-fact"><dt>Layer</dt><dd>${escapeHtml(LAYER_LABEL)}</dd></div>` : "",
        node.type === "group" ? `<div class="gv-fact"><dt>Tagging</dt><dd>${escapeHtml(STATUS_LABELS[node.status] ?? "Not yet tagged")}</dd></div>` : ""
      ].join("");
      const open = node.type === "group" && typeof options.onOpenGroup === "function"
        ? `<p><button type="button" class="gv-btn" data-net="open" data-group-id="${escapeHtml(node.id)}">Open group card</button></p>`
        : "";
      ui.details.innerHTML = `<h3>${escapeHtml(node.label)}</h3><dl class="gv-facts">${rows}</dl>${open}`;
      return;
    }
    ui.details.innerHTML = '<p class="gv-caption">Select an item or a link to see its details. Selecting an item shows only its neighbourhood.</p>';
  }

  // The graphology graph is one object for the life of the component; sigma keeps drawing it.
  function fillGraph() {
    gx.clear();
    for (const node of view.nodes) {
      const focusOn = selected && (selected.id === node.id || neighbours.has(node.id));
      const base = node.type === "group"
        ? colours.sectors[Math.max(0, sectors.indexOf(node.sector)) % colours.sectors.length]
        : colours.type[node.type] ?? colours.type.group;
      gx.addNode(node.id, {
        x: node.x,
        y: node.y,
        size: nodeSize(node, degrees.get(node.id) ?? 0),
        label: node.label,
        color: selected && !focusOn ? colours.faint : base,
        zIndex: selected?.id === node.id ? 2 : 0
      });
    }
    for (const edge of view.edges) {
      const touches = selected && (edge.source === selected.id || edge.target === selected.id || (selected.kind === "edge" && selected.id === edge.key));
      gx.addEdgeWithKey(edge.key, edge.source, edge.target, {
        size: edge.edge_type === "co_occurrence" ? Math.min(6, 0.6 + Math.sqrt(edge.weight)) : 1,
        color: selected && !touches ? colours.faint : colours.edge[edge.edge_type] ?? colours.edge.assignment
      });
    }
  }

  function startRenderer() {
    if (renderer || disposed || !view.nodes.length) return;
    if (!webglAvailable()) {
      ui.stage.hidden = true;
      return;
    }
    try {
      renderer = new Sigma(gx, ui.stage, {
        renderEdgeLabels: false,
        // Sigma 3 ignores clickEdge unless edge events (picking) are enabled; default is false.
        enableEdgeEvents: true,
        labelDensity: 0.07,
        labelGridCellSize: 70,
        labelRenderedSizeThreshold: 6,
        minCameraRatio: 0.05,
        maxCameraRatio: 5,
        defaultNodeColor: colours.type.group,
        defaultEdgeColor: colours.edge.assignment
      });
    } catch {
      renderer = null;
      ui.stage.hidden = true;
      return;
    }
    ui.stage.querySelectorAll("canvas").forEach((canvas) => canvas.setAttribute("aria-hidden", "true"));
    renderer.on("clickNode", ({node}) => choose({kind: "node", id: node}, true));
    renderer.on("clickEdge", ({edge}) => choose({kind: "edge", id: edge}, false));
    renderer.on("clickStage", () => choose(null, false));
  }

  function draw() {
    refreshView();
    renderControls();
    renderText();
    renderList();
    renderDetails();
    fillGraph();
    renderer?.refresh();
  }

  // Selecting a node focuses its ego network (hash net_ego); selecting a link only highlights it.
  function choose(next, focusEgo) {
    selected = next;
    if (focusEgo && next) state = {...state, ego: next.id};
    draw();
    writeHash();
  }

  function setState(patch) {
    state = {...state, ...patch};
    if (patch.mode !== undefined || patch.affiliations !== undefined) selected = null;
    draw();
    writeHash();
  }

  root.addEventListener("change", (event) => {
    const field = event.target.dataset.net;
    if (field === "mode") setState({mode: event.target.value, ego: ""});
    else if (field === "aff") setState({affiliations: event.target.checked});
    else if (field === "ext") setState({externals: event.target.checked});
    else if (field === "adj") setState({adjacent: event.target.checked});
    else if (field === "status") setState({status: event.target.value});
  }, {signal});
  root.addEventListener("input", (event) => {
    if (event.target.dataset.net === "q") setState({query: event.target.value.trim()});
  }, {signal});
  root.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button || !root.contains(button)) return;
    if (button.dataset.netNode) choose({kind: "node", id: button.dataset.netNode}, true);
    else if (button.dataset.net === "full") { selected = null; setState({ego: ""}); }
    else if (button.dataset.net === "open" && typeof options.onOpenGroup === "function") options.onOpenGroup(button.dataset.groupId);
  }, {signal});
  window.addEventListener("hashchange", () => {
    state = netHashState(location.hash);
    ui.search.value = state.query;
    ui.status.value = state.status;
    root.querySelector(`[data-net="mode"][value="${state.mode}"]`).checked = true;
    root.querySelector('[data-net="aff"]').checked = state.affiliations;
    root.querySelector('[data-net="ext"]').checked = state.externals;
    root.querySelector('[data-net="adj"]').checked = state.adjacent;
    draw();
  }, {signal});

  function dispose() {
    if (disposed) return;
    disposed = true;
    abort.abort();
    rootWatch?.disconnect();
    stageWatch?.disconnect();
    renderer?.kill();
    renderer = null;
  }

  rootWatch = new MutationObserver(() => { if (!root.isConnected) dispose(); });
  rootWatch.observe(document.documentElement, {childList: true, subtree: true});

  draw();
  // sigma starts when the stage first scrolls into view, not at page load.
  if ("IntersectionObserver" in window) {
    stageWatch = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        stageWatch.disconnect();
        startRenderer();
      }
    });
    stageWatch.observe(ui.stage);
  } else {
    startRenderer();
  }
  return dispose;
}
