// Focused, DOM-free checks for the CG-10 hierarchy renderer and shareable state.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {groupsTreeHtml, hierarchyData, treeHashState} from "../framework/src/components/groups_tree.js";

const payload = JSON.parse(readFileSync(new URL("../site/data/global/groups/groups_tree.json", import.meta.url), "utf8"));
assert.equal(payload.schema, "cg-tree-v1");
assert.equal(hierarchyData(payload, "geography")?.level, "root");
assert.equal(hierarchyData(payload, "unknown")?.id, "geography");

const state = treeHashState("#q=roster&tree=centrality&tree_all=1&tree_open=%5B%22centrality%2Fprimary%22%5D&tree_find=plastic");
assert.equal(state.hierarchy, "centrality");
assert.equal(state.allActivities, true);
assert.deepEqual(state.expanded, ["centrality/primary"]);
assert.equal(state.query, "plastic");
assert.equal(treeHashState("#tree_open=all&tree_closed=%5B%22a%22%5D").allExpanded, true);
assert.deepEqual(treeHashState("#tree_open=all&tree_closed=%5B%22a%22%5D").collapsed, ["a"]);

const html = groupsTreeHtml(payload);
assert.match(html, /role="tree"/);
assert.match(html, /data-tree-hierarchy/);
assert.match(html, /data-tree-expand-all/);
assert.match(html, /data-tree-collapse-all/);
assert.match(html, /data-tree-search/);
assert.match(html, /tabindex="0"/);
assert.doesNotMatch(html, /role="treeitem"[^>]*aria-expanded="true"/);
assert.match(html, /role="treeitem"[^>]*aria-expanded="false"/);
console.log("groups tree runtime assertions passed");
