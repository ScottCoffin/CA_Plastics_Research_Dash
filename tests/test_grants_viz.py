from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "grants.html"

# Runs the grants page's pure helpers in a Node VM context that loads the real
# site/assets/topics.js and the <script id="grants-app"> block from grants.html.
NODE_CHECK = r"""
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = process.argv[2];
const html = fs.readFileSync(path.join(root, "site", "grants.html"), "utf8");
const block = html.match(/<script id="grants-app">([\s\S]*?)<\/script>/);
assert.ok(block, "grants.html must include the <script id=\"grants-app\"> logic block");
const context = vm.createContext({ URLSearchParams });
vm.runInContext(fs.readFileSync(path.join(root, "site", "assets", "topics.js"), "utf8"), context, { filename: "topics.js" });
vm.runInContext(block[1], context, { filename: "grants-app.js" });

function mk(i, o) {
  return Object.assign({
    grant_key: "G" + i, title: "Award " + i, pi_names: ["PI " + i], org: "Org A", funder_agency: "NSF", funder_type: "federal",
    sector: "academia", fiscal_year: 2020, amount: 1000, plastic_related: true, ca_led: true, domain_tags: ["air"], program: "P"
  }, o);
}
context.rows = [
  mk(1, { domain_tags: ["air", "occurrence_and_monitoring"], amount: 3000 }),
  mk(2, { org: "Org B", domain_tags: ["air"] }),
  mk(3, { org: "ORG C", domain_tags: [], amount: null, fiscal_year: 2021 }),
  mk(4, { org: "Org D", funder_agency: "NIH", sector: "nonprofit", domain_tags: ["analytical_methods", "air", "occurrence_and_monitoring"], ca_led: false, fiscal_year: 2022 }),
  mk(5, { org: "Org E", funder_agency: "NIH", sector: "nonprofit", domain_tags: ["matrix:marine"], plastic_related: false, fiscal_year: null }),
  mk(6, { org: "org a", funder_agency: "NOAA", sector: "government", domain_tags: ["air"], fiscal_year: 2023, title: "Marine fibres" }),
  mk(7, { org: "Org F", domain_tags: ["air"] }),
  mk(8, { org: "Org F", domain_tags: ["air"] })
];

const R = JSON.parse(vm.runInContext(`JSON.stringify((() => {
  prepareRows(rows);
  const all = filterRows(rows, { plastic: false });
  const f = (o) => filterRows(rows, Object.assign({ plastic: false }, o)).map((r) => r.grant_key);
  const out = {};
  out.all = f({});
  out.plasticOnly = f({ plastic: true });
  out.agency = f({ agency: "NIH" });
  out.agencySector = f({ agency: "NIH", sector: "nonprofit", topic: "analytical_methods" });
  out.years = f({ yf: "2021", yt: "2022" });
  out.undatedDrop = f({ yf: "2000" });
  out.untagged = f({ topic: "__untagged__" });
  out.search = f({ q: "marine FIBRES" });
  out.ca = f({ ca: true });
  out.org = f({ org: "org a" });
  out.compose = f({ agency: "NSF", ca: true, yf: "2021", plastic: true });
  out.orgNames = rows.map((r) => r._orgName);

  const sums = (g) => {
    const inSum = {}, outSum = {};
    g.links.forEach((l) => { outSum[l.source] = (outSum[l.source] || 0) + l.value; inSum[l.target] = (inSum[l.target] || 0) + l.value; });
    return g.nodes.filter((n) => n.col > 0 && n.col < g.ncols - 1).map((n) => Math.abs((inSum[n.id] || 0) - (outSum[n.id] || 0)));
  };
  const modes = {};
  ["awards", "amount"].forEach((mode) => {
    const g = buildSankey(all, { mode, topN: 2, orgs: true });
    const L = layoutSankey(g, { width: 900, height: 500 });
    modes[mode] = {
      total: g.total, excluded: g.excluded,
      colSums: [0, 1, 2, 3].map((c) => g.nodes.filter((n) => n.col === c).reduce((s, n) => s + n.value, 0)),
      midDiff: sums(g),
      names: g.nodes.filter((n) => n.col === 2).map((n) => n.name),
      layoutOk: L.nodes.every((n) => isFinite(n.y) && n.h > 0) && L.links.every((l) => /^M/.test(l.d)),
      noOverlap: [0, 1, 2, 3].every((c) => { const ns = L.nodes.filter((n) => n.col === c).sort((a, b) => a.y - b.y); return ns.every((n, i) => i === 0 || n.y >= ns[i - 1].y + ns[i - 1].h + 2 - 1e-6); })
    };
  });
  const collapsed = buildSankey(all, { mode: "awards", orgs: false });
  const g1 = buildSankey(all, { mode: "awards", topN: 1, orgs: true });
  const conn = connected(g1.links, "s:academia");
  const state = { yf: "2019", yt: "2023", topic: "air", agency: "NIH", sector: "nonprofit", ftype: "state", ca: true, plastic: false, q: "sea turtle & co", org: "org a", amt: true, n: 9, orgs: false };
  const heat = buildHeat(all);
  const mx = buildSectorTopic(all);
  return Object.assign(out, {
    modes, collapsedNcols: collapsed.ncols, collapsedMid: sums(collapsed), collapsedTotal: collapsed.total,
    top1Orgs: g1.nodes.filter((n) => n.type === "org").map((n) => n.name),
    top1Other: g1.nodes.filter((n) => n.type === "other").map((n) => n.name),
    connNodes: [...conn.nodes].sort(), connLinks: conn.links.size,
    roundTrip: decodeHash(encodeHash(state)), state,
    defaultHash: encodeHash(decodeHash("")), defaultPlastic: decodeHash("").plastic,
    clamp: decodeHash("#n=99").n + "," + decodeHash("#n=1").n, badYear: decodeHash("#yf=abc&yt=20x").yf,
    csv: rowsToCsv([Object.assign({}, rows[0], { title: '=cmd,"x"' })], null).split(String.fromCharCode(13) + String.fromCharCode(10))[1],
    labels: topicsOf(rows[0]).map(topicLabel), untaggedLabel: topicLabel("__untagged__"),
    heatLabels: heat.rows.map((r) => r.label), heatCols: heat.cols,
    matrixSectors: mx.sectors, matrixMax: mx.max,
    sorted: sortRows(rows, "amount", "desc").map((r) => r.grant_key).slice(0, 1),
    top: topOrgs(all, 2).map((o) => [o.name, o.n]),
    sum: summarize(all),
    fills: [heatFill(0, 5), heatFill(5, 5)], ink: [inkFor("#0b4f9c"), inkFor("#f3f5f6")]
  });
})())`, context));

// Filters compose with AND.
assert.equal(R.all.length, 8);
assert.equal(R.plasticOnly.length, 7);
assert.ok(!R.plasticOnly.includes("G5"), "plastic-only drops non-plastic awards");
assert.deepEqual(R.agency, ["G4", "G5"]);
assert.deepEqual(R.agencySector, ["G4"]);
assert.deepEqual(R.years, ["G3", "G4"]);
assert.ok(!R.undatedDrop.includes("G5"), "undated awards drop out of a year range");
assert.ok(R.untagged.includes("G3") && R.untagged.includes("G5"));
assert.deepEqual(R.search, ["G6"], "search is case-insensitive and matches every term");
assert.ok(!R.ca.includes("G4"));
assert.deepEqual(R.org, ["G1", "G6"], "organisation names are merged ignoring case");
assert.deepEqual(R.compose, ["G3"], "agency + CA-led + year + plastic compose");
assert.ok(R.orgNames.includes("Org A") && R.orgNames.includes("Org C"), "all-caps names are title-cased; mixed case preferred");

// Sankey conservation, splitting, grouping.
for (const mode of ["awards", "amount"]) {
  const m = R.modes[mode];
  assert.ok(m.midDiff.every((d) => d < 1e-6), mode + ": flow in equals flow out for every middle node");
  assert.ok(m.colSums.every((s) => Math.abs(s - m.total) < 1e-6), mode + ": every column sums to the total, so topic splitting conserves weight");
  assert.ok(m.layoutOk && m.noOverlap, mode + ": layout positions are finite and nodes keep their 2px gaps");
}
assert.ok(Math.abs(R.modes.awards.total - 8) < 1e-9, "split weights sum to the award count");
assert.equal(R.modes.awards.excluded, 0);
assert.equal(R.modes.amount.excluded, 1, "awards without an amount are excluded and counted");
assert.equal(R.modes.amount.total, 9000);
assert.ok(R.modes.awards.names.some((n) => n.startsWith("Other ")), "top-N grouping creates Other nodes");
assert.equal(R.collapsedNcols, 3);
assert.ok(R.collapsedMid.every((d) => d < 1e-6));
assert.ok(Math.abs(R.collapsedTotal - 8) < 1e-9);
assert.equal(R.top1Orgs.length, 3, "topN=1 keeps one organisation in each of the three sectors");
assert.ok(R.top1Other.length >= 1);
assert.ok(R.connNodes.includes("a:NSF") && R.connNodes.includes("s:academia"));
assert.ok(R.connLinks > 0);

// Hash.
assert.deepEqual(R.roundTrip, R.state, "hash encode/decode round-trips");
assert.equal(R.defaultHash, "", "default state encodes to an empty hash");
assert.equal(R.defaultPlastic, true);
assert.equal(R.clamp, "15,3");
assert.equal(R.badYear, "");

// Helpers.
assert.ok(R.csv.split(",")[1].endsWith("'=cmd"));
assert.ok(R.csv.includes("\"'=cmd,\"\"x\"\"\""), "CSV cells are quoted and formula prefixes neutralised");
assert.deepEqual(R.labels, ["Occurrence & monitoring", "Air & atmosphere"]);
assert.equal(R.untaggedLabel, "Untagged");
assert.ok(R.heatLabels.every((l) => !l.includes("_")), "no raw tag keys");
assert.ok(R.heatCols.length >= 1);
assert.equal(R.matrixSectors.length, 3);
assert.ok(R.matrixMax > 0);
assert.deepEqual(R.sorted, ["G1"]);
assert.equal(R.top[0][1], 2);
assert.equal(R.sum.awards, 8);
assert.equal(R.sum.noAmt, 1);
assert.equal(R.fills[0], "#f3f5f6");
assert.equal(R.fills[1], "#0b4f9c");
assert.deepEqual(R.ink, ["#ffffff", "#000000"]);
console.log("Grants page runtime checks passed.");
"""  # noqa: E501

ATTR_RE = re.compile(r"""\b(?:src|href)\s*=\s*["']([^"']*)["']""", re.IGNORECASE)


def test_grants_page_has_no_external_hosts() -> None:
    html = PAGE.read_text(encoding="utf-8")
    refs = ATTR_RE.findall(html)
    assert refs
    external = [
        ref
        for ref in refs
        if re.match(r"^(?:https?:)?//", ref, re.IGNORECASE) or ref.lower().startswith("http:")
    ]
    assert external == [], f"external src/href values are not allowed: {external}"
    assert not re.search(r"url\(\s*['\"]?https?:", html, re.IGNORECASE)
    assert not re.search(r"@import", html)


def test_grants_page_structure_and_links() -> None:
    html = PAGE.read_text(encoding="utf-8")
    assert '<script src="assets/topics.js"></script>' in html
    assert 'href="index.html#funding"' in html
    assert "Independent project; not an official OEHHA or State product." in html
    assert "not comparable or additive across sources" in html
    index = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert 'href="grants.html"' in index
    assert "Open the funding visualizations" in index
    assert index.index("Open the funding visualizations") > index.index('id="panel-funding"')


def test_grants_page_runtime(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for the grants page runtime check.")
    script = tmp_path / "grants_page_check.cjs"
    script.write_text(NODE_CHECK, encoding="utf-8")
    subprocess.run([node, str(script), str(ROOT)], cwd=ROOT, check=True)
