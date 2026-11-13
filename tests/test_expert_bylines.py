# ruff: noqa: E501 (embedded Node check; long JavaScript lines are kept readable)
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "site" / "assets" / "expert_page.js"
PAGE = ROOT / "site" / "expert.html"
DRAWER_MODEL = ROOT / "framework" / "src" / "components" / "experts_model.js"

# Checks the byline, co-author and topic-scale helpers in site/assets/expert_page.js (Node VM, module exports).
NODE_CHECK = r"""
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(process.argv[2], "utf8");
const context = vm.createContext({ URLSearchParams, URL, module: { exports: {} } });
vm.runInContext(source, context, { filename: "expert_page.js" });
const A = context.module.exports;
const plain = (value) => JSON.parse(JSON.stringify(value));

// Topic scale: sqrt of count over max, font 0.8rem to 1.6rem, clamped.
assert.deepEqual(plain(A.tagScale(10, 10)), { fontRem: 1.6, padYRem: 0.35, padXRem: 1 });
assert.deepEqual(plain(A.tagScale(0, 10)), { fontRem: 0.8, padYRem: 0.2, padXRem: 0.6 });
assert.deepEqual(plain(A.tagScale(5, 10)), { fontRem: 1.37, padYRem: 0.31, padXRem: 0.88 });
assert.equal(A.tagScale(40, 10).fontRem, 1.6, "counts above the max are clamped");
assert.equal(A.tagScale(3, 0).fontRem, 0.8, "zero max gives the smallest size");
assert.equal(A.tagScale(NaN, 5).fontRem, 0.8, "missing count gives the smallest size");
assert.ok(A.tagScale(8, 10).fontRem > A.tagScale(2, 10).fontRem, "larger counts are larger");

const works = [
  {
    work_id: "W1", title: "Paper", author_count: 27,
    authors: [{ id: "A1", name: "Self Person" }, { id: "A2", name: "CA Expert" }, { id: "A3", name: "Outsider One" }, { id: "", name: "Unknown Id" }],
    author_ids: ["A1", "A2", "A3"]
  },
  {
    work_id: "W2", title: "Paper two", author_count: 2,
    authors: [{ id: "A1", name: "Self Person" }, { id: "A3", name: "Outsider One" }, { id: "A4", name: "  " }],
    author_ids: ["A1", "A3", "A4"]
  },
  { work_id: "W3", title: "Old snapshot", author_ids: ["A1", "A5"] }
];
const expertNames = new Map([["A2", "CA Expert"]]);

// Byline names: first name seen per id; empty ids and names skipped.
assert.deepEqual(Object.fromEntries(A.bylineNames(works)), { A1: "Self Person", A2: "CA Expert", A3: "Outsider One" });

// Co-authors: names from bylines; unnamed co-authors are dropped; experts keep their expert-list name.
const counts = A.coauthorCounts(works, "A1");
assert.deepEqual(plain(counts), [
  { author_id: "A3", shared: 2 },
  { author_id: "A2", shared: 1 },
  { author_id: "A4", shared: 1 },
  { author_id: "A5", shared: 1 }
]);
assert.deepEqual(plain(A.coauthorEntries(counts, A.bylineNames(works), expertNames)), [
  { author_id: "A3", shared: 2, name: "Outsider One", expert: false },
  { author_id: "A2", shared: 1, name: "CA Expert", expert: true }
]);
assert.deepEqual(plain(A.coauthorEntries(counts, A.bylineNames(works), null)), [
  { author_id: "A3", shared: 2, name: "Outsider One", expert: false },
  { author_id: "A2", shared: 1, name: "CA Expert", expert: false }
], "without the expert list no name is linked");
assert.deepEqual(plain(A.coauthorEntries(counts, new Map(), expertNames)), [
  { author_id: "A2", shared: 1, name: "CA Expert", expert: true }
], "co-authors with no name are omitted");

// Publication byline: self in bold, experts linked, others plain, escaped, "et al." from author_count.
assert.equal(
  A.authorLineHtml(works[0], "A1", expertNames),
  '<p class="pub-authors"><strong>Self Person</strong>, <a href="expert.html#author=A2">CA Expert</a>, Outsider One, Unknown Id, et al. (27 authors)</p>'
);
assert.equal(
  A.authorLineHtml(works[1], "A1", expertNames),
  '<p class="pub-authors"><strong>Self Person</strong>, Outsider One</p>',
  "unnamed entries are skipped and no et al. when the list is complete"
);
assert.equal(A.authorLineHtml(works[2], "A1", expertNames), "", "old snapshot without authors adds no line");
assert.equal(A.authorLineHtml(works[0], "A1", null).includes("expert.html"), false, "no expert links without the list");
const escaped = A.authorLineHtml({ authors: [{ id: "A7", name: "<img src=x>" }] }, "", null);
assert.equal(escaped, '<p class="pub-authors">&lt;img src=x&gt;</p>', "names are escaped");

// Ten names at most, then et al. with the full count (here from the entries, since author_count is absent).
const long = { authors: Array.from({ length: 12 }, (_, i) => ({ id: `A${i + 10}`, name: `Person ${i + 1}` })) };
const longHtml = A.authorLineHtml(long, "", null);
assert.ok(longHtml.includes("Person 10, et al."), longHtml);
assert.ok(!longHtml.includes("Person 11"), longHtml);
assert.ok(longHtml.endsWith(", et al. (12 authors)</p>"), longHtml);

console.log("expert_bylines: all assertions passed");
"""


def test_expert_bylines_runtime(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not on PATH; install Node.js 20+ to run the byline checks.")
    script = tmp_path / "expert_bylines_check.cjs"
    script.write_text(NODE_CHECK, encoding="utf-8")
    subprocess.run([node, str(script), str(HELPERS)], cwd=ROOT, check=True)


def test_expert_page_wires_bylines_scaling_and_no_placeholder() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "tagScale(count, max)" in page
    assert "--tag-font:" in page
    assert "authorLineHtml(work, S.id, S.expertNames)" in page
    assert "Co-author outside the expert list" not in page
    assert "data/index.json" in page  # expert names only, loaded once in the background
    assert "pub-authors" in page


def test_drawer_model_has_no_placeholder_and_shows_bylines() -> None:
    model = DRAWER_MODEL.read_text(encoding="utf-8")
    assert "workAuthorsHtml(work, authorId)" in model
    assert "Co-author outside" not in model
    assert "outside the California expert list" not in model
