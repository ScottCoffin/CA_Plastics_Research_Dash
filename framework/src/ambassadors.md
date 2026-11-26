---
title: Become a local ambassador · Plastiverse Live
sidebar: false
header: false
footer: false
toc: false
pager: false
---

<!-- AMB-1 slice 1: the public ambassadors landing page (no sign-in yet). Markup is static here; components/ambassadors.js
     fills the world map, the place search, the region panel, the table and the "Can I join?" checker from real data
     (site/data/global/ambassador_regions.json and each region's ambassador_institutions.json). Styles: components/ambassadors.css.
     The badge is components/ambassador_badge.js. The ORCID-first sign-up (#amb-signup) is components/ambassador_signup.js. -->

<link rel="stylesheet" href="./components/ambassadors.css">
<link rel="stylesheet" href="./components/ambassador_signup_map.css">
<link rel="stylesheet" href="./components/ambassador_knowledge.css">
<link rel="stylesheet" href="./components/ambassador_settings.css">
<link rel="stylesheet" href="./components/ambassador_invite.css">

<div class="am" data-mode="checking">
<a class="skip" href="#main">Skip to the content</a>
<header class="top">
  <a class="brand" href="./" aria-label="Plastiverse Live home"><svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="5"/><line x1="2.6" y1="13" x2="23.4" y2="13"/><line x1="13" y1="2.6" x2="13" y2="23.4"/></svg><span class="wm">PLASTI<b>VERSE</b> LIVE</span></a>
  <nav class="nav" aria-label="Main">
    <a href="./explore">Explore the data</a>
    <a href="./ambassadors" aria-current="page">Ambassadors</a>
    <a href="./california/about">About</a>
  </nav>
</header>

<main id="main" tabindex="-1">

<!-- Page mode (owner 2026-11-26): data-mode is "checking" until GET /me answers, then "public" (this recruiting page) or
     "dashboard" (a signed-in ambassador). The .recruit sections are hidden in both checking and dashboard modes. -->
<section class="only-checking" aria-labelledby="h-checking">
  <h2 id="h-checking" class="sr">Checking your sign-in</h2>
  <div class="ws-skel" aria-hidden="true"><span></span><span></span><span></span></div>
</section>

<section class="hero recruit">
  <h1>Become a local ambassador</h1>
  <p class="lede">Plastiverse Live grows region by region. Researchers and community leaders who know a place check our data there and add what only locals know.</p>
  <div class="actions">
    <a class="btn solid" href="https://api.plastiverse.live/orcid/start" data-orcid-start>Sign up with ORCID</a>
    <a class="btn" href="#can-i-join">Check if you can join</a>
  </div>
  <p class="hint">Already an ambassador? <a class="link" href="https://api.plastiverse.live/orcid/start" data-orcid-start>Sign in with ORCID</a></p>
</section>

<section class="sec signup" id="amb-signup" aria-label="Ambassador sign-up" hidden>
  <p class="sr" id="amb-signup-status" role="status" aria-live="polite"></p>
  <div id="amb-signup-body"></div>
</section>

<section class="sec recruit" id="regions" aria-labelledby="h-regions">
  <div class="sec-head"><h2 id="h-regions">Regions on the world map</h2><span class="sec-note">Natural Earth projection</span></div>

  <div class="search-field">
    <label for="amb-q">Search a country, state or city</label>
    <div class="search-host" id="amb-search"></div>
    <p class="hint">Type, then use the arrow keys and Enter. Choosing a place zooms the map to it.</p>
    <p class="threshold"><b>Cities and towns of 15,000 people or more</b> are in the search. Smaller places are found by their state, province or county.</p>
    <p class="sr" id="amb-search-status" role="status" aria-live="polite"></p>
  </div>

  <div class="geo-grid">
    <div class="geo-main">
      <div id="amb-map-host" class="map-host"><p class="status" role="status">Loading the map.</p></div>
      <ul class="legend" aria-label="Map legend">
        <li><span class="sw st-open" aria-hidden="true"></span>Open to ambassadors</li>
        <li><span class="sw st-none" aria-hidden="true"></span>Not open yet</li>
        <li><span class="sw line-disp" aria-hidden="true"></span>Disputed boundary, as drawn by Natural Earth</li>
        <li><span class="sw line-pac" aria-hidden="true"></span>Pacific island grouping line (Natural Earth)</li>
      </ul>
      <p class="hint">Hold Ctrl (Cmd on a Mac) and scroll to zoom, or click the map first. Drag to pan. Two fingers pan and pinch on a phone. With the map focused, plus and minus zoom, the arrow keys pan and 0 resets.</p>
      <p class="credit">Map: Natural Earth 1:50m (public domain). Boundaries: Natural Earth disputed boundary lines, shown as Natural Earth's default view, and Pacific groupings (10m). Place names: GeoNames (CC BY 4.0) and Natural Earth. California is outlined on the US map.</p>
      <div class="actions"><button type="button" class="btn" id="amb-table-toggle" aria-expanded="false" aria-controls="amb-table-wrap">Show the regions as a table</button></div>
      <div class="tbl-wrap" id="amb-table-wrap" hidden>
        <table>
          <caption class="sr">Regions, their status and the next step</caption>
          <thead><tr><th scope="col">Region</th><th scope="col">Status</th><th scope="col">Ambassadors</th><th scope="col">Next step</th></tr></thead>
          <tbody id="amb-table-body"></tbody>
        </table>
      </div>
    </div>
    <aside class="geo-panel" id="amb-panel" aria-live="polite" aria-label="Selected place">
      <p class="hint">Choose a shaded country or a dot on the map, or search above. This panel shows whether a region is open and how to join it.</p>
    </aside>
  </div>
</section>

<section class="sec recruit" aria-labelledby="h-do">
  <div class="sec-head"><h2 id="h-do">What ambassadors do</h2><span class="sec-note">Work from your own desk</span></div>
  <ul class="rows">
    <li><div><h3>Check doubtful matches</h3><p>The automatic sorting is unsure about some works and institutions. You say whether it is right: a place name in the wrong country, or a local-language study that is about plastics.</p></div></li>
    <li><div><h3>Confirm placeholders</h3><p>Some funders, monitoring programmes and policies on a region page are not yet checked. Confirm the name and link, correct them, or mark them not relevant.</p></div></li>
    <li><div><h3>Add local knowledge</h3><p>Tell us about community groups, volunteer clean-ups, local policies with their dates, and monitoring data with its licence.</p></div></li>
  </ul>
  <div class="badge-block" aria-labelledby="h-badge">
    <p class="badge-lg"><span class="amb lg" data-amb="Norway" data-big></span></p>
    <h3 id="h-badge">The Ambassador badge</h3>
    <p class="hint">Once an ambassador's author record is linked and confirmed, their name shows a badge with the region. The badge names the region only. An ambassador can hide it in settings, and it is removed when they leave the programme.</p>
  </div>
</section>

<section class="sec recruit" id="can-i-join" aria-labelledby="h-check">
  <h2 id="h-check">Can I join? Check your institution</h2>
  <p class="sec-note">Type your work email or your institution's name. We check it against the institutions already tagged for plastics research in each region.</p>
  <form class="check-box" id="amb-check-form" novalidate>
    <div class="check-row">
      <div class="field">
        <label for="amb-check-place-search">Place</label>
        <div class="search-host" id="amb-check-place"></div>
      </div>
      <div class="field">
        <label for="amb-check-q">Work email or institution name</label>
        <div class="search-host">
          <input type="text" id="amb-check-q" role="combobox" aria-expanded="false" aria-autocomplete="list" aria-controls="amb-check-list" aria-activedescendant="" autocomplete="off" placeholder="you@institution.no or an institution name">
          <div class="pop" id="amb-check-list" role="listbox" aria-label="Matching institutions" hidden></div>
        </div>
      </div>
      <div class="check-btn"><button class="btn solid" type="submit">Check eligibility</button></div>
    </div>
    <p class="hint">Free email services (Gmail, Outlook, Proton and similar) cannot be accepted. The place is optional: without one, we check every region.</p>
    <div id="amb-check-result" class="result" aria-live="polite" role="status" hidden></div>
  </form>
</section>

<section class="sec recruit" aria-labelledby="h-how">
  <div class="sec-head"><h2 id="h-how">How it works</h2><span class="sec-note">Three steps. No passwords.</span></div>
  <ol class="steps">
    <li>Sign up with your ORCID iD. We check your author record and the institutions on it, and you tick the ones you can speak for.</li>
    <li>Confirm one institutional email. We send a one-time link that works for 30 minutes. Then set your display name once and agree to the contribution terms (CC BY-NC 4.0, the same licence as the Atlas data).</li>
    <li>Work on your region's three streams. Contributions to the data are reviewed before they reach the Atlas. A region you propose from inside your own institution goes live at once; other proposals wait for review.</li>
  </ol>
  <div class="actions">
    <a class="btn solid" href="https://api.plastiverse.live/orcid/start" data-orcid-start>Sign up with ORCID</a>
    <a class="link" href="./ambassador_terms">Read the contribution terms</a>
  </div>
</section>

</main>

<footer class="foot">
  <p><b>Plastiverse Live</b> · <a href="./ambassador_terms">Contribution terms</a> · <a href="./explore">Explore the data</a> · Email <span class="addr">theplastiverse@gmail.com</span></p>
</footer>
</div>

```js
import {mountAmbassadors} from "./components/ambassadors.js";
import {mountSignup} from "./components/ambassador_signup.js";
mountAmbassadors(document.querySelector(".am")).catch((error) => console.error("ambassadors:", error));
mountSignup(document.querySelector(".am")).catch((error) => console.error("sign-up:", error));
```
