# Regional Water Board boundaries (Add-on A2 EM-2)

Verified 2026-11-09 (UTC 2026-11-10) by one live request from the lead.

- Service: California Water Boards hosted feature service "Regional Board
  Boundary Features", layer 1:
  `https://gispublic.waterboards.ca.gov/portalserver/rest/services/Hosted/Regional_Board_Boundary_Features/FeatureServer/1`.
  Geoportal listing: `https://gis.data.ca.gov/datasets/waterboards::regional-board-boundaries`.
- Request: `.../FeatureServer/1/query?where=1%3D1&outFields=*&outSR=4326&f=geojson`
  returned HTTP 200, 8,523,474 bytes, `exceededTransferLimit: false`, SHA-256
  `25576df6ee9551a35a3d424bd9956e31bd4859a8468a63a36582db676e70d490`.
  The raw file is kept in ignored `data/raw/rwqcb/regional_board_boundaries.geojson`.
- Result: 9 features; properties `objectid, rb, rb_name, SHAPE__Length,
  SHAPE__Area, globalid`; `rb` 1-9 = North Coast, San Francisco Bay, Central
  Coast, Los Angeles, Central Valley, Lahontan, Colorado River, Santa Ana, San
  Diego (the service says "Colorado River", not "Colorado River Basin"). All
  geometries are valid; 212,739 exterior vertices in total.
- Point checks (EPSG:4326, lon/lat): Sacramento (-121.4944, 38.5816) → rb 5;
  San Francisco Bay (-122.35, 37.80) → rb 2; offshore (-123.20, 37.70, about
  60 km) and (-122.75, 37.70, about 20 km) → no feature, matching A2 §4.
- Offshore rule (A2 §4; A2-D11 default): no region hit and inside the S1.3 CDFW
  ds3158 state-waters polygon (`data/processed/geo/ca_state_waters.parquet`,
  CC BY 4.0) → `offshore_state_waters`; no region hit and outside it →
  `offshore_or_unassigned`. Checked: (-122.545, 37.76), about 3 km off Ocean Beach,
  and (-123.0, 37.70), near the Farallones, are both `offshore_state_waters`. A
  point can be inside both a region and state waters (for example SF Bay); the
  region wins.
- Licence: the geoportal shows a "Custom License" whose text was not retrieved,
  and the service JSON has no licence field. The owner determined the layer is
  open to use, with a mandatory accuracy disclaimer (ADR-A2-OWNER; `docs/REUSE.md`).
- Cost: free public endpoint, no key, one request.
