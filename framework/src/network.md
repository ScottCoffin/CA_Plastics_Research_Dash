---
title: Collaboration network
---

<div class="net-page-head">
<header class="atlas-page-head">
<p class="atlas-page-head__eyebrow"><svg class="icon" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><use href="#i-network"></use></svg> Explore</p>
<h1>Collaboration network</h1>
<p class="atlas-page-head__lead">Each dot represents an Atlas expert who co-authored plastic-related work, and each line connects co-authors. The network shows relationships in the current data snapshot; it is not a geographic map or a measure of research quality.</p>
</header>
</div>
<p class="atlas-callout atlas-callout--info"><svg class="icon" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><use href="#i-info"></use></svg> <span><strong>Volume note.</strong> The network shows the 400 most active experts. Counts show volume, not quality: a well-connected expert is not necessarily a better researcher.</span></p>

<link rel="stylesheet" href="./components/network.css">

<section class="net-page" aria-label="Collaboration network explorer">
<section class="atlas-filters" aria-labelledby="network-filters-heading">
<div class="atlas-filters__head">
<h2 id="network-filters-heading">Network filters</h2>
<button id="network-reset" class="atlas-btn atlas-btn--secondary" type="button">Reset filters</button>
</div>
<div class="atlas-filters__body">
<div class="atlas-filters__grid net-primary-grid">
<div class="atlas-field">
<label class="atlas-label" for="net-search">Find an expert</label>
<span class="atlas-search" id="net-search-wrap"><input class="atlas-input" id="net-search" type="search" list="net-search-list" autocomplete="off" placeholder="Type a name"><datalist id="net-search-list"></datalist></span>
</div>
<div class="atlas-field">
<label class="atlas-label" for="net-colour">Colour by</label>
<select class="atlas-select" id="net-colour" name="colour"><option value="cluster">Collaboration cluster</option><option value="topic">Main research topic</option><option value="sector">Institution sector</option></select>
</div>
<div class="atlas-field">
<label class="atlas-label" for="net-size">Size by</label>
<select class="atlas-select" id="net-size" name="size"><option value="works">Plastic-related works</option><option value="collaborators">Collaborators</option></select>
</div>
<form id="network-filters" class="net-filter-form" novalidate>
<div class="atlas-field">
<label class="atlas-label" for="net-topic">Research topic</label>
<select class="atlas-select" id="net-topic" name="topic"><option value="">All topics</option></select>
</div>
<details class="atlas-filters__more">
<summary>More filters (6)</summary>
<div class="atlas-filters__grid net-more-grid">
<div class="atlas-field"><label class="atlas-label" for="net-sector">Institution sector</label><select class="atlas-select" id="net-sector" name="sector"><option value="">All sectors</option></select></div>
<div class="atlas-field"><label class="atlas-label" for="net-institution">Institution contains</label><input class="atlas-input" id="net-institution" name="institution" type="search" autocomplete="off" placeholder="e.g. UC Davis"></div>
<div class="atlas-field"><label class="atlas-label" for="net-year-from">From year</label><input class="atlas-input" id="net-year-from" name="year_from" type="number" inputmode="numeric" min="1900" max="2100" placeholder="Any"></div>
<div class="atlas-field"><label class="atlas-label" for="net-year-to">To year</label><input class="atlas-input" id="net-year-to" name="year_to" type="number" inputmode="numeric" min="1900" max="2100" placeholder="Any"></div>
<div class="atlas-field"><label class="atlas-label" for="net-min">Minimum co-authored works</label><div class="net-range-row"><input class="net-range" id="net-min" name="min" type="range" min="1" max="10" step="1" value="1"><output id="net-min-out" class="net-range-out" for="net-min">1</output></div></div>
<div class="atlas-field atlas-field--check"><label class="atlas-label" for="net-current"><input class="atlas-check" id="net-current" name="now" type="checkbox"> Now in California only</label></div>
</div>
</details>
</form>
</div>
</div>

<div class="atlas-result-line">
<p id="network-status" class="result-count" role="status" aria-live="polite">Loading network…</p>
</div>

<details id="network-how-to" class="atlas-disclosure">
<summary>How to read the network</summary>
<div class="atlas-disclosure__body">
<p>Colours show collaboration clusters found automatically with the Louvain community-detection method, unless you choose another colour mode. Positions come from a force-directed layout and have no geographic meaning.</p>
<p>Each cluster is named after the institution and research topic that most of its members share, when one is common enough; a cluster with no shared name stays "Cluster n". The legend and table show these names. In cluster colour mode the chart names up to eight of the largest clusters.</p>
<p>Zoom with the buttons, mouse wheel, or a pinch. Drag the background to pan and drag a dot to move it. Hover a dot to see its links. Click a dot to open its details beside the chart, or choose a name in the search box to centre it. The search box and table below are the keyboard route.</p>
</div>
</details>

<div class="atlas-help-row net-chart-heading"><h2 id="network-graph-heading">Network graph</h2><button type="button" class="atlas-help" aria-label="About this network: Each dot is an expert, and each line joins two experts who co-authored plastic-related work; thicker lines mean more shared works. Clusters are found automatically (Louvain) and named after the institution and topic most of their members share, and the force-directed layout (ForceAtlas2) has no geographic meaning." data-atlas-tip="Each dot is an expert, and each line joins two experts who co-authored plastic-related work; thicker lines mean more shared works. Clusters are found automatically (Louvain) and named after the institution and topic most of their members share, and the force-directed layout (ForceAtlas2) has no geographic meaning." aria-expanded="false"><svg class="atlas-help__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9.5"/><path d="M12 11v5.5M12 7.5h.01"/></svg></button></div>
<div id="network-chart" class="net-chart" role="group" aria-label="Collaboration network graph of California experts. Each dot is an expert and a line joins two experts who wrote together. The table below lists the same experts.">
<p id="network-message" class="net-message"><span class="expert-spinner" aria-hidden="true"></span>Loading network…</p>
<div class="net-body">
<div id="network-stage" class="net-stage"></div>
<div class="net-toolbar" role="toolbar" aria-label="Chart controls">
<button id="net-zoom-in" class="atlas-btn atlas-btn--secondary atlas-btn--icon net-btn" type="button" aria-label="Zoom in" data-tooltip="Zoom in" data-needs-graph></button>
<button id="net-zoom-out" class="atlas-btn atlas-btn--secondary atlas-btn--icon net-btn" type="button" aria-label="Zoom out" data-tooltip="Zoom out" data-needs-graph></button>
<button id="net-reset-view" class="atlas-btn atlas-btn--secondary atlas-btn--icon net-btn" type="button" aria-label="Reset view" data-tooltip="Reset view" data-needs-graph></button>
<button id="net-fullscreen" class="atlas-btn atlas-btn--secondary atlas-btn--icon net-btn" type="button" aria-label="Full screen" data-tooltip="Full screen" data-needs-graph></button>
<button id="net-layout" class="atlas-btn atlas-btn--secondary atlas-btn--icon net-btn" type="button" aria-label="Re-run layout" data-tooltip="Re-run layout" aria-pressed="false" data-needs-graph></button>
<button id="net-restore" class="atlas-btn atlas-btn--secondary atlas-btn--icon net-btn" type="button" aria-label="Restore saved layout" data-tooltip="Restore saved layout" data-needs-graph></button>
</div>
<section id="network-panel" class="net-panel atlas-card" aria-label="Selected expert"><p class="net-panel-note">Select a dot on the chart, or search for a name, to see that expert's collaborations here.</p></section>
</div>
</div>

<ul id="network-legend" class="net-legend" aria-label="Legend: select a group to hide or show it"></ul>
<details id="network-table" class="net-table atlas-disclosure">
<summary>View as table</summary>
<div class="net-table-wrap atlas-table-wrap">
<table class="atlas-table">
<caption id="network-table-caption">Loading experts…</caption>
<thead><tr><th scope="col">Expert</th><th scope="col">Cluster</th><th scope="col">Collaborators</th><th scope="col">Plastic-related works</th></tr></thead>
<tbody id="network-rows"></tbody>
</table>
</div>
</details>
</section>

```js
import {mountNetwork} from "./components/network.js";
import {initTooltips} from "./components/shared/tooltip.js";
initTooltips(document);
mountNetwork();
```
