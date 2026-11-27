---
title: Plastiverse Live
sidebar: false
header: false
footer: false
toc: false
pager: false
head: |
  <style>
    @font-face { font-family: "Schibsted Grotesk"; font-style: normal; font-weight: 400 700; font-display: swap; src: url("./assets/fonts/SchibstedGrotesk-Variable-latin.woff2") format("woff2"); unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD, U+2192; }
    @font-face { font-family: "Martian Mono"; font-style: normal; font-weight: 400; font-display: swap; src: url("./assets/fonts/MartianMono-Regular-latin.woff2") format("woff2"); unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD, U+2192; }
  </style>
  <meta name="theme-color" content="#000000">
---

<!-- PLAT-2 global landing (docs/PLAT_2_LANDING_SPEC.md; ADR-PLAT2-SPECTRAL-STORY-2026-11-17).
     Engine and sections: components/landing_story.js and .css. Captions are the approved copy. -->

<link rel="stylesheet" href="./components/landing_story.css">

<div class="plv">
<header class="plv-top on-dark"><a class="plv-brand" href="./" aria-label="Plastiverse Live home"><svg class="plv-mark" width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="5"/><g><line x1="20.60" y1="13.00" x2="23.40" y2="13.00"/><line x1="20.02" y1="15.91" x2="23.72" y2="17.44"/><line x1="18.37" y1="18.37" x2="20.35" y2="20.35"/><line x1="15.91" y1="20.02" x2="17.44" y2="23.72"/><line x1="13.00" y1="20.60" x2="13.00" y2="23.40"/><line x1="10.09" y1="20.02" x2="8.56" y2="23.72"/><line x1="7.63" y1="18.37" x2="5.65" y2="20.35"/><line x1="5.98" y1="15.91" x2="2.28" y2="17.44"/><line x1="5.40" y1="13.00" x2="2.60" y2="13.00"/><line x1="5.98" y1="10.09" x2="2.28" y2="8.56"/><line x1="7.63" y1="7.63" x2="5.65" y2="5.65"/><line x1="10.09" y1="5.98" x2="8.56" y2="2.28"/><line x1="13.00" y1="5.40" x2="13.00" y2="2.60"/><line x1="15.91" y1="5.98" x2="17.44" y2="2.28"/><line x1="18.37" y1="7.63" x2="20.35" y2="5.65"/><line x1="20.02" y1="10.09" x2="23.72" y2="8.56"/></g></svg><span class="plv-wm" aria-hidden="true">PLASTIVERSE <b>LIVE</b></span></a>
<nav class="plv-nav" aria-label="Main"><a href="./explore">Explore the data</a><a href="./ambassadors">Ambassadors</a><a href="./groups">Community groups</a><a href="#evidence">Evidence map</a><button type="button" class="plv-btn keep" id="plv-regions-btn" aria-expanded="false" aria-controls="plv-hdr-picker">Regions <svg width="10" height="7" viewBox="0 0 10 7" aria-hidden="true"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg></button><a href="./california/about#how-works-are-screened">Methods</a><a href="./california/about">About</a><a class="plv-btn solid keep" href="#updates">Get updates</a></nav>
<div class="plv-picker" id="plv-hdr-picker" data-plv="picker" hidden></div></header>
<section class="plv-intro" id="plv-intro" aria-label="Plastiverse Live">
<h1 class="sr-only">Plastiverse Live: plastics research, worldwide and local</h1>
<div class="plv-ilogo-box"><img class="plv-ilogo" src="./assets/landing/logo_motion_poster.webp" width="564" height="564" alt="Plastiverse Live logo: scattered plastic fragments flow into a bright node and a network of research" fetchpriority="high"></div>
<div class="cue plv-icue" aria-hidden="true"><svg class="cue-arrow" width="24" height="56" viewBox="0 0 24 56" aria-hidden="true"><path d="M12 2v50M3 43l9 9 9-9" fill="none" stroke="currentColor" stroke-width="2"/></svg><span>scroll</span></div>
<a class="skip" href="#evidence">Skip to the evidence map</a>
</section>
<section class="plv-story" id="plv-story" aria-label="Why Plastiverse Live exists">
<div class="plv-stage" id="plv-stage">
<img class="plv-firstpaint in" id="plv-firstpaint" src="./assets/landing/picnic_first_paint.webp" srcset="./assets/landing/picnic_first_paint_800.webp 800w, ./assets/landing/picnic_first_paint.webp 1600w" sizes="100vw" width="1600" height="1067" alt="" fetchpriority="low">
<canvas id="plv-cv" aria-hidden="true"></canvas>
<svg id="plv-bulbsrc" width="0" height="0" style="position:absolute" focusable="false" aria-hidden="true"><path d="M100 10 C150 10 186 46 186 96 C186 134 162 152 146 176 C138 188 136 196 136 206 L64 206 C64 196 62 188 54 176 C38 152 14 134 14 96 C14 46 50 10 100 10 Z"/><path d="M66 218 H134 M68 232 H132 M72 246 H128 M84 262 H116"/><path d="M82 206 L86 132 L94 118 L100 132 L106 118 L114 132 L118 206"/></svg>
<p class="sr-only">A picnic laid out on a checked blanket, made entirely of disposable plastics: cups, plates, cutlery, straws, a soda bottle, squeeze bottles, wrapped sandwiches, a food tub, a beach ball and a jump rope. Scrolling, it shatters into microplastic particles that become published studies, then a chart of research output, an evidence map, a collaboration network and a world map.</p>
<div class="plv-stack" id="plv-stack" aria-hidden="true"></div>
<div class="cap c0 dk" data-a=".45" data-b="1.45"><h2>Plastic is everywhere&hellip;</h2></div>
<div class="cap c1 dk" data-a="4.0" data-b="5.4"><h2>Microplastics were first described in the ocean more than 50&nbsp;years ago.</h2><p class="src">Carpenter et al. (1972), &ldquo;Polystyrene spherules in coastal waters,&rdquo; Science 178:749. doi:10.1126/science.178.4062.749</p></div>
<div class="cap c1n dk" data-a="5.4" data-b="7.2"><h2>Now picture every particle as a published study. Thousands more arrive every year.</h2></div>
<div class="cap c2 dk" data-a="8.5" data-b="10.5"><h2>Connected, studies become knowledge.</h2></div>
<div class="cap c2b bot dk" data-a="9.2" data-b="10.5"><p>Grouped by what they study and linked by who did the work, scattered results start to form a picture.</p></div>
<div class="cap cb dk" data-a="11.6" data-b="12.9"><h2>Put to work, knowledge becomes understanding.</h2></div>
<div class="cap c3s" data-a="17.45" data-b="20.55"><p class="src">Plastics-pollution research works per year, worldwide. OpenAlex, query <span data-plv="query">plastic-v3.1</span>, fetched <span data-plv="fetched"></span>. One dot = <span data-plv="unit"></span> works.</p></div>
<div class="cap c3" data-a="19.2" data-b="20.55"><h2>Plastic pollution research is expanding at an unprecedented pace.</h2><p>The world needs innovative tools to turn data into knowledge and solutions to effectively react to this global crisis.</p></div>
<div class="cap c5" data-a="21.8" data-b="23.4"><h2>See where the evidence is, worldwide, and where it is missing.</h2><p data-a="22.3">A live evidence map sorts every study by what it examines and where.</p></div>
<div class="cap c4" data-a="24.6" data-b="26.1"><h2>See who works with whom, and forge new connections.</h2><p data-a="25.1">Collaboration networks show the research communities and the people who bridge them.</p></div>
<div class="cap c6" data-a="27.3" data-b="28.5"><h2>The problem is global.</h2><p data-a="27.75">Plastics research now comes from almost every country.</p><p class="src" data-a="27.75">Works by country, OpenAlex, <span data-plv="map-fetched"></span>.</p></div>
<div class="cap c7" data-a="29.6" data-b="99"><h2>Local knowledge and connections matter.</h2><p data-a="30">Regional atlases zoom in on the people, monitoring, funding and policy of one place. Powered by local researchers and community leaders.</p><p class="cta" data-a="30.35"><a class="plv-btn solid" href="./ambassadors">Join the movement, and become a local ambassador <svg width="14" height="10" viewBox="0 0 14 10" aria-hidden="true"><path d="M1 5h11M8 1l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></a></p><p class="sep" data-a="30.7">California is live; Norway is next.</p></div>
<ul class="sr-only" id="plv-ann-list" aria-label="Chart annotations"></ul>
<div class="cue" id="plv-cue" aria-hidden="true"><svg class="cue-arrow" width="24" height="56" viewBox="0 0 24 56" aria-hidden="true"><path d="M12 2v50M3 43l9 9 9-9" fill="none" stroke="currentColor" stroke-width="2"/></svg>scroll</div>
<a class="skip" href="#evidence">Skip to the evidence map</a>
</div>
<div class="plv-stills" id="plv-stills"></div>
</section>
<section class="plv-band" id="evidence" aria-labelledby="plv-evidence-h"><div class="plv-wrap">
<h2 id="plv-evidence-h">The live evidence map.</h2>
<p class="lede" data-plv="evidence-lede">Every plastics-pollution study worldwide, sorted by what it examines and where. Rebuilt daily from OpenAlex once the cell definitions are agreed.</p>
<div class="plv-evtools" role="group" aria-label="Region"><button type="button" class="plv-btn solid" aria-pressed="true">Worldwide</button><button type="button" class="plv-btn" aria-pressed="false" disabled>California</button><button type="button" class="plv-btn" aria-pressed="false" disabled>Norway</button><span class="plv-evnote">regional views arrive with the regional atlases</span></div>
<div class="plv-evwrap" tabindex="0" role="region" aria-label="Evidence map table"><table class="plv-evt" data-plv="evidence-table"><caption class="sr-only" data-plv="evidence-caption">Illustrative study counts by topic and setting, worldwide</caption><thead><tr><td></td><th scope="col">ocean</th><th scope="col"><span class="plv-long">freshwater</span><span class="plv-short" aria-hidden="true">fresh</span></th><th scope="col">soil</th><th scope="col">air</th><th scope="col"><span class="plv-long">food and biota</span><span class="plv-short" aria-hidden="true">biota</span></th><th scope="col">people</th></tr></thead><tbody><tr><th scope="row"><span class="plv-long">occurrence</span><span class="plv-short" aria-hidden="true">occur.</span></th><td style="--v:1.00"><span>3900</span></td><td style="--v:0.67"><span>2600</span></td><td style="--v:0.27"><span>1040</span></td><td style="--v:0.17"><span>650</span></td><td style="--v:0.40"><span>1560</span></td><td style="--v:0.13"><span>520</span></td></tr><tr><th scope="row">effects</th><td style="--v:0.60"><span>2340</span></td><td style="--v:0.33"><span>1300</span></td><td style="--v:0.13"><span>520</span></td><td style="--v:0.03"><span>130</span></td><td style="--v:0.53"><span>2080</span></td><td style="--v:0.20"><span>780</span></td></tr><tr><th scope="row">methods</th><td style="--v:0.33"><span>1300</span></td><td style="--v:0.20"><span>780</span></td><td style="--v:0.10"><span>390</span></td><td style="--v:0.07"><span>260</span></td><td style="--v:0.10"><span>390</span></td><td style="--v:0.03"><span>130</span></td></tr><tr><th scope="row"><span class="plv-long">fate and transport</span><span class="plv-short" aria-hidden="true">fate</span></th><td style="--v:0.27"><span>1040</span></td><td style="--v:0.20"><span>780</span></td><td style="--v:0.10"><span>390</span></td><td style="--v:0.07"><span>260</span></td><td style="--v:0.03"><span>130</span></td><td class="gap" style="--v:0.00"><span>gap</span></td></tr><tr><th scope="row">solutions</th><td style="--v:0.13"><span>520</span></td><td style="--v:0.07"><span>260</span></td><td class="gap" style="--v:0.00"><span>gap</span></td><td class="gap" style="--v:0.00"><span>gap</span></td><td style="--v:0.03"><span>130</span></td><td class="gap" style="--v:0.00"><span>gap</span></td></tr></tbody></table></div>
<p class="plv-evsrc" data-plv="evidence-src">Illustrative counts. The live version counts works per cell with the reviewed plastics query and agreed cell definitions.</p>
</div></section>
<section class="plv-band grid-bg" id="regions" aria-labelledby="plv-regions-h"><div class="plv-wrap">
<h2 id="plv-regions-h">From global to local: open a regional atlas.</h2>
<p class="lede">Each atlas maps who studies plastic pollution in one region, where they work, who funds them, what is monitored and which policies apply. It rebuilds every day from open data.</p>
<div class="plv-regions">
<div><div class="plv-mapbox" id="plv-mapbox" style="aspect-ratio: 1288 / 448"><canvas aria-hidden="true"></canvas><svg role="img" aria-label="World map of plastics research by country; California is live, Norway is in preparation"></svg></div>
<div class="plv-legend">works per country <span class="plv-ramp" aria-hidden="true"><span style="background:var(--pv-wash)"></span><span style="background:var(--pv-mint)"></span><span style="background:var(--pv-slate-2)"></span><span style="background:var(--pv-slate)"></span></span> under 30 · 30–299 · 300–2,999 · 3,000+ works; OpenAlex, plastics query</div></div>
<div class="plv-picker" data-plv="picker"></div>
</div>
<p class="plv-explore">Or compare every country: <a href="./explore">explore the global data</a> <svg width="14" height="10" viewBox="0 0 14 10" aria-hidden="true"><path d="M1 5h11M8 1l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></p>
</div></section>
<section class="plv-band" aria-labelledby="plv-feat-h"><div class="plv-wrap plv-feat">
<div><h2 id="plv-feat-h">What a regional atlas does.</h2><p class="lede">Built and checked for California first. Every count links back to its open source.</p></div>
<ol>
<li><svg viewBox="0 0 56 40" aria-hidden="true"><circle class="g" cx="18" cy="14" r="7"/><path class="g" d="M6 36 C6 26 30 26 30 36"/><circle class="m" cx="42" cy="14" r="4"/></svg><div><b>Find an author</b><span>Search researchers by topic, institution and recent work.</span></div><a href="./california/authors">Authors<span class="sr-only"> (California)</span></a></li>
<li><svg viewBox="0 0 56 40" aria-hidden="true"><path class="g" d="M10 30 L26 10 L46 22 L10 30 L46 22"/><circle class="t" cx="10" cy="30" r="4"/><circle class="t" cx="26" cy="10" r="4"/><circle class="m" cx="46" cy="22" r="4"/></svg><div><b>See who works with whom</b><span>A collaboration network of co-authors and communities.</span></div><a href="./california/network">Network<span class="sr-only"> (California)</span></a></li>
<li><svg viewBox="0 0 56 40" aria-hidden="true"><rect class="t" x="8" y="20" width="8" height="14"/><rect class="t" x="22" y="10" width="8" height="24"/><rect class="m" x="36" y="4" width="8" height="30"/></svg><div><b>Compare institutions</b><span>Output, trends and leaders across universities and agencies.</span></div><a href="./california/institutions">Institutions<span class="sr-only"> (California)</span></a></li>
<li><svg viewBox="0 0 56 40" aria-hidden="true"><path class="g" d="M4 32 H52"/><path class="g" d="M8 32 L18 22 L28 26 L40 10 L50 14"/><circle class="m" cx="40" cy="10" r="3.5"/></svg><div><b>Follow the funding</b><span>Federal and state awards for plastics research.</span></div><a href="./california/funding">Funding<span class="sr-only"> (California)</span></a></li>
<li><svg viewBox="0 0 56 40" aria-hidden="true"><g class="t"><rect x="6" y="6" width="6" height="6"/><rect x="14" y="14" width="6" height="6"/><rect x="22" y="6" width="6" height="6"/><rect x="30" y="22" width="6" height="6"/></g><rect class="m" x="38" y="14" width="6" height="6"/></svg><div><b>Check monitoring data</b><span>Where microplastics have been sampled, with licences shown.</span></div><a href="./california/monitoring">Monitoring<span class="sr-only"> (California)</span></a></li>
<li><svg viewBox="0 0 56 40" aria-hidden="true"><g class="t"><rect x="6" y="6" width="10" height="8"/><rect x="18" y="16" width="10" height="8"/><rect x="30" y="6" width="10" height="8"/></g><rect class="m" x="42" y="26" width="10" height="8"/><path class="g" d="M6 26 H40"/></svg><div><b>Map the evidence</b><span>Topics by matrix, so gaps show up as empty cells.</span></div><a href="./california/evidence">Evidence map<span class="sr-only"> (California)</span></a></li>
<li><svg viewBox="0 0 56 40" aria-hidden="true"><path class="g" d="M4 20 H52"/><circle class="t" cx="12" cy="20" r="4"/><circle class="t" cx="28" cy="20" r="4"/><circle class="m" cx="44" cy="20" r="4"/></svg><div><b>Track policy</b><span>Laws, regulations and plans on one timeline.</span></div><a href="./california/policy">Policy<span class="sr-only"> (California)</span></a></li>
</ol>
</div></section>
<footer class="plv-foot" id="updates"><img class="plv-flogo" src="./assets/landing/logo_motion_poster.webp" width="282" height="282" alt="Plastiverse Live logo: scattered plastic fragments flow into a bright node and a network of research" loading="lazy">
<div><b>Get updates</b><br>Weekly email (soon), <a href="./feed.xml">RSS feed</a>, <a href="https://ntfy.sh/plastiverse-california" rel="noreferrer">ntfy alerts</a>.</div>
<div><b>Plastiverse Live</b><br>Created by <a href="https://scottcoff.in" rel="noreferrer">Scott Coffin</a>. Not a State product.</div>
<div>Story framing after Hartmann, Mennekes &amp; Wagner (2026).</div>
<details class="plv-pcred"><summary>Image credits</summary><p>Paper first pages reproduced under CC BY 4.0, with download stamps removed: Lost in a Sea of Information: The Microplastics Publication Deluge (doi:10.1021/acs.est.6c01796); Risk-based management framework for microplastics in aquatic ecosystems (doi:10.1186/s43591-022-00033-3); Reporting Guidelines to Increase the Reproducibility and Comparability of Research on Microplastics (doi:10.1177/0003702820930292); Microplastics in freshwater: A global review of factors affecting spatial and temporal variations (doi:10.1016/j.envpol.2021.118393); Rapid single-particle chemical imaging of nanoplastics by SRS microscopy (doi:10.1073/pnas.2300582121); Nanoplastics transport to the remote, high-altitude Alps (doi:10.1016/j.envpol.2021.117697); Micro(nano)plastics sources, fate, and effects: What we know after ten years of research (doi:10.1016/j.hazadv.2022.100057); Microplastics analytics: why we should not underestimate the importance of blank controls (doi:10.1186/s43591-023-00065-3); Microplastics and Trash Cleaning and Harmonization (MaTCH): Semantic Data Ingestion and Harmonization Using Artificial Intelligence (doi:10.1021/acs.est.4c02406); Microplastics: A Matter of the Heart (and Vascular System) (doi:10.3390/biomedicines11020264); Studies of the effects of microplastics on aquatic organisms: What do we know and where should we focus our efforts in the future? (doi:10.1016/j.scitotenv.2018.07.207); Microplastics but not natural particles induce multigenerational effects in Daphnia magna (doi:10.1016/j.envpol.2019.113904); Plastic ingestion by green turtles ( Chelonia mydas ) over 33 years along the coast of Texas, USA (doi:10.1016/j.marpolbul.2021.113111); Size Distributions of Microplastics in the St Louis Estuary and Western Lake Superior (doi:10.1021/acs.est.3c10776); Paradigms to assess the human health risks of nano- and microplastics (doi:10.1186/s43591-021-00011-1).</p></details></footer>
</div>

```js
import {mountLandingStory, mountPickers, mountRegionsMap} from "./components/landing_story.js";
import {mountLogoMotion, mountIntroLogo} from "./components/logo_motion.js";
const landingRoot = document.querySelector(".plv");
mountPickers(landingRoot);
mountRegionsMap(landingRoot);
mountLandingStory(landingRoot).catch((error) => console.error("landing story:", error));
mountIntroLogo(document.querySelector(".plv-intro"));
mountLogoMotion(document.querySelector(".plv-foot"));
```
