"""Parse an already-authorized local JATS file into bounded evidence snippets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.fulltext.jats import parse_jats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml", type=Path, help="local XML file from a permitted copy")
    parser.add_argument("--max-chars", type=int, default=1200)
    args = parser.parse_args()
    result = parse_jats(args.xml.read_bytes(), max_chars=args.max_chars)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
