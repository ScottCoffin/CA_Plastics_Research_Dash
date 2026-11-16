# VD-13 verification: Overview entry-card counts

Date: 2026-11-16

## Result

`build_metadata.json` `counts` gains six keys; `index.json` counts are unchanged
(`check_s3_1.py` pins them). Each count follows the default view of the page that
shows it:

| Key | Definition | Value | Page figure |
|---|---|---|---|
| `awards` | `grants.json` rows with `plastic_related` not false (Funding opens with "true or unknown") | 503 | Funding "503 of 524 awards match" |
| `monitoring_samples` | `monitoring.json` `sample_count`; omitted for a `private_preview` | 298 | Monitoring "298 samples in extent" |
| `monitoring_sources` | rows in `monitoring.json` `datasets` | 25 | Monitoring dataset list |
| `network_experts` | `network.json` nodes | 400 | Network "400 experts, 1,245 links shown" |
| `network_links` | edges between listed nodes with weight >= 1 | 1,245 | same |
| `plastic_works` | slim works with `plastic_related` true | 1,579 | Evidence map (plastic-related only) |

`export_site` reads the sibling payloads when present (absent or malformed files
leave the key out, so the card stays hidden). The daily ingest builds the network
after the export, so `scripts/build_network.py` refreshes the two network keys in
`build_metadata.json` after writing `network.json`. The committed
`site/data/build_metadata.json` was updated once by the lead with
`refresh_metadata_counts` (counts only; every other field unchanged), so the
cards show before the next daily run. The Overview Evidence card now shows
plastic-related works instead of all works, since the Evidence map is
plastic-related only. About keeps its four existing stats.

## Verification

- Tests: `tests/test_vd13_counts.py` (11 tests: keys present with sibling files,
  absent without them, private preview omitted, network refresh keeps other
  fields, Overview hooks) and two updated assertions in `tests/test_vd5_overview.py`.
- Clean worktree of HEAD with VD-10 and VD-13 applied: Ruff check and format,
  links, pytest 1,719 passed with 13 skips.
- Assembled local site: the Overview cards read "2,635 authors", "400 experts ·
  1,245 links", "2,400 institutions · 211 California institutions", "298 samples ·
  25 sources", "503 plastic-related awards" and "1,579 plastic-related works";
  Policy and Related resources show no count, as specified.

## Known issue (not caused by this task)

`scripts/check_s3_1.py` fails on its pinned fixture counts (expects 4 works and
authors, gets 3) at HEAD as well; not in CI. Recorded for a separate fix.

## Deployed

Pushed `3d15e753`..`2cc15d30` on 2026-11-16; CI `43964970928`, Pages `43964971620` and legacy Pages `43964967242` passed. Live check on https://plastiverse.live/: Overview cards show the six new counts; network legend six Okabe-Ito colours plus `#8a969c`; Monitoring map `#0072B2`/`#CC79A7`; Funding "503 of 524 awards match".
