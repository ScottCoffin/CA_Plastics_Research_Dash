// Post-processes the Framework build (runs automatically after `npm run build`).
// Framework 1.13.4 hardcodes parts of its page template that fail accessibility audits and
// rewrites header links that leave the app root (UX-1, docs/EM_spec.md):
//   - <html> has no lang attribute (axe html-has-lang)          -> <html lang="en">
//   - the viewport meta sets maximum-scale=1, blocking zoom      -> removed (axe meta-viewport)
//   - the header's "Classic site" link (class atlas-classic) is rewritten from ../ to ./,
//     i.e. the page the reader is already on                     -> ../index.html
//   - the sidebar toggle is labelled only by title (axe label-title-only) -> adds aria-label
// Every page sits at the top level of the app (check_at5.py), so ../index.html always
// reaches the classic site root beside the app.
import {readdirSync, readFileSync, statSync, writeFileSync} from "node:fs";
import {basename, dirname, join} from "node:path";
import {fileURLToPath} from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dist = join(here, "..", process.env.ATLAS_FW_OUT || "dist");

export function fixHtml(html, page) {
  return addDescription(fixTemplate(html), page);
}

function fixTemplate(html) {
  return html
    .replace(/<html>/, '<html lang="en">')
    .replace(/(<meta name="viewport" content="[^"]*?),\s*maximum-scale=1/, "$1")
    .replace(/<input id="observablehq-sidebar-toggle" type="checkbox" title="([^"]*)">/,
      '<input id="observablehq-sidebar-toggle" type="checkbox" title="$1" aria-label="$1">')
    .replace(/<a href="[^"]*" class="atlas-classic">/g, '<a href="../index.html" class="atlas-classic">')
    .replace(/<a class="atlas-classic" href="[^"]*">/g, '<a class="atlas-classic" href="../index.html">');
}

// Plain-language meta descriptions per built page (SEO audit). Keyed by page file name without .html.
export const PAGE_DESCRIPTIONS = {
  index: "Overview of the California Plastics Research Atlas, an independent guide to research on plastics in California.",
  experts: "Researchers working on plastics in California, with their publications and affiliations.",
  institutions: "Universities, agencies and other organisations active in California plastics research.",
  monitoring: "Monitoring programmes and observations of plastics in California, with sources, locations and licence details.",
  funding: "Grants and funding programmes that support California plastics research, with totals by source and year.",
  evidence: "Evidence map of California plastics research: filter studies by topic, year and source.",
  policy: "Timeline of California and related policies on plastics, with dates and the sources behind each entry.",
  resources: "Related resources on plastics in California, including data portals, reports and the organisations that maintain them.",
  about: "About the Atlas: what it covers, how the data is sourced, and how to cite it.",
  glossary: "Plain-language definitions of terms used in the California Plastics Research Atlas.",
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
    const after = fixHtml(before, basename(file, ".html"));
    if (after !== before) {
      writeFileSync(file, after);
      changed += 1;
    }
  }
  console.log(`postbuild: fixed ${changed} HTML files in ${dist}`);
}
