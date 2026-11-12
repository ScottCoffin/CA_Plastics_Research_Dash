// Post-processes the Framework build (runs automatically after `npm run build`).
// Framework 1.13.4 hardcodes parts of its page template that fail accessibility audits and
// rewrites header links that leave the app root (UX-1, docs/EM_spec.md):
//   - <html> has no lang attribute (axe html-has-lang)          -> <html lang="en">
//   - the viewport meta sets maximum-scale=1, blocking zoom      -> removed (axe meta-viewport)
//   - the header's "Classic site" link (class atlas-classic) is rewritten from ../ to ./,
//     i.e. the page the reader is already on                     -> ../index.html
// Every page sits at the top level of the app (check_at5.py), so ../index.html always
// reaches the classic site root beside the app.
import {readdirSync, readFileSync, statSync, writeFileSync} from "node:fs";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dist = join(here, "..", process.env.ATLAS_FW_OUT || "dist");

export function fixHtml(html) {
  return html
    .replace(/<html>/, '<html lang="en">')
    .replace(/(<meta name="viewport" content="[^"]*?),\s*maximum-scale=1/, "$1")
    .replace(/<a href="[^"]*" class="atlas-classic">/g, '<a href="../index.html" class="atlas-classic">')
    .replace(/<a class="atlas-classic" href="[^"]*">/g, '<a class="atlas-classic" href="../index.html">');
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
    const after = fixHtml(before);
    if (after !== before) {
      writeFileSync(file, after);
      changed += 1;
    }
  }
  console.log(`postbuild: fixed ${changed} HTML files in ${dist}`);
}
