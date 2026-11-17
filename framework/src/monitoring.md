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
      <div class="atlas-field"><div class="atlas-help-row"><label class="atlas-label" for="monitoring-tier">Access tier</label><button type="button" class="atlas-help" aria-label="About this filter: Tiers describe how a source's data can be reached, not its quality: A is public data or a download, B a documented program whose export, subset or licence still needs review, C has no confirmed public endpoint yet, and D is evidence from literature or reports rather than a data source." data-atlas-tip="Tiers describe how a source's data can be reached, not its quality: A is public data or a download, B a documented program whose export, subset or licence still needs review, C has no confirmed public endpoint yet, and D is evidence from literature or reports rather than a data source." aria-expanded="false"><svg class="atlas-help__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9.5"/><path d="M12 11v5.5M12 7.5h.01"/></svg></button></div><select class="atlas-select" id="monitoring-tier"><option value="">All tiers</option><option>A</option><option>B</option><option>C</option><option>D</option></select></div>
      <div class="atlas-field"><label class="atlas-label" for="monitoring-search">Source or steward</label><div class="atlas-search"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-search"></use></svg><input class="atlas-input" id="monitoring-search" type="search" autocomplete="off"></div></div>
      <div class="atlas-field"><label class="atlas-label" for="monitoring-contributor">Contributor in California</label><select class="atlas-select" id="monitoring-contributor"><option value="">All / unknown</option><option value="true">Yes</option><option value="false">No</option></select></div>
      <div class="atlas-field"><label class="atlas-label" for="monitoring-matrix">Sample matrix</label><select class="atlas-select" id="monitoring-matrix"><option value="">All matrices</option></select></div>
      <div class="atlas-field"><label class="atlas-label" for="monitoring-year">Sample year</label><select class="atlas-select" id="monitoring-year"><option value="">All years</option></select></div>
      <div class="atlas-field"><label class="atlas-label" for="monitoring-region">Sample region</label><select class="atlas-select" id="monitoring-region"><option value="">All regions</option><option value="land">California land</option><option value="state_waters">California state waters</option><option value="outside">Outside California polygons</option><option value="unknown">Unknown location</option></select></div>
    </form>
  </details>

  <section class="monitoring-sources" aria-labelledby="monitoring-sources-heading">
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
          <p id="monitoring-map-hint" class="map-hint">How to use: drag to pan, scroll or +/- to zoom, select a marker for details. With the map focused, arrow keys pan. The buttons at the top right of the map change the extent, zoom, reset the view and open full screen.</p>
          <div id="monitoring-map-frame" class="monitoring-map-frame">
            <div class="monitoring-map-tools" role="group" aria-label="Map controls">
              <button type="button" class="monitoring-map-tool" data-map-extent="statewide" aria-pressed="true" aria-label="Statewide view" data-atlas-tip="Statewide view" data-atlas-tip-pos="left"><svg class="monitoring-map-tool__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M9 4.5 3.5 6.5v13l5.5-2 6 2 5.5-2v-13l-5.5 2-6-2Z"/><path d="M9 4.5v13M15 6.5v13"/></svg></button>
              <button type="button" class="monitoring-map-tool" data-map-extent="sf_bay" aria-pressed="false" aria-label="San Francisco Bay view" data-atlas-tip="San Francisco Bay view" data-atlas-tip-pos="left"><svg class="monitoring-map-tool__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 20.5s6-5.3 6-10.2a6 6 0 1 0-12 0c0 4.9 6 10.2 6 10.2Z"/><circle cx="12" cy="10.3" r="2.2"/></svg></button>
              <button type="button" class="monitoring-map-tool" id="monitoring-zoom-in" aria-label="Zoom in" data-atlas-tip="Zoom in" data-atlas-tip-pos="left"><svg class="monitoring-map-tool__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5M11 8.5v5M8.5 11h5"/></svg></button>
              <button type="button" class="monitoring-map-tool" id="monitoring-zoom-out" aria-label="Zoom out" data-atlas-tip="Zoom out" data-atlas-tip-pos="left"><svg class="monitoring-map-tool__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5M8.5 11h5"/></svg></button>
              <button type="button" class="monitoring-map-tool" id="monitoring-zoom-reset" aria-label="Reset view" data-atlas-tip="Reset view" data-atlas-tip-pos="left"><svg class="monitoring-map-tool__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="3.5"/><path d="M12 3.5v3M12 17.5v3M3.5 12h3M17.5 12h3"/></svg></button>
              <button type="button" class="monitoring-map-tool" id="monitoring-fullscreen" aria-label="Full screen" data-atlas-tip="Full screen" data-atlas-tip-pos="left" aria-controls="monitoring-map-frame"><svg class="monitoring-map-tool__icon monitoring-map-tool__icon--enter" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/></svg><svg class="monitoring-map-tool__icon monitoring-map-tool__icon--exit" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M9 4v5H4M15 4v5h5M15 20v-5h5M9 20v-5H4"/></svg></button>
            </div>
            <div id="monitoring-map" class="monitoring-map" role="group" tabindex="0" aria-label="Sample locations on a California basemap" aria-describedby="monitoring-map-hint"></div>
            <div id="monitoring-map-legend" class="monitoring-map-legend" role="group" aria-label="Marker colours by matrix"></div>
          </div>
          <div id="monitoring-map-details" class="monitoring-map-details" aria-live="polite"></div>
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
import {initTooltips} from "./components/shared/tooltip.js";
initTooltips(document);
mountMonitoring();
```
