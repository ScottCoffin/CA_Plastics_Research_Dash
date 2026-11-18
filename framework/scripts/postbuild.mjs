// Post-processes the Framework build (runs automatically after `npm run build`).
// Framework 1.13.4 hardcodes parts of its page template that fail accessibility audits
// (UX-1, docs/EM_spec.md):
//   - <html> has no lang attribute (axe html-has-lang)          -> <html lang="en">
//   - the viewport meta sets maximum-scale=1, blocking zoom      -> removed (axe meta-viewport)
//   - the sidebar toggle is labelled only by title (axe label-title-only) -> adds aria-label
// The header's former "Classic site" link was removed at the H16 switch (app at the root).
// Pages with their own frontmatter head lose the config head, so addGlobalHead restores the
// font faces, favicon and site search (VD-19) there too.
import {readdirSync, readFileSync, statSync, writeFileSync} from "node:fs";
import {dirname, join, relative, sep} from "node:path";
import {fileURLToPath} from "node:url";
import frameworkConfig from "../observablehq.config.js";

const here = dirname(fileURLToPath(import.meta.url));
const dist = join(here, "..", process.env.ATLAS_FW_OUT || "dist");
const FONT_PRELOAD =
  '<link rel="preload" href="./assets/fonts/Archivo-Variable-latin.woff2" ' +
  'as="font" type="font/woff2" crossorigin>';
// Matches the preload at any depth (./ for root pages, ../ after nestAssets), so fixHtml is idempotent.
const FONT_PRELOAD_PATTERN = /<link\b(?=[^>]*\bhref=["'](?:\.\.?\/)+assets\/fonts\/Archivo-Variable-latin\.woff2["'])[^>]*>\s*/gi;
const SKIP_LINK = '<a class="atlas-skip-link" href="#observablehq-main">Skip to content</a>';
const CONFIG_HEAD = frameworkConfig.head;
const GLOBAL_FONT_STYLE = CONFIG_HEAD.match(/<style\b[\s\S]*?<\/style>/i)?.[0];
const GLOBAL_FAVICON = CONFIG_HEAD.match(
  /<link\b(?=[^>]*\brel="icon")(?=[^>]*\bhref="data:image\/svg\+xml[;,])[^>]*>/i
)?.[0];
// Site search (VD-19) is loaded from the config head too, so pages with their own head get it here.
// Framework cannot resolve a head <link>/<script src> to site/assets, so the head carries an
// @import in a <style> and a small loader script instead.
const GLOBAL_SEARCH_STYLE = CONFIG_HEAD.match(
  /<style>@import url\("\.\/assets\/site_search\.css"\);<\/style>/
)?.[0];
const GLOBAL_SEARCH_SCRIPT = CONFIG_HEAD.match(
  /<script>[^<]*site_search\.js[^<]*<\/script>/
)?.[0];

if (!GLOBAL_FONT_STYLE || !GLOBAL_FAVICON || !GLOBAL_SEARCH_STYLE || !GLOBAL_SEARCH_SCRIPT) {
  throw new Error(
    "Framework config.head must include the Atlas font faces, data favicon and site search assets"
  );
}

// `page` is the built file's path below dist without ".html", with "/" separators: "index" for the
// global page, "california/experts" for a California page (PLAT-1).
export function fixHtml(html, page) {
  // Add stable page metadata first; fixTemplate then owns the final head ordering.
  return nestAssets(fixShell(fixTemplate(addGlobalHead(addDescription(html, page))), page), page);
}

// data/ and assets/ stay at the site root, so a page in a subfolder needs ../assets/ where the
// config head (written for a root page) says ./assets/. Framework's own URLs never use ./assets/.
export function nestAssets(html, page) {
  const depth = page.split("/").length - 1;
  if (!depth) return html;
  return html.replace(/(["'(])\.\/assets\//g, `$1${"../".repeat(depth)}assets/`);
}

function addGlobalHead(html) {
  const missing = [];
  if (!/@font-face\b[\s\S]*?font-family:\s*["']Archivo["']/i.test(html)) {
    missing.push(GLOBAL_FONT_STYLE);
  }
  if (!/<link\b(?=[^>]*\brel="icon")(?=[^>]*\bhref="data:image\/svg\+xml[;,])[^>]*>/i.test(html)) {
    missing.push(GLOBAL_FAVICON);
  }
  if (!/site_search\.css/.test(html)) missing.push(GLOBAL_SEARCH_STYLE);
  if (!/site_search\.js/.test(html)) missing.push(GLOBAL_SEARCH_SCRIPT);
  return missing.length ? html.replace("</head>", `${missing.join("\n")}\n</head>`) : html;
}

function fixShell(html, page) {
  let fixed = html.replace(SKIP_LINK, "");
  fixed = fixed.replace(/<body>\s*/, "<body>");
  fixed = fixed.replace("<body>", "<body>\n" + SKIP_LINK + "\n");
  fixed = fixed.replace(/<label id="observablehq-sidebar-close"[^>]*><\/label>/, "");
  fixed = fixed.replace(
    /<input id="observablehq-sidebar-toggle" type="checkbox" title="([^"]*)" aria-label="([^"]*)">/,
    '<input id="observablehq-sidebar-toggle" type="checkbox" title="$1" aria-label="$2" aria-hidden="true" tabindex="-1">'
  );
  fixed = fixed.replace(
    /(<li class="observablehq-link observablehq-link-active"><a)(?![^>]*\baria-current=)/g,
    '$1 aria-current="page"'
  );
  if (page === "california/index") {
    fixed = fixed.replace(
      /(<li class="observablehq-link observablehq-link-active"><a)(?![^>]*\baria-label=)/,
      '$1 aria-label="Overview"'
    );
  }
  return fixed;
}

function fixTemplate(html) {
  const withoutFontPreloads = html.replace(FONT_PRELOAD_PATTERN, "");
  return withoutFontPreloads
    .replace(/<html>/, '<html lang="en">')
    .replace(/(<meta name="viewport" content="[^"]*?),\s*maximum-scale=1/, "$1")
    .replace(/<input id="observablehq-sidebar-toggle" type="checkbox" title="([^"]*)">/,
      '<input id="observablehq-sidebar-toggle" type="checkbox" title="$1" aria-label="$1">')
    // Owner 2026-11-17: page titles are not links. Framework wraps every heading with an id in a
    // self-link; unwrap it on h1 only (section headings keep their anchors for deep links).
    .replace(/(<h1\b[^>]*>)<a class="observablehq-header-anchor" href="#[^"]*">([\s\S]*?)<\/a>(<\/h1>)/g, "$1$2$3")
    // Inject after Framework's build so it leaves the assembled site's local URL intact.
    .replace("</head>", `${FONT_PRELOAD}\n</head>`);
}

// Plain-language meta descriptions per built page (SEO audit). Keyed by page path without .html.
export const PAGE_DESCRIPTIONS = {
  index: "Plastiverse Live: research on plastics and microplastics, organised region by region, starting with California.",
  "california/index": "Overview of the California Plastics Research Atlas, an independent guide to research on plastics in California.",
  "california/experts": "Researchers working on plastics in California, with their publications and affiliations.",
  "california/network": "Interactive map of who co-authors plastics research with whom among California experts.",
  "california/institutions": "Universities, agencies and other organisations active in California plastics research.",
  "california/institution": "One institution's plastics research: publications, lead authors, topics and collaborators.",
  "california/monitoring": "Monitoring programmes and observations of plastics in California, with sources, locations and licence details.",
  "california/funding": "Grants and funding programmes that support California plastics research, with totals by source and year.",
  "california/evidence": "Evidence map of California plastics research: filter studies by topic, year and source.",
  "california/policy": "Timeline of California and related policies on plastics, with dates and the sources behind each entry.",
  "california/resources": "Related resources on plastics in California, including data portals, reports and the organisations that maintain them.",
  "california/about": "About the Atlas: what it covers, how the data is sourced, and how to cite it.",
  "california/glossary": "Plain-language definitions of terms used in the California Plastics Research Atlas.",
  "california/styleguide": "Reference for the shared styles, icons, filters, tables, charts and accessible components used throughout the California Plastics Research Atlas.",
};

export function addDescription(html, page) {
  const text = PAGE_DESCRIPTIONS[page];
  if (!text || /<meta name="description"/.test(html)) return html;
  const content = text.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
  return html.replace("</head>", `<meta name="description" content="${content}">
</head>`);
}

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path, out);
    else if (name.endsWith(".html")) out.push(path);
  }
  return out;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  let changed = 0;
  for (const file of walk(dist)) {
    const before = readFileSync(file, "utf8");
    const page = relative(dist, file).split(sep).join("/").replace(/\.html$/, "");
    const after = fixHtml(before, page);
    if (after !== before) {
      writeFileSync(file, after);
      changed += 1;
    }
  }
  console.log(`postbuild: fixed ${changed} HTML files in ${dist}`);
}
