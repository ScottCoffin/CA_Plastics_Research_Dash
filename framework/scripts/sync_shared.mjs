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

// PLAT-2: the landing's static images (first paint = LCP, footer logo) are referenced from
// framework/src/index.md, so Framework must find them under src/ to fingerprint them. The source of
// truth stays site/assets/landing/ (scripts/build_landing_assets.py); the copies are gitignored.
export const LANDING_STATIC = ["picnic_first_paint.webp", "picnic_first_paint_800.webp", "logo_564.webp"];
const landingTarget = join(here, "..", "src", "assets", "landing");
mkdirSync(landingTarget, {recursive: true});
for (const file of LANDING_STATIC) copyFileSync(join(siteAssets, "landing", file), join(landingTarget, file));
console.log(`sync_shared: copied ${LANDING_STATIC.length} landing images from site/assets/landing`);
