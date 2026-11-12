// Copies the shared, dependency-free helpers from site/assets into src/components/shared/
// so Framework pages import the same code the classic site runs (single source of truth).
// Runs automatically before `npm run build` and `npm run dev`.
import {copyFileSync, mkdirSync} from "node:fs";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const siteAssets = join(here, "..", "..", "site", "assets");
const target = join(here, "..", "src", "components", "shared");

export const SHARED_FILES = [
  "topics.js",
  "facets.js",
  "expert_page.js",
  "vendor/minisearch-7.2.0.js"
];

mkdirSync(join(target, "vendor"), {recursive: true});
for (const file of SHARED_FILES) copyFileSync(join(siteAssets, file), join(target, file));
console.log(`sync_shared: copied ${SHARED_FILES.length} files from site/assets`);
