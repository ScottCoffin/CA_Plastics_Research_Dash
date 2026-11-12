from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "site" / "index.html"
VENDOR = ROOT / "site" / "assets" / "vendor" / "minisearch-7.2.0.js"
FACETS = ROOT / "site" / "assets" / "facets.js"

# Runs AtlasFacets.rankedSearchBits in Node VM contexts: once with the vendored MiniSearch
# global loaded, and once without it (the fallback path must equal searchBits).
NODE_CHECK = r"""
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = process.argv[2];
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), "utf8");

function makeIndex(context) {
  // Minimal bundle: 3 works, no facets (header-only facets.bin with zero bit-sets).
  const header = Buffer.alloc(16);
  header.write("BMF1", 0, "ascii");
  header.writeUInt32LE(1, 4);
  header.writeUInt32LE(3, 8);
  header.writeUInt32LE(0, 12);
  const works = {
    work_ids: ["W1", "W2", "W3"],
    titles: ["Microplastic loads in marine fish", "River survey of plastic debris", "Air fibres in cities"],
  };
  const { BitmaskIndex } = context.AtlasFacets;
  return new BitmaskIndex("{}", new Uint8Array(header), JSON.stringify(works));
}

function bits(arr) {
  return Array.from(arr).map((n) => n.toString(2)).join(",");
}

// With MiniSearch loaded: typo "microplastc" finds the title; prefix finds "fib" -> "fibres".
const withMs = { TextDecoder };
withMs.window = withMs;
vm.createContext(withMs);
vm.runInContext(read("site", "assets", "vendor", "minisearch-7.2.0.js"), withMs, { filename: "minisearch.js" });
assert.equal(typeof withMs.MiniSearch, "function", "vendor script must define the MiniSearch global");
vm.runInContext(read("site", "assets", "facets.js"), withMs, { filename: "facets.js" });
const msIndex = makeIndex(withMs);

assert.equal(bits(msIndex.rankedSearchBits("microplastc")), bits(msIndex.searchBits("microplastic")), "typo must match the title");
assert.equal(bits(msIndex.rankedSearchBits("microplastc")), "1", "work 0 only");
assert.equal(bits(msIndex.rankedSearchBits("fib")), bits(msIndex.searchBits("fibres")), "prefix must match");
assert.equal(bits(msIndex.rankedSearchBits("plastic debris")), bits(msIndex.searchBits("plastic debris")), "AND across words");
assert.equal(bits(msIndex.rankedSearchBits("zzzqqq")), "0", "no match gives an empty set");
assert.equal(bits(msIndex.rankedSearchBits("")), bits(msIndex.searchBits("")), "empty query falls back to searchBits");
assert.equal(bits(msIndex.searchBits("microplastc")), "0", "exact searchBits is unchanged");

// Without MiniSearch: rankedSearchBits falls back to the exact substring search.
const noMs = { TextDecoder };
noMs.window = noMs;
vm.createContext(noMs);
vm.runInContext(read("site", "assets", "facets.js"), noMs, { filename: "facets.js" });
assert.equal(typeof noMs.MiniSearch, "undefined");
const plainIndex = makeIndex(noMs);
assert.equal(bits(plainIndex.rankedSearchBits("microplastc")), bits(plainIndex.searchBits("microplastc")), "fallback equals searchBits");
assert.equal(bits(plainIndex.rankedSearchBits("microplastc")), "0", "fallback does not fuzzy match");
assert.equal(bits(plainIndex.rankedSearchBits("river plastic")), bits(plainIndex.searchBits("river plastic")));

console.log("MiniSearch search runtime checks passed: typo, prefix, AND, empty, fallback.");
"""  # noqa: E501


ATTR_RE = re.compile(
    r"""<script\s+src\s*=\s*["']assets/vendor/minisearch-7\.2\.0\.js["']\s*>\s*</script>"""
)


def test_index_loads_vendored_minisearch_once_before_topics() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    matches = ATTR_RE.findall(html)
    assert len(matches) == 1, "index.html must include the vendored MiniSearch script exactly once"
    assert html.index(matches[0]) < html.index('<script src="assets/topics.js"></script>')
    assert VENDOR.exists(), "vendored MiniSearch file is missing"
    assert (VENDOR.parent / "minisearch-LICENSE.txt").exists(), (
        "MiniSearch licence must sit beside the vendor file"
    )


def test_experts_search_placeholder_and_ranked_path() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'placeholder="e.g. Rochman, UC Davis"' in html
    assert "const ranked = authorSearchIds(query);" in html, (
        "filteredAuthors uses the ranked author search"
    )
    assert 'typeof window.MiniSearch !== "function"' in html, (
        "substring fallback when MiniSearch is missing"
    )
    assert "ranked.has(author.author_id) : haystack.includes(search)" in html, (
        "fallback is the substring match"
    )


def test_facets_ranked_search_runtime(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for the MiniSearch runtime check; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    script = tmp_path / "minisearch_check.cjs"
    script.write_text(NODE_CHECK, encoding="utf-8")
    subprocess.run([node, str(script), str(ROOT)], cwd=ROOT, check=True)
