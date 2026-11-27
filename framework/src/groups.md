---
title: Community groups · Plastiverse Live
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

<!-- CG-13 / CG-10 (Add-on A4): /groups. components/groups.js fills #groups-root from the groups data payloads.
     The tree payload loads independently so a tree error never blocks the roster. Styles are scoped to .gv. -->

<link rel="stylesheet" href="./components/explore.css">
<link rel="stylesheet" href="./components/groups.css">

<div class="gx gv">
<a class="skip" href="#main">Skip to the content</a>
<header class="top">
  <a class="brand" href="./" aria-label="Plastiverse Live home"><svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="5"/><line x1="2.6" y1="13" x2="23.4" y2="13"/><line x1="13" y1="2.6" x2="13" y2="23.4"/></svg><span class="wm" aria-hidden="true">PLASTI<b>VERSE</b> LIVE</span></a>
  <nav class="nav" aria-label="Main">
    <a href="./explore">Explore the data</a>
    <a href="./groups" aria-current="page">Community groups</a>
    <a href="./ambassadors">Ambassadors</a>
    <a href="./quality">Data quality</a>
  </nav>
</header>
<main id="main" tabindex="-1">
<div class="gv-intro">
  <h1>Community groups</h1>
  <p>Only organisations are listed. Volunteer ambassadors add tags from public evidence, such as a group's own website and its public statements. Select a group name to see where it was listed and the evidence behind each tag.</p>
  <p><b>Not yet tagged</b> means the group has not been tagged yet. It never means the group has no plastics work.</p>
</div>
<div id="groups-root" class="gv-root"><p class="gv-status">Loading the roster…</p></div>
<section class="gv-panel gv-net-panel gv-root" aria-labelledby="gv-net-title" id="gv-network">
  <h2 id="gv-net-title">Network</h2>
  <p class="gv-caption">This view shows tagged groups only. Each link joins a group to a tag, or shows a stated affiliation that the group has published. A missing link means the data is missing, not that no work exists.</p>
  <div id="groups-network"></div>
</section>
<section class="gv-panel gv-root" aria-labelledby="gv-methods-title" id="gv-methods">
<h2 id="gv-methods-title">How this list is made</h2>
<h3>Source</h3>
<p>This list of organisations was informed by Break Free From Plastic (BFFP), with permission. The Atlas is independent of Break Free From Plastic.</p>
<h3>Organisations only</h3>
<p>Only collective organisations are listed. Individuals and single-person practices, such as a freelance consultant, a sole trader, or an artist trading under their own name, are left out when the list is read and are not kept.</p>
<h3>Tags</h3>
<p>Volunteer ambassadors tag each group from the group's own public pages. Each tag is backed by a quote of at most 25 words from those pages, with a link to the source.</p>
<p>Untagged groups appear only in the roster table and the counts. The badges mean: <b>Volunteer-tagged</b>, an ambassador tag from public evidence; <b>Reviewed</b>, checked by a reviewer; <b>Confirmed by group</b>, the group has confirmed its own tags.</p>
<h3>Corrections and removal</h3>
<p>Anyone can ask for a correction, and a group can ask to be removed. A removal request sent from the group's own web domain is honoured within 14 days and takes precedence over ambassador tags. Other corrections are checked by a reviewer.</p>
<p>To ask for a correction or removal, write to <b>theplastiverse@gmail.com</b> with the group name and what should change.</p>
</section>
</main>

<footer class="foot">
  <div><b>Plastiverse Live</b><br>Created by <a href="https://scottcoff.in" rel="noreferrer">Scott Coffin</a>. Not a State product.</div>
  <div><b>Read more</b><br><a href="./california/about">About</a> · <a href="./ambassadors">Become an ambassador</a> · <a href="./explore">Explore the data</a></div>
</footer>
</div>

```js
import {mountGroups} from "./components/groups.js";
import {globalDataUrl, loadJson} from "./components/atlas.js";
const root = document.getElementById("groups-root");
await mountGroups(root, async () => ({
  // groups.json is {schema, generated_from, groups: [...]}; the table needs the list.
  groups: (await loadJson("groups/groups.json", {url: globalDataUrl}))?.groups ?? [],
  coverage: await loadJson("groups/coverage.json", {url: globalDataUrl}),
  tree: await loadJson("groups/groups_tree.json", {url: globalDataUrl}).catch(() => null),
}));
```

```js
import {mountGroupsNetwork} from "./components/groups_network.js";
import {globalDataUrl as networkDataUrl, loadJson as loadNetworkJson} from "./components/atlas.js";
// The network loads on its own, so a missing graph never blocks the roster. Opening a card reuses the roster's
// dialog through the hash key group=<id>; the network's own keys (net_*) are kept in the hash.
mountGroupsNetwork(document.getElementById("groups-network"), await loadNetworkJson("groups/groups_graph.json", {url: networkDataUrl}).catch(() => null), {
  onOpenGroup: (id) => {
    const params = new URLSearchParams(location.hash.replace(/^#/, ""));
    params.set("group", id);
    location.hash = params.toString();
  }
});
```
