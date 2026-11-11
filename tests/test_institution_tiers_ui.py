# ruff: noqa: E501
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "index.html"

# Runs the pure instTiers helpers from <script id="inst-tiers-helpers"> in a Node VM.
NODE_CHECK = r"""
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(process.argv[2], "site", "index.html"), "utf8");
const block = html.match(/<script id="inst-tiers-helpers">([\s\S]*?)<\/script>/);
assert.ok(block, "index.html must include the inst-tiers-helpers block");
const context = vm.createContext({ URLSearchParams });
vm.runInContext(block[1] + "\nthis.instTiers = instTiers;", context);
const T = context.instTiers;
const jeq = (a, b) => assert.equal(JSON.stringify(a), JSON.stringify(b));

const mk = (id, tier, type, f, lo, hi, rl, rh, name) => ({ inst_id: id, name: name || id, atlas_type: type, tier, works_full: 10, works_frac: f, frac_lo: lo, frac_hi: hi, rank_frac: rl, rank_lo: rl, rank_hi: rh });
const rows = [
  mk("c", 2, "UC", 5, 3, 7, 3, 4), mk("a", 1, "UC", 20, 15, 25, 1, 2), mk("b", 1, "CSU", 30, 22, 38, 1, 1, "B <Uni>"),
  mk("d", 2, "CSU", 9, 6, 12, 3, 3), mk("e", 3, "other", 1, 0, 2, 5, 5),
];
const groups = T.groupTiers(rows);
jeq(groups.map((g) => g.tier), [1, 2, 3]);
jeq(groups[0].rows.map((r) => r.inst_id), ["b", "a"]);
jeq(groups[1].rows.map((r) => r.inst_id), ["d", "c"]);
assert.equal(groups[0].scaleMin, 15);
assert.equal(groups[0].scaleMax, 38);
assert.equal(T.summary(groups[0]), "Tier 1 · 2 institutions · fractional works 20.0–30.0");
assert.match(T.summary(groups[2]), /1 institution ·/);
jeq(T.groupTiers(rows, "CSU").map((g) => g.tier), [1, 2]);
jeq(T.groupTiers(rows, "nope"), []);
assert.equal(T.rankText(rows[1]), "ranks 1–2");
assert.equal(T.rankText(rows[2]), "rank 1");
const out = T.tiersHtml(rows, "");
assert.equal((out.match(/<details/g) || []).length, 3);
assert.equal((out.match(/<details class="tier-group" open>/g) || []).length, 2);
assert.ok(out.includes("B &lt;Uni&gt;") && !out.includes("<Uni>"));
assert.ok(out.includes("30.0 (22.0–38.0)"));
assert.ok(out.includes('aria-label="30.0 fractional works, 95% range 22.0 to 38.0"'));
assert.ok(T.tiersHtml(rows, "nope").includes("No ranked institutions"));
// Hash state round-trip: tiers is the default and stays out of the URL; list persists.
for (const view of ["tiers", "list"]) {
  const params = new URLSearchParams();
  T.applyViewParam(params, view);
  assert.equal(T.viewFromParams(new URLSearchParams(params.toString())), view);
}
assert.equal(T.viewFromParams(new URLSearchParams("inst_view=bogus")), "tiers");
const p = new URLSearchParams();
T.applyViewParam(p, "tiers");
assert.equal(p.toString(), "");
console.log("ok");
"""


def test_inst_tiers_helpers_group_sort_and_hash(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")
    script = tmp_path / "check.js"
    script.write_text(NODE_CHECK, encoding="utf-8")
    result = subprocess.run(
        [node, str(script), str(ROOT)], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_institutions_panel_wires_tiers_view() -> None:
    html = PAGE.read_text(encoding="utf-8")
    for needle in (
        'data-inst-view="tiers"',
        'data-inst-view="list"',
        'id="institution-tier-groups"',
        "data/bundle/inst_tiers.json",
        "inst_view",
    ):
        assert needle in html, needle
    assert "ensureInstitutionTiers" in html
    assert PAGE.stat().st_size < 300_000
