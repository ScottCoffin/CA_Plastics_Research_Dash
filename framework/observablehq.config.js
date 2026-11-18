// AT-5 Observable Framework shell (ADR-EM5-FRAMEWORK-2026-11-12, ADR-AT5-SHELL-2026-11-12).
// Since the owner's H16 switch (2026-11-13) the deploy puts this build at the site root over
// the classic site/ (scripts/assemble_site.py; /app/, grants.html, sem.html and expert.html
// become redirects). Pages read site/data at runtime (components/atlas.js).
// PLAT-1 (2026-11-17): the California pages live in src/california/ and deploy to /california/;
// src/index.md is the global Plastiverse Live page. data/ and assets/ stay at the site root, so
// California pages read ../data/ (atlas.js siteRoot) and postbuild rewrites their head's
// ./assets/ URLs to ../assets/.
// VD-25a, VD-27: the brand mark and the favicon are the Overview's paper California: the state
// outline cut from four flat planes, one per task (indigo water, vermilion people, gold money, ink evidence).
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
const FAVICON = "data:image/svg+xml;base64," + Buffer.from(PLANE_MARK.replace(' aria-hidden="true" focusable="false"', "")).toString("base64");
const PAGE_GROUPS = [
  {name: "Explore", pages: [
    {name: "Experts", path: "/california/experts"},
    {name: "Collaboration network", path: "/california/network"},
    {name: "Institutions", path: "/california/institutions"},
  ]},
  {name: "Data", pages: [
    {name: "Monitoring", path: "/california/monitoring"},
    {name: "Funding", path: "/california/funding"},
    {name: "Evidence map", path: "/california/evidence"},
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
// to each page, so these fragments always write root-relative links ("./california/experts").
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
    <link rel="icon" href="${FAVICON}">
    <link rel="icon" type="image/png" sizes="32x32" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAFd0lEQVR4nL1XW2hcVRRde59zZyaTTB6TqFipttWKjbWK1mIRDfVBoRRBSuKjopgIYsGv/uiP03wI+iX4I0J9YauQKOqPEBVi/BAt+mEhqQrRSsVH0oxN0mQyM/fsLXtmUmJN2iaNLjj3zpx779nr7PchdHY69PeHq29+7BYCva5BSkpgQHE2CFAFEVTnoHr/T0cPjQE5BnoFK4RHf3tVUpHGNJL17KOM6tLrkckPZSHRBFYBXGNPo8NvnlDoMVUVDXGsEsu/Rwh2BzBL7P6tohXAVzULvWbb3kYpYiNUuLLN6vzZUNMBVBmrBAZyVUGxbyfipKquys4umEBHh5EAVPQu51NpVQlL7P6/ITA01BvMk4upwkshnjvCLvI4lxeuNgFU7DpCv37VX1CR/VUz/1/iUVU/0FeJBFY5riEuAFwjtjQkrryzWgTILjpN9BeAAhHkPPLR4HW6moRWhQDUFvvz6KEZAAPskkyAVGNRMR93bDGoIs651CzpPssh2jeyVMguiwCA3goJmhl/PC4XP5qjJBeUpASPMjzNKsNGQR3PBGDOpZ5v29LzAnW9F5DLkeXolRCghX9yAPcCsn/LvfW3Z0//niJkCgGTApQTpFlUakQNQUOiMeHW7p56ZfNT3+2ztTQHol4z3woJEIDnAD7QCTo1ufGdiGisrLg2Io7mFLcxUZ1YnjJbzAG0SWdTe5Lpv06Gvh+Pte3d0TsUaw68HBK02OS8Jkbu3rw9Rfpia8LfkS/FQkR8piyWVOk+jXkdKJvwfqogA2MF3nPTo0dn+vrgurpgCe284MUmD3R0sGWDetIdTZ5vP1Uulx1ZbCqYFC5W8CUa+ApyVCafPx2XM2neeVk6fPr94WvbTLj2dboVE8DQUIV9mdzBougXUbX06ZndxwBtJKEk2JRNRFF+Oo7TSbe9ORkNjr7VfiV19YfBXIcVu3OClnpQLXvQwQ74jcn2LxPkts6JiClAnQY8AOVG8kZmfhVVjTNp50slPT47o7vWPzZ8TAc7PO0YipenAUMOZCQ28PVXqdKtRRGtdEplAGshaCa3ULiBiPzUTAjO07r6DD4fPdy+zYQbCSyXAJkn50Bftw0fV9WXWyJnbVqopMjrAKbFtcdMbqYQAkCXNqT4s18Ob7rnXCQI50CtLJkp5MTO619rhuueSMdF7oInJlfxiiVWEFVJemZ2VJotysPrHhx+/5tXb4m2Pvlt+YI0YDAfqJi2s9Ot/WS459Tp8GHzDS4ZNRLMxS0o7QVRwFSzcKgSF0oixZJEdQl6b/TQph4T3tdZ+fQMGOdBjYRdKfb07B/Z+I+T44KZosQikMhB6pOkTWnSlgZGNlMd9rulwXFdguAYenlrdHD8g837u/oRLE8sWP/C0AH4ISDOtrW83Zjkh5IJzDWkyNenmDJpokya0ZRmba5naqonaWpw3FhH2ljP3JAizaRdWNPqU8WS7L36kZF3ta+TLVSXU0C8abqtpfkgmLuDKMTUHayNVhELT0sWtSpurat1DJ5JIw94R3FDHfuEx5Effp7YXtO+LIdApXtesybTGseJm1gkIcBuYtpnAWEcFjOrETIfsXsQDcTsHPDEyXz+NQDuopuvbLbpfgZvA+GZyqFF1bLoYmnYaom51PegcN/4+NRoLcKWDfpnI1OtfG3ZbA9InyaiG+1ws4iDly1li8obExOnumtnknglLZUJDbUhtd1GplJRulNVBmpV8+ySXJlT5Y/nzTk/ebEwIpZcEvl8fkrhulW1WCNgz+abSyPKgKQXNry8CgTmUTK1TkxM/AbFADN7InI0n7JVp1X1T1LdsPCj1T4BVNr51tbGrUR+FyScANOYCI85F0+USpSfnJy0zvsM/gZz7pTHJ13uYwAAAABJRU5ErkJggg==">
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
  header: atlasHeader,
  // Owner 2026-11-17: the footer credits the creator instead of the former disclaimer.
  footer: '<p class="atlas-footer__note">Created by <a href="https://scottcoff.in" target="_blank" rel="noreferrer">Scott Coffin</a>.</p>' +
    '<nav aria-label="Footer links"><ul class="atlas-footer__links">' +
    '<li><a href="./california/about">About</a></li><li><a href="./california/glossary">Glossary</a></li>' +
    '<li><a href="./california/about#how-to-cite">How to cite</a></li>' +
    '<li><a href="./california/about#get-updates">Get updates</a></li>' +
    '<li><a href="mailto:theplastiverse@gmail.com?subject=Atlas%20data%20correction" rel="external">Report a correction</a></li></ul></nav>'
};
