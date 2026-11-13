---
title: Institutions
---

# Institutions

<link rel="stylesheet" href="./components/institutions.css">

<div id="institutions-root">
<p class="panel-intro">Tagged-work volume is a descriptive count from the same data snapshot used by the Experts view; it is not a quality ranking. Each topic bar shows the share of topic tags across the institution's plastic-related works (a work can carry several topics).</p>
<div class="institution-toolbar">
<div id="institution-type-chips" class="institution-type-chips" role="group" aria-label="Filter institutions by type"></div>
<div class="institution-sort-row">
<div class="field"><label for="institution-sort">Sort by</label><select id="institution-sort"></select></div>
<div class="field"><label for="institution-topic-filter">Primary topic</label><select id="institution-topic-filter"></select></div>
<div class="field institution-collab-field"><label for="institution-collab"><input id="institution-collab" type="checkbox"> Include out-of-state collaborators</label></div>
</div>
<p class="data-note">California institutions only by default. Collaborators outside California appear only through works co-authored with California researchers.</p>
<details class="term-help"><summary>What do the counts and tiers mean?</summary><p>Counts use <a href="./glossary#fractional-works">fractional works</a>: each paper's credit is split among its authors' institutions. A <a href="./glossary#rank-range">rank range</a> and a <a href="./glossary#bootstrap-interval">bootstrap interval</a> show how much an institution's position could move. Institutions in the same <a href="./glossary#tier">tier</a> cannot be reliably ordered. Plastic-related works are defined in the <a href="./glossary#plastic-related">glossary</a>.</p></details>
<div id="institution-view-field" class="field" hidden><span id="institution-view-label">Leaderboard view</span><div class="institution-type-chips" role="group" aria-labelledby="institution-view-label"><button class="chip-button" type="button" data-inst-view="tiers">Tiers (fractional credit)</button><button class="chip-button" type="button" data-inst-view="list">Institution cards</button></div></div>
<p id="institution-count" class="result-count" role="status" aria-live="polite">Loading institutions…</p>
</div>
<div class="institutions-layout">
<div>
<div id="institution-tiers" hidden><p class="data-note tier-note">Institutions in the same <a href="./glossary#tier">tier</a> cannot be reliably ordered, because their <a href="./glossary#bootstrap-interval">bootstrap</a> <a href="./glossary#rank-range">rank ranges</a> overlap. Fractional credit splits each paper among its authors' institutions (<a href="./glossary#fractional-works">definition</a>); see <a href="./about">About</a> and docs/METHODS.md (Institution counts and stability).</p><div id="institution-tier-groups"></div></div>
<div id="institution-list" class="cards" aria-live="polite"></div>
</div>
<div class="institution-map-panel is-sticky">
<h2>California institution map</h2>
<p id="institution-map-hint" class="map-hint">Drag to pan, scroll or +/- to zoom, select a marker for institution details. With the map focused, arrow keys pan. Marker size follows plastic-related work count.</p>
<div class="monitoring-map-controls" role="group" aria-label="Institution map zoom"><button type="button" id="institution-zoom-in">Zoom in (+)</button><button type="button" id="institution-zoom-out">Zoom out (-)</button><button type="button" id="institution-zoom-reset">Reset view</button></div>
<div id="institution-map" class="monitoring-map institution-map" role="group" tabindex="0" aria-label="Clustered map of California institutions on a California basemap" aria-describedby="institution-map-hint"></div>
<div class="map-legend" aria-label="Map legend"><span>Institution marker</span><span class="cluster">Cluster</span></div>
<p id="institution-map-note" class="data-note"></p>
<div id="institution-map-details" class="monitoring-map-details" aria-live="polite"></div>
</div>
</div>
</div>

```js
import "./components/shared/topics.js";
import {mountInstitutions} from "./components/institutions.js";
mountInstitutions();
```
