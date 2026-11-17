// AT-5 Observable Framework shell (ADR-EM5-FRAMEWORK-2026-11-12, ADR-AT5-SHELL-2026-11-12).
// Since the owner's H16 switch (2026-11-13) the deploy puts this build at the site root over
// the classic site/ (scripts/assemble_site.py; /app/, grants.html, sem.html and expert.html
// become redirects). Pages read site/data at runtime (components/atlas.js).
// Every page lives at the top level of src/ (atlas.js resolves ../data/ from the page URL).
const REPO = "https://github.com/ScottCoffin/CA_Plastics_Research_Dash";
// VD-25a: the brand mark and the favicon are four flat planes (indigo, gold, vermilion, ink), one per task.
const PLANE_MARK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 30" aria-hidden="true" focusable="false"><rect width="15" height="15" fill="#23305e"/><rect x="15" width="15" height="15" fill="#e3a92b"/><rect y="15" width="15" height="15" fill="#e2452b"/><rect x="15" y="15" width="15" height="15" fill="#141311"/></svg>';
const CA_MARK = "data:image/svg+xml;base64," + Buffer.from(PLANE_MARK).toString("base64");
const PAGE_GROUPS = [
  {name: "Explore", pages: [
    {name: "Experts", path: "/experts"},
    {name: "Collaboration network", path: "/network"},
    {name: "Institutions", path: "/institutions"},
  ]},
  {name: "Data", pages: [
    {name: "Monitoring", path: "/monitoring"},
    {name: "Funding", path: "/funding"},
    {name: "Evidence map", path: "/evidence"},
  ]},
  {name: "Context", pages: [
    {name: "Policy", path: "/policy"},
    {name: "Related resources", path: "/resources"},
  ]},
  {name: "Reference", pages: [
    {name: "About", path: "/about"},
    {name: "Glossary", path: "/glossary"},
  ]},
];
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
  const pageTitle = title || (path === "/index" ? "Overview" : "CA Plastics Research Atlas");
  const breadcrumb = current
    ? '<span class="atlas-header__group">' + current[1] + '</span><span aria-hidden="true">/</span><span class="atlas-header__page">' + pageTitle + '</span>'
    : '<span class="atlas-header__page">' + pageTitle + '</span>';
  return '<button id="atlas-menu-button" class="atlas-menu-button" type="button" aria-label="Toggle navigation menu" aria-controls="observablehq-sidebar" aria-expanded="false"><svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"></path></svg></button>' +
    '<a class="atlas-header__brand" href="./"><img src="' + CA_MARK + '" alt=""><span>CA Plastics Research Atlas</span></a>' +
    topNav(path) +
    '<nav class="atlas-header__breadcrumb" aria-label="Page location">' + breadcrumb + '</nav>' +
    '<form class="atlas-header__search" action="./search" method="get" role="search" data-atlas-site-search><label for="atlas-header-search-input">Search the Atlas</label><input id="atlas-header-search-input" name="q" type="search" placeholder="Search experts, institutions, topics, funders…" autocomplete="off"><button type="submit">Search</button></form>' +
    '<button id="atlas-search-toggle" class="atlas-search-toggle" type="button" aria-label="Show search" aria-controls="atlas-header-search-input" aria-expanded="false"><svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"></circle><path d="m16 16 4.5 4.5"></path></svg></button>' +
    '<script>document.addEventListener("DOMContentLoaded",()=>{const t=document.getElementById("observablehq-sidebar-toggle"),b=document.getElementById("atlas-menu-button");if(t&&b)b.setAttribute("aria-expanded",String(t.checked||t.indeterminate))});document.addEventListener("click",e=>{const m=e.target.closest("#atlas-menu-button"),s=e.target.closest("#atlas-search-toggle"),t=document.getElementById("observablehq-sidebar-toggle");if(m&&t){t.click();m.setAttribute("aria-expanded",String(t.checked||t.indeterminate))}if(s){const h=document.getElementById("observablehq-header"),i=document.getElementById("atlas-header-search-input"),x=s.getAttribute("aria-expanded")!=="true";h.classList.toggle("atlas-search-open",x);s.setAttribute("aria-expanded",String(x));s.setAttribute("aria-label",x?"Hide search":"Show search");if(x)i.focus()}if(t&&e.target===t){const b=document.getElementById("atlas-menu-button");if(b)b.setAttribute("aria-expanded",String(t.checked||t.indeterminate))}});' + TOP_NAV_JS + '</script>';
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
    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 30 30'%3E%3Crect width='15' height='15' fill='%2323305e'/%3E%3Crect x='15' width='15' height='15' fill='%23e3a92b'/%3E%3Crect y='15' width='15' height='15' fill='%23e2452b'/%3E%3Crect x='15' y='15' width='15' height='15' fill='%23141311'/%3E%3C/svg%3E">
    <style>@import url("./assets/site_search.css");</style>
    <script>(function(){var s=document.createElement("script");s.src="./assets/site_search.js";document.head.appendChild(s)})();</script>`,
  style: "style.css",
  // No external CDNs (C5/S3.7): drop Framework's default Google Fonts link; display fonts are local.
  globalStylesheets: [],
  search: false,
  toc: false,
  pager: false,
  sidebar: true,
  home: '<span class="atlas-home-brand"><img src="' + CA_MARK + '" alt=""><span>CA Plastics Research Atlas</span></span>',
  pages: PAGE_GROUPS,
  header: atlasHeader,
  footer: '<p class="atlas-footer__note">Independent project; not an official OEHHA or State product.</p>' +
    '<nav aria-label="Footer links"><ul class="atlas-footer__links">' +
    '<li><a href="./about">About</a></li><li><a href="./glossary">Glossary</a></li>' +
    '<li><a href="./about#how-to-cite">How to cite</a></li>' +
    '<li><a href="' + REPO + '/issues/new?title=Atlas%20data%20correction" target="_blank" rel="noreferrer">Report a correction</a></li></ul></nav>'
};
