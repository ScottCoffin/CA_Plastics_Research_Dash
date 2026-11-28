---
title: Community groups · Plastiverse Live
sidebar: false
header: false
footer: false
toc: false
pager: false
head: |
  <style>
    @font-face { font-family: "Schibsted Grotesk"; font-style: normal; font-weight: 400 700; font-display: swap; src: url("./assets/fonts/SchibstedGrotesk-Variable-latin.woff2") format("woff2"); unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD, U+2192; }
    @font-face { font-family: "Martian Mono"; font-style: normal; font-weight: 400; font-display: swap; src: url("./assets/fonts/MartianMono-Regular-latin.woff2") format("woff2"); unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD, U+2192; }
  </style>
  <meta name="theme-color" content="#000000">
---

<!-- CG-13 / CG-10 (Add-on A4): /groups. components/groups.js fills #groups-root from the groups data payloads.
     The tree payload loads independently so a tree error never blocks the roster. Styles are scoped to .gv. -->

<link rel="stylesheet" href="./components/explore.css">
<link rel="stylesheet" href="./components/groups.css">
<link rel="stylesheet" href="./components/groups_coverage.css">
<link rel="stylesheet" href="./components/groups_composition.css">
<link rel="stylesheet" href="./components/groups_flows.css">
<link rel="stylesheet" href="./components/groups_scope_map.css">

<div class="gx gv">
<a class="skip" href="#main">Skip to the content</a>
<header class="top">
  <a class="brand" href="./" aria-label="Plastiverse Live home"><svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="5"/><g><line x1="20.60" y1="13.00" x2="23.40" y2="13.00"/><line x1="20.02" y1="15.91" x2="23.72" y2="17.44"/><line x1="18.37" y1="18.37" x2="20.35" y2="20.35"/><line x1="15.91" y1="20.02" x2="17.44" y2="23.72"/><line x1="13.00" y1="20.60" x2="13.00" y2="23.40"/><line x1="10.09" y1="20.02" x2="8.56" y2="23.72"/><line x1="7.63" y1="18.37" x2="5.65" y2="20.35"/><line x1="5.98" y1="15.91" x2="2.28" y2="17.44"/><line x1="5.40" y1="13.00" x2="2.60" y2="13.00"/><line x1="5.98" y1="10.09" x2="2.28" y2="8.56"/><line x1="7.63" y1="7.63" x2="5.65" y2="5.65"/><line x1="10.09" y1="5.98" x2="8.56" y2="2.28"/><line x1="13.00" y1="5.40" x2="13.00" y2="2.60"/><line x1="15.91" y1="5.98" x2="17.44" y2="2.28"/><line x1="18.37" y1="7.63" x2="20.35" y2="5.65"/><line x1="20.02" y1="10.09" x2="23.72" y2="8.56"/></g></svg><span class="wm" aria-hidden="true">PLASTIVERSE <b>LIVE</b></span></a>
  <nav class="nav" aria-label="Main">
    <a href="./explore">Explore the data</a>
    <a href="./ambassadors">Ambassadors</a>
    <a href="./groups" aria-current="page">Community groups</a>
    <button type="button" class="btn keep" id="groups-regions-btn" aria-expanded="false" aria-controls="groups-regions-pop">Regions <svg width="10" height="7" viewBox="0 0 10 7" aria-hidden="true"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg></button>
    <a href="./california/about#how-works-are-screened">Methods</a>
    <a href="./california/about">About</a>
    <a class="btn solid keep" href="#updates">Get updates</a>
  </nav>
  <details class="gm-mobile-menu">
  <summary>Menu</summary>
  <div class="gm-mobile-links" aria-label="Site links">
    <a href="./explore">Explore the data</a>
    <a href="./groups" aria-current="page">Community groups</a>
    <a href="./ambassadors">Ambassadors</a>
    <a href="./california/">California atlas</a>
    <a href="./norway/">Norway atlas</a>
    <a href="./california/about#how-works-are-screened">Methods</a>
    <a href="./california/about">About</a>
    <a href="#updates">Get updates</a>
  </div>
</details>
</header>
<div class="pop" id="groups-regions-pop" hidden style="right:var(--pv-gut);top:64px;position:fixed;width:min(420px, calc(100vw - 32px))">
  <div class="pop-h">Regional atlases <span>2 regions</span></div>
  <a class="opt live" href="./california/"><i class="sw live"></i><span>California<small>live atlas, daily build</small></span><span class="go">Open atlas</span></a>
  <a class="opt" href="./ambassadors"><i class="sw prep"></i><span>Norway<small>in preparation</small></span><span class="go quiet">Help build it</span></a>
  <a class="opt" href="./ambassadors"><i class="sw ask"></i><span>Your region<small>opens on request</small></span><span class="go quiet">Request</span></a>
  <p class="pop-note">Every country already has an automatic profile here. A regional atlas adds local researchers, monitoring, funding and policy.</p>
</div>
<div id="main" tabindex="-1">
<div class="gv-intro">
  <h1>Community groups</h1>
  <p>Only organisations are listed. Volunteer ambassadors add tags from public evidence. Select a group to see its sources. <b>Not yet tagged</b> means the group has not been tagged yet. It never means the group has no plastics work.</p>
</div>
<div id="groups-scope-map" class="gv-root" aria-label="Community groups map"><p class="gv-status">Loading the map and scope counts…</p></div>
<div id="groups-scope-panels" class="gv-root"><p class="gv-status">Loading scope views…</p></div>
<section class="gv-panel gv-root" aria-labelledby="gv-methods-title" id="gv-methods">
<h2 id="gv-methods-title">How this list is made</h2>
<h3>Source</h3>
<p>This list of organisations was informed by Break Free From Plastic (BFFP), with permission. The Atlas is independent of Break Free From Plastic.</p>
<h3>Organisations only</h3>
<p>Only collective organisations are listed. Individuals and single-person practices, such as a freelance consultant, a sole trader, or an artist trading under their own name, are left out when the list is read and are not kept.</p>
<h3>Tags</h3>
<p>Volunteer ambassadors tag each group from the group's own public pages. Each tag is backed by a quote of at most 25 words from those pages, with a link to the source.</p>
<p>To help volunteers find a group's details faster, the tagging form shows hints from Wikidata (CC0 public domain dedication) and links to official charity registers (United States Internal Revenue Service, Charity Commission for England and Wales, Canada Revenue Agency, Australian Charities and Not-for-profits Commission). A hint is never published as a tag: a volunteer confirms every value on the group's own pages.</p>
<p>Untagged groups appear only in the roster table and the counts. The badges mean: <b>Volunteer-tagged</b>, an ambassador tag from public evidence; <b>Reviewed</b>, checked by a reviewer; <b>Confirmed by group</b>, the group has confirmed its own tags.</p>
<h3>Corrections and removal</h3>
<p>Anyone can ask for a correction, and a group can ask to be removed. A removal request sent from the group's own web domain is honoured within 14 days and takes precedence over ambassador tags. Other corrections are checked by a reviewer.</p>
<p>To ask for a correction or removal, write to <b>theplastiverse@gmail.com</b> with the group name and what should change.</p>
</section>
</div>

<footer class="foot" id="updates">
  <div><img src="./assets/landing/logo_564.webp" width="282" height="247" alt="Plastiverse Live logo: scattered plastic fragments flow into a bright node and a network of research" loading="lazy"></div>
  <div><b>Get updates</b><br>Weekly email, <a href="./feed.xml">RSS feed</a>, <a href="https://ntfy.sh/plastiverse-california" rel="noreferrer">ntfy alerts</a>.</div>
  <div><b>Plastiverse Live</b><br>Created by <a href="https://scottcoff.in" rel="noreferrer">Scott Coffin</a>. Not a State product.</div>
</footer>
</div>

```js
import {globalDataUrl as payloadUrl, loadJson as loadPayload, siteRoot} from "./components/atlas.js";
import {mountGroupsScopeMap} from "./components/groups_scope_map.js";
import {mountGroupsScopePanels} from "./components/groups_scope_panels.js";

const shellEvents = new AbortController();
const regionsButton = document.getElementById("groups-regions-btn");
const regionsPopover = document.getElementById("groups-regions-pop");
const closeRegions = () => { regionsPopover.hidden = true; regionsButton.setAttribute("aria-expanded", "false"); };
regionsButton.addEventListener("click", () => {
  const open = regionsPopover.hidden;
  regionsPopover.hidden = !open;
  regionsButton.setAttribute("aria-expanded", String(open));
}, {signal: shellEvents.signal});
regionsPopover.addEventListener("click", (event) => { if (event.target.closest("a")) closeRegions(); }, {signal: shellEvents.signal});
document.addEventListener("pointerdown", (event) => {
  if (!regionsPopover.hidden && !regionsPopover.contains(event.target) && !regionsButton.contains(event.target)) closeRegions();
}, {signal: shellEvents.signal});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !regionsPopover.hidden) { closeRegions(); regionsButton.focus(); }
}, {signal: shellEvents.signal});

const [groupsPayload, coveragePayload, scopesPayload, explorePayload, treePayload, flowsPayload, graphPayload, precisionPayload, worldMap] = await Promise.all([
  loadPayload("groups/groups.json", {url: payloadUrl}).catch(() => null),
  loadPayload("groups/coverage.json", {url: payloadUrl}).catch(() => null),
  loadPayload("groups/scopes.json", {url: payloadUrl}).catch(() => null),
  loadPayload("explore.json", {url: payloadUrl}).catch(() => null),
  loadPayload("groups/groups_tree.json", {url: payloadUrl}).catch(() => null),
  loadPayload("groups/flows.json", {url: payloadUrl}).catch(() => null),
  loadPayload("groups/groups_graph.json", {url: payloadUrl}).catch(() => null),
  loadPayload("groups/precision_card.json", {url: payloadUrl}).catch(() => null),
  fetch(new URL("assets/world/world.json", siteRoot()), {cache: "no-cache"}).then((r) => r.ok ? r.json() : null).catch(() => null),
]);
const groupsAll = groupsPayload?.groups ?? [];
const updateScopePanels = mountGroupsScopePanels(document.getElementById("groups-scope-panels"), {
  Plot, d3, graph: graphPayload, precision: precisionPayload,
});
const updateForScope = async (scope) => {
  const ids = Array.isArray(scope?.group_ids) ? new Set(scope.group_ids) : null;
  const groups = ids ? groupsAll.filter((group) => ids.has(group.group_id)) : groupsAll;
  await updateScopePanels({
    scope, groups,
    coverage: scope?.coverage ?? coveragePayload,
    tree: scope?.tree ?? treePayload,
    flows: scope?.flows ?? flowsPayload,
  });
};
let groupsMap = null;
if (scopesPayload && worldMap) {
  groupsMap = mountGroupsScopeMap(document.getElementById("groups-scope-map"), {
    world: worldMap, scopes: scopesPayload, explore: explorePayload, coverage: coveragePayload,
    onScope: updateForScope,
  });
} else {
  document.getElementById("groups-scope-map").innerHTML = '<p class="gv-status">The interactive map is unavailable. Group views show the world scope.</p>';
  const worldScope = scopesPayload?.scopes?.find((scope) => scope.key === "world") || {key: "world", kind: "world", label: "World"};
  await updateForScope(worldScope);
}
void invalidation.then(() => {
  shellEvents.abort();
  groupsMap?.dispose();
  updateScopePanels.dispose?.();
});
```
