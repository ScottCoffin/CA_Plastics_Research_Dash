// Scoped panels for /groups. The map owns scope selection; this module owns the data views below it.
import {mountGroups} from "./groups.js";
import {mountGroupsCoverage} from "./groups_coverage.js";
import {mountGroupsComposition} from "./groups_composition.js";
import {mountGroupsFlows} from "./groups_flows.js";
import {mountGroupsNetwork} from "./groups_network.js";

const list = (value) => (Array.isArray(value) ? value : Array.isArray(value?.groups) ? value.groups : []);
const scopeKey = (scope) => String(scope?.key || (scope?.kind === "world" ? "world" : scope?.iso || scope?.name || scope?.id || scope?.kind || "world"));

function clearStaleGeographyFilters(groups) {
  const params = new URLSearchParams(location.hash.replace(/^#/, ""));
  const regions = new Set(groups.map((group) => String(group?.region || "region_unknown")));
  const countries = new Set(groups.map((group) => String(group?.country || "").toUpperCase()).filter(Boolean));
  if (params.has("region") && !regions.has(params.get("region"))) params.delete("region");
  if (params.has("country") && !countries.has(params.get("country").toUpperCase())) params.delete("country");
  const value = params.toString();
  history.replaceState(null, "", `${location.pathname}${location.search}${value ? `#${value}` : ""}`);
}

/** Mount the panels below the map. Call the returned updater whenever the active scope changes. */
export function mountGroupsScopePanels(root, {Plot = null, d3 = null, graph = null, precision = null} = {}) {
  if (!root) throw new Error("mountGroupsScopePanels needs a root element");
  let generation = 0;
  let activeKey = null;
  let disposeRoster = null;
  let disposeNetwork = null;
  let disposed = false;

  root.innerHTML = `<section class="gv-panel" aria-labelledby="gv-scope-coverage-title">
      <h2 id="gv-scope-coverage-title">Coverage</h2>
      <div id="groups-scope-coverage"></div>
    </section>
    <div id="groups-scope-roster"></div>
    <section class="gv-panel" aria-labelledby="gv-scope-composition-title">
      <h2 id="gv-scope-composition-title">Group composition</h2>
      <div id="groups-scope-composition"></div>
    </section>
    <section class="gv-panel" aria-labelledby="gv-scope-flows-title">
      <h2 id="gv-scope-flows-title">Group flows</h2>
      <div id="groups-scope-flows"></div>
    </section>
    <section class="gv-panel" aria-labelledby="gv-scope-network-title">
      <h2 id="gv-scope-network-title">Network</h2>
      <p class="gv-caption">This view shows tagged groups only. Assignments connect each group to its tags; co-occurrence links show tags used together.</p>
      <div id="groups-scope-network"></div>
    </section>`;
  root.classList.add("gv");
  const coverageRoot = root.querySelector("#groups-scope-coverage");
  const rosterRoot = root.querySelector("#groups-scope-roster");
  const compositionRoot = root.querySelector("#groups-scope-composition");
  const flowsRoot = root.querySelector("#groups-scope-flows");
  const networkRoot = root.querySelector("#groups-scope-network");
  const panelRoots = [coverageRoot, rosterRoot, compositionRoot, flowsRoot, networkRoot];

  const dispose = () => {
    disposeRoster?.();
    disposeRoster = null;
    disposeNetwork?.();
    disposeNetwork = null;
  };
  const rootWatch = new MutationObserver(() => {
    if (!root.isConnected && !disposed) {
      disposed = true;
      generation += 1;
      dispose();
      rootWatch.disconnect();
    }
  });
  rootWatch.observe(root.ownerDocument.documentElement, {childList: true, subtree: true});

  const update = async function update(data = {}) {
    if (disposed) return;
    const scope = data.scope || {kind: "world", key: "world", label: "World"};
    const nextKey = scopeKey(scope);
    if (activeKey === nextKey) return;
    const groups = list(data.groups);
    const current = ++generation;
    if (activeKey !== null && activeKey !== nextKey) clearStaleGeographyFilters(groups);
    activeKey = nextKey;
    dispose();
    for (const host of panelRoots) host?.replaceChildren();
    // Let any already queued scope update observe its generation before mounting listeners or WebGL.
    await Promise.resolve();
    if (current !== generation) return;

    mountGroupsCoverage(coverageRoot, {coverage: data.coverage, groups, Plot, showMap: false});
    const rosterDispose = await mountGroups(rosterRoot, {groups, coverage: data.coverage, tree: data.tree}, {showCoverage: false});
    if (current !== generation) { rosterDispose?.(); return; }
    disposeRoster = rosterDispose;

    const isWorld = scope.kind === "world";
    mountGroupsComposition(compositionRoot, {
      groups,
      precision,
      Plot,
      d3,
      precisionGlobalOnly: !isWorld,
    });
    mountGroupsFlows(flowsRoot, {flows: data.flows, groups, Plot});

    const scopedGraph = isWorld ? graph : scope.graph
      ? {...scope.graph, denominator_note: scope.denominator_note || scope.graph.denominator_note}
      : null;
    disposeNetwork = mountGroupsNetwork(networkRoot, scopedGraph, {
      onOpenGroup: (id) => {
        const params = new URLSearchParams(location.hash.replace(/^#/, ""));
        params.set("group", id);
        location.hash = params.toString();
      },
    });
  };
  update.dispose = () => {
    if (disposed) return;
    disposed = true;
    generation += 1;
    dispose();
    rootWatch.disconnect();
  };
  return update;
}
