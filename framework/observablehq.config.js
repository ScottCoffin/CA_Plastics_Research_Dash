import {readFileSync} from "node:fs";
// AT-5 Observable Framework shell (ADR-EM5-FRAMEWORK-2026-11-12, ADR-AT5-SHELL-2026-11-12).
// Since the owner's H16 switch (2026-11-13) the deploy puts this build at the site root over
// the classic site/ (scripts/assemble_site.py; /app/, grants.html, sem.html and expert.html
// become redirects). Pages read site/data at runtime (components/atlas.js).
// PLAT-1 (2026-11-17): the California pages live in src/california/ and deploy to /california/;
// src/index.md is the global Plastiverse Live page. data/ and assets/ stay at the site root, so
// California pages read ../data/ (atlas.js siteRoot) and postbuild rewrites their head's
// ./assets/ URLs to ../assets/.
// VD-25a, VD-27: the header brand mark (CA_MARK) is the Overview's paper California: the state
// outline cut from four flat planes, one per task (indigo water, vermilion people, gold money, ink evidence).
// FAVICON-MAIN (owner 2026-11-26): the favicon is the Plastiverse Live sun instead, read from the
// site/assets icon files (made by scripts/build_favicons.py); the header keeps the paper California.
const CA_OUTLINE = "M469,474L492,458L469,407L486,379L488,336L523,299L501,280L478,221L0,-221L0,-553L-375,-553L-379,-528L-361,-490L-376,-416L-369,-427L-363,-425L-392,-381L-343,-313L-331,-212L-278,-160L-252,-121L-266,-137L-269,-110L-225,-90L-213,-128L-189,-115L-150,-127L-158,-115L-149,-121L-143,-122L-132,-116L-129,-111L-150,-112L-210,-112L-181,-51L-211,-67L-214,-90L-224,-59L-208,-13L-160,18L-157,31L-176,46L-169,77L-79,173L-78,196L-57,206L-57,269L-40,283L39,286L77,321L132,329L141,360L167,360L221,405L256,494L469,474Z";
const PLANE_MARK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-400 -560 930 1070" aria-hidden="true" focusable="false">' +
  '<defs><clipPath id="m"><path d="' + CA_OUTLINE + '"/></clipPath></defs><g clip-path="url(#m)">' +
  '<polygon fill="#23305e" points="-470,-575 560,-575 560,-150 -470,-150"/>' +
  '<polygon fill="#e2452b" points="-470,-150 70,-150 -70,205 -470,205"/>' +
  '<polygon fill="#e3a92b" points="70,-150 560,-150 560,250 -70,205"/>' +
  '<polygon fill="#141311" points="-470,205 -70,205 560,250 560,520 -470,520"/></g></svg>';
const CA_MARK = "data:image/svg+xml;base64," + Buffer.from(PLANE_MARK).toString("base64");
// Base64, like CA_MARK: Framework re-escapes "%" inside head hrefs (%23 became %2523), which turned every
// fill into an invalid colour and broke the clip, so browsers drew a black square (owner 2026-11-17).
// Both icons are read from site/assets at config time, so the favicon always matches the files (FAVICON-MAIN).
const FAVICON = "data:image/svg+xml;base64," + readFileSync(new URL("../site/assets/favicon.svg", import.meta.url)).toString("base64");
const FAVICON_PNG = "data:image/png;base64," + readFileSync(new URL("../site/assets/favicon-32.png", import.meta.url)).toString("base64");
const PAGE_GROUPS = [
  {name: "Explore", pages: [
    {name: "Authors", path: "/california/authors"},
    {name: "Collaboration network", path: "/california/network"},
    {name: "Institutions", path: "/california/institutions"},
  ]},
  {name: "Data", pages: [
    {name: "Monitoring", path: "/california/monitoring"},
    {name: "Funding", path: "/california/funding"},
    {name: "Topics", path: "/california/topics"},
    {name: "Evidence map", path: "/california/evidence"},
    {name: "Quality", path: "/california/quality"},
  ]},
  {name: "Context", pages: [
    {name: "Policy", path: "/california/policy"},
    {name: "Related resources", path: "/california/resources"},
  ]},
  {name: "Reference", pages: [
    {name: "About", path: "/california/about"},
    {name: "Glossary", path: "/california/glossary"},
  ]},
];
// Framework resolves header and footer links against the site root and then makes them relative
// to each page, so these fragments always write root-relative links ("./california/authors").
const PAGE_LABELS = new Map(PAGE_GROUPS.flatMap(({name, pages}) => pages.map(({name: label, path}) => [path, [label, name]])));

// VD-21: the four PAGE_GROUPS as disclosure buttons for the desktop header (hidden at <= 52rem, where
// the Framework sidebar drawer keeps the groups). Each button controls its own panel; the current
// page's link gets aria-current="page" and its group button is highlighted.
function topNav(path) {
  const groups = PAGE_GROUPS.map(({name, pages}) => {
    const id = "atlas-topnav-" + name.toLowerCase();
    const current = pages.some(page => page.path === path);
    const links = pages.map(page => '<li><a class="atlas-topnav__link" href=".' + page.path + '"' +
      (page.path === path ? ' aria-current="page"' : "") + ">" + page.name + "</a></li>").join("");
    return '<li class="atlas-topnav__item"><button type="button" class="atlas-topnav__button' +
      (current ? " atlas-topnav__button--current" : "") + '" aria-expanded="false" aria-controls="' + id + '">' +
      name + '</button><div class="atlas-topnav__panel" id="' + id + '" hidden><ul>' + links + "</ul></div></li>";
  });
  return '<nav class="atlas-topnav" aria-label="Primary"><ul class="atlas-topnav__list">' + groups.join("") + "</ul></nav>";
}

// VD-21: disclosure behaviour for the top nav, appended to the header's inline script. One group
// is open at a time; Esc closes it and returns focus to its button; focus leaving the group or a
// click outside the nav closes it. Closed panels use the hidden attribute, so their links are not tabbable.
const TOP_NAV_JS = `
(() => {
  const setOpen = (button, open) => {
    const panel = document.getElementById(button.getAttribute("aria-controls"));
    button.setAttribute("aria-expanded", String(open));
    if (panel) panel.hidden = !open;
  };
  const openButtons = () => Array.from(document.querySelectorAll('.atlas-topnav__button[aria-expanded="true"]'));
  const closeAll = except => openButtons().forEach(button => { if (button !== except) setOpen(button, false); });
  document.addEventListener("click", event => {
    const button = event.target.closest?.(".atlas-topnav__button");
    if (button) {
      const open = button.getAttribute("aria-expanded") !== "true";
      closeAll(button);
      setOpen(button, open);
    } else if (!event.target.closest?.(".atlas-topnav")) {
      closeAll(null);
    }
  });
  document.addEventListener("keydown", event => {
    const [open] = openButtons();
    if (event.key !== "Escape" || !open) return;
    const inNav = Boolean(event.target.closest?.(".atlas-topnav"));
    setOpen(open, false);
    if (inNav) open.focus();
  });
  document.addEventListener("focusout", event => {
    const item = event.target.closest?.(".atlas-topnav__item");
    if (!item || (event.relatedTarget && item.contains(event.relatedTarget))) return;
    const button = item.querySelector(".atlas-topnav__button");
    if (button && button.getAttribute("aria-expanded") === "true") setOpen(button, false);
  });
})();
`;

function atlasHeader({title, path}) {
  const current = PAGE_LABELS.get(path);
  const pageTitle = title || (path === "/california/index" ? "Overview" : "CA Plastics Research Atlas");
  const breadcrumb = current
    ? '<span class="atlas-header__group">' + current[1] + '</span><span aria-hidden="true">/</span><span class="atlas-header__page">' + pageTitle + '</span>'
    : '<span class="atlas-header__page">' + pageTitle + '</span>';
  return '<button id="atlas-menu-button" class="atlas-menu-button" type="button" aria-label="Toggle navigation menu" aria-controls="observablehq-sidebar" aria-expanded="false"><svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"></path></svg></button>' +
    '<a class="atlas-header__brand" href="./california/"><img src="' + CA_MARK + '" alt=""><span>CA Plastics Research Atlas</span></a>' +
    topNav(path) +
    '<nav class="atlas-header__breadcrumb" aria-label="Page location">' + breadcrumb + '</nav>' +
    '<form class="atlas-header__search" action="./search" method="get" role="search" data-atlas-site-search><label for="atlas-header-search-input">Search the Atlas</label><input id="atlas-header-search-input" name="q" type="search" placeholder="Search authors, institutions, topics, funders…" autocomplete="off"><button type="submit">Search</button></form>' +
    '<button id="atlas-search-toggle" class="atlas-search-toggle" type="button" aria-label="Show search" aria-controls="atlas-header-search-input" aria-expanded="false"><svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"></circle><path d="m16 16 4.5 4.5"></path></svg></button>' +
    '<script>document.addEventListener("DOMContentLoaded",()=>{const t=document.getElementById("observablehq-sidebar-toggle"),b=document.getElementById("atlas-menu-button");if(t&&b)b.setAttribute("aria-expanded",String(t.checked||t.indeterminate))});document.addEventListener("click",e=>{const m=e.target.closest("#atlas-menu-button"),s=e.target.closest("#atlas-search-toggle"),t=document.getElementById("observablehq-sidebar-toggle");if(m&&t){t.click();m.setAttribute("aria-expanded",String(t.checked||t.indeterminate))}if(s){const h=document.getElementById("observablehq-header"),i=document.getElementById("atlas-header-search-input"),x=s.getAttribute("aria-expanded")!=="true";h.classList.toggle("atlas-search-open",x);s.setAttribute("aria-expanded",String(x));s.setAttribute("aria-label",x?"Hide search":"Show search");if(x)i.focus()}if(t&&e.target===t){const b=document.getElementById("atlas-menu-button");if(b)b.setAttribute("aria-expanded",String(t.checked||t.indeterminate))}});' + TOP_NAV_JS + '</script>';
}

const REGION_SHELLS = {
  norway: {label: "Norway", path: "norway", routes: [
    ["Authors", "authors"], ["Institutions", "institutions"], ["Network", "network"],
    ["Topics", "topics"], ["Evidence", "evidence"], ["Search", "search"],
  ]},
  belgium: {label: "Belgium", path: "belgium", routes: [
    ["Authors", "authors"], ["Institutions", "institutions"], ["Network", "network"],
    ["Topics", "topics"], ["Evidence", "evidence"], ["Search", "search"],
  ]},
};

function regionShell(path) {
  const normalized = path.replace(/^\/+/, "");
  const slug = normalized.split("/")[0];
  const region = REGION_SHELLS[slug];
  if (!region) return null;
  const routeLinks = region.routes.map(([label, route]) =>
    `<li><a href="./${region.path}/${route}"${normalized === `${region.path}/${route}` ? ' aria-current="page"' : ""}>${label}</a></li>`
  ).join("");
  return {region, routeLinks, path: normalized};
}

function regionHeader({title, path}) {
  const shell = regionShell(path);
  if (!shell) return atlasHeader({title, path});
  const {region, routeLinks, path: normalized} = shell;
  const current = region.routes.find(([, route]) => normalized === `${region.path}/${route}`)?.[0] || title || "Overview";
  return `<div class="pv-region-header">
  <a class="pv-region-brand" href="./" aria-label="Plastiverse Live home"><svg viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="5"/><g>${Array.from({length: 16}, (_, i) => { const a = i * Math.PI / 8; const x1 = (13 + Math.cos(a) * 7.6).toFixed(2); const y1 = (13 + Math.sin(a) * 7.6).toFixed(2); const x2 = (13 + Math.cos(a) * 10.4).toFixed(2); const y2 = (13 + Math.sin(a) * 10.4).toFixed(2); return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`; }).join("")}</g></svg><span class="pv-region-wordmark">PLASTIVERSE <b>LIVE</b></span></a>
  <span class="pv-region-context"><a href="./${region.path}/">${region.label}</a><span aria-hidden="true">/</span><span aria-current="page">${current}</span></span>
  <details class="pv-region-menu"><summary>Menu</summary><nav aria-label="${region.label} header pages"><ul><li><a href="./${region.path}/">${region.label} home</a></li>${routeLinks}</ul><ul class="pv-region-menu-main" aria-label="Main site"><li><a href="./explore">Explore all regions</a></li><li><a href="./groups">Community groups</a></li><li><a href="./ambassadors">Ambassadors</a></li></ul></nav></details>
  <form class="pv-region-search" action="./search" method="get" role="search" aria-label="Search ${region.label} atlas" data-atlas-site-search><label for="pv-region-q">Search ${region.label}</label><input id="pv-region-q" name="q" type="search" placeholder="Search ${region.label}"/><button type="submit">Search</button></form>
  <nav class="pv-region-main-links" aria-label="Plastiverse Live"><a href="./explore">Explore</a><a href="./groups">Community groups</a><a href="./ambassadors">Ambassadors</a></nav>
</div>`;
}

function regionFooter({path}) {
  const shell = regionShell(path);
  if (!shell) return '<p class="atlas-footer__note">Created by <a href="https://scottcoff.in" target="_blank" rel="noreferrer">Scott Coffin</a>.</p>' +
    '<nav aria-label="Footer links"><ul class="atlas-footer__links">' +
    '<li><a href="./california/about">About</a></li><li><a href="./california/glossary">Glossary</a></li>' +
    '<li><a href="./california/quality">Quality</a></li><li><a href="./california/topics">Topics</a></li>' +
    '<li><a href="./california/about#how-to-cite">How to cite</a></li>' +
    '<li><a href="./california/about#get-updates">Get updates</a></li>' +
    '<li><a href="mailto:theplastiverse@gmail.com?subject=Atlas%20data%20correction" rel="external">Report a correction</a></li></ul></nav>';
  const {region, routeLinks} = shell;
  return `<div class="pv-region-footer"><div class="pv-region-footer-brand"><a href="./">Plastiverse Live</a><img src="./assets/landing/logo_564.webp" width="282" height="247" alt="Plastiverse Live logo: scattered plastic fragments flow into a bright node and a network of research" loading="lazy"><span>${region.label} research atlas</span></div>
<nav aria-label="${region.label} footer pages"><ul>${routeLinks}</ul></nav>
<nav aria-label="Main site footer"><ul><li><a href="./explore">Explore all regions</a></li><li><a href="./groups">Community groups</a></li><li><a href="./ambassadors">Become an ambassador</a></li></ul></nav>
<p>Created by <a href="https://scottcoff.in" rel="noreferrer">Scott Coffin</a>.</p></div>`;
}

export default {
  title: "CA Plastics Research Atlas",
  root: "src",
  // ATLAS_FW_OUT lets parallel local builds use separate folders (dist-*/ is gitignored).
  output: process.env.ATLAS_FW_OUT || "dist",
  theme: "air",
  // Page-relative font URLs resolve to site/assets/fonts after assembly.
  // postbuild adds the preload after Framework has finished parsing assets.
  head: `<style>
      @font-face {
        font-family: "Archivo";
        font-style: normal;
        font-weight: 400 800;
        font-stretch: 75% 100%;
        font-display: swap;
        src: url("./assets/fonts/Archivo-Variable-latin.woff2") format("woff2");
        unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304,
          U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
      }
    </style>
    <link rel="icon" href="${FAVICON}">
    <link rel="icon" type="image/png" sizes="32x32" href="${FAVICON_PNG}">
    <style>@import url("./assets/site_search.css");</style>
    <script>(function(){var s=document.createElement("script");s.src="./assets/site_search.js";document.head.appendChild(s)})();</script>`,
  style: "style.css",
  // No external CDNs (C5/S3.7): drop Framework's default Google Fonts link; display fonts are local.
  globalStylesheets: [],
  search: false,
  toc: false,
  pager: false,
  sidebar: true,
  home: '<span class="atlas-home-brand"><img src="' + CA_MARK + '" alt=""><span>Plastiverse Live</span></span>',  // links to the global page (/)
  // The sidebar's home link is the global page (/); the California overview is its first entry.
  pages: [{name: "California overview", path: "/california/"}, ...PAGE_GROUPS],
  header: regionHeader,
  // Owner 2026-11-17: the footer credits the creator instead of the former disclaimer.
  footer: regionFooter
};
