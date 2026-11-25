# Collaboration network build (S9.4)

This page explains how `site/data/california/network.json` is built, what it contains, and where its
known limits are. It describes the code as checked on 2026-11-18. The build reads only
committed site files, so it runs offline. The build was not run for this page; the constants
and line numbers below come from reading the code.

Files:

| Role | File |
|---|---|
| Library (graph, layout, communities, labels) | [`src/atlas/build/network.py`](../src/atlas/build/network.py) |
| Command-line entry point | [`scripts/build_network.py`](../scripts/build_network.py) |
| Output consumed by the `/network` page | [`site/data/california/network.json`](../site/data/california/network.json) |
| Structure metrics library (BQ-3.2) | [`src/atlas/analytics/network_metrics.py`](../src/atlas/analytics/network_metrics.py) |
| Structure metrics command (BQ-3.2) | [`scripts/build_network_metrics.py`](../scripts/build_network_metrics.py) |
| Output of the structure metrics (BQ-3.2) | [`site/data/california/network_metrics.json`](../site/data/california/network_metrics.json) |
| Daily run | [`.github/workflows/ingest_works.yml`](../.github/workflows/ingest_works.yml) |
| Field reference | [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md) |
| Renderer decision | [`.agent/DECISIONS.md`](../.agent/DECISIONS.md) (ADR-S9.4-SIGMA-2026-11-14) |

Current file (2026-11-18): schema `s9.4-v1.1`, 400 nodes, 1259 edges, 23 entries in
`community_labels`.

## 1. Purpose

The build produces a co-authorship graph of California plastics experts. A node is an Atlas
expert. An edge joins two experts who co-authored plastic-related works. The file stores
precomputed positions and community labels, so the page shows clusters on first load
(`src/atlas/build/network.py:5-7`). The page draws the graph with sigma.js (ADR-S9.4-SIGMA-2026-11-14,
`.agent/DECISIONS.md:617-618`). Its "Re-run layout" runs ForceAtlas2 in the browser on request, and
the settings mirror this build's (`src/atlas/build/network.py:22-23`).

## 2. Inputs

Both inputs are site files, not raw data (`src/atlas/build/network.py:3`).

| Input | Default path | Used for | If missing |
|---|---|---|---|
| Index | `site/data/california/index.json` (`scripts/build_network.py:24`) | `authors` and `works` lists, `generated_at` | The build fails (`scripts/build_network.py:32`). |
| Institutions | `site/data/california/institutions.json` (`scripts/build_network.py:25`) | Institution names and sector types | Optional. The build continues with no institution names or sectors (`scripts/build_network.py:35`). |

The institutions file may be a JSON object with an `institutions` key or a bare list
(`scripts/build_network.py:36-39`).

Filters applied:

- **Works:** only works with `plastic_related is True`, a strict boolean check
  (`src/atlas/build/network.py:36`). Other works do not affect nodes, edges or topics.
- **Experts:** a node must be in `authors` and have at least one plastic-related work that lists
  two or more distinct `author_ids` (`src/atlas/build/network.py:49-57`).
- **Edges:** the work needs an integer `year` (`src/atlas/build/network.py:74-76`), and both ends
  must be selected nodes (`src/atlas/build/network.py:77`).
- **California:** this module applies no residency filter. The `current_in_ca` value is copied to
  each node (`src/atlas/build/network.py:279`). Membership is whatever `authors` contains.

Index fields read:

- authors: `author_id` (`src/atlas/build/network.py:57`), `ca_plastic_works_count` (`:59`),
  `plastic_citations` (`:60`), `name` (`:266`), `institution_ids` (`:261`), `domain_tags` (`:274`),
  `primary_affiliations` (`:278`), `current_in_ca` (`:279`).
- works: `plastic_related` (`:36`), `author_ids` (`:51`), `year` (`:74`), `domain_tags` (`:252`).
- institutions: `inst_id` (`:254`), `name` (`:255`), `atlas_type` (`:262`).

## 3. Nodes

A node is one expert, keyed by the string `author_id`. The node `id` is that value
(`src/atlas/build/network.py:265`).

Selection (`select_nodes`, `src/atlas/build/network.py:39-64`):

1. For each expert, count the plastic-related works that list two or more distinct author ids
   (`:49-55`).
2. Keep experts whose count is above zero (`:57`).
3. Rank by `ca_plastic_works_count` (descending), then `plastic_citations` (descending), then
   `author_id` (ascending) (`:56-63`).
4. Keep the first `cap` experts (`:64`). The default is `DEFAULT_NODE_CAP = 400`
   (`src/atlas/build/network.py:20`). The CLI flag is `--cap` (`scripts/build_network.py:27`).

The cap binds in the current file (400 nodes). An expert outside the cap has no node, and their
co-authorships create no edges. Nodes are written in rank order (`src/atlas/build/network.py:258`).

## 4. Edges and weights

Pair rule: two selected experts are joined when both are listed on the same plastic-related work
with an integer year (`src/atlas/build/network.py:67-83`). Pairs come from `itertools.combinations`
over sorted ids (`:77`, `:81`). Each edge is stored once, with `source` sorting before `target`
because the ids are sorted (`:77`), and edges are written in sorted order (`:238`, `:289`).

Weight per work (`edge_years`, `src/atlas/build/network.py:80`):

- Default: each shared work adds 1.0 to its year.
- `--fractional`: each work adds 1/(k − 1), where k is the number of selected experts on that work.
  The module docstring calls this optional Newman fractional counting (`:4`).

Edge weight is the sum of the per-year values (`:239`, `:286`), rounded to 3 decimals. Per-year
values are also rounded to 3 decimals (`:287`).

Thresholds:

- The build has no minimum edge weight. In fractional mode, edges with weight below 1 are kept in
  the file.
- The page's default of one shared work appears only in the headline count `network_links`, which
  counts edges with weight of at least 1 (`src/atlas/build/network.py:343`). The docstring says it
  mirrors the page's default minimum (`:318-323`).
- Self-loops are not created (`src/atlas/build/network.py:81` pairs distinct ids).

Node metrics:

- `degree`: number of neighbours among selected nodes, unweighted (`src/atlas/build/network.py:270`).
- `strength`: sum of edge weights at the node (`:246`, `:271`).
- `plastic_works`: the author's `ca_plastic_works_count` (`:272`).

## 5. Layout

Positions are computed in Python and stored in the file.

Step 1, seeded spring start: `nx.spring_layout(graph, weight="weight", seed=SEED, iterations=200)`
(`src/atlas/build/network.py:244`), with `SEED = 42` (`:21`). Arguments not listed are networkx
defaults (see section 11).

Step 2, ForceAtlas2 (`forceatlas2_positions`, `src/atlas/build/network.py:102-126`). It calls
networkx `nx.forceatlas2_layout` (`:114`) and starts from the spring positions (`:116`):

| Setting | Value | Lines |
|---|---|---|
| Iterations (`max_iter`) | `LAYOUT_ITERATIONS = 1000` | `:24`, `:117` |
| Scaling ratio | `LAYOUT_SCALING_RATIO = 10.0` | `:25`, `:119` |
| Gravity | `LAYOUT_GRAVITY = 0.05` | `:26`, `:120` |
| Strong gravity | `True` | `:121` |
| Linear attraction (`linlog`) | `False` | `:122` |
| Jitter tolerance | `1.0` | `:118` |
| Node mass | 1 + weighted degree | `:113`, `:123` |
| Edge weight | `weight="weight"` | `:124` |

Step 3, normalise (`_normalise`, `src/atlas/build/network.py:86-99`): centre the points on their
bounding box, then scale so the longer side spans [-1, 1]. A layout with no extent uses a
half-width of 1.0 (`:97-98`). Non-finite positions raise an error (`:92-93`). Stored `x` and `y`
are rounded to 4 decimals (`:267-268`).

Determinism note: the ForceAtlas2 call passes no `seed` (`:114-125`). The docstring says networkx
adds no randomness once `pos` is given (`:107`). That is the code's claim. It was not checked
against the networkx source for this page.

## 6. Communities and labels

Algorithm: Louvain, `nx.algorithms.community.louvain_communities(graph, weight="weight", seed=SEED)`
(`src/atlas/build/network.py:240`). Seed 42.

Ordering: communities are sorted by size, largest first, then by smallest member id (`:242`).
The community index is the position in that order, so community 0 is the largest (`:243`). The
comment at `:241` says this keeps colours stable.

Labels (`community_labels`, `src/atlas/build/network.py:174-199`) are computed after the layout,
from the node rows:

- Only communities with at least `LABEL_MIN_SIZE = 4` members get an entry (`:28`, `:189`).
  Entries are in community index order (`:187`).
- **Institution** (`_institution_label`, `:141-150`). Each member's home institution is the first
  primary affiliation. Without one, it is the first institution other than `System`
  (`_home_institution`, `:129-138`). The most common name wins, and ties go to the name that sorts
  first (`:147`). The label is kept when the count is at least `INSTITUTION_MIN_COUNT = 2`
  (`:30`) and the share is at least `INSTITUTION_MIN_SHARE = 0.35` (`:29`, `:148`).
- **Topic** (`_topic_label`, `:153-171`). Each member's `topics` (top five tags, `:273`) are
  counted. A tag needs a share of at least `TOPIC_MIN_SHARE = 0.4` within the community (`:31`,
  `:161`). Lift is (community count × network total) ÷ (community size × network count for the
  tag) (`:164`; totals at `:184-185`). The highest lift wins, then the highest share, then the tag
  name (`:165`). The label is kept when lift is at least `TOPIC_MIN_LIFT = 1.15` (`:32`, `:168`).
- Share and lift are rounded to 3 decimals (`:150`, `:171`). A field that fails its threshold is
  `null`, and the page then shows "Cluster n" (docstring `:178-179`).
- The method text is `COMMUNITY_LABELS_METHOD` (`:202-210`), copied to `method.community_labels`.

## 7. Output: `site/data/california/network.json`

`scripts/build_network.py` writes one line of JSON, UTF-8, without ASCII escaping, with compact
separators, sorted keys and a trailing newline (`scripts/build_network.py:41`, `:49`).

Top-level keys (`src/atlas/build/network.py:291-306`):

| Key | Type | Content | Line |
|---|---|---|---|
| `schema_version` | string | `"s9.4-v1.1"` (`SCHEMA_VERSION`, `:19`) | `:292` |
| `generated_at` | string | Copied from `index.json` (`:293`). The CLI passes no value (`scripts/build_network.py:40`). | `:293` |
| `method` | object | Method text and settings (keys below) | `:294-302` |
| `communities` | integer | Number of communities | `:303` |
| `community_labels` | array | Section 6 | `:304` |
| `nodes` | array | One object per expert, in rank order | `:305` |
| `edges` | array | One object per co-authored pair, sorted by `source` then `target` | `:306` |

`method` keys (`:295-301`): `edge_weight` (`"co-authored works"` or `"fractional (Newman)"`),
`works`, `node_cap`, `community`, `layout`, `community_labels` and `networkx` (the installed
networkx version). The `community` text is the literal "Louvain (networkx), seed 42" (`:298`).

Node fields (`src/atlas/build/network.py:263-281`): `id`, `name`, `x`, `y`, `community`, `degree`,
`strength`, `plastic_works`, `topics`, `institution_ids`, `institutions`, `sectors`,
`primary_affiliations`, `current_in_ca`.

- `topics`: the top five tags across the expert's plastic-related works (`:273`). If there are
  none, the author's `domain_tags` are used (`:274`).
- `institutions`: names of the `institution_ids` found in `institutions.json` (`:276`).
- `sectors`: sorted unique `atlas_type` values for those institutions (`:262`).

Edge fields (`src/atlas/build/network.py:282-290`): `source`, `target`, `weight`, and `years`, an
object keyed by year string with values rounded to 3 decimals (`:287`).

`community_labels` entry fields (`:191-197`): `community`, `size`, `institution` (`{name, share}`
or `null`) and `topic` (`{tag, share, lift}` or `null`).

For the field reference and licence, see `DATA_DICTIONARY.md` (section starting at line 103).

## 8. Rebuilding

```
py -3.14 scripts/build_network.py
py -3.14 scripts/build_network.py --cap 400 --fractional
py -3.14 scripts/build_network.py --check
py -3.14 scripts/build_network.py --index PATH --institutions PATH --out PATH
```

Flags (`scripts/build_network.py:24-29`):

| Flag | Default | Effect |
|---|---|---|
| `--index PATH` | `site/data/california/index.json` | Input index |
| `--institutions PATH` | `site/data/california/institutions.json` | Optional institutions input |
| `--out PATH` | `site/data/california/network.json` | Output file |
| `--cap N` | `400` (integer) | Maximum number of nodes |
| `--fractional` | off | Fractional edge weights |
| `--check` | off | Rebuild in memory. Exit 1 if `--out` is missing or differs byte for byte; exit 0 if identical (`:43-48`) |

Without `--check`, the script writes `--out` and then refreshes `network_experts` and
`network_links` in `build_metadata.json`, in the same folder as `--out`
(`scripts/build_network.py:50-57`; counts from `src/atlas/build/network.py:317-346`). The export
writes that file before this script runs (`scripts/build_network.py:50-51`). If it is missing, the
script prints a warning and still exits 0 (`:53-57`). It prints a summary line with node, edge,
community and byte counts (`:58-61`).

Networkx is imported lazily inside the functions that need it (`src/atlas/build/network.py:109`,
`:228`), so both the build and `--check` need it installed.

## 9. Daily ingest

`.github/workflows/ingest_works.yml` is named "Daily works ingestion" and runs on the cron
`17 10 * * *` (`.github/workflows/ingest_works.yml:1`, `:5`).

- The step "Build collaboration network" (`.github/workflows/ingest_works.yml:122-125`) runs
  `python scripts/build_network.py` with no flags, so the defaults above apply.
- It runs after "Build analytics and serving bundle" (`:115-120`). It runs only when
  `steps.refresh.outputs.status == 'success'` (`:124`). Otherwise the step is skipped and the
  committed file is not rebuilt.
- The commit step's `git add -f` list (starts at `:247`) includes `site/data/california/network.json`
  (`:267`).
- The workflow comment calls this "the new export" (`:122`).

## 10. Determinism

- **Seeds:** `SEED = 42` is used for Louvain (`src/atlas/build/network.py:240`) and for the spring
  start (`:244`). The ForceAtlas2 step starts from those positions and passes no seed (`:114-125`).
- **Stable order:** the ranking key ends with `author_id` (`:56-63`). Ids are sorted before pairing
  (`:51`, `:77`). Edges are sorted (`:238`, `:289`). Communities are ordered by size, then smallest
  member id (`:242`).
- **Fixed serialisation:** sorted keys and fixed separators (`scripts/build_network.py:41`). The
  `--check` mode depends on this (`:43-48`).
- **Expected result:** the same index, networkx version and flags give the same bytes. This is the
  design intent; it was not re-run for this page.
- **Byte changes without network changes:** `generated_at` (copied from `index.json`, `:293`) and
  the networkx version (`:301`). So `--check` reports the file as stale whenever `index.json` is
  regenerated or networkx changes, even if the nodes and edges are the same.
- **Topic ties:** `Counter.most_common(5)` keeps first-seen order for equal counts (`:273`), so the
  order of works in `index.json` can change which tags are kept.
- **Rounding:** edge weights, years and positions are rounded before writing (`:267-268`,
  `:286-287`), which hides small float differences from summing in a different order.
- **Library version:** the layout and communities come from networkx algorithms. The version is
  recorded in `method.networkx`. The code does not pin networkx. ADR-S9.4-SIGMA-2026-11-14 says
  `networkx>=3.4` (`.agent/DECISIONS.md:618`). The version installed when this page was checked was
  3.6.1.

## 11. Known limits

1. **Eligibility counts every listed id.** `select_nodes` counts each id in a work's `author_ids`
   (`src/atlas/build/network.py:49-55`), not only ids present in `authors`. The docstring says the
   partner must be "another Atlas expert" (`:46-47`). If `index.json` lists co-authors who are not
   in `authors`, an expert can pass the rule with no edge to a node. This page did not check the
   index for that case.
2. **The cap removes collaborators.** Only the top `cap` experts become nodes (`:64`). Edges to
   dropped experts are lost. `degree` and `strength` count selected nodes only (`:270-271`).
3. **Works without a year still rank.** A work without an integer `year` counts for eligibility and
   ranking (`:49-55`) but adds no edges (`:74-76`).
4. **Fractional denominator.** The `k − 1` divisor counts selected experts on the work, not all
   listed authors (`:77`, `:80`).
5. **No minimum edge weight in the build.** Fractional mode can produce weights below 1 that the
   headline `network_links` count excludes (`:343`).
6. **Silent institutions fallback.** If `institutions.json` is missing, institution names and
   sectors are empty and no error is raised (`scripts/build_network.py:35`).
7. **Stale comments.** `src/atlas/build/network.py:8`, `:109` and `:228`, and
   `scripts/build_network.py:5`, say networkx is not yet a declared dependency. ADR-S9.4-SIGMA-2026-11-14
   (`.agent/DECISIONS.md:618`) records it as declared. The ADR is the current record.
8. **Hard-coded seed text.** The layout and community method strings contain the literal text
   "seed 42" (`src/atlas/build/network.py:212`, `:298`). Changing `SEED` does not update them.
9. **Docstring scope.** The module docstring says the build reads only `index.json`
   (`src/atlas/build/network.py:3`). The CLI also reads `institutions.json`
   (`scripts/build_network.py:25`).
10. **No layout convergence check.** The iteration count is fixed at 1000 (`src/atlas/build/network.py:24`).
    The code has no convergence test.

## 12. Not set in code

These are not set in this repository. Where networkx has a default, it applies.

- Louvain `resolution`, `threshold` and `max_level` are not passed (`src/atlas/build/network.py:240`).
  Installed networkx 3.6.1 defaults are resolution 1 and threshold 1e-07.
- Spring layout `k`, `threshold`, `method`, `gravity`, `scale` and `center` are not passed
  (`src/atlas/build/network.py:244`).
- ForceAtlas2 `seed` is not passed (`src/atlas/build/network.py:114-125`).
- Minimum edge weight, minimum degree and minimum shared works for an edge are not set in the build.
- `--cap` has no range check (`scripts/build_network.py:27`).
- The CLI passes no `generated_at` value (`scripts/build_network.py:40`).
- No networkx version pin in code. The ADR's `networkx>=3.4` is the only stated constraint
  (`.agent/DECISIONS.md:618`).

## 13. Planned, not built

The BQ-3.2 structure metrics are built; section 14 describes them. The other BQ-3.x outputs are
not built. Owner rule A3-D8 governs only new outputs. Sections 1 to 12 describe `network.json`
only.

## 14. Metrics (BQ-3.2)

`site/data/california/network_metrics.json` (schema `bq3-v1`) measures the collaboration structure in two
graphs: authors (G-A) and institutions (G-I). It is separate from `network.json`. The page does
not draw it. The build reads only committed site files, so it runs offline.

Inputs (`scripts/build_network_metrics.py`):

- `site/data/california/index.json`: works (`plastic_related`, `author_ids`, `institution_ids`, `year`,
  `ca_any_author`) and authors (`author_id`, `institution_ids`, `current_in_ca`).
- `site/data/california/institutions.json`: `inst_id`, `atlas_type` (sector) and `ca_flag`.
- `site/data/california/build_metadata.json`: the index build time, copied to `source.index_build_timestamp`.
  If the file is missing, the index's own `generated_at` is used.

Scope and graphs (`src/atlas/analytics/network_metrics.py`, `build_metrics`):

- All plastic-related works in the index are used, not the 400-node cap of `network.json`.
- G-A nodes are Atlas authors (the `authors` list) listed on a plastic-related work in the
  window. A co-author who is not in the list is not a node and creates no edge.
- G-I nodes are the institutions in a work's `institution_ids`, whether or not they belong to a
  California author.
- Edge weight is the number of works in the window on which both ends are listed (a co-authored
  work count, not Newman fractional weighting).
- Windows: `all` (every plastic-related work, including works before 2011 and works with no
  year), `2011-2015`, `2016-2020`, `2021-2025` (inclusive year ranges) and `2026` (`partial`
  true). Works before 2011 appear only in `all`.

Metrics per graph and window: `nodes`, `edges`, `components` (isolates count as components),
`components_with_edges`, `giant_component_nodes` and `giant_component_share`, `density`
(2 x edges / (n (n - 1))), `average_clustering` (networkx default: nodes with fewer than two
neighbours count as 0), `isolates` and `isolate_share`, `degree` quantiles (min, p25, median,
p75, p90, max), `communities` and `modularity` (Louvain, seed 42, run on nodes with at least one
edge), and three edge fractions, each with `edges_considered`: `cross_institution`,
`cross_sector` and `out_of_region`. The payload's `definitions` object gives the plain-language
rule for each metric.

Isolates: for authors, a node with no other Atlas author on any window work (single-author works,
or works whose other authors are outside the authors list). For institutions, a node with no other
institution on any window work.

Ascertainment: the corpus is California-only. Collaborators outside California appear only through
works co-authored with California researchers. The payload's `ascertainment_note` states this.
`corpus.works_with_no_california_author` counts plastic-related works with no California author.

Rebuilding:

```
py -3.14 scripts/build_network_metrics.py
py -3.14 scripts/build_network_metrics.py --check
py -3.14 scripts/build_network_metrics.py --index PATH --institutions PATH --metadata PATH --out PATH
```

`--check` exits 1 when the file is missing or differs from a rebuild. It ignores `generated_at`
(the build time, UTC) and compares everything else, including `method.networkx`. A networkx
upgrade can change the Louvain partition, so `--check` then reports the file as stale.

Determinism: the Louvain result depends on the order nodes and edges are inserted, so the build
sorts ids before it inserts them. The result is the same for any input order (tested in
`tests/test_network_metrics.py`).

Limits:

1. Isolates and the author counts depend on the authors list. Co-authors outside it are dropped
   (see above).
2. `institutions.json` gives every non-California institution `atlas_type` `other`. That value is
   treated as unclassified. So cross-sector is judged only on edges where both ends have a
   California sector. The `edges_considered` count shows how many edges that is.
3. The institution graph's `cross_institution` is always 1, because an institution edge joins two
   different institutions. It is kept only so both graphs have the same fields.
4. `out_of_region` is judged only where both ends are known. Authors with a null `current_in_ca`
   are excluded.
5. Average clustering counts isolates as 0, so it falls when isolates are more common.
6. The daily ingest (`.github/workflows/ingest_works.yml`) does not run this builder. The file
   goes stale when `index.json` changes until the builder is run again.
7. The literature context figures quoted in the A3 Module 3 spec are not included in the payload
   and were not checked here.

## 15. Null model (BQ-3.3)

`null_model` in `site/data/california/network_metrics.json` (added by
`scripts/build_network_metrics.py`; code in `src/atlas/analytics/network_null.py`) asks whether
the observed clustering, modularity and giant-component share are higher than chance, given how
many collaborators each member has. It is additive: `schema_version` stays `bq3-v1`.

Method:

- Each replicate rewires the observed graph by random double-edge swaps. A swap takes two links
  (a, b) and (c, d) and replaces them with (a, d) and (c, b), with the orientation chosen at
  random. Each member keeps its number of links. Each link keeps its shared-work count, so the
  weight multiset is unchanged. Swaps that would create a self-loop or a duplicate link are
  rejected.
- Target: 10 successful swaps per link (`nswap`). Attempts are capped at 20 times `nswap`
  (`max_tries`). The swap counts (`swaps_succeeded`, `attempts_mean`) are in the block.
- Replicate seeds: one base seed (42) draws one seed per replicate, so replicate i is the same
  on every run. Louvain inside each replicate uses the BQ-3.2 seed (42).
- Replicates R: 100 by default (`--null-replicates`). The null is run for G-A and G-I, for every
  window (`all`, `2011-2015`, `2016-2020`, `2021-2025`, `2026`).
- Statistics: the same functions as BQ-3.2 (`structure_metrics`): `average_clustering`,
  `modularity` and `giant_component_share`. Observed, null mean, null sd (sample standard
  deviation), `z = (observed - null mean) / null sd`, and `p_two_sided`. `z` is null when the
  null sd is 0 or the observed value is missing. `p_two_sided = (1 + k) / (R + 1)`, where k counts
  replicates at least as far from the null mean as the observed value.

How to read `z`: a large positive z means the network is more clustered (or more divided into
groups) than its collaborator counts alone would produce. Around 0 means the value is typical of
chance. Negative z means less than chance. Compare z across windows only with the caveat that the
windows differ in size. A small p means few replicates were as extreme as the observed value; with
R = 100 the smallest possible p is 1/101.

Sensitivity (`null_model.sensitivity`, G-A all years): how the observed statistics move when the
profiles are grouped differently.

- (a) Merge: authors with the same normalized display name (lower case, letters and digits only)
  inside one connected component are merged into one node. This is a crude over-merge, because
  two people can share a name. Merging never joins people across components.
- (b) Split: a seeded 5% of authors with at least two collaborators are each split into two
  nodes. Each of their works goes to one copy or the other at random.
- Each variant reports its node count and the change (`delta`) in each statistic against the
  observed value. Only aggregates are written; no ids or names.

Runtime: the default build (R = 100) took about 17 minutes on the committed inputs (one run, 2026-11-25), mostly in
the G-I all-years and 2021-2025 windows (about 5 seconds per replicate for G-I all years and about
1 second for G-A all years). `--check` repeats this work, so pass the same `--null-replicates`
value that the committed file used. `--null-replicates 0` leaves out the block.

Limits:

1. Profile splitting and merging. Two people can appear as one author, and one person can
   appear as two. The sensitivity block shows the size of that effect for the merge and split
   rules named above; the true error is unknown.
2. The null keeps each member's number of collaborators and each link's shared-work count. It
   does not keep which members work together by field, year or institution. A high z can
   therefore reflect topic or institution clustering, not only collaboration habits.
3. Ascertainment: the corpus is California-only (see section 14). The null describes the
   Atlas corpus, not the whole field.
4. Degree-preserving null is a test of structure given degree, not a test of causes.
5. Windows are small: the 2026 window is partial and the 2011-2015 window has few links, so
   z there is noisy.
6. Projection artefact (lead review, 2026-11-25). Every work with k authors adds a complete
   clique of k(k-1)/2 links, so a co-authorship graph is highly clustered by construction. The
   rewired null breaks those cliques, which is why the all-years z values are in the hundreds
   (authors: clustering 0.68 vs 0.013 in the null, modularity 0.88 vs 0.44, giant component share
   0.48 vs 0.87). Read them as "far from random", not as a measure of how much more clustered.
   A stricter baseline would rewire the bipartite author-work graph and keep work sizes; it is
   not implemented.

`--check` recomputes everything except the null block and checks only that block's shape and R
(about 7 s); `--check --check-null` recomputes the block too (about 17 minutes at R=100).

## 16. Global institutions graph (BQ-V.1 slice 1)

Data only, no author-level output. Builder: `src/atlas/build/global_graphs.py`; command:
`py -3.14 scripts/build_global_graphs.py [--check]`. Output: `site/data/global/graphs/`
(`institutions.json`, `institutions_phone.json`, `layout_institutions.bin`,
`graphs_manifest.json`, schema `bqv-v1`, status `unscreened_query_hit`).

- **Input.** The ignored raw store `data/raw/openalex_global/pages/*.jsonl.gz`, read in fetch-time
  order so a later page replaces an earlier copy of a work. Each work's nodes are the distinct
  institutions over all authorships (OpenAlex short id, e.g. `I170726198`). Authors are read for
  nothing and written nowhere.
- **Edges.** One per institution pair on the same work, weight = shared works. Works with more
  than 50 distinct institutions still count toward node works but add no edges.
- **Component and cap.** Largest connected component of the edge graph, then the top 20,000 nodes
  by works (ties by id). The cap did not bind at the 2026-11-25 backfill (17,234 nodes in the
  component); the cap is recorded in the manifest.
- **Thinning (budgets).** Desktop: at most 60,000 edges (BQ-V.0 benchmarked budget). Phone: at most
  15,000 edges. Rule (`thin_edges`): for each node keep its k strongest edges (ties: the other
  node's works, then id, which is index order), keep the union. If over budget, drop weight-1
  edges (last index first), never one that leaves an endpoint with no edge. If still over budget,
  lower k by one and repeat. Desktop starts at k=8; phone at k=3, applied to the phone subset
  alone. Every node keeps at least its strongest edge. The manifest records `k_used`, edge counts,
  `weight_one_dropped`, `weight_retained_share` and `components_after` per file.
- **Communities.** Louvain (networkx), seed 42, on the thinned desktop graph; community 0 is the
  largest.
- **Layout.** ForceAtlas2 (networkx, scaling ratio 10, strong gravity 0.05, node mass 1 + weighted
  degree) run separately inside each community on the thinned graph for 150 iterations, from
  seeded random points, then communities packed on a sunflower spiral. A single ForceAtlas2 run is
  O(n²) per iteration in networkx (estimated from a 1,000-node timing: about 37 s per iteration at
  20k nodes, with large dense arrays), so the layout is per community. Edges between communities
  do not shape the layout.
- **Positions.** Stored in `layout_institutions.bin` (float32 little-endian x, y in node order,
  4-decimal values before packing). Chosen over inline JSON because 8 bytes per node is well under
  the roughly 22 bytes per node that inline two-decimal coordinates would add (estimated). The
  phone graph uses the first 5,000 entries.
- **Phone subset.** `institutions_phone.json`: the first 5,000 nodes in canonical order (works
  descending, then id) and the phone-thinned edges among them.
- **Determinism.** Nodes are sorted by (works, id) before any graph step; edges by node index; all
  seeds fixed. `--check` rebuilds from the raw store and compares bytes; without the raw store it
  validates the committed files and reports `SKIP staleness`.
- **Files.** Node rows `[id, display_name, ror, country_code, type, works, community]`; edge rows
  `[source, target, weight]` with node indices (source < target). Manifest keys are documented in
  the file itself (`what_this_is_and_is_not`, `caps`, per-graph `layout_method`).

Current build (2026-11-25 raw store: 1,413 pages, 136,074 distinct works, 108,740 with
institutions, 19,206 institutions seen; 212,846 institution pairs before thinning):

| File | Nodes | Edges (before thinning) | k used | Weight kept | Weight-1 dropped | Components | Raw / gzip |
|---|---:|---:|---:|---:|---:|---:|---|
| `institutions.json` | 17,234 | 60,000 (212,599) | 8 | 50.9% | 24,259 | 136 (giant: 16,909 nodes) | 2.55 MB / 0.75 MB |
| `institutions_phone.json` | 5,000 | 12,952 (140,191) | 3 | 34.0% | 0 | 1 | 0.67 MB / 0.21 MB |

Layout `layout_institutions.bin` 0.14 MB raw / 0.09 MB gzip; manifest 3.5 KB. Communities on the thinned
desktop graph: 156 (largest 2,604 nodes; 15 before thinning).

Thinning leaves 325 nodes outside the giant component in 135 small pieces (2 to 9 nodes). Each
keeps its strongest edge, as the rule requires, but those pieces are not connected to the giant
component. The giant component keeps 98% of nodes.

Known limits: the desktop graph keeps about half the edge weight, and the phone graph about a
third; the thinned graph is a picture of the strongest links, not the full co-occurrence. Phone
edge count is now within the 15,000 budget but was 140k before thinning. Layout quality is not
visually checked. The layout does not show inter-community links, and packed communities can
overlap a little. Build time about 5.5 min (raw read about 80 s).

## 16b. Global authors graph (BQ-V.1 slice 2)

Same builder and command as section 16 (`py -3.14 scripts/build_global_graphs.py [--check]`); the
institution files are unchanged byte for byte. Added files: `authors.json`, `authors_phone.json`,
`layout_authors.bin`; the manifest gains `graphs.authors`, `graphs.authors_phone` and an
`author_graph` block (backbone counts, caps, rules). Owner decision 2026-11-25 (QUESTIONS
GLOBAL-AUTHORS): author display names are published as public OpenAlex names. Emails, raw
affiliation strings, ORCIDs and abstracts are never written.

- **Backbone.** A work is on the backbone when a pollution-core v0 term (`config/pollution_core_v0.yml`,
  loaded by `atlas.analytics.denominators.load_pollution_core`) matches its title or abstract. The
  matcher is `atlas.review_highlight.term_pattern` (whole word, case-insensitive, plural allowed),
  applied to the raw pages in memory. It is a local check, not OpenAlex's stemmed search.
- **Nodes.** OpenAlex author short id, public display name (latest page), primary country (most
  frequent institution `country_code` over the author's backbone authorships; each authorship counts
  each country once; ties: lowest code; null if none), works = backbone works the author is on.
- **Edges.** One per author pair sharing a backbone work; weight = shared works. Works with more
  than 25 distinct authors count toward node works but add no edges (hyper-authorship cap).
- **Component, cap, thinning.** Same rules as section 16: largest connected component, top 20,000
  authors by works (ties by id), desktop budget 60,000 edges (k starts at 8); phone top 5,000 with
  a 15,000 budget (k starts at 3, phone subset alone).
- **Communities and layout.** Louvain (seed 42) on the thinned desktop graph; ForceAtlas2 per
  community, packed as in section 16. Positions are float32 pairs in `layout_authors.bin`; the
  phone file uses the first 5,000 entries.
- **Fields.** Node rows `[id, display_name, country_code, works, community]`; edge rows
  `[source, target, weight]`. No other person-level fields. `check_outputs` rejects any forbidden
  key (`email`, `affiliations`, `raw_affiliation_strings`, `orcid`, `observed_orcids`) in the
  author files.
- **Determinism.** Pages are read in fetch-time order; authors sorted by (works, id) before any
  graph step; all seeds fixed. `--check` rebuilds and compares bytes when the raw store is present.

Build at the 2026-11-25 raw store (136,074 distinct works): 78,045 works match the core terms
(backbone works with authors 75,941; 139 of them above the 25-author cap, no edges). 188,592
authors seen; 779,021 author pairs with edges before thinning; the giant component has 112,939
authors.

| File | Nodes | Edges (before thinning) | k used | Weight kept | Weight-1 dropped | Components | Raw / gzip |
|---|---:|---:|---:|---:|---:|---:|---|
| `authors.json` | 20,000 | 60,000 (117,259) | 8 | 77.6% | 25,455 | 956 | 1.73 MB / 0.63 MB |
| `authors_phone.json` | 5,000 | 10,141 (33,586) | 3 | 62.8% | 0 | 127 | 0.36 MB / 0.14 MB |

Layout `layout_authors.bin` 0.16 MB raw. Communities on the thinned desktop graph: 1,226 (both
files). Full build (both graphs, including the second raw read for the backbone): about 11 min
(the institution-only build of section 16 took about 5.5 min).

Known limits: the author graph is the backbone's strongest co-authorship links, not the full
network; the cap of 20,000 takes the top authors by backbone works and can cut the giant component
into pieces. Layout is not visually checked. Matching is a local approximation of OpenAlex's search.
