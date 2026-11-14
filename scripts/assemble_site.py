"""Put the Observable Framework app at the site root with redirect stubs (owner H16 switch).

Usage:
    py -3.14 scripts/assemble_site.py --site site --dist framework/dist --out scratch/deploy
    python scripts/assemble_site.py --site site --dist framework/dist --out site  # deploy

Local preview of the result: py -3.14 scripts/serve_framework_preview.py --assembled scratch/deploy
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.assemble import assemble  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", default=str(ROOT / "site"))
    parser.add_argument("--dist", default=str(ROOT / "framework" / "dist"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    counts = assemble(Path(args.site), Path(args.dist), Path(args.out))
    print(f"assembled: {counts['pages']} app pages at the root, {counts['stubs']} redirect stubs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
