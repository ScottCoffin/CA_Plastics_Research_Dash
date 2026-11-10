"""Ingest SWRCB FAAST awarded proposals (S8.8) into ``data/interim/grants/swrcb_faast.parquet``.

Searches the public FAAST tool for each keyword in ``KEYWORDS`` (awarded only), unions the
hits by PIN, and reads one detail page per awarded PIN. Only the four labelled detail fields
are used; the Contacts section is never parsed or stored.

``--html-fixture-dir`` runs offline against saved pages (``grid_<keyword>.html`` and
``detail_<pin>.html``) and makes no network calls. A FAAST error, robots disallow, or budget
overrun defers the run: the script exits 0 with status ``deferred`` and leaves the output
untouched. Only counts are printed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from atlas.ingest.grants.faast import (
    MAX_REQUESTS,
    OUTPUT,
    RAW_DIR,
    STATUS_PATH,
    FaastSession,
    FixtureFaast,
    LiveFaast,
    run_faast,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a YAML mapping in {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html-fixture-dir", type=Path, default=None)
    parser.add_argument("--max-requests", type=int, default=MAX_REQUESTS)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--status", type=Path, default=STATUS_PATH)
    parser.add_argument("--config", type=Path, default=Path("config/queries.yml"))
    parser.add_argument("--taxonomy", type=Path, default=Path("config/taxonomy.yml"))
    args = parser.parse_args(argv)
    if args.max_requests < 1:
        parser.error("--max-requests must be at least 1")

    provider: Any
    if args.html_fixture_dir is not None:
        provider = FixtureFaast(args.html_fixture_dir)
    else:
        provider = LiveFaast(FaastSession(max_requests=args.max_requests), args.raw_dir)
    summary = run_faast(
        provider,
        query_config=_load_yaml(args.config),
        taxonomy=_load_yaml(args.taxonomy),
        output=args.output,
        status_path=args.status,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
