---
title: Norway · Plastiverse Live
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
<!-- REG-1 region page (docs/REGION_PAGES.md): the shared component components/region_page.js fills #rg-root from
     data/norway/region.json. The header and footer are static markup (no runtime header: no layout shift).
     Styles: components/region_page.css, scoped under .rg. Local data is a placeholder until a local researcher confirms it. -->

<link rel="stylesheet" href="../components/region_page.css">

<div class="rg">
<a class="rg-skip" href="#rg-main">Skip to the region</a>
<header class="rg-top">
  <a class="rg-brand" href="../" aria-label="Plastiverse Live home"><svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="5"/><g><line x1="20.60" y1="13.00" x2="23.40" y2="13.00"/><line x1="20.02" y1="15.91" x2="23.72" y2="17.44"/><line x1="18.37" y1="18.37" x2="20.35" y2="20.35"/><line x1="15.91" y1="20.02" x2="17.44" y2="23.72"/><line x1="13.00" y1="20.60" x2="13.00" y2="23.40"/><line x1="10.09" y1="20.02" x2="8.56" y2="23.72"/><line x1="7.63" y1="18.37" x2="5.65" y2="20.35"/><line x1="5.98" y1="15.91" x2="2.28" y2="17.44"/><line x1="5.40" y1="13.00" x2="2.60" y2="13.00"/><line x1="5.98" y1="10.09" x2="2.28" y2="8.56"/><line x1="7.63" y1="7.63" x2="5.65" y2="5.65"/><line x1="10.09" y1="5.98" x2="8.56" y2="2.28"/><line x1="13.00" y1="5.40" x2="13.00" y2="2.60"/><line x1="15.91" y1="5.98" x2="17.44" y2="2.28"/><line x1="18.37" y1="7.63" x2="20.35" y2="5.65"/><line x1="20.02" y1="10.09" x2="23.72" y2="8.56"/></g></svg><span class="rg-wm" aria-hidden="true">PLASTIVERSE <b>LIVE</b></span></a>
  <nav class="rg-nav" aria-label="Main">
    <a href="../explore">Explore the data</a>
    <details class="rg-regions">
      <summary>Regions</summary>
      <ul>
        <li><a href="../california/">California</a></li>
        <li><a href="../norway/" aria-current="page">Norway</a></li>
        <li><a href="../belgium/">Belgium</a></li>
      </ul>
    </details>
    <a href="../california/about#how-works-are-screened">Methods</a>
    <a href="../california/about">About</a>
    <a class="rg-btn" href="#rg-updates">Get updates</a>
  </nav>
</header>
<main id="rg-main" class="rg-main"><div class="rg-root" id="rg-root"></div></main>
<footer class="rg-foot" id="rg-updates">
  <div><b>Get updates</b><br>Weekly email, <a href="../feed.xml">RSS feed</a>, <a href="https://ntfy.sh/plastiverse-california" rel="noreferrer">ntfy alerts</a>.</div>
  <div><b>Plastiverse Live</b><br>Created by <a href="https://scottcoff.in" rel="noreferrer">Scott Coffin</a>. Not a State product.</div>
  <div><a href="../ambassadors">Help build this page</a></div>
</footer>
</div>

```js
import {mountRegion} from "../components/region_page.js";
mountRegion(document.querySelector("#rg-root"), "norway").catch((error) => console.error("region:", error));
```
