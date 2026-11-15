---
title: Shared components | CA Plastics Research Atlas
head: '<meta name="robots" content="noindex, nofollow">'
---

```js
import {icon} from "./components/shared/icons.js";
import "./components/shared/topics.js";
```

<div class="atlas-page-head">
  <span class="motif" aria-hidden="true"></span>
  <p class="atlas-page-head__eyebrow">${icon("grid")} Reference</p>
  <h1>Shared components</h1>
  <p class="atlas-page-head__lead">A living reference for the visual pieces used across the CA Plastics Research Atlas. Examples use the Atlas snapshot and remain separate from the research views.</p>
  <div class="atlas-page-head__meta">
    <span class="atlas-pill atlas-pill--brand">${icon("check")} <strong>15</strong> components</span>
    <span class="atlas-pill">${icon("calendar")} Snapshot: 13 November 2026</span>
    <a class="atlas-pill" href="./glossary">${icon("book")} Atlas glossary</a>
  </div>
</div>

<p class="atlas-callout atlas-callout--info">${icon("info")} <span><strong>Reference page.</strong> Controls below show their appearance and labels; they do not filter, submit, or change Atlas data.</span></p>

## Pills and buttons

<div class="atlas-card">
  <p><span class="atlas-pill atlas-pill--brand">${icon("person")} <strong>2,614</strong> experts</span> <span class="atlas-pill">California-connected research</span></p>
  <div class="atlas-demo-row" role="group" aria-label="Button examples">
    <button class="atlas-btn atlas-btn--primary" type="button">${icon("search")} Browse experts</button>
    <button class="atlas-btn atlas-btn--secondary" type="button">${icon("download")} Download table</button>
    <button class="atlas-btn atlas-btn--ghost" type="button">View methods</button>
    <button class="atlas-btn atlas-btn--secondary atlas-btn--icon" type="button" aria-label="Open Atlas help">${icon("info")}</button>
  </div>
</div>

## Fields and filter panel

<section class="atlas-filters" aria-labelledby="styleguide-filter-title">
  <div class="atlas-filters__head">
    <h2 id="styleguide-filter-title">Filters</h2>
    <span class="atlas-filters__count">2 on</span>
    <button class="atlas-btn atlas-btn--ghost" type="button">Clear all</button>
  </div>
  <div class="atlas-filters__body">
    <div class="atlas-filters__grid">
      <label class="atlas-field">
        <span class="atlas-label">Topic</span>
        <span class="atlas-search">${icon("search")}<input type="search" value="microplastics" aria-label="Search topics"></span>
        <span class="atlas-hint">Search the Atlas topic vocabulary.</span>
      </label>
      <label class="atlas-field">
        <span class="atlas-label">Institution</span>
        <select class="atlas-select" aria-label="Institution"><option>All institutions</option><option>University of California, Davis</option></select>
        <span class="atlas-hint">Choose an institution in the registry.</span>
      </label>
      <label class="atlas-field">
        <span class="atlas-label">Work title or DOI</span>
        <input class="atlas-input" type="search" placeholder="Search publications" aria-label="Work title or DOI">
        <span class="atlas-hint">This example field is not connected to the data.</span>
      </label>
    </div>
    <label class="atlas-field atlas-field--check">
      <input class="atlas-check" type="checkbox" checked>
      <span class="atlas-label">California-led work</span>
    </label>
    <details class="atlas-filters__more" open>
      <summary>More filters (3)</summary>
      <div class="atlas-filters__grid">
        <label class="atlas-field"><span class="atlas-label">Year from</span><input class="atlas-input" type="number" value="2018"></label>
        <label class="atlas-field"><span class="atlas-label">Year to</span><input class="atlas-input" type="number" value="2026"></label>
        <label class="atlas-field"><span class="atlas-label">Evidence type</span><select class="atlas-select"><option>All types</option><option>Peer-reviewed article</option></select></label>
      </div>
    </details>
    <div class="atlas-active-filters" role="group" aria-label="Active filters">
      <span class="atlas-filter-chip">Topic: microplastics <button type="button" aria-label="Remove Topic filter">${icon("x")}</button></span>
      <span class="atlas-filter-chip">From: 2018 <button type="button" aria-label="Remove Year filter">${icon("x")}</button></span>
    </div>
  </div>
</section>

## Result line and callouts

<p class="atlas-result-line"><span>1,205 of 2,614 experts</span><span class="atlas-result-line__caption">Matching the current example filters</span></p>

<p class="atlas-callout atlas-callout--info">${icon("info")} <span><strong>Volume note.</strong> Counts describe indexed works in the current public snapshot.</span></p>
<p class="atlas-callout atlas-callout--caution">${icon("alert")} <span><strong>Interpret with care.</strong> Topic labels are screening metadata, not a validated ranking of pollution or research quality.</span></p>
<p class="atlas-callout atlas-callout--new">${icon("spark")} <span><strong>Recently refreshed.</strong> New records are incorporated through the Atlas review and release process.</span></p>
<p class="atlas-callout atlas-callout--dev">${icon("tools")} <span><strong>In development.</strong> This area is being prepared for a later release.</span></p>

## Badges and topic chips

<div class="atlas-card">
  <p><span class="atlas-badge atlas-badge--good">${icon("check")} Verified source</span> <span class="atlas-badge atlas-badge--accent">${icon("spark")} New in this snapshot</span> <span class="atlas-badge atlas-badge--muted">${icon("info")} Provisional label</span> <span class="atlas-badge">${icon("external")} External source</span></p>
  <p><span class="topic-chip" data-tag="occurrence_and_monitoring" style="--topic:#2a78d6"><span class="topic-dot" aria-hidden="true"></span>Occurrence &amp; monitoring</span> <span class="topic-chip hatch" data-tag="risk_assessment" style="--topic:#6250d6"><span class="topic-dot" aria-hidden="true"></span>Risk assessment</span> <span class="topic-chip matrix" data-tag="matrix:marine">Marine</span></p>
  <p class="atlas-hint">Topic chips keep their existing topic vocabulary and colour mapping.</p>
</div>

## Stat tiles

<dl class="atlas-kpis" aria-label="Atlas snapshot statistics">
  <div class="atlas-kpi"><dt class="atlas-kpi__label">${icon("person")} Experts</dt><dd class="atlas-kpi__value">2,614</dd><dd class="atlas-kpi__note">California-connected researchers</dd></div>
  <div class="atlas-kpi"><dt class="atlas-kpi__label">${icon("book")} Works</dt><dd class="atlas-kpi__value">18,420</dd><dd class="atlas-kpi__note">Indexed publication records</dd></div>
  <div class="atlas-kpi atlas-kpi--loading" aria-hidden="true"><dt class="atlas-kpi__label">Loading</dt><dd class="atlas-kpi__value">&mdash;</dd><dd class="atlas-kpi__note">Reserved space</dd></div>
</dl>

## Cards

<div class="atlas-demo-cards">
  <a class="atlas-entry" href="./experts">
    <span class="atlas-entry__icon">${icon("person")}</span>
    <span class="atlas-entry__body"><span class="atlas-entry__title">Explore experts</span><span class="atlas-entry__text">Browse researchers connected to California plastics work and open an expert profile.</span><span class="atlas-entry__meta">2,614 researchers</span></span>
  </a>
  <a class="atlas-task" href="./evidence">
    <span class="atlas-entry__icon">${icon("grid")}</span>
    <span class="atlas-task__body"><span class="atlas-task__title">Review the evidence</span><span class="atlas-task__text">Compare publication records and see how provisional topic labels are applied.</span></span>
  </a>
  <article class="atlas-card"><h3>Source context</h3><p>OpenAlex provides public bibliographic and affiliation metadata for the research views.</p></article>
</div>

## Table

<div class="atlas-table-wrap" role="region" aria-label="Example institution counts" tabindex="0">
  <table class="atlas-table">
    <caption>Works associated with selected California institutions</caption>
    <thead><tr><th scope="col">Institution</th><th scope="col" class="r">Works</th><th scope="col">Leading topic</th></tr></thead>
    <tbody><tr><td>University of California, Davis</td><td class="r">1,842</td><td>microplastics</td></tr><tr><td>University of California, San Diego</td><td class="r">1,506</td><td>marine debris</td></tr></tbody>
  </table>
</div>

## Chart card

<section class="atlas-chart" aria-labelledby="styleguide-chart-title">
  <div class="atlas-chart__head">
    <div><h2 id="styleguide-chart-title">Works by publication year</h2><p class="atlas-chart__source">Source: public OpenAlex records in this Atlas snapshot.</p></div>
    <div class="atlas-segmented" role="group" aria-label="Chart display mode"><button type="button" aria-pressed="true">Chart</button><button type="button" aria-pressed="false">Table</button></div>
  </div>
  <div class="atlas-chart__body">
    <svg viewBox="0 0 520 140" role="img" aria-label="Example chart showing publication works rising over time" style="display:block; width:100%; height:auto; color:var(--atlas-brand);">
      <path d="M24 118H500M24 20V118" fill="none" stroke="var(--atlas-line)" stroke-width="2"></path>
      <path d="m32 104 75-15 75 4 75-30 75 9 75-42 75-15" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>
      <g fill="currentColor"><circle cx="32" cy="104" r="4"></circle><circle cx="107" cy="89" r="4"></circle><circle cx="182" cy="93" r="4"></circle><circle cx="257" cy="63" r="4"></circle><circle cx="332" cy="72" r="4"></circle><circle cx="407" cy="30" r="4"></circle><circle cx="482" cy="15" r="4"></circle></g>
    </svg>
    <p class="atlas-caption">Illustrative shape only; a live chart also exposes its equivalent data table.</p>
    <details class="atlas-disclosure">
      <summary>${icon("grid")} View chart data as a table</summary>
      <div class="atlas-disclosure__body"><div class="atlas-table-wrap" role="region" aria-label="Example chart data" tabindex="0"><table class="atlas-table"><caption>Demonstration values for the chart control</caption><thead><tr><th scope="col">Year</th><th scope="col" class="r">Illustrative works</th></tr></thead><tbody><tr><td>2018</td><td class="r">420</td></tr><tr><td>2022</td><td class="r">680</td></tr><tr><td>2026</td><td class="r">940</td></tr></tbody></table></div></div>
    </details>
  </div>
</section>

## Disclosure and skeletons

<details class="atlas-disclosure">
  <summary>${icon("chevron")} About this page</summary>
  <div class="atlas-disclosure__body"><p>This Atlas view combines public bibliographic records with California institution resolution. Read the <a href="./about">method and limitations</a> before interpreting counts.</p></div>
</details>

<div class="atlas-card">
  <div class="atlas-skeleton atlas-skeleton--title" aria-hidden="true"></div>
  <p class="atlas-skeleton atlas-skeleton--line" aria-hidden="true"></p>
  <p class="atlas-skeleton atlas-skeleton--block" aria-hidden="true"></p>
</div>
