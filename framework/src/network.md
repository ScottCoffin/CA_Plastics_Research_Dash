---
title: Collaboration network
---

<link rel="stylesheet" href="./components/network.css">

<div id="network-root">
<section class="panel">
<h1>Collaboration network</h1>
<p class="panel-intro">Each dot is a California expert in the Atlas who co-authored plastic-related works. A line connects two experts who wrote at least one work together, and thicker lines mean more shared works.</p>
<p class="data-note">Colours show collaboration clusters found automatically with the Louvain community-detection method, unless you choose another colour mode. Positions come from a force-directed layout and have no geographic meaning. Counts show volume, not quality: a well-connected expert is not necessarily a better researcher. The 400 most active experts are shown.</p>
<form id="network-filters" class="controls" novalidate>
<div class="field"><label for="net-topic">Research topic</label><select id="net-topic" name="topic"><option value="">All topics</option></select></div>
<div class="field"><label for="net-sector">Institution sector</label><select id="net-sector" name="sector"><option value="">All sectors</option></select></div>
<div class="field"><label for="net-institution">Institution contains</label><input id="net-institution" name="institution" type="search" autocomplete="off" placeholder="e.g. UC Davis"></div>
<div class="field"><label for="net-year-from">From year</label><input id="net-year-from" name="year_from" type="number" inputmode="numeric" min="1900" max="2100" placeholder="Any"></div>
<div class="field"><label for="net-year-to">To year</label><input id="net-year-to" name="year_to" type="number" inputmode="numeric" min="1900" max="2100" placeholder="Any"></div>
<div class="field"><label for="net-min">Minimum co-authored works</label><input id="net-min" name="min" type="range" min="1" max="10" step="1" value="1"> <output id="net-min-out" for="net-min">1</output></div>
<div class="field field-check"><label for="net-current"><input id="net-current" name="now" type="checkbox"> Now in California only</label></div>
</form>
<div class="net-tools">
<div class="field"><label for="net-search">Find an expert</label><input id="net-search" type="search" list="net-search-list" autocomplete="off" placeholder="Type a name"><datalist id="net-search-list"></datalist></div>
<div class="field"><label for="net-colour">Colour by</label><select id="net-colour" name="colour"><option value="cluster">Collaboration cluster</option><option value="topic">Main research topic</option><option value="sector">Institution sector</option></select></div>
<div class="field"><label for="net-size">Size by</label><select id="net-size" name="size"><option value="works">Plastic-related works</option><option value="collaborators">Collaborators</option></select></div>
</div>
<div class="button-row" aria-label="Network actions">
<button id="network-reset" class="button secondary" type="button">Reset filters</button>
</div>
<div class="result-line"><p id="network-status" class="result-count" role="status" aria-live="polite">Loading network…</p></div>
<p class="data-note">To explore the chart, zoom with the buttons, the mouse wheel or a pinch. Drag the background to pan, and drag a dot to move it. Hover a dot to see its links. Click a dot to open its details beside the chart, or pick a name in the search box to centre it. The search box and the table below are the keyboard route.</p>
<div id="network-chart" class="net-chart" role="group" aria-label="Collaboration network graph of California experts. Each dot is an expert and a line joins two experts who wrote together. The table below lists the same experts.">
<div class="net-toolbar" role="toolbar" aria-label="Chart controls">
<button id="net-zoom-in" class="button secondary net-btn" type="button" data-needs-graph>Zoom in</button>
<button id="net-zoom-out" class="button secondary net-btn" type="button" data-needs-graph>Zoom out</button>
<button id="net-reset-view" class="button secondary net-btn" type="button" data-needs-graph>Reset view</button>
<button id="net-fullscreen" class="button secondary net-btn" type="button" data-needs-graph>Full screen</button>
<button id="net-layout" class="button secondary net-btn" type="button" aria-pressed="false" data-needs-graph>Re-run layout</button>
<button id="net-restore" class="button secondary net-btn" type="button" data-needs-graph>Restore saved layout</button>
</div>
<p id="network-message" class="net-message"><span class="expert-spinner" aria-hidden="true"></span>Loading network…</p>
<div class="net-body">
<div id="network-stage" class="net-stage"></div>
<aside id="network-panel" class="net-panel" aria-label="Selected expert"><p class="net-panel-note">Select a dot on the chart, or search for a name, to see that expert's collaborations here.</p></aside>
</div>
</div>
<ul id="network-legend" class="net-legend" aria-label="Legend: select a group to hide or show it"></ul>
<details id="network-table" class="net-table">
<summary>View as table</summary>
<div class="net-table-wrap">
<table>
<caption id="network-table-caption">Loading experts…</caption>
<thead><tr><th scope="col">Expert</th><th scope="col">Cluster</th><th scope="col">Collaborators</th><th scope="col">Plastic-related works</th></tr></thead>
<tbody id="network-rows"></tbody>
</table>
</div>
</details>
</section>
</div>

```js
import {mountNetwork} from "./components/network.js";
mountNetwork();
```
