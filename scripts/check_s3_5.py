"""Acceptance checks for the S3.5 About/Methods snapshot contract."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DATA = SITE / "data"
DISCLAIMER = "Independent project; not an official OEHHA or State product."


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path} must contain a JSON object"
    return payload


def _check_about_runtime(metadata_path: Path, index_path: Path) -> None:
    node = shutil.which("node")
    assert node, "Node.js is required to exercise the About view-model acceptance check"
    script = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const [htmlPath, metadataPath, indexPath] = process.argv.slice(1);
const html = fs.readFileSync(htmlPath, "utf8");
const pageScript = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(pageScript, "site page has no inline application script");
const source = pageScript[1];
const start = source.indexOf("function aboutViewModel(");
const renderStart = source.indexOf("function renderAbout()", start);
const end = source.indexOf("function updateViews()", renderStart);
assert.ok(
  start >= 0 && renderStart > start && end > renderStart,
  "About renderer could not be isolated"
);
const metadata = JSON.parse(fs.readFileSync(metadataPath, "utf8"));
const index = JSON.parse(fs.readFileSync(indexPath, "utf8"));
const elements = {
  "generated-at": { textContent: "" },
  "about-freshness": { textContent: "" },
  "about-stats": { innerHTML: "" }
};
const context = vm.createContext({
  state: { data: { metadata, index } },
  $: (id) => elements[id],
  escapeHtml: (value) => String(value)
});
vm.runInContext(
  `${source.slice(start, end)}\nglobalThis.renderAbout = renderAbout;`,
  context,
  { filename: "site/index.html#renderAbout" }
);
const aboutViewModel = context.aboutViewModel;
const fixture = aboutViewModel(metadata, index);
// Committed site data is the fixture until CI exports a live refresh (S2.1-B).
if (metadata.generated_at === "fixture") {
  assert.equal(fixture.isFixture, true);
  assert.equal(
    fixture.refreshText,
    "Example data loaded — sample data, not a current refresh."
  );
} else {
  assert.equal(fixture.isFixture, false);
  assert.equal(fixture.refreshText, `Last refresh (UTC): ${metadata.generated_at}`);
}
const countKeys = [
  ["Authors", "authors"],
  ["Works", "works"],
  ["Institutions", "institutions"],
  ["California institutions", "ca_institutions"],
  ["Labeled works", "labeled_works"]
];
for (const [label, key] of countKeys) {
  const actual = fixture.stats.find((item) => item.label === label);
  assert.ok(actual, `About view is missing the ${label} count`);
  assert.equal(actual.value, new Intl.NumberFormat().format(metadata.counts[key]));
}
context.renderAbout();
assert.equal(elements["generated-at"].textContent, fixture.refreshText);
assert.equal(elements["about-freshness"].textContent, fixture.refreshText);
assert.ok(
  elements["about-stats"].innerHTML.includes(
    `<dt>Authors</dt><dd>${new Intl.NumberFormat().format(metadata.counts.authors)}</dd>`
  ),
  "About renderer did not put the build-metadata author count in the page"
);
const liveCounts = {
  authors: 29,
  works: 41,
  institutions: 7,
  ca_institutions: 5,
  labeled_works: 31
};
const live = aboutViewModel(
  { schema_version: "s3.1", generated_at: "2026-11-06T12:34:56+00:00", counts: liveCounts },
  { schema_version: "old", counts: { authors: 1, works: 1 } }
);
assert.equal(live.isFixture, false);
assert.equal(live.refreshText, "Last refresh (UTC): 2026-11-06T12:34:56+00:00");
assert.equal(live.stats.find((item) => item.label === "Authors").value, "29");
assert.equal(live.stats.find((item) => item.label === "Works").value, "41");
assert.equal(live.stats.find((item) => item.label === "California institutions").value, "5");
context.state.data = {
  metadata: {
    schema_version: "s3.1",
    generated_at: "2026-11-06T12:34:56+00:00",
    counts: liveCounts
  },
  index: { schema_version: "old", counts: { authors: 1, works: 1 } }
};
context.renderAbout();
assert.equal(elements["generated-at"].textContent, live.refreshText);
assert.ok(elements["about-stats"].innerHTML.includes("<dt>Authors</dt><dd>29</dd>"));
const missing = aboutViewModel({ schema_version: "s3.1", counts: {} }, {});
assert.equal(missing.refreshText, "Refresh time unavailable");
assert.equal(missing.stats.find((item) => item.label === "Authors").value, "Unavailable");
context.state.data = { metadata: { schema_version: "s3.1", counts: {} }, index: {} };
context.renderAbout();
assert.equal(elements["about-freshness"].textContent, "Refresh time unavailable");
assert.ok(elements["about-stats"].innerHTML.includes("<dt>Authors</dt><dd>Unavailable</dd>"));
console.log(
  "About renderer runtime checks passed: fixture, build counts, " +
  "live timestamp, and missing values"
);
"""
    result = subprocess.run(
        [
            node,
            "-e",
            script,
            str(SITE / "index.html"),
            str(metadata_path),
            str(index_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "About renderer runtime checks passed" in result.stdout
    print(result.stdout.strip())


def main() -> None:
    html = (SITE / "index.html").read_text(encoding="utf-8")
    methods = (ROOT / "docs" / "METHODS.md").read_text(encoding="utf-8")
    normalized_methods = " ".join(methods.split())
    metadata_path = DATA / "build_metadata.json"
    index_path = DATA / "index.json"
    metadata = _read_json(metadata_path)
    index = _read_json(index_path)

    assert f"<strong>Disclaimer:</strong> {DISCLAIMER}</p>" in html
    for marker in (
        'id="about-freshness"',
        'id="about-stats"',
        "aboutViewModel(state.data.metadata, state.data.index)",
        "data/build_metadata.json",
        "docs/METHODS.md",
        "issues/new?title=Atlas%20data%20correction",
        "CA-sampled",
        "three-nautical-mile",
        "provisional, rule-based screening metadata",
    ):
        assert marker in html, f"About page is missing the S3.5 contract: {marker}"

    for method in (
        "Public snapshot, definitions, and limits",
        "Current source and classification caveats",
        "Corrections and source work",
        "The timestamp is the time this static snapshot was built",
        "three-nautical-mile maritime zone",
        "held-out gold set",
        "data-correction issue",
    ):
        assert method in normalized_methods, (
            f"docs/METHODS.md is missing required public guidance: {method}"
        )

    assert metadata.get("schema_version") == "s3.1"
    generated_at = metadata.get("generated_at")
    assert isinstance(generated_at, str) and generated_at, "build metadata needs generated_at"
    assert generated_at == "fixture" or generated_at.endswith("+00:00"), (
        "generated_at must be the fixture sentinel or a UTC timestamp"
    )
    counts = metadata.get("counts")
    assert isinstance(counts, dict), "build metadata must contain generated counts"
    assert counts == index.get("counts"), "export metadata and index counts disagree"
    assert all(isinstance(value, int) and value >= 0 for value in counts.values())
    assert {
        "authors",
        "works",
        "institutions",
        "ca_institutions",
        "labeled_works",
    } <= set(counts), "build metadata is missing About counts"

    _check_about_runtime(metadata_path, index_path)
    print(
        "S3.5 acceptance passed: public methods/disclaimer, fixture sentinel, "
        f"and build metadata counts ({counts['authors']} authors, {counts['works']} works)"
    )


if __name__ == "__main__":
    main()
