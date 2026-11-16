---
title: Experts
---

<link rel="stylesheet" href="./components/experts.css">

<div id="experts-root">
<header class="atlas-page-head experts-page-head">
<div class="motif" aria-hidden="true"></div>
<p class="atlas-page-head__eyebrow">${icon("person")} Explore</p>
<h1>Experts</h1>
<p class="atlas-page-head__lead">Explore California-linked researchers and plastics topics. Filter the index or share a focused view by URL.</p>
<div class="atlas-page-head__meta">
<span class="atlas-pill atlas-pill--brand">${icon("person")} Research profiles</span>
<span class="atlas-pill">Filters are shareable by URL</span>
<a class="atlas-pill" href="./glossary#plastic-related">Expert terms in the glossary</a>
</div>
</header>

<section id="panel-experts" aria-label="Experts">
<section class="atlas-filters" aria-labelledby="expert-filters-heading">
<div class="atlas-filters__head">
<h2 id="expert-filters-heading">Filters</h2>
<span id="expert-filter-count" class="atlas-filters__count" aria-live="polite">0 on</span>
<button id="clear-all-filters" class="atlas-btn atlas-btn--ghost" type="button">Clear all</button>
</div>
<form id="expert-filters" class="atlas-filters__body" novalidate>
<div class="atlas-filters__grid expert-primary-filters">
<div class="atlas-field">
<label class="atlas-label" for="expert-search">Search name or ID</label>
<div class="atlas-search">${icon("search")}<input id="expert-search" class="atlas-input" name="search" type="search" autocomplete="off" placeholder="e.g. Rochman, UC Davis"></div>
</div>
<div class="atlas-field">
<label class="atlas-label" for="tag-filter">Domain or matrix tag</label>
<select id="tag-filter" class="atlas-select" name="tag"><option value="">All tags</option></select>
</div>
<div class="atlas-field">
<label class="atlas-label" for="institution-type-filter">Institution type</label>
<select id="institution-type-filter" class="atlas-select" name="institution_type"><option value="">All institution types</option></select>
</div>
<div class="atlas-field">
<label class="atlas-label" for="expert-sort">Sort by</label>
<select id="expert-sort" class="atlas-select" name="sort"><option value="plastic_citations">Plastics citations</option><option value="plastic_works">Plastics works</option><option value="rising">Rising (citation momentum)</option><option value="m_quotient">m-quotient (h per career year)</option><option value="h_index">h-index</option><option value="cited_by">Total citations</option><option value="ca_works">CA works</option></select>
</div>
</div>
<details id="expert-more-filters" class="atlas-filters__more">
<summary>More filters <span>(7)</span></summary>
<div class="atlas-filters__grid expert-more-grid">
<div class="atlas-field">
<label class="atlas-label" for="institution-filter">Institution</label>
<select id="institution-filter" class="atlas-select" name="institution"><option value="">All institutions</option></select>
</div>
<div class="atlas-field">
<label for="now-filter"><span class="atlas-label"><a href="./glossary#current-affiliation">Current affiliation</a></span></label>
<select id="now-filter" class="atlas-select" name="now"><option value="">Any</option><option value="ca">In California now</option><option value="outside">Outside California now</option><option value="unknown">Unknown</option></select>
</div>
<div class="atlas-field expert-career-field">
<span class="atlas-label">Career stage</span>
<label class="expert-check-line" for="early-filter"><input id="early-filter" class="atlas-check" name="early" type="checkbox"> Early career only <span class="atlas-hint">(first paper ≤ 10 years ago)</span></label>
<button type="button" id="rising-preset" class="atlas-btn atlas-btn--ghost" title="Early-career experts sorted by rising citation momentum">Find up-and-coming researchers</button>
</div>
<div class="atlas-field">
<label class="atlas-label" for="year-from">From year</label>
<input id="year-from" class="atlas-input" name="year_from" type="number" inputmode="numeric" min="1900" max="2100" placeholder="Any">
</div>
<div class="atlas-field">
<label class="atlas-label" for="year-to">To year</label>
<input id="year-to" class="atlas-input" name="year_to" type="number" inputmode="numeric" min="1900" max="2100" placeholder="Any">
</div>
<div class="atlas-field">
<label class="atlas-label" for="ca-basis-filter">CA basis</label>
<select id="ca-basis-filter" class="atlas-select" name="ca_basis"><option value="">Any CA basis</option><option value="ca-led">CA-led</option><option value="ca-sampled">CA-sampled</option><option value="both">Both</option><option value="ca-affiliated">CA-affiliated</option><option value="none">No CA basis</option></select>
</div>
<div class="atlas-field">
<label class="atlas-label" for="oa-filter">OA availability</label>
<select id="oa-filter" class="atlas-select" name="oa"><option value="">Any OA status</option><option value="oa">Has OA work</option><option value="closed">No OA work</option></select>
</div>
</div>
</details>
</form>
<div id="expert-active-filters" class="atlas-active-filters" aria-label="Active filters" aria-live="polite"></div>
</section>

<div class="button-row" aria-label="Expert actions">
<button id="reset-filters" class="atlas-btn atlas-btn--secondary" type="button">Reset filters</button>
<button id="export-csv" class="atlas-btn atlas-btn--primary" type="button">${icon("download")} Export filtered CSV</button>
</div>
<div class="atlas-result-line">
<p id="expert-count" role="status" aria-live="polite">Loading experts…</p>
<p class="data-note volume-caption">Counts show volume, not strength; the list does not rank expertise.</p>
</div>

<h2 class="expert-sr-only">Expert list</h2>
<div id="expert-state" class="expert-state" tabindex="-1"><p class="expert-state-message"><span class="expert-spinner" aria-hidden="true"></span>Loading experts…</p></div>
<div id="expert-list" class="virtual-list" role="list" aria-label="Experts" aria-live="polite" hidden><div id="expert-spacer" class="virtual-spacer"><div id="expert-rows"></div></div></div>

<details class="atlas-disclosure term-help">
<summary>What do the expert terms mean?</summary>
<div class="atlas-disclosure__body">
<p class="expert-term-note">Chips show each expert's research topics with the number of their works in each topic. Citation figures are career-wide OpenAlex counts; "on plastics" counts citations of the expert's plastic-related works in this corpus, so a low share suggests plastics is a secondary focus.</p>
<ul>
<li><a href="./glossary#m-quotient">m-quotient</a>: h-index divided by career length in years.</li>
<li><a href="./glossary#rising-percentile">Rising percentile</a>: rank of citation momentum among scored experts (those with at least 10 plastics citations in the last 5 complete years).</li>
<li><a href="./glossary#plastic-related">Plastic-related</a> works, and the <a href="./glossary#ca-led">CA-led</a> and <a href="./glossary#ca-sampled">CA-sampled</a> bases for the CA basis filter.</li>
<li><a href="./glossary#current-affiliation">Current affiliation</a>: where the expert's latest affiliations are. "Outside California now" means none is a California institution in the Atlas registry.</li>
<li><a href="./glossary#matrix">Matrix</a>: the sampled medium; the tag filter uses provisional work tags.</li>
</ul>
</div>
</details>
</section>
<div id="drawer-backdrop" class="drawer-backdrop" hidden></div>
<aside id="researcher-drawer" class="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" hidden>
<header class="atlas-page-head drawer-header">
<div class="motif" aria-hidden="true"></div>
<div class="drawer-heading">
<p class="atlas-page-head__eyebrow">${icon("person")} Researcher detail</p>
<h2 id="drawer-title">Researcher</h2>
<p class="atlas-page-head__lead"><a id="drawer-issue-link" class="atlas-btn atlas-btn--ghost" href="https://github.com/ScottCoffin/CA_Plastics_Research_Dash/issues/new" target="_blank" rel="noreferrer">Is this you? Report an issue</a></p>
</div>
<button id="drawer-close" class="atlas-btn atlas-btn--secondary" type="button">Close</button>
</header>
<div id="drawer-content"><p class="detail-meta">Select an expert to load their works.</p></div>
</aside>
</div>

```js
import {icon} from "./components/shared/icons.js";
import {mountExperts} from "./components/experts.js";
mountExperts();
```
