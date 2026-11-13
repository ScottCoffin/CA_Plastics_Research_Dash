// AT-5 Observable Framework shell (ADR-EM5-FRAMEWORK-2026-11-12, ADR-AT5-SHELL-2026-11-12).
// The build is deployed under <site>/app/ beside the classic site/, which stays the live root
// until the owner approves the switch after parity checks. Pages read the classic site's
// data at runtime (components/atlas.js), so both shells always show the same snapshot.
// Every page lives at the top level of src/ (atlas.js resolves ../data/ from the page URL).
const REPO = "https://github.com/ScottCoffin/CA_Plastics_Research_Dash";

export default {
  title: "CA Plastics Research Atlas",
  root: "src",
  // ATLAS_FW_OUT lets parallel local builds use separate folders (dist-*/ is gitignored).
  output: process.env.ATLAS_FW_OUT || "dist",
  theme: ["air", "near-midnight"],
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
    {name: "Institutions", path: "/institutions"},
    {name: "Monitoring", path: "/monitoring"},
    {name: "Funding", path: "/funding"},
    {name: "Evidence map", path: "/evidence"},
    {name: "Policy", path: "/policy"},
    {name: "Related resources", path: "/resources"},
    {name: "About", path: "/about"},
    {name: "Glossary", path: "/glossary"}
  ],
  header: `<span class="atlas-header">California research atlas · <a class="atlas-classic" href="../index.html">Classic site</a></span>`,
  footer: `Independent project; not an official OEHHA or State product. ` +
    `<a href="./glossary">Glossary</a>. ` +
    `<a href="${REPO}/issues/new?title=Atlas%20data%20correction" target="_blank" rel="noreferrer">Report a correction</a>.`
};
