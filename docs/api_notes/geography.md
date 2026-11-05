# Geography source verification

Verified 2026-11-05 with `python scripts/smoke/geography.py`. The script accepts
`--land-archive` and `--cdfw-archive` to recheck already-downloaded official
archives without another network transfer.

## California land: Natural Earth

- Dataset: Natural Earth 1:10m Admin 1 states and provinces, version 5.1.1.
- Archive: `https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip`.
- Parameters/filter: select `admin == "United States of America"` and
  `iso_3166_2 == "US-CA"` from `ne_10m_admin_1_states_provinces.shp`.
- Observed shape: exactly one California `MultiPolygon` in WGS84. It follows
  the coastline and does not include the offshore state jurisdiction as land.
- License/terms: Natural Earth's official Terms of Use says all raster and
  vector map data on its site are public domain. Attribution is not required;
  this project nevertheless records Natural Earth as the source.
- Rate limits: no rate limit was published or observed for the static archive;
  builds make one bounded archive request and support a local archive override.
- Fitness caveat: this is generalized 1:10m cartographic geometry, not a legal
  boundary. It is used as a reproducible land classifier, not for surveying.

## California state waters: CDFW ds3158

- Dataset: Three Nautical Mile State Maritime Limit - R7 - CDFW [ds3158].
- Catalog: `https://data.ca.gov/@california-department-of-fish-and-wildlife/three-nautical-mile-state-maritime-limit-r7-cdfw-ds31581`.
- Official archive: `https://filelib.wildlife.ca.gov/Public/BDB/GIS/BIOS/Public_Datasets/3100_3199/ds3158.zip`.
- ArcGIS item metadata: item `28454c15a784418fa5488241559bcd18` at
  `https://www.arcgis.com/sharing/rest/content/items/28454c15a784418fa5488241559bcd18?f=json`.
- Parameters/layers: the ZIP contains `ds3158.gdb` layer `ds3158`
  (`MultiLineString`) and `ds3158_alt.gdb` layer `ds3158_poly`
  (`MultiPolygon`). The build uses the polygon and reprojects EPSG:3310 to
  WGS84; the hosted ArcGIS FeatureServer exposes only the line.
- License/terms: the ArcGIS item and Data.ca.gov catalog state Creative Commons
  Attribution 4.0. Derived assets retain CDFW source and license properties.
- Rate limits: no rate limit was published or observed for the static archive
  or item metadata; smoke checks use one request per resource and allow a local
  archive override.
- Fitness caveat: CDFW describes the line as cartographic and recommends the
  tandem polygon for area calculations/analysis. The State disclaims accuracy
  and completeness; this classifier is not a legal depiction of maritime
  limits.

## Generated artifacts

- `data/processed/geo/ca_land.parquet`: unsimplified pipeline geometry.
- `data/processed/geo/ca_state_waters.parquet`: unsimplified pipeline geometry.
- `site/assets/ca_boundaries.geojson`: both polygons simplified with
  topology preservation at 0.002 degrees; 306,997 bytes on 2026-11-05.
