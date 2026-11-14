// AT-5 Observable Framework shell (ADR-EM5-FRAMEWORK-2026-11-12, ADR-AT5-SHELL-2026-11-12).
// Since the owner's H16 switch (2026-11-13) the deploy puts this build at the site root over
// the classic site/ (scripts/assemble_site.py; /app/, grants.html, sem.html and expert.html
// become redirects). Pages read site/data at runtime (components/atlas.js).
// Every page lives at the top level of src/ (atlas.js resolves ../data/ from the page URL).
const REPO = "https://github.com/ScottCoffin/CA_Plastics_Research_Dash";

export default {
  title: "CA Plastics Research Atlas",
  root: "src",
  // ATLAS_FW_OUT lets parallel local builds use separate folders (dist-*/ is gitignored).
  output: process.env.ATLAS_FW_OUT || "dist",
  theme: "air",
  head: `<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='8' cy='8' r='7' fill='%23075a46'/%3E%3C/svg%3E">`,
  style: "style.css",
  // No external CDNs (C5/S3.7): drop Framework's default Google Fonts link; system fonts apply.
  globalStylesheets: [],
  search: false,
  toc: false,
  pager: false,
  sidebar: true,
  pages: [
    {name: "Experts", path: "/experts"},
    {name: "Collaboration network", path: "/network"},
    {name: "Institutions", path: "/institutions"},
    {name: "Monitoring", path: "/monitoring"},
    {name: "Funding", path: "/funding"},
    {name: "Evidence map", path: "/evidence"},
    {name: "Policy", path: "/policy"},
    {name: "Related resources", path: "/resources"},
    {name: "About", path: "/about"},
    {name: "Glossary", path: "/glossary"}
  ],
  header: `<span class="atlas-header">California research atlas</span>`,
  footer: `Independent project; not an official OEHHA or State product. ` +
    `<a href="./glossary">Glossary</a>. ` +
    `<a href="${REPO}/issues/new?title=Atlas%20data%20correction" target="_blank" rel="noreferrer">Report a correction</a>.`
};
