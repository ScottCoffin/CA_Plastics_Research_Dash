---
title: Experts
---

<link rel="stylesheet" href="./components/experts.css">

<div id="experts-root">
<section id="panel-experts" class="panel">
<h1>Experts</h1>
<p class="panel-intro">Browse the author index from the latest static export. Use the filters to narrow the starting list.</p>
<form id="expert-filters" class="controls expert-controls" novalidate>
<div class="field"><label for="expert-search">Search name or ID</label><input id="expert-search" name="search" type="search" autocomplete="off" placeholder="e.g. Rochman, UC Davis"></div>
<div class="field"><label for="institution-type-filter">Institution type</label><select id="institution-type-filter" name="institution_type"><option value="">All institution types</option></select></div>
<div class="field"><label for="institution-filter">Institution</label><select id="institution-filter" name="institution"><option value="">All institutions</option></select></div>
<div class="field"><label for="expert-sort">Sort by</label><select id="expert-sort" name="sort"><option value="plastic_citations">Plastics citations</option><option value="plastic_works">Plastics works</option><option value="rising">Rising (citation momentum)</option><option value="m_quotient">m-quotient (h per career year)</option><option value="h_index">h-index</option><option value="cited_by">Total citations</option><option value="ca_works">CA works</option></select></div>
<div class="field field-check"><span class="field-check-label">Career stage</span><label for="early-filter"><input id="early-filter" name="early" type="checkbox"> Early career only <span class="detail-meta">(first paper ≤ 10 years ago)</span></label><button type="button" id="rising-preset" class="link-button" title="Early-career experts sorted by rising citation momentum">Find up-and-coming researchers</button></div>
<div class="field"><label for="tag-filter">Domain or matrix tag</label><select id="tag-filter" name="tag"><option value="">All tags</option></select></div>
<div class="field"><label for="year-from">From year</label><input id="year-from" name="year_from" type="number" inputmode="numeric" min="1900" max="2100" placeholder="Any"></div>
<div class="field"><label for="year-to">To year</label><input id="year-to" name="year_to" type="number" inputmode="numeric" min="1900" max="2100" placeholder="Any"></div>
<div class="field"><label for="ca-basis-filter">CA basis</label><select id="ca-basis-filter" name="ca_basis"><option value="">Any CA basis</option><option value="ca-led">CA-led</option><option value="ca-sampled">CA-sampled</option><option value="both">Both</option><option value="ca-affiliated">CA-affiliated</option><option value="none">No CA basis</option></select></div>
<div class="field"><label for="oa-filter">OA availability</label><select id="oa-filter" name="oa"><option value="">Any OA status</option><option value="oa">Has OA work</option><option value="closed">No OA work</option></select></div>
</form>
<div class="button-row" aria-label="Expert actions">
<button id="reset-filters" class="button secondary" type="button">Reset filters</button>
<button id="export-csv" class="button" type="button">Export filtered CSV</button>
</div>
<div class="result-line"><p id="expert-count" class="result-count" role="status" aria-live="polite">Loading experts…</p></div>
<p class="data-note">Chips show each expert's research topics with the number of their works in each topic. Citation figures are career-wide OpenAlex counts; "on plastics" counts citations of the expert's plastic-related works in this corpus, so a low share suggests plastics is a secondary focus.</p>
<h2 class="expert-sr-only">Expert list</h2>
<div id="expert-list" class="virtual-list" role="list" aria-label="Experts" aria-live="polite"><div id="expert-spacer" class="virtual-spacer"><div id="expert-rows"></div></div></div>
</section>
<div id="drawer-backdrop" class="drawer-backdrop" hidden></div>
<aside id="researcher-drawer" class="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" hidden>
<div class="drawer-header"><div><p class="eyebrow">Researcher detail</p><h2 id="drawer-title">Researcher</h2><p class="detail-meta"><a id="drawer-issue-link" href="https://github.com/ScottCoffin/CA_Plastics_Research_Dash/issues/new" target="_blank" rel="noreferrer">Is this you? Report an issue</a></p></div><button id="drawer-close" class="drawer-close" type="button">Close</button></div>
<div id="drawer-content"><p class="detail-meta">Select an expert to load their works.</p></div>
</aside>
</div>

```js
import {mountExperts} from "./components/experts.js";
mountExperts();
```
