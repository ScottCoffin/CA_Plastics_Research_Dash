# Gazetteer ambiguity blacklist

`config/gazetteer_blacklist.csv` is an explicit pre-lookup exclusion list for
exact strings that are ordinary English terms as well as California place
names. It prevents the recall-oriented gazetteer gate from calling a paper
geographic merely because it contains a word such as `Orange`, `Paradise`, or
`Commerce`.

The blacklist is deliberately narrow: it does not exclude `California`, named
water bodies, counties, or unambiguous city names. It applies before both
GeoNames records and curated aliases. A later extraction stage can recover a
blacklisted place only with contextual evidence (for example, an address,
coordinate, county, or a manually reviewed override); it must not silently
remove the blacklist.

`The Bay` and `The Delta` are excluded separately because they are informal
regional labels whose intended geographic extent is not a stable point. The
curated alias file therefore keeps specific forms such as `SF Bay` and
`California Delta` instead.
