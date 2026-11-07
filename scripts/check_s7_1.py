"""Machine acceptance check for the S7.1 monitoring registry."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from atlas.ingest.monitoring.registry import load_registry


def _smoke_url(url: str, timeout: float) -> tuple[str, int, str]:
    request = Request(url, headers={"Range": "bytes=0-1023", "User-Agent": "CA-Plastics-Atlas/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(1024)
            if not body:
                raise RuntimeError("empty response body")
            return url, response.status, response.headers.get("Content-Type", "unknown")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"source URL smoke failed for {url}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/datasets.yml"))
    parser.add_argument(
        "--smoke-urls", action="store_true", help="make bounded GETs to verified seed URLs"
    )
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args()

    registry = load_registry(args.config)
    entries = registry["datasets"]
    eligible = [entry for entry in entries if entry["seed_eligible"]]
    assert len(eligible) >= 15
    assert len({entry["id"] for entry in entries}) == len(entries)
    assert len({entry["underlying_dataset_id"] for entry in eligible}) == len(eligible)
    assert all(entry["provenance_url"] and entry["last_checked"] for entry in eligible)
    assert all(entry["evidence_excerpt"] and entry["evidence_identity"] for entry in eligible)
    assert all(entry["verification_url"].startswith("https://") for entry in eligible)
    assert any(entry["provenance_type"] == "literature_secondary" for entry in eligible)
    assert any(entry["access_tier"] == "A" for entry in eligible)
    assert any(entry["access_tier"] == "B" for entry in eligible)
    assert any(entry["access_tier"] == "D" for entry in eligible)

    if args.smoke_urls:
        with ThreadPoolExecutor(max_workers=4) as pool:
            urls = sorted(
                {
                    entry[field]
                    for entry in eligible
                    for field in ("url", "provenance_url", "verification_url")
                }
            )
            futures = [pool.submit(_smoke_url, url, args.timeout) for url in urls]
            for future in as_completed(futures):
                url, status, content_type = future.result()
                print(f"URL PASS {status} {content_type} {url}")
        print(f"URL smoke passed: {len(urls)} distinct source/provenance links")

    print(
        f"S7.1 acceptance passed: {len(eligible)} distinct verified seed identities "
        f"of {len(entries)} registry records"
    )


if __name__ == "__main__":
    main()
