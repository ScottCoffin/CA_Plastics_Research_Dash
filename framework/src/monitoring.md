---
title: Monitoring
---

<link rel="stylesheet" href="./components/monitoring.css">

<div id="monitoring-root">
  <header class="atlas-page-head">
    <span class="motif" aria-hidden="true"></span>
    <p class="atlas-page-head__eyebrow"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-drop"></use></svg>Data</p>
    <h1 id="monitoring">Monitoring</h1>
    <p class="atlas-page-head__lead">Explore the source registry and available sample observations.</p>
    <div class="atlas-page-head__meta"><span id="monitoring-status" class="atlas-pill">Loading verified source catalogue…</span></div>
  </header>

  <div id="monitoring-quality-note" class="atlas-callout atlas-callout--caution">
    <svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-alert"></use></svg>
    <p class="notice-lead">Observations describe individual source samples; they do not establish statewide monitoring coverage or comparable concentrations. Blank cells are not evidence of a data gap.</p>
    <details class="notice-details"><summary>Licences, citations and caveats</summary><p id="monitoring-quality-detail"></p></details>
  </div>

  <div class="facet-controls" role="group" aria-label="Expand or collapse every section">
    <button type="button" class="atlas-btn atlas-btn--secondary" id="monitoring-facets-expand">Expand all</button>
    <button type="button" class="atlas-btn atlas-btn--secondary" id="monitoring-facets-collapse">Collapse all</button>
  </div>

  <details class="atlas-disclosure atlas-filters" id="facet-filters" open>
    <summary><span class="atlas-filters__head"><span class="facet-title" id="monitoring-filters-heading">Filters</span><span class="facet-count" id="facet-filters-count"></span></span></summary>
    <form id="monitoring-filters" class="atlas-filters__body atlas-filters__grid" aria-label="Filter monitoring sources and samples">
      <div class="atlas-field"><label class="atlas-label" for="monitoring-tier">Access tier</label><select class="atlas-select" id="monitoring-tier"><option value="">All tiers</option><option>A</option><option>B</option><option>C</option><option>D</option></select></div>
      <div class="atlas-field"><label class="atlas-label" for="monitoring-search">Source or steward</label><div class="atlas-search"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-search"></use></svg><input class="atlas-input" id="monitoring-search" type="search" autocomplete="off"></div></div>
      <div class="atlas-field"><label class="atlas-label" for="monitoring-contributor">Contributor in California</label><select class="atlas-select" id="monitoring-contributor"><option value="">All / unknown</option><option value="true">Yes</option><option value="false">No</option></select></div>
      <div class="atlas-field"><label class="atlas-label" for="monitoring-matrix">Sample matrix</label><select class="atlas-select" id="monitoring-matrix"><option value="">All matrices</option></select></div>
      <div class="atlas-field"><label class="atlas-label" for="monitoring-year">Sample year</label><select class="atlas-select" id="monitoring-year"><option value="">All years</option></select></div>
      <div class="atlas-field"><label class="atlas-label" for="monitoring-region">Sample region</label><select class="atlas-select" id="monitoring-region"><option value="">All regions</option><option value="land">California land</option><option value="state_waters">California state waters</option><option value="outside">Outside California polygons</option><option value="unknown">Unknown location</option></select></div>
    </form>
  </details>

  <section aria-labelledby="monitoring-sources-heading">
    <details class="atlas-disclosure" id="facet-sources">
      <summary><span class="facet-title" id="monitoring-sources-heading">Source registry</span><span class="facet-count" id="facet-sources-count"></span></summary>
      <div class="atlas-disclosure__body"><p id="monitoring-source-count" class="result-count" role="status" aria-live="polite"></p><div id="monitoring-sources" class="monitoring-table-wrap"></div></div>
    </details>
  </section>

  <div class="monitoring-layout">
    <section class="atlas-card institution-map-panel" aria-labelledby="monitoring-map-heading">
      <details class="atlas-disclosure" id="facet-map" open>
        <summary><span class="facet-title" id="monitoring-map-heading">Sample map</span><span class="facet-count" id="facet-map-count"></span></summary>
        <div class="atlas-disclosure__body">
          <p id="monitoring-map-note" class="data-note"></p>
          <p id="monitoring-map-hint" class="map-hint">How to use: drag to pan, scroll or +/- to zoom, select a marker for details. With the map focused, arrow keys pan.</p>
          <div class="monitoring-map-controls" role="group" aria-label="Map extent and zoom"><button type="button" class="atlas-btn atlas-btn--secondary" data-map-extent="statewide" aria-pressed="true">Statewide</button><button type="button" class="atlas-btn atlas-btn--secondary" data-map-extent="sf_bay" aria-pressed="false">SF Bay</button><button type="button" class="atlas-btn atlas-btn--secondary" id="monitoring-zoom-in">Zoom in (+)</button><button type="button" class="atlas-btn atlas-btn--secondary" id="monitoring-zoom-out">Zoom out (-)</button><button type="button" class="atlas-btn atlas-btn--secondary" id="monitoring-zoom-reset">Reset view</button></div>
          <div id="monitoring-map" class="monitoring-map" role="group" tabindex="0" aria-label="Sample locations on a California basemap" aria-describedby="monitoring-map-hint"></div>
          <div id="monitoring-map-details" class="monitoring-map-details" aria-live="polite"></div>
          <div id="monitoring-map-legend" class="monitoring-map-legend" aria-label="Marker colours by matrix"></div>
        </div>
      </details>
    </section>
    <section aria-labelledby="monitoring-gaps-heading">
      <details class="atlas-disclosure" id="facet-gaps">
        <summary><span class="facet-title" id="monitoring-gaps-heading">Data coverage by matrix, region and year</span><span class="facet-count" id="facet-gaps-count"></span></summary>
        <div class="atlas-disclosure__body"><p id="monitoring-gaps-note" class="data-note"></p><div id="monitoring-gaps" class="monitoring-table-wrap"></div></div>
      </details>
    </section>
    <section aria-labelledby="monitoring-samples-heading">
      <details class="atlas-disclosure" id="facet-samples">
        <summary><span class="facet-title" id="monitoring-samples-heading">Sample observations</span><span class="facet-count" id="facet-samples-count"></span></summary>
        <div class="atlas-disclosure__body"><div class="monitoring-download"><button type="button" class="atlas-btn atlas-btn--primary" id="monitoring-download-csv" disabled>Download observations (CSV)</button><p id="monitoring-download-note" class="data-note" aria-live="polite"></p></div><div id="monitoring-samples" class="monitoring-table-wrap"></div></div>
      </details>
    </section>
  </div>
</div>

```js
import {mountMonitoring} from "./components/monitoring.js";
mountMonitoring();
```
