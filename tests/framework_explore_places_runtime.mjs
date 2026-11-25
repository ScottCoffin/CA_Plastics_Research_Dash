// Runtime check for the AMB-1 place helpers in framework/src/components/explore.js, run by
// tests/test_explore_places.py. It reads the committed site/data/global/places.json and asserts
// the frame, minimum-box and search behaviour. No network, no DOM.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {dirname, join} from "node:path";
import {
  foldName,
  frameExtent,
  frameXY,
  minimumBox,
  placeRows,
  searchPlaces,
} from "../framework/src/components/explore.js";

const here = dirname(fileURLToPath(import.meta.url));
const places = JSON.parse(readFileSync(join(here, "..", "site", "data", "global", "places.json"), "utf8"));

// The raster frame: the Natural Earth I crop of world.json (grid.y0 in explore.json), and the same
// projected points as tests/test_ne_projection_alignment.py, which uses scripts/build_world_map.py.
const top = frameXY(0, 84)[1], bottom = frameXY(0, -57)[1];
assert.ok(Math.abs(top - 7.3) < 0.1, `crop top ${top}`);
assert.ok(Math.abs(bottom - 442.0) < 0.1, `crop bottom ${bottom}`);
assert.ok(Math.abs(frameXY(180, 0)[0] - 1000) < 0.1, "longitude 180 is the right edge");
for (const [lon, lat, x, y] of [[0, 0, 500, 260], [134.5, 7.5, 872.6, 235.9], [-119.4, 37.2, 190.4, 140.0], [133.9, -25.3, 860.7, 341.5], [-150, -15, 87.7, 308.2], [100, 60, 727.5, 69.1]]) {
  const [fx, fy] = frameXY(lon, lat);
  assert.ok(Math.abs(fx - x) < 0.1 && Math.abs(fy - y) < 0.1, `frameXY(${lon}, ${lat}) = ${fx}, ${fy}`);
}

// Minimum box: a tiny box grows to at least 300 km each way; a large box is unchanged.
const km = (deg) => deg * 111.32;
const tiny = minimumBox([134.4, 7.2, 134.7, 7.8]);
const tinyWidthKm = (tiny[2] - tiny[0]) * 111.32 * Math.cos((7.5 * Math.PI) / 180);
assert.ok(tinyWidthKm >= 299.9, `width ${tinyWidthKm} km`);
assert.ok(km(tiny[3] - tiny[1]) >= 299.9, `height ${km(tiny[3] - tiny[1])} km`);
const big = [0, 0, 30, 20];
assert.deepEqual(minimumBox(big), big);
// A point gets a box centred on it.
const point = minimumBox([8.5, 47.5, 8.5, 47.5]);
assert.ok(Math.abs((point[0] + point[2]) / 2 - 8.5) < 1e-9);

// The projected extent of the Palau minimum box is at least 7 frame units wide (about 300 km).
const [x0, , x1] = frameExtent(minimumBox([134.4, 7.2, 134.7, 7.8]));
assert.ok(x1 - x0 >= 7, `extent ${x1 - x0}`);

// Search over the committed index.
const rows = placeRows(places);
assert.equal(rows.length, places.entries.length);
assert.equal(foldName("Curaçao"), "curacao");
const first = (q, kind) => searchPlaces(rows, q).find((r) => !kind || r.kind === kind);
assert.equal(first("Palau").kind, "country");
assert.equal(first("Palau").iso, "PW");
assert.equal(first("Nauru").iso, "NR");
assert.equal(first("Singapore", "country").iso, "SG");
assert.equal(first("Koror", "admin1").parent, "Palau");
assert.equal(first("Hordaland").parent, "Norway");
// Bergen: the Norwegian city outranks the Dutch one on population.
const bergen = searchPlaces(rows, "Bergen").filter((r) => r.kind === "city");
assert.equal(bergen[0].iso, "NO");
assert.equal(bergen[0].parent, "Hordaland, Norway");
// Accent-insensitive and prefix matches.
assert.ok(searchPlaces(rows, "malmo").some((r) => r.name === "Malmö"));
assert.ok(searchPlaces(rows, "pal").length > 0);
assert.deepEqual(searchPlaces(rows, "   "), []);
assert.ok(searchPlaces(rows, "zzqxv").length === 0);
// Countries come before regions and cities for the same text.
const ranks = searchPlaces(rows, "Niger").map((r) => r.kind);
assert.equal(ranks[0], "country");

console.log("explore places runtime checks passed");
