---
title: Monitoring
---

# Monitoring

<link rel="stylesheet" href="./components/monitoring.css">

<div id="monitoring-root">
        <p id="monitoring-status" class="panel-intro">Loading verified source catalogue…</p>
        <div id="monitoring-quality-note" class="notice">
          <p class="notice-lead">Observations describe individual source samples; they do not establish statewide monitoring coverage or comparable concentrations. Blank cells are not evidence of a data gap.</p>
          <details class="notice-details"><summary>Licences, citations and caveats</summary><p id="monitoring-quality-detail"></p></details>
        </div>
        <div class="facet-controls" role="group" aria-label="Expand or collapse every section">
          <button type="button" id="monitoring-facets-expand">Expand all</button>
          <button type="button" id="monitoring-facets-collapse">Collapse all</button>
        </div>
        <details class="facet" id="facet-filters" open>
          <summary><span class="facet-title" id="monitoring-filters-heading">Filters</span><span class="facet-count" id="facet-filters-count"></span></summary>
        <form id="monitoring-filters" class="controls" aria-label="Filter monitoring sources and samples">
          <div class="field"><label for="monitoring-tier">Access tier</label><select id="monitoring-tier"><option value="">All tiers</option><option>A</option><option>B</option><option>C</option><option>D</option></select></div>
          <div class="field"><label for="monitoring-search">Source or steward</label><input id="monitoring-search" type="search" autocomplete="off"></div>
          <div class="field"><label for="monitoring-contributor">Contributor in California</label><select id="monitoring-contributor"><option value="">All / unknown</option><option value="true">Yes</option><option value="false">No</option></select></div>
          <div class="field"><label for="monitoring-matrix">Sample matrix</label><select id="monitoring-matrix"><option value="">All matrices</option></select></div>
          <div class="field"><label for="monitoring-year">Sample year</label><select id="monitoring-year"><option value="">All years</option></select></div>
          <div class="field"><label for="monitoring-region">Sample region</label><select id="monitoring-region"><option value="">All regions</option><option value="land">California land</option><option value="state_waters">California state waters</option><option value="outside">Outside California polygons</option><option value="unknown">Unknown location</option></select></div>
        </form>
        </details>
        <section aria-labelledby="monitoring-sources-heading"><details class="facet" id="facet-sources"><summary><span class="facet-title" id="monitoring-sources-heading">Source registry</span><span class="facet-count" id="facet-sources-count"></span></summary><p id="monitoring-source-count" class="result-count" role="status" aria-live="polite"></p><div id="monitoring-sources" class="monitoring-table-wrap"></div></details></section>
        <div class="monitoring-layout">
          <section class="institution-map-panel" aria-labelledby="monitoring-map-heading"><details class="facet" id="facet-map" open><summary><span class="facet-title" id="monitoring-map-heading">Sample map</span><span class="facet-count" id="facet-map-count"></span></summary><p id="monitoring-map-note" class="data-note"></p><p id="monitoring-map-hint" class="map-hint">How to use: drag to pan, scroll or +/- to zoom, select a marker for details. With the map focused, arrow keys pan.</p><div class="monitoring-map-controls" role="group" aria-label="Map extent and zoom"><button type="button" data-map-extent="statewide" aria-pressed="true">Statewide</button><button type="button" data-map-extent="sf_bay" aria-pressed="false">SF Bay</button><button type="button" id="monitoring-zoom-in">Zoom in (+)</button><button type="button" id="monitoring-zoom-out">Zoom out (-)</button><button type="button" id="monitoring-zoom-reset">Reset view</button></div><div id="monitoring-map" class="monitoring-map" role="group" tabindex="0" aria-label="Sample locations on a California basemap" aria-describedby="monitoring-map-hint"></div><div id="monitoring-map-details" class="monitoring-map-details" aria-live="polite"></div><div id="monitoring-map-legend" class="monitoring-map-legend" aria-label="Marker colours by matrix"></div></details></section>
          <section aria-labelledby="monitoring-gaps-heading"><details class="facet" id="facet-gaps"><summary><span class="facet-title" id="monitoring-gaps-heading">Data coverage by matrix, region and year</span><span class="facet-count" id="facet-gaps-count"></span></summary><p id="monitoring-gaps-note" class="data-note"></p><div id="monitoring-gaps" class="monitoring-table-wrap"></div></details></section>
          <section aria-labelledby="monitoring-samples-heading"><details class="facet" id="facet-samples"><summary><span class="facet-title" id="monitoring-samples-heading">Sample observations</span><span class="facet-count" id="facet-samples-count"></span></summary><div id="monitoring-samples" class="monitoring-table-wrap"></div></details></section>
        </div>
</div>

```js
import {mountMonitoring} from "./components/monitoring.js";
mountMonitoring();
```
