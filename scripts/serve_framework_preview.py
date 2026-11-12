"""Serve the classic site and the Framework build together, laid out as on GitHub Pages (AT-5).

    <prefix>/        -> site/              (classic site, the live root)
    <prefix>/app/    -> framework/<dist>/  (Observable Framework build)

Extensionless paths fall back to ``.html`` like GitHub Pages, so Framework's clean URLs work.

Usage:
    py -3.14 scripts/serve_framework_preview.py [--port 8766] [--dist dist]
    then open http://127.0.0.1:8766/CA_Plastics_Research_Dash/app/
"""

from __future__ import annotations

import argparse
import functools
import http.server
import threading
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "/CA_Plastics_Research_Dash"


def resolve(url_path: str, site: Path, dist: Path) -> Path | None:
    """Map a request path to a file, or None when it is outside both trees or missing."""
    path = unquote(urlsplit(url_path).path)
    if not path.startswith(PREFIX + "/"):
        return None
    rest = path[len(PREFIX) + 1 :]
    if rest == "app" or rest.startswith("app/"):
        base, rest = dist, rest[4:]
    else:
        base = site
    target = (base / rest).resolve()
    if base.resolve() not in (target, *target.parents):
        return None
    if target.is_dir():
        target = target / "index.html"
    if not target.exists() and target.suffix == "":
        target = target.with_suffix(".html")
    return target if target.is_file() else None


class Handler(http.server.SimpleHTTPRequestHandler):
    site: Path = ROOT / "site"
    dist: Path = ROOT / "framework" / "dist"

    def translate_path(self, path: str) -> str:  # noqa: D102 - stdlib override
        target = resolve(path, self.site, self.dist)
        return str(target) if target else str(ROOT / "__missing__")

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
        pass


def make_server(port: int, dist: str = "dist") -> http.server.ThreadingHTTPServer:
    handler = type("PreviewHandler", (Handler,), {"dist": ROOT / "framework" / dist})
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(handler))


def serve_in_background(port: int, dist: str = "dist") -> http.server.ThreadingHTTPServer:
    server = make_server(port, dist)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument(
        "--dist", default="dist", help="build folder under framework/ (default dist)"
    )
    args = parser.parse_args()
    server = make_server(args.port, args.dist)
    print(f"Serving http://127.0.0.1:{args.port}{PREFIX}/app/  (classic site at {PREFIX}/)")
    server.serve_forever()


if __name__ == "__main__":
    main()
