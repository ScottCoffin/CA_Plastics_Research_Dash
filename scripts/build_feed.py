"""Write ``site/feed.xml``, the Atom digest of new CA-plastic papers and awards (S11.4).

Reads only the public payloads ``site/data/index.json`` and ``site/data/grants.json``.
Offline and deterministic: unchanged inputs give a byte-identical feed. The workflow
step is best effort, so a failure here never blocks the Pages deploy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.build.feed import DEFAULT_GRANTS, DEFAULT_INDEX, DEFAULT_OUTPUT, write_feed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--grants", type=Path, default=DEFAULT_GRANTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    counts = write_feed(args.index, args.grants, args.output)
    print(json.dumps({"output": str(args.output), **counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
