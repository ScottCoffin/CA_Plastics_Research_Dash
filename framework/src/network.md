---
title: Collaboration network
---

<link rel="stylesheet" href="./components/network.css">

<div id="network-root">
<section class="panel">
<h1>Collaboration network</h1>
<p class="panel-intro">Each dot is a California expert in the Atlas who co-authored plastic-related works. A line connects two experts who wrote at least one work together, and thicker lines mean more shared works.</p>
<p class="data-note">Colours show collaboration clusters found automatically with the Louvain community-detection method. Positions come from a force-directed layout and have no geographic meaning. Counts show volume, not quality: a well-connected expert is not necessarily a better researcher. The 400 most active experts are shown.</p>
<form id="network-filters" class="controls" novalidate>
<div class="field"><label for="net-topic">Research topic</label><select id="net-topic" name="topic"><option value="">All topics</option></select></div>
<div class="field"><label for="net-sector">Institution sector</label><select id="net-sector" name="sector"><option value="">All sectors</option></select></div>
<div class="field"><label for="net-institution">Institution contains</label><input id="net-institution" name="institution" type="search" autocomplete="off" placeholder="e.g. UC Davis"></div>
<div class="field"><label for="net-year-from">From year</label><input id="net-year-from" name="year_from" type="number" inputmode="numeric" min="1900" max="2100" placeholder="Any"></div>
<div class="field"><label for="net-year-to">To year</label><input id="net-year-to" name="year_to" type="number" inputmode="numeric" min="1900" max="2100" placeholder="Any"></div>
<div class="field"><label for="net-min">Minimum co-authored works</label><input id="net-min" name="min" type="range" min="1" max="10" step="1" value="1"> <output id="net-min-out" for="net-min">1</output></div>
<div class="field field-check"><label for="net-current"><input id="net-current" name="now" type="checkbox"> Now in California only</label></div>
</form>
<div class="button-row" aria-label="Network actions">
<button id="network-reset" class="button secondary" type="button">Reset filters</button>
</div>
<div class="result-line"><p id="network-status" class="result-count" role="status" aria-live="polite">Loading network…</p></div>
<p class="data-note">Hover or focus an expert to see their links. Press Enter or click a dot to open their page.</p>
<div id="network-chart" class="net-chart"><p id="network-message" class="net-message"><span class="expert-spinner" aria-hidden="true"></span>Loading network…</p></div>
<ul id="network-legend" class="net-legend" aria-label="Collaboration clusters"></ul>
<details class="net-table">
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
