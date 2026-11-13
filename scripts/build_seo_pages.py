"""Generate static SEO entity pages and sitemaps under ``site/`` (S3.8).

Writes ``site/experts/<id>/index.html``, ``site/institutions/<id>/index.html``,
``site/sitemap.xml`` and its child sitemaps. These are deploy-only outputs (gitignored).
The workflow step is best effort, so a failure here never blocks the Pages deploy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.build.seo import DEFAULT_BASE_URL, build_site

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    parser.add_argument("--base", default=DEFAULT_BASE_URL)
    args = parser.parse_args(argv)

    counts = build_site(args.site, args.base)
    print(json.dumps({"site": str(args.site), **counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
