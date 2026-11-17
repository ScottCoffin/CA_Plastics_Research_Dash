---
title: Institutions
---

<link rel="stylesheet" href="./components/institutions.css">

<div id="institutions-root">
<header class="atlas-page-head institutions-page-head">
<span class="motif" aria-hidden="true"></span>
<p class="atlas-page-head__eyebrow"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-building"></use></svg>Explore</p>
<h1>Institutions</h1>
<p class="atlas-page-head__lead">California institutions compared by plastic-related work: fractional credit, topic mix and rank ranges.</p>
<div class="atlas-page-head__meta"><span class="atlas-pill atlas-pill--brand">Tiers and rank ranges</span><a class="atlas-pill" href="./glossary#fractional-works">Fractional works in the glossary</a><a class="atlas-pill" href="./glossary#plastic-related">Plastic-related works</a></div>
</header>
<div class="atlas-callout atlas-callout--caution">
<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-alert"></use></svg>
<p class="panel-intro">Tagged-work volume is a descriptive count from the same data snapshot used by the Experts view; it is not a quality ranking. Each topic bar shows the share of topic tags across the institution's plastic-related works (a work can carry several topics).</p>
</div>
<div class="institution-toolbar">
<div id="institution-type-chips" class="institution-type-chips" role="group" aria-label="Filter institutions by type"></div>
<div class="institution-sort-row">
<div class="atlas-field"><label class="atlas-label" for="institution-sort">Sort by</label><select id="institution-sort" class="atlas-select"></select></div>
<div class="atlas-field"><label class="atlas-label" for="institution-topic-filter">Primary topic</label><select id="institution-topic-filter" class="atlas-select"></select></div>
<div class="atlas-field institution-collab-field"><label class="atlas-label" for="institution-collab"><input id="institution-collab" class="atlas-check" type="checkbox"> Include out-of-state collaborators</label></div>
</div>
<p class="data-note">California institutions only by default. Collaborators outside California appear only through works co-authored with California researchers.</p>
<details class="term-help atlas-disclosure"><summary>What do the counts and tiers mean?</summary><div class="atlas-disclosure__body"><p>Counts use <a href="./glossary#fractional-works">fractional works</a>: each paper's credit is split among its authors' institutions. A <a href="./glossary#rank-range">rank range</a> and a <a href="./glossary#bootstrap-interval">bootstrap interval</a> show how much an institution's position could move. Institutions in the same <a href="./glossary#tier">tier</a> cannot be reliably ordered. Plastic-related works are defined in the <a href="./glossary#plastic-related">glossary</a>.</p></div></details>
<div id="institution-view-field" class="atlas-field institution-view-field" hidden><div class="atlas-help-row"><span id="institution-view-label" class="atlas-label">Leaderboard view</span><button type="button" class="atlas-help" aria-label="About this view: Tiers group institutions whose rank ranges overlap, so their order cannot be reliably told apart; each tier is sorted by fractional works. Tiers are not a quality grade." data-atlas-tip="Tiers group institutions whose rank ranges overlap, so their order cannot be reliably told apart; each tier is sorted by fractional works. Tiers are not a quality grade." aria-expanded="false"><svg class="atlas-help__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9.5"/><path d="M12 11v5.5M12 7.5h.01"/></svg></button></div><div class="atlas-segmented" role="group" aria-labelledby="institution-view-label"><button type="button" data-inst-view="tiers" aria-pressed="true">Tiers (fractional credit)</button><button type="button" data-inst-view="list" aria-pressed="false">Institution cards</button></div></div>
<p id="institution-count" class="result-count" role="status" aria-live="polite">Loading institutions…</p>
</div>
<div class="institutions-layout">
<div>
<div id="institution-tiers" hidden><div class="atlas-callout atlas-callout--caution"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-info"></use></svg><p class="tier-note">Institutions in the same <a href="./glossary#tier">tier</a> cannot be reliably ordered, because their <a href="./glossary#bootstrap-interval">bootstrap</a> <a href="./glossary#rank-range">rank ranges</a> overlap. Fractional credit splits each paper among its authors' institutions (<a href="./glossary#fractional-works">definition</a>); see <a href="./about">About</a> (the methods are also in each archived release).</p></div><div id="institution-tier-groups"></div></div>
<div id="institution-list" class="cards" aria-live="polite"></div>
</div>
<div class="institution-map-panel atlas-card is-sticky">
<div class="atlas-help-row"><h2>California institution map</h2><button type="button" class="atlas-help" data-atlas-tip-align="end" aria-label="About this map: Each marker is one institution, or a group of nearby institutions at this zoom; select it to see them. Marker size follows the plastic-related work count." data-atlas-tip="Each marker is one institution, or a group of nearby institutions at this zoom; select it to see them. Marker size follows the plastic-related work count." aria-expanded="false"><svg class="atlas-help__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9.5"/><path d="M12 11v5.5M12 7.5h.01"/></svg></button></div>
<p id="institution-map-hint" class="map-hint">Drag to pan, scroll or +/- to zoom, select a marker for institution details. With the map focused, arrow keys pan. Marker size follows plastic-related work count.</p>
<div class="institution-map-controls" role="group" aria-label="Institution map zoom"><button type="button" id="institution-zoom-in" class="atlas-btn atlas-btn--icon atlas-btn--secondary" aria-label="Zoom in" title="Zoom in"><span class="map-glyph" aria-hidden="true">+</span></button><button type="button" id="institution-zoom-out" class="atlas-btn atlas-btn--icon atlas-btn--secondary" aria-label="Zoom out" title="Zoom out"><span class="map-glyph" aria-hidden="true">&minus;</span></button><button type="button" id="institution-zoom-reset" class="atlas-btn atlas-btn--icon atlas-btn--secondary" aria-label="Reset view" title="Reset view"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-home"></use></svg></button></div>
<div id="institution-map" class="monitoring-map institution-map" role="group" tabindex="0" aria-label="Clustered map of California institutions on a California basemap" aria-describedby="institution-map-hint"></div>
<div class="map-legend" aria-label="Map legend"><span>Institution marker</span><span class="cluster">Cluster</span></div>
<p id="institution-map-note" class="data-note"></p>
<div id="institution-map-details" class="monitoring-map-details" aria-live="polite"></div>
</div>
</div>
</div>

```js
import {injectIconSprite} from "./components/shared/icons.js";
import "./components/shared/topics.js";
import {mountInstitutions} from "./components/institutions.js";
import {initTooltips} from "./components/shared/tooltip.js";
injectIconSprite();
initTooltips(document);
mountInstitutions();
```
