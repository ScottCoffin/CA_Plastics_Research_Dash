# Collaboration network build (S9.4)

This page explains how `site/data/network.json` is built, what it contains, and where its
known limits are. It describes the code as checked on 2026-11-18. The build reads only
committed site files, so it runs offline. The build was not run for this page; the constants
and line numbers below come from reading the code.

Files:

| Role | File |
|---|---|
| Library (graph, layout, communities, labels) | [`src/atlas/build/network.py`](../src/atlas/build/network.py) |
| Command-line entry point | [`scripts/build_network.py`](../scripts/build_network.py) |
| Output consumed by the `/network` page | [`site/data/network.json`](../site/data/network.json) |
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
| Index | `site/data/index.json` (`scripts/build_network.py:24`) | `authors` and `works` lists, `generated_at` | The build fails (`scripts/build_network.py:32`). |
| Institutions | `site/data/institutions.json` (`scripts/build_network.py:25`) | Institution names and sector types | Optional. The build continues with no institution names or sectors (`scripts/build_network.py:35`). |

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

## 7. Output: `site/data/network.json`

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
| `--index PATH` | `site/data/index.json` | Input index |
| `--institutions PATH` | `site/data/institutions.json` | Optional institutions input |
| `--out PATH` | `site/data/network.json` | Output file |
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
- The commit step's `git add -f` list (starts at `:247`) includes `site/data/network.json`
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

A3 Module 3 (BQ-3.x) will add collaboration-structure metrics. Owner rule A3-D8 governs only new
outputs. This page describes the current build only.
