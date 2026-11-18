---
title: Explore the data · Plastiverse Live
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
  <link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNiAyNiI+PHJlY3Qgd2lkdGg9IjI2IiBoZWlnaHQ9IjI2IiByeD0iNSIgZmlsbD0iIzE3MjYzZCIvPjxjaXJjbGUgY3g9IjEzIiBjeT0iMTMiIHI9IjUiIGZpbGw9IiNmZmY0OWEiLz48ZyBzdHJva2U9IiNmZmY0OWEiIHN0cm9rZS13aWR0aD0iMS42IiBzdHJva2UtbGluZWNhcD0icm91bmQiPjxsaW5lIHgxPSIyMC42MCIgeTE9IjEzLjAwIiB4Mj0iMjMuNDAiIHkyPSIxMy4wMCIvPjxsaW5lIHgxPSIxOS40NyIgeTE9IjE1LjY4IiB4Mj0iMjMuMTYiIHkyPSIxNy4yMSIvPjxsaW5lIHgxPSIxOC4zNyIgeTE9IjE4LjM3IiB4Mj0iMjAuMzUiIHkyPSIyMC4zNSIvPjxsaW5lIHgxPSIxNS42OCIgeTE9IjE5LjQ3IiB4Mj0iMTcuMjEiIHkyPSIyMy4xNiIvPjxsaW5lIHgxPSIxMy4wMCIgeTE9IjIwLjYwIiB4Mj0iMTMuMDAiIHkyPSIyMy40MCIvPjxsaW5lIHgxPSIxMC4zMiIgeTE9IjE5LjQ3IiB4Mj0iOC43OSIgeTI9IjIzLjE2Ii8+PGxpbmUgeDE9IjcuNjMiIHkxPSIxOC4zNyIgeDI9IjUuNjUiIHkyPSIyMC4zNSIvPjxsaW5lIHgxPSI2LjUzIiB5MT0iMTUuNjgiIHgyPSIyLjg0IiB5Mj0iMTcuMjEiLz48bGluZSB4MT0iNS40MCIgeTE9IjEzLjAwIiB4Mj0iMi42MCIgeTI9IjEzLjAwIi8+PGxpbmUgeDE9IjYuNTMiIHkxPSIxMC4zMiIgeDI9IjIuODQiIHkyPSI4Ljc5Ii8+PGxpbmUgeDE9IjcuNjMiIHkxPSI3LjYzIiB4Mj0iNS42NSIgeTI9IjUuNjUiLz48bGluZSB4MT0iMTAuMzIiIHkxPSI2LjUzIiB4Mj0iOC43OSIgeTI9IjIuODQiLz48bGluZSB4MT0iMTMuMDAiIHkxPSI1LjQwIiB4Mj0iMTMuMDAiIHkyPSIyLjYwIi8+PGxpbmUgeDE9IjE1LjY4IiB5MT0iNi41MyIgeDI9IjE3LjIxIiB5Mj0iMi44NCIvPjxsaW5lIHgxPSIxOC4zNyIgeTE9IjcuNjMiIHgyPSIyMC4zNSIgeTI9IjUuNjUiLz48bGluZSB4MT0iMTkuNDciIHkxPSIxMC4zMiIgeDI9IjIzLjE2IiB5Mj0iOC43OSIvPjwvZz48L3N2Zz4=">
  <meta name="theme-color" content="#000000">
---

<!-- GA-2b: /explore, the approved GA-1 prototype (.impeccable/sketches/global_app.html) ported to Framework.
     Markup below is static; components/explore.js fills the scope bar, statement, tabs and panels.
     Styles: components/explore.css. Data: data/global/explore.json (fetched at runtime). -->

<link rel="stylesheet" href="./components/explore.css">

<div class="gx">
<a class="skip" href="#main">Skip to the data</a>
<header class="top">
  <a class="brand" href="./" aria-label="Plastiverse Live home"><svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="5"/><g><line x1="20.60" y1="13.00" x2="23.40" y2="13.00"/><line x1="20.02" y1="15.91" x2="23.72" y2="17.44"/><line x1="18.37" y1="18.37" x2="20.35" y2="20.35"/><line x1="15.91" y1="20.02" x2="17.44" y2="23.72"/><line x1="13.00" y1="20.60" x2="13.00" y2="23.40"/><line x1="10.09" y1="20.02" x2="8.56" y2="23.72"/><line x1="7.63" y1="18.37" x2="5.65" y2="20.35"/><line x1="5.98" y1="15.91" x2="2.28" y2="17.44"/><line x1="5.40" y1="13.00" x2="2.60" y2="13.00"/><line x1="5.98" y1="10.09" x2="2.28" y2="8.56"/><line x1="7.63" y1="7.63" x2="5.65" y2="5.65"/><line x1="10.09" y1="5.98" x2="8.56" y2="2.28"/><line x1="13.00" y1="5.40" x2="13.00" y2="2.60"/><line x1="15.91" y1="5.98" x2="17.44" y2="2.28"/><line x1="18.37" y1="7.63" x2="20.35" y2="5.65"/><line x1="20.02" y1="10.09" x2="23.72" y2="8.56"/></g></svg><span class="wm" aria-hidden="true">PLASTIVERSE <b>LIVE</b></span></a>
  <nav class="nav" aria-label="Main">
    <a href="./explore" aria-current="page">Explore the data</a>
    <button type="button" class="btn keep" id="regions-btn" aria-expanded="false" aria-controls="regions-pop">Regions <svg width="10" height="7" viewBox="0 0 10 7" aria-hidden="true"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg></button>
    <a href="./california/about#how-works-are-screened">Methods</a>
    <a href="./california/about">About</a>
    <a class="btn solid keep" href="#updates">Get updates</a>
  </nav>
</header>
<div class="pop" id="regions-pop" hidden style="right:var(--pv-gut);top:64px;position:fixed;width:min(420px, calc(100vw - 32px))">
  <div class="pop-h">Regional atlases <span>2 regions</span></div>
  <a class="opt live" href="./california/"><i class="sw live"></i><span>California<small>live atlas, daily build</small></span><span class="go">Open atlas <svg class="i" viewBox="0 0 14 10" aria-hidden="true"><path d="M1 5h11M8 1l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></span></a>
  <a class="opt" href="./ambassadors"><i class="sw prep"></i><span>Norway<small>in preparation</small></span><span class="go quiet">Help build it</span></a>
  <a class="opt" href="./ambassadors"><i class="sw ask"></i><span>Your region<small>opens on request</small></span><span class="go quiet">Request</span></a>
  <p class="pop-note">Every country already has an automatic profile here. A regional atlas adds local experts, monitoring, funding and policy.</p>
</div>
<nav class="scope" aria-label="Scope">
  <div class="wrap">
    <ol class="ladder" id="ladder"></ol>
    <button type="button" class="btn scope-btn" id="scope-btn" aria-haspopup="dialog" aria-controls="drawer"></button>
    <div class="find" id="find-desk"></div>
  </div>
</nav>
<div id="main" class="wrap">
  <div class="head">
    <h1 id="h1"></h1>
    <p class="statement" id="statement"></p>
  </div>
  <div class="tabs" role="tablist" aria-label="Views" id="tabs"></div>
  <div id="panels"></div>
  <p class="sr" aria-live="polite" id="live"></p>
</div>
<footer class="foot" id="updates">
  <div><img src="./assets/landing/logo_564.webp" width="282" height="247" alt="Plastiverse Live logo: scattered plastic fragments flow into a bright node and a network of research" loading="lazy"></div>
  <div><b>Get updates</b><br>Weekly email, <a href="./feed.xml">RSS feed</a>, <a href="https://ntfy.sh/plastiverse-california" rel="noreferrer">ntfy alerts</a>.</div>
  <div><b>Plastiverse Live</b><br>Created by <a href="https://scottcoff.in" rel="noreferrer">Scott Coffin</a>. Not a State product.</div>
</footer>
<div class="drawer" id="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-h">
  <button type="button" class="scrim" tabindex="-1" aria-label="Close menu"></button>
  <div class="sheet">
    <div class="sheet-h"><span id="drawer-h">Menu</span><button type="button" id="drawer-x" aria-label="Close"><svg class="i" viewBox="0 0 14 14" aria-hidden="true"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" stroke-width="1.6"/></svg></button></div>
    <div class="sheet-body">
      <div role="group" aria-labelledby="menu-views"><p class="lab" id="menu-views">Views</p><ul class="vlad" id="views"></ul></div>
      <div role="group" aria-labelledby="menu-scope"><p class="lab" id="menu-scope">Scope</p><div class="find" id="find-mob"></div><ul class="vlad" id="vlad"></ul></div>
    </div>
  </div>
</div>
</div>

```js
import {mountExplore} from "./components/explore.js";
mountExplore(document.querySelector(".gx")).catch((error) => console.error("explore:", error));
```
