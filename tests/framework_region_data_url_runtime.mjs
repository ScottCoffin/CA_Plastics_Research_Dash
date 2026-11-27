// Runtime checks for the region-aware data URL helpers (GP-5 step 1) in framework/src/components/atlas.js.
// Run by tests/test_region_data_url.py with the node binary found on PATH.
import assert from "node:assert/strict";
import {pathToFileURL} from "node:url";

const atlas = await import(pathToFileURL(process.argv[2]).href);
const {regionDataUrl, regionSlug, REGION_SLUGS, siteRoot} = atlas;

// The registry slugs, passed in by the Python runner (regions/_registry.yml, tier A).
const registrySlugs = JSON.parse(process.argv[3]);
assert.deepEqual([...REGION_SLUGS].sort(), [...registrySlugs].sort());

const HOST = "https://example.org";
const at = (pathname) => `${HOST}${pathname}`;

// Region slug from the page path.
assert.equal(regionSlug(at("/california/institutions")), "california");
assert.equal(regionSlug(at("/norway/institutions")), "norway");
assert.equal(regionSlug(at("/belgium/institution")), "belgium");
assert.equal(regionSlug(at("/explore")), "california");
assert.equal(regionSlug(at("/")), "california");
assert.equal(regionSlug(at("/app/norway/x")), "norway");
assert.equal(regionSlug(at("/CA_Plastics_Research_Dash/belgium/x")), "belgium");
// Only the first segment after the site root counts.
assert.equal(regionSlug(at("/explore/norway")), "california");
assert.equal(regionSlug(at("/norway-extra/institutions")), "california");

// California pages and global pages: byte-identical to the pre-GP-5 California URLs.
assert.equal(regionDataUrl("bundle/", at("/california/institutions")), `${HOST}/data/california/bundle/`);
assert.equal(regionDataUrl("open_calls.json", at("/california/")), `${HOST}/data/california/open_calls.json`);
assert.equal(regionDataUrl("/grants.json", at("/explore")), `${HOST}/data/california/grants.json`);
assert.equal(regionDataUrl("bundle/", at("/")), `${HOST}/data/california/bundle/`);
assert.equal(regionDataUrl("x.json", at("/groups")), `${HOST}/data/california/x.json`);
assert.equal(regionDataUrl("x.json", at("/app/california/x")), `${HOST}/data/california/x.json`);
assert.equal(regionDataUrl("x.json", at("/app/x")), `${HOST}/data/california/x.json`);
assert.equal(
  regionDataUrl("x.json", at("/CA_Plastics_Research_Dash/california/x")),
  `${HOST}/CA_Plastics_Research_Dash/data/california/x.json`,
);
assert.equal(
  regionDataUrl("x.json", at("/CA_Plastics_Research_Dash/explore")),
  `${HOST}/CA_Plastics_Research_Dash/data/california/x.json`,
);

// Other regions resolve under their own folder, with the same site-root handling.
assert.equal(regionDataUrl("institutions.json", at("/norway/institutions")), `${HOST}/data/norway/institutions.json`);
assert.equal(regionDataUrl("bundle/", at("/belgium/institution")), `${HOST}/data/belgium/bundle/`);
assert.equal(regionDataUrl("x.json", at("/app/norway/x")), `${HOST}/data/norway/x.json`);
assert.equal(
  regionDataUrl("x.json", at("/CA_Plastics_Research_Dash/norway/x")),
  `${HOST}/CA_Plastics_Research_Dash/data/norway/x.json`,
);

// The root site helper still resolves from the same page base as the region helper.
assert.equal(siteRoot(at("/norway/institutions")).href, `${HOST}/`);
assert.equal(siteRoot(at("/app/norway/x")).href, `${HOST}/`);
assert.equal(siteRoot(at("/app/california/x")).href, `${HOST}/`);

// With no base argument, the helper reads document.baseURI or the Node fallback (/app/ -> California).
assert.equal(regionDataUrl("x.json"), "http://localhost/data/california/x.json");

console.log("region data URL runtime checks passed");
