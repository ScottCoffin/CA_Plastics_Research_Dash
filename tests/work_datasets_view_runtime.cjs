"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");
const helperBlock = html.match(/<script id="work-dataset-view-helpers">([\s\S]*?)<\/script>/);
assert.ok(helperBlock, "the page must include the work-dataset view helpers");

const context = vm.createContext({});
vm.runInContext(helperBlock[1], context, { filename: "work-dataset-view-helpers.js" });
const run = (expression) => vm.runInContext(expression, context);

const datasetsHtml = run(`JSON.stringify(workDatasetView.datasetsHtml({
  datasets: [
    { doi: "10.5281/zenodo.1", relation: "IsCitedBy", evidence_type: "DataCite-relation" },
    { doi: "10.1000/x<img>", relation: "", evidence_type: "DAS-match" },
    { doi: "10.1000/unknown", relation: "", evidence_type: "something-new" }
  ]
}))`);
const markup = JSON.parse(datasetsHtml);
assert.match(markup, /<div class="work-datasets"><p><strong>Datasets<\/strong><\/p><ul>/);
assert.match(markup, /href="https:\/\/doi\.org\/10\.5281\/zenodo\.1"/);
assert.match(markup, /Evidence: DataCite relation<\/span>· relation: IsCitedBy|Evidence: DataCite relation<\/span> · relation: IsCitedBy/);
assert.match(markup, /Evidence: Data availability statement/);
assert.match(markup, /Evidence: Unrecognized evidence/);
assert.ok(markup.includes("10.1000/x&lt;img&gt;"), "dataset DOIs must be escaped");
assert.ok(!markup.includes("<img>"), "raw markup from a DOI must not reach the page");

assert.equal(run(`workDatasetView.datasetsHtml({})`), "");
assert.equal(run(`workDatasetView.datasetsHtml({ datasets: [] })`), "");

const linked = run(`workDatasetView.linkedWorksHtml({
  linked_works: [
    { work_id: "W1", evidence_type: "DataCite-relation" },
    { work_id: "W1", evidence_type: "DAS-match" },
    { work_id: "W2", evidence_type: "DataCite-relation" }
  ]
})`);
assert.equal(linked, "<br><small>Linked works: 2 (Data availability statement, DataCite relation)</small>");
assert.equal(run(`workDatasetView.linkedWorksHtml({})`), "");
assert.equal(run(`workDatasetView.linkedWorksHtml({ linked_works: [] })`), "");

console.log("Work-dataset view runtime checks passed: evidence labels, escaping, registry counts.");
