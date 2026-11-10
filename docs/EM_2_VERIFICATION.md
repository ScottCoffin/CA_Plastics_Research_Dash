# EM-2 verification (partial): Regional Water Board layer and offshore rule

Task: EM-2 in `.agent/TODO.md`; contract in [Add-on A2](add_on_spec_2.md) §4 and §9.
Date: 2026-11-09. Partial work before S5.4 is permitted by `QUESTIONS.md` A2-INT-2.

| DoD / acceptance item | Status | Evidence |
|---|---|---|
| Fetch the layer as GeoJSON | Done (one live request, free public endpoint) | [api note](api_notes/rwqcb_regions.md): HTTP 200, 8,523,474 bytes, SHA-256 recorded; raw kept in ignored `data/raw/rwqcb/` |
| Nine features, codes 1–9 (EAT-12) | Pass | `scripts/build_rwqcb_regions.py` validates count, codes and names; `tests/acceptance/add_on_a2/test_eat12_regional_layer.py` |
| Four point checks (EAT-12) | Pass: Sacramento → 5; SF Bay → 2; about 60 km and 20 km offshore → no region | same, on the committed asset |
| Offshore rule | Implemented: region hit wins; otherwise inside the CDFW ds3158 state waters (S1.3, CC BY 4.0) → `offshore_state_waters`; otherwise `offshore_or_unassigned` | `atlas.geo.rwqcb.assign_region`; tests cover Ocean Beach 3 km and the Farallones |
| Record the state-waters source | CDFW ds3158 from S1.3 (A2-D11 default: picked in EM-2; owner confirmation still pending) | api note |
| REUSE.md entry [OWNER] | Done at A2 integration | `docs/REUSE.md` A2 ledger |
| Disclaimer wired into V-2, V-9a, About | Not done: the text and links exist as `REGIONAL_DISCLAIMER` / `DISCLAIMER_LINKS`; V-2 (EM-9) and V-9a (EM-11) do not exist yet, and About wiring is left to the site task that first displays regions | `src/atlas/geo/rwqcb.py` |
| Derive `rwqcb_region` on works | Not done: waits for S5.4 `geo_mentions` | — |

Committed asset: `data/processed/geo/rwqcb_regions.parquet` (893,777 bytes; 9 valid
polygons, EPSG:4326). It uses shapely `simplify(0.0002°, preserve_topology=True)`, about
20 m, then merges simplification slivers (each < 1e-5 deg²) into the nearest region.
The union part count is asserted unchanged, provenance sits in the GeoParquet metadata
(`atlas_provenance`), and a rebuild is byte-identical.

Commands: `py -3.14 scripts/build_rwqcb_regions.py`; `py -3.14 -m pytest -q
tests/test_rwqcb_em2.py tests/acceptance/add_on_a2/test_eat12_regional_layer.py` (40
passed); full gate passed (407 passed, 9 skipped).
