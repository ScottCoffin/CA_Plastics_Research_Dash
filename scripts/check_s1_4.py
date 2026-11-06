"""Machine acceptance check for S1.4 California gazetteer assets."""

from __future__ import annotations

import sqlite3

from atlas.geo.gazetteer import DEFAULT_DATABASE_PATH, is_blacklisted, lookup


def main() -> None:
    with sqlite3.connect(DEFAULT_DATABASE_PATH) as connection:
        feature_count = connection.execute("SELECT COUNT(*) FROM feature").fetchone()[0]
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    assert feature_count > 1_000
    assert metadata["license"] == "CC BY 4.0"
    assert metadata["subset_rule"] == "country_code=US and admin1_code=CA"

    sacramento = lookup("Sacramento")
    assert any(match.geonames_id == 5389489 for match in sacramento)
    assert lookup("SF Bay") and lookup("SF Bay")[0].source == "curated_alias"
    assert is_blacklisted("Orange")
    assert lookup("Orange") == ()
    print(f"features={feature_count}")
    print("lookup=Sacramento,SF Bay passed")
    print("blacklist=Orange passed")


if __name__ == "__main__":
    main()
