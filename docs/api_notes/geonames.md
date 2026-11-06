# GeoNames extract notes

Verified 2026-11-05 for S1.4.

- Source: `https://download.geonames.org/export/dump/US.zip`.
- Contract: the official dump README describes country ZIP extracts, UTF-8
  tab-delimited geoname records, and 19 ordered fields. `US.zip` supplied a
  ZIP payload; the build retains rows with `country_code=US` and
  `admin1_code=CA`. The verified 2026-11-05 build yielded 127,963 features
  and 187,760 normalized name variants.
- License: the README explicitly states Creative Commons Attribution 4.0.
  Derived database users must credit GeoNames and link to
  <https://www.geonames.org/>.
- Access/rate note: this task uses the static download, not the username-based
  web-service API. The full raw ZIP stays ignored under `data/raw/`.
- Recheck: `py -3.14 scripts/smoke/geonames.py`; rebuild with
  `py -3.14 scripts/build_gazetteer.py`.
