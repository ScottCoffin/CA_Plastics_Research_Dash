// Runtime checks for the V-3 pipeline flow helpers (EM-6). The pure helpers live in
// framework/src/components/v3_flow_model.js; the view module is imported only to confirm it loads
// in Node without touching `document` at module load.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {footerText, formatCount, stageRows, UNAVAILABLE} from "../framework/src/components/v3_flow_model.js";
import {mountV3Flow} from "../framework/src/components/v3_flow.js";

assert.equal(typeof mountV3Flow, "function");
assert.equal(UNAVAILABLE, "Pipeline counts are unavailable.");

// Thousands separators (en-US) and refusal of non-counts.
assert.equal(formatCount(1933), "1,933");
assert.equal(formatCount(0), "0");
assert.equal(formatCount(-1), "Unavailable");
assert.equal(formatCount(1.5), "Unavailable");
assert.equal(formatCount("1933"), "Unavailable");

const data = {
  release_date: "2026-11-11",
  release_version: "v2026.11.11",
  stages: [
    {stage: "Searching", status: "performed", steps: [{label: "Records", value: 1933, source: "x"}], note: null},
    {stage: "Data extraction", status: "not performed", steps: [], note: null},
    {stage: "Broken", steps: [{label: "skip", value: "nope"}], note: ""}
  ]
};
const rows = stageRows(data);
assert.equal(rows.length, 3);
assert.deepEqual(rows[0], {
  stage: "Searching",
  status: "performed",
  performed: true,
  steps: [{label: "Records", value: "1,933", raw: 1933}],
  note: null
});
assert.equal(rows[1].status, "not performed");
assert.equal(rows[1].performed, false);
assert.equal(rows[2].status, "not performed");
assert.equal(rows[2].steps[0].value, "Unavailable");
assert.equal(rows[2].note, null);

assert.deepEqual(stageRows(null), []);
assert.deepEqual(stageRows({stages: "bad"}), []);
assert.deepEqual(stageRows({stages: [null, {status: "performed"}]}), []);

assert.equal(
  footerText(data),
  "Flow follows the ROSES template for systematic maps (CC BY 4.0). Counts from the v2026.11.11 methods card."
);
assert.equal(
  footerText({...data, release_version: null}),
  "Flow follows the ROSES template for systematic maps (CC BY 4.0). Counts from the 2026-11-11 methods card."
);

// The model must stay DOM-free.
const model = readFileSync(fileURLToPath(new URL("../framework/src/components/v3_flow_model.js", import.meta.url)), "utf8");
assert.doesNotMatch(model, /\bdocument\b/);

console.log("framework_v3_flow_runtime: all checks passed");
