// AT-5 Observable Framework shell (ADR-EM5-FRAMEWORK-2026-11-12, ADR-AT5-SHELL-2026-11-12).
// Since the owner's H16 switch (2026-11-13) the deploy puts this build at the site root over
// the classic site/ (scripts/assemble_site.py; /app/, grants.html, sem.html and expert.html
// become redirects). Pages read site/data at runtime (components/atlas.js).
// Every page lives at the top level of src/ (atlas.js resolves ../data/ from the page URL).
const REPO = "https://github.com/ScottCoffin/CA_Plastics_Research_Dash";
const CA_MARK = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9Ii00NDMgLTU1NyA5NzAgMTA1NSIgYXJpYS1oaWRkZW49InRydWUiIGZvY3VzYWJsZT0iZmFsc2UiPjxzdHlsZT4ubWFyay1sYW5ke2ZpbGw6IzA3NWE0Nn0ubWFyay1saW5le3N0cm9rZTojYzQ1MTAwO3N0cm9rZS13aWR0aDoxNH08L3N0eWxlPjxwYXRoIGNsYXNzPSJtYXJrLWxhbmQiIGQ9Ik00NjksNDc0TDQ5Miw0NThMNDY5LDQwN0w0ODYsMzc5TDQ4OCwzMzZMNTIzLDI5OUw1MDEsMjgwTDQ3OCwyMjFMLTAsLTIyMUwtMCwtNTUzTC0zNzUsLTU1M0wtMzc5LC01MjhMLTM2MSwtNDkwTC0zNzYsLTQxNkwtMzY5LC00MjdMLTM2MywtNDI1TC0zOTIsLTM4MUwtMzQzLC0zMTNMLTMzMSwtMjEyTC0yNzgsLTE2MEwtMjUyLC0xMjFMLTI2NiwtMTM3TC0yNjksLTExMEwtMjYzLC0xMTBMLTI2NSwtMTEyTC0yNjEsLTExNEwtMjYyLC0xMTdMLTI2MCwtMTE4TC0yMjUsLTkwTC0yMTMsLTEyOEwtMTg5LC0xMTVMLTE1MCwtMTI3TC0xNTgsLTExNUwtMTU1LC0xMTRMLTE0OSwtMTIxTC0xNDMsLTEyMkwtMTMyLC0xMTZMLTEyOSwtMTExTC0xNDMsLTEyMkwtMTUwLC0xMTJMLTIxMCwtMTEyTC0xODEsLTUxTC0yMTEsLTY3TC0yMTQsLTkwTC0yMjQsLTU5TC0yMDgsLTEzTC0xNjAsMThMLTE1NywzMUwtMTc2LDQ2TC0xNjksNzdMLTc5LDE3M0wtNzgsMTk2TC01NywyMDZMLTU3LDI2OUwtNDAsMjgzTDM5LDI4Nkw3NywzMjFMMTMyLDMyOUwxNDEsMzYwTDE1MiwzNjVMMTUzLDM1OUwxNTUsMzU4TDE1OCwzNTdMMTYxLDM2MUwxNjcsMzYwTDIyMSw0MDVMMjU2LDQ5NEw0NjksNDc0WiIvPjxwYXRoIGNsYXNzPSJtYXJrLWxpbmUiIGZpbGw9Im5vbmUiIGQ9Ik0tMzk4LC00MTJMLTQxMywtMzc2TC0zNjQsLTMwNUwtMzUxLC0yMDJMLTI4OSwtMTM2TC0yODYsLTk2TC0yNDIsLTc2TC0yNDUsLTUxTC0yMjksLTZMLTE4NywyN0wtMTk4LDQzTC0xODUsOTJMLTEwMSwxODJMLTk4LDIwNUwtNzksMjIwTC03NiwyNzlMLTQ4LDMwM0wzMCwzMDhMNjMsMzM3TDExNSwzNDlMMTI1LDM3NUwxNjIsMzg0TDIwMyw0MThMMjMyLDQ5NE0tMzk3LC01NTNMLTQwMSwtNTI1TC0zODQsLTQ4OEwtMzk4LC00MTIiLz48cGF0aCBjbGFzcz0ibWFyay1saW5lIiBmaWxsPSJub25lIiBkPSJNLTQyMywtNDIwTC00MzksLTM3MEwtMzg5LC0yOTVMLTM3NCwtMTkxTC0zMTUsLTEzMEwtMzA1LC03OUwtMjcxLC02MkwtMjUzLDNMLTIyMiwzNUwtMjA0LDExMEwtMTI2LDE5M0wtMTA1LDIzNUwtMTAwLDI5MEwtNTcsMzI4TDIwLDMzM0w0NSwzNTZMOTUsMzcyTDEyMyw0MDVMMTU1LDQxMkwxODEsNDM0TDIwNCw0OTRNLTQyMywtNTUzTC00MjcsLTUyMkwtNDExLC00ODRMLTQyMywtNDIwIi8+PC9zdmc+";
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

function atlasHeader({title, path}) {
  const current = PAGE_LABELS.get(path);
  const pageTitle = title || (path === "/index" ? "Overview" : "CA Plastics Research Atlas");
  const breadcrumb = current
    ? '<span class="atlas-header__group">' + current[1] + '</span><span aria-hidden="true">/</span><span class="atlas-header__page">' + pageTitle + '</span>'
    : '<span class="atlas-header__page">' + pageTitle + '</span>';
  return '<button id="atlas-menu-button" class="atlas-menu-button" type="button" aria-label="Toggle navigation menu" aria-controls="observablehq-sidebar" aria-expanded="false"><svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"></path></svg></button>' +
    '<a class="atlas-header__brand" href="./"><img src="' + CA_MARK + '" alt=""><span>CA Plastics Research Atlas</span></a>' +
    '<nav class="atlas-header__breadcrumb" aria-label="Page location">' + breadcrumb + '</nav>' +
    '<form class="atlas-header__search" action="./experts" method="get" data-atlas-expert-search><label for="atlas-header-search-input">Search experts</label><input id="atlas-header-search-input" name="search" type="search" placeholder="Search experts" autocomplete="off"><button type="submit">Search</button></form>' +
    '<button id="atlas-search-toggle" class="atlas-search-toggle" type="button" aria-label="Show expert search" aria-controls="atlas-header-search-input" aria-expanded="false"><svg aria-hidden="true" focusable="false" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"></circle><path d="m16 16 4.5 4.5"></path></svg></button>' +
    '<script>document.addEventListener("DOMContentLoaded",()=>{const t=document.getElementById("observablehq-sidebar-toggle"),b=document.getElementById("atlas-menu-button");if(t&&b)b.setAttribute("aria-expanded",String(t.checked||t.indeterminate))});document.addEventListener("click",e=>{const m=e.target.closest("#atlas-menu-button"),s=e.target.closest("#atlas-search-toggle"),t=document.getElementById("observablehq-sidebar-toggle");if(m&&t){t.click();m.setAttribute("aria-expanded",String(t.checked||t.indeterminate))}if(s){const h=document.getElementById("observablehq-header"),i=document.getElementById("atlas-header-search-input"),x=s.getAttribute("aria-expanded")!=="true";h.classList.toggle("atlas-search-open",x);s.setAttribute("aria-expanded",String(x));s.setAttribute("aria-label",x?"Hide expert search":"Show expert search");if(x)i.focus()}if(t&&e.target===t){const b=document.getElementById("atlas-menu-button");if(b)b.setAttribute("aria-expanded",String(t.checked||t.indeterminate))}});document.addEventListener("submit",e=>{const f=e.target.closest("[data-atlas-expert-search]");if(!f)return;e.preventDefault();const u=new URL(f.action,location.href);u.hash=new URLSearchParams({search:f.elements.search.value.trim()}).toString();location.assign(u.href)})</script>';
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
        font-family: "Barlow Semi Condensed";
        font-style: normal;
        font-weight: 600;
        font-display: swap;
        src: url("./assets/fonts/BarlowSemiCondensed-SemiBold-latin.woff2") format("woff2");
        unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304,
          U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
      }
      @font-face {
        font-family: "Barlow Semi Condensed";
        font-style: normal;
        font-weight: 700;
        font-display: swap;
        src: url("./assets/fonts/BarlowSemiCondensed-Bold-latin.woff2") format("woff2");
        unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304,
          U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
      }
    </style>
    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='8' cy='8' r='7' fill='%23075a46'/%3E%3C/svg%3E">`,
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
    '<li><a href="' + REPO + '/issues/new?title=Atlas%20data%20correction" target="_blank" rel="noreferrer">Report a correction</a></li>' +
    '<li><a href="' + REPO + '" target="_blank" rel="noreferrer">Source code</a></li></ul></nav>'
};
