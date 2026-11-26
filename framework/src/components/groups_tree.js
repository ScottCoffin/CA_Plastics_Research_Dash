// CG-10: accessible, lazy-rendered public group hierarchy. The payload is built by
// atlas.groups.build; this module only renders its pre-aggregated nodes.
import {escapeHtml, formatCount} from "./atlas.js";

const HIERARCHIES = ["geography", "function", "centrality"];
const regionNames = typeof Intl.DisplayNames === "function" ? new Intl.DisplayNames(["en"], {type: "region"}) : null;
const labelFor = (node) => {
  const label = String(node?.label ?? node?.id ?? "");
  if (node?.level === "region" && label === "region_unknown") return "Region not known";
  if (node?.level === "country" && /^[A-Z]{2}$/.test(label)) {
    try { return `${regionNames?.of(label) || label} (${label})`; } catch { return label; }
  }
  if ((node?.level === "subnational" || node?.level === "state") && /^[A-Z]{2}-[A-Z0-9-]+$/.test(label)) {
    try { return `${regionNames?.of(label) || label} (${label})`; } catch { return label; }
  }
  return label;
};
const kids = (node) => Array.isArray(node?.children) ? node.children : [];
const counts = (node) => node?.counts ?? {};
const isBranch = (node) => kids(node).length > 0;
const searchKey = (value) => String(value ?? "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();

export function hierarchyData(data, hierarchy, allActivities = false) {
  const key = HIERARCHIES.includes(hierarchy) ? hierarchy : "geography";
  const variants = allActivities && (key === "function" || key === "centrality")
    ? data?.hierarchies_all_activities
    : null;
  return (variants?.[key] ?? data?.hierarchies?.[key]) || null;
}

export function treeHashState(hash = "") {
  const params = new URLSearchParams(String(hash).replace(/^#/, ""));
  const hierarchy = HIERARCHIES.includes(params.get("tree")) ? params.get("tree") : "geography";
  let expanded = [];
  let collapsed = [];
  try {
    const value = JSON.parse(params.get("tree_open") || "[]");
    if (Array.isArray(value)) expanded = value.filter((id) => typeof id === "string");
  } catch { /* malformed shared state falls back to the default */ }
  try {
    const value = JSON.parse(params.get("tree_closed") || "[]");
    if (Array.isArray(value)) collapsed = value.filter((id) => typeof id === "string");
  } catch { /* malformed shared state falls back to the default */ }
  return {hierarchy, allActivities: params.get("tree_all") === "1", expanded, collapsed, allExpanded: params.get("tree_open") === "all", query: params.get("tree_find") || ""};
}

export function treeNodeHtml(node, expanded, depth = 1, position = 1, size = 1, parentId = "", focusId = "", allExpanded = false, collapsed = new Set(), showDistinct = false) {
  const id = String(node?.id ?? "");
  const branch = isBranch(node);
  const open = allExpanded ? !collapsed.has(id) : expanded.has(id);
  const c = counts(node);
  const tagged = Number(c.tagged) || 0;
  const roster = Number(c.roster) || 0;
  const distinct = Number(c.distinct);
  const badge = showDistinct && Number.isFinite(distinct)
    ? `${formatCount(tagged)} tagged / ${formatCount(roster)} roster · ${formatCount(distinct)} distinct`
    : `${formatCount(tagged)} tagged / ${formatCount(roster)} roster`;
  const level = String(node?.level ?? "");
  const itemAttrs = `role="treeitem" tabindex="${focusId === id ? "0" : "-1"}" aria-level="${depth}" aria-setsize="${size}" aria-posinset="${position}" data-treeitem data-node-id="${escapeHtml(id)}"${parentId ? ` data-parent-id="${escapeHtml(parentId)}"` : ""}`;
  let attrs = branch ? ` aria-expanded="${open}"` : "";
  if (branch) attrs += ` data-tree-branch`;
  else if (node?.group_id) attrs += ` data-group="${escapeHtml(node.group_id)}" aria-haspopup="dialog"`;
  else if (level === "not_yet_tagged") {
    const filters = rosterFilters(node);
    attrs += ` data-tree-roster="${escapeHtml(JSON.stringify(filters))}"`;
  }
  const children = branch && open
    ? `<ul role="group">${kids(node).map((child, index) => treeNodeHtml(child, expanded, depth + 1, index + 1, kids(node).length, id, focusId, allExpanded, collapsed, showDistinct)).join("")}</ul>`
    : "";
  const status = node?.group_id && node?.status ? `<span class="gv-badge gv-badge--${escapeHtml(statusKey(node.status))}">${escapeHtml(statusLabel(node.status))}</span>` : "";
  return `<li ${itemAttrs}${attrs}><div class="gv-tree-row"><span class="gv-tree-caret" aria-hidden="true">${branch ? (open ? "−" : "+") : ""}</span><span class="gv-tree-label">${escapeHtml(labelFor(node))}</span><span class="gv-tree-count">${escapeHtml(badge)}</span>${status}</div>${children}</li>`;
}

function rosterFilters(node) {
  const out = {};
  if (node?.country) out.country = node.country;
  if (node?.region && node.region !== "region_unknown") out.region = node.region;
  const parts = String(node?.id ?? "").split("/");
  if (!out.region && parts[1] === "region_unknown") out.region = "region_unknown";
  if (!out.country && parts.length >= 3) {
    const country = parts.find((part) => /^[A-Z]{2}$/.test(part));
    if (country) out.country = country;
  }
  return out;
}

function statusKey(status) {
  return status === "ambassador_tagged" ? "volunteer" : status === "reviewed" ? "reviewed" : status === "group_confirmed" ? "confirmed" : status === "cannot_determine" ? "cannot" : "not_tagged";
}
function statusLabel(status) {
  return status === "ambassador_tagged" ? "Volunteer-tagged" : status === "reviewed" ? "Reviewed" : status === "group_confirmed" ? "Confirmed by group" : status === "cannot_determine" ? "Could not be tagged from public pages" : "Not yet tagged";
}

export function groupsTreeHtml(data, state = treeHashState(), query = "") {
  const hierarchy = hierarchyData(data, state.hierarchy, state.allActivities);
  if (!hierarchy) return `<section class="gv-panel gv-tree-panel"><h2 id="gv-tree-title">Explore groups by hierarchy</h2><p class="gv-caption">The hierarchy is not available right now. The roster table remains available below.</p></section>`;
  if (query && !state.searchAllowed) {
    const entries = walk(hierarchy);
    const needle = searchKey(query.trim());
    const matches = entries.filter(({node}) => searchKey(labelFor(node)).includes(needle) || (node.group_id && searchKey(node.name).includes(needle)));
    const allowed = new Set();
    for (const {node, ancestors} of matches) {
      allowed.add(String(node.id ?? ""));
      ancestors.forEach((id) => allowed.add(id));
    }
    const branches = new Set(entries.filter(({node}) => isBranch(node)).map(({node}) => String(node.id ?? "")));
    const matchingBranches = [...allowed].filter((id) => branches.has(id));
    if (state.allExpanded) state.collapsed = (state.collapsed || []).filter((id) => !matchingBranches.includes(id));
    else state.expanded = [...new Set([...state.expanded, ...matchingBranches])];
    state.searchAllowed = allowed;
    state.searchMatchCount = matches.length;
  }
  const expanded = new Set(state.expanded);
  const collapsed = new Set(state.collapsed || []);
  const isOpen = (id) => state.allExpanded ? !collapsed.has(id) : expanded.has(id);
  const topNodes = kids(hierarchy);
  const visibleIds = [];
  const addVisible = (node) => {
    visibleIds.push(String(node.id ?? ""));
    if (isOpen(String(node.id ?? ""))) kids(node).forEach(addVisible);
  };
  topNodes.forEach(addVisible);
  const focusableIds = state.searchAllowed ? visibleIds.filter((id) => state.searchAllowed.has(id)) : visibleIds;
  const focusId = focusableIds.includes(state.focusId) ? state.focusId : (focusableIds[0] ?? "");
  return `<section class="gv-panel gv-tree-panel" aria-labelledby="gv-tree-title" id="gv-tree">
    <h2 id="gv-tree-title">Explore groups by hierarchy</h2>
    <p class="gv-caption">Browse the roster by place or plastics focus. Branch counts show tagged organisations out of the roster; untagged groups stay aggregated. Tagged groups are not a random sample.</p>
    <div class="gv-tree-controls">
      <label class="gv-field"><span>Arrange by</span><select data-tree-hierarchy aria-label="Arrange groups by"><option value="geography"${state.hierarchy === "geography" ? " selected" : ""}>Geography first</option><option value="function"${state.hierarchy === "function" ? " selected" : ""}>Function first</option><option value="centrality"${state.hierarchy === "centrality" ? " selected" : ""}>Plastics focus first</option></select></label>
      ${state.hierarchy !== "geography" ? `<label class="gv-tree-check"><input type="checkbox" data-tree-all${state.allActivities ? " checked" : ""}> Show all activities <span>(distinct counts)</span></label>` : ""}
      <label class="gv-field gv-tree-search"><span>Find a group or branch</span><input type="search" data-tree-search autocomplete="off" placeholder="Type a name" value="${escapeHtml(query)}"></label>
      <div class="gv-tree-actions"><button type="button" class="gv-btn" data-tree-expand-all>Expand all</button><button type="button" class="gv-btn" data-tree-collapse-all>Collapse all</button></div>
    </div>
    <p class="gv-tree-result" data-tree-result aria-live="polite"></p>
    <div class="gv-tree-scroll"><ul class="gv-tree" role="tree" aria-labelledby="gv-tree-title" aria-label="${escapeHtml(hierarchy.label || "Community groups")}">${topNodes.map((node, index) => treeNodeHtml(node, expanded, 1, index + 1, topNodes.length, "", focusId, state.allExpanded, collapsed, state.allActivities)).join("")}</ul></div>
  </section>`;
}

function walk(node, ancestors = [], out = []) {
  out.push({node, ancestors});
  for (const child of kids(node)) walk(child, [...ancestors, String(node.id ?? "")], out);
  return out;
}

function writeTreeHash(state) {
  const params = new URLSearchParams(location.hash.replace(/^#/, ""));
  if (state.hierarchy === "geography") params.delete("tree"); else params.set("tree", state.hierarchy);
  if (state.allActivities) params.set("tree_all", "1"); else params.delete("tree_all");
  if (state.allExpanded) params.set("tree_open", "all");
  else if (state.expanded.length) params.set("tree_open", JSON.stringify(state.expanded));
  else params.delete("tree_open");
  if (state.allExpanded && state.collapsed?.length) params.set("tree_closed", JSON.stringify(state.collapsed)); else params.delete("tree_closed");
  if (state.query) params.set("tree_find", state.query); else params.delete("tree_find");
  const value = params.toString();
  history.replaceState(null, "", `${location.pathname}${location.search}${value ? `#${value}` : ""}`);
}

// mount receives the shared group-card and roster-filter callbacks from groups.js.
export function mountGroupsTree(root, data, {onGroup, onRoster} = {}) {
  if (!data) return false;
  let state = treeHashState(location.hash);
  let query = state.query;
  let indexKey = "";
  let entries = [];
  let branchIds = new Set();
  const refreshIndex = () => {
    const key = `${state.hierarchy}:${state.allActivities}`;
    if (key === indexKey) return;
    indexKey = key;
    entries = walk(hierarchyData(data, state.hierarchy, state.allActivities) || {});
    branchIds = new Set(entries.filter(({node}) => isBranch(node)).map(({node}) => String(node.id ?? "")));
  };
  const prepareSearch = () => {
    if (!query) { state.searchAllowed = null; return; }
    refreshIndex();
    const needle = searchKey(query);
    const matches = entries.filter(({node}) => searchKey(labelFor(node)).includes(needle) || (node.group_id && searchKey(node.name).includes(needle)));
    const allowed = new Set();
    for (const {node, ancestors} of matches) {
      allowed.add(String(node.id ?? ""));
      ancestors.forEach((id) => allowed.add(id));
    }
    const matchingBranches = [...allowed].filter((id) => branchIds.has(id));
    if (state.allExpanded) state.collapsed = state.collapsed.filter((id) => !matchingBranches.includes(id));
    else state.expanded = [...new Set([...state.expanded, ...matchingBranches])];
    state.searchAllowed = allowed;
    state.searchMatchCount = matches.length;
  };
  const render = (restore = null) => {
    const old = root.querySelector("#gv-tree");
    if (!old) return;
    if (!restore) {
      const active = document.activeElement;
      if (old.contains(active)) {
        if (active.matches("[data-treeitem]")) restore = {selector: `[data-node-id="${CSS.escape(active.dataset.nodeId)}"]`};
        else if (active.matches("[data-tree-search]")) restore = {selector: "[data-tree-search]", start: active.selectionStart, end: active.selectionEnd};
        else if (active.matches("[data-tree-hierarchy]")) restore = {selector: "[data-tree-hierarchy]"};
        else if (active.matches("[data-tree-all]")) restore = {selector: "[data-tree-all]"};
        else if (active.matches("[data-tree-expand-all]")) restore = {selector: "[data-tree-expand-all]"};
        else if (active.matches("[data-tree-collapse-all]")) restore = {selector: "[data-tree-collapse-all]"};
      }
    }
    prepareSearch();
    const shell = document.createElement("div");
    shell.innerHTML = groupsTreeHtml(data, state, query);
    old.replaceWith(shell.firstElementChild);
    if (query) applySearch(query, false);
    if (restore?.selector) {
      const target = root.querySelector(`#gv-tree ${restore.selector}`);
      target?.focus();
      if (restore.start != null && target?.setSelectionRange) target.setSelectionRange(restore.start, restore.end);
    }
  };
  const persist = () => { writeTreeHash(state); render(); };
  const applySearch = (value, persistState = true) => {
    query = value.trim();
    state.query = query;
    prepareSearch();
    if (!query) {
      root.querySelectorAll("[data-treeitem]").forEach((item) => item.hidden = false);
      root.querySelector("[data-tree-result]")?.replaceChildren();
      if (persistState) writeTreeHash(state);
      return;
    }
    if (persistState) { writeTreeHash(state); render({selector: "[data-tree-search]", start: root.querySelector("[data-tree-search]")?.selectionStart, end: root.querySelector("[data-tree-search]")?.selectionEnd}); return; }
    const result = root.querySelector("[data-tree-result]");
    if (result) result.textContent = `${state.searchMatchCount.toLocaleString("en-US")} matching ${state.searchMatchCount === 1 ? "entry" : "entries"}`;
    root.querySelectorAll("[data-treeitem]").forEach((item) => item.hidden = !state.searchAllowed.has(item.dataset.nodeId));
  };
  render();
  root.addEventListener("change", (event) => {
    if (event.target.matches("[data-tree-hierarchy]")) {
      state = {...state, hierarchy: event.target.value, allActivities: event.target.value === "geography" ? false : state.allActivities, expanded: [], collapsed: [], allExpanded: false};
      persist();
    } else if (event.target.matches("[data-tree-all]")) {
      state = {...state, allActivities: event.target.checked, expanded: [], collapsed: [], allExpanded: false};
      indexKey = "";
      persist();
    }
  });
  root.addEventListener("input", (event) => {
    if (event.target.matches("[data-tree-search]")) applySearch(event.target.value);
  });
  root.addEventListener("click", (event) => {
    const item = event.target.closest("[data-treeitem]");
    if (!item) return;
    if (item.dataset.group) { onGroup?.(item.dataset.group); return; }
    if (item.dataset.treeRoster) {
      let filters = {};
      try { filters = JSON.parse(item.dataset.treeRoster); } catch { /* ignore invalid payload data */ }
      onRoster?.(filters);
      return;
    }
    if (item.hasAttribute("data-tree-branch")) {
      const id = item.dataset.nodeId;
      const open = item.getAttribute("aria-expanded") === "true";
      if (state.allExpanded) state.collapsed = open ? [...new Set([...state.collapsed, id])] : state.collapsed.filter((value) => value !== id);
      else state.expanded = open ? state.expanded.filter((value) => value !== id) : [...new Set([...state.expanded, id])];
      state.focusId = id;
      persist();
      root.querySelector(`[data-node-id="${CSS.escape(id)}"]`)?.focus();
    }
  });
  root.addEventListener("keydown", (event) => {
    const item = event.target.closest?.("[data-treeitem]");
    if (!item) return;
    const all = [...root.querySelectorAll("[data-treeitem]:not([hidden])")];
    const index = all.indexOf(item);
    let next = null;
    if (event.key === "ArrowDown") next = all[Math.min(all.length - 1, index + 1)];
    else if (event.key === "ArrowUp") next = all[Math.max(0, index - 1)];
    else if (event.key === "Home") next = all[0];
    else if (event.key === "End") next = all.at(-1);
    else if (event.key === "ArrowRight" && item.hasAttribute("data-tree-branch")) {
      if (item.getAttribute("aria-expanded") !== "true") item.click();
      else item.querySelector(":scope > [role=group] > [role=treeitem]")?.focus();
    } else if (event.key === "ArrowLeft") {
      if (item.hasAttribute("data-tree-branch") && item.getAttribute("aria-expanded") === "true") item.click();
      else if (item.dataset.parentId) root.querySelector(`[data-node-id="${CSS.escape(item.dataset.parentId)}"]`)?.focus();
    }
    else if (event.key === "Enter" || event.key === " ") item.click();
    if (next) { event.preventDefault(); next.focus(); }
    if (["ArrowDown", "ArrowUp", "Home", "End", "ArrowRight", "ArrowLeft", "Enter", " "].includes(event.key)) event.preventDefault();
  });
  root.addEventListener("click", (event) => {
    if (event.target.closest("[data-tree-expand-all]")) {
      state.allExpanded = true;
      state.expanded = [];
      state.collapsed = [];
      persist();
    } else if (event.target.closest("[data-tree-collapse-all]")) {
      state.allExpanded = false;
      state.expanded = [];
      state.collapsed = [];
      persist();
    }
  });
  root.addEventListener("focusin", (event) => {
    const item = event.target.closest?.("[data-treeitem]");
    if (!item) return;
    state.focusId = item.dataset.nodeId;
    root.querySelectorAll("[data-treeitem]").forEach((node) => node.tabIndex = node === item ? 0 : -1);
  });
  window.addEventListener("hashchange", () => { state = {...state, ...treeHashState(location.hash)}; query = state.query; render(); });
  return true;
}
