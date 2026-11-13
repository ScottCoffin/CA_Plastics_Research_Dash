# UX-11 verification (2026-11-12)

Contract: `docs/EM_spec.md` UX-11 (one "Reuse terms not recorded" badge, shown only when true;
fill knowable stewards from the stewards' own pages, with a source link).

## Changes
- `framework/src/components/resources.js` (+ `resources.css`): cards show "Updates" only when the
  steward states an update model and "Terms" only when terms are recorded; otherwise one
  "Reuse terms not recorded" badge. A steward name links to its source when one is recorded.
- `config/linkouts.yml`: new optional `steward_source` (validated as https in
  `src/atlas/linkouts.py`, exported to `site/data/linkouts.json`, documented in DATA_DICTIONARY).
  - NOAA NCEI Marine Microplastics: steward "NOAA National Centers for Environmental Information",
    stated as Publisher and Distributor on the NCEI metadata page (fetched 2026-11-12).
  - Plastiverse tools directory: steward "Plastiverse", the only operator named on the directory
    page (fetched 2026-11-12; the footer credits only the site designer). No terms of use are
    stated there, so the entry keeps "not recorded".
- Tests: `tests/test_ux11_resources.py`; `tests/test_linkouts_strip_em5.py` field set updated.
