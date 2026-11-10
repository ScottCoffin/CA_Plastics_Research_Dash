"""S11.4 acceptance check: Atom digest feed, feed links, and workflow wiring.

Offline only. Checks that ``site/feed.xml`` parses as Atom with the site feed id, that the
committed fallback matches a fresh render from ``site/data`` (byte-identical, deterministic),
the feed link in ``site/index.html`` (head and About tab), and the ``Build digest feed``
step in ``build_deploy.yml`` (before the upload, best effort, lock-constrained install).
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.build import feed as fd  # noqa: E402

ATOM = "{http://www.w3.org/2005/Atom}"
FEED = ROOT / "site" / "feed.xml"
INDEX_JSON = ROOT / "site" / "data" / "index.json"
GRANTS_JSON = ROOT / "site" / "data" / "grants.json"
INDEX_HTML = ROOT / "site" / "index.html"
WORKFLOW = ROOT / ".github" / "workflows" / "build_deploy.yml"


def _fail(message: str) -> None:
    print(json.dumps({"status": "fail", "error": message}, sort_keys=True))
    raise SystemExit(1)


def check_feed() -> dict:
    if not FEED.exists():
        _fail("site/feed.xml is missing")
    try:
        root = ET.fromstring(FEED.read_bytes())
    except ET.ParseError as exc:
        _fail(f"site/feed.xml is not well-formed XML: {exc}")
    if root.tag != f"{ATOM}feed":
        _fail("site/feed.xml root is not an Atom feed")
    if root.find(f"{ATOM}id").text != fd.FEED_ID:
        _fail("feed id is not the site URL")
    entries = root.findall(f"{ATOM}entry")
    papers = sum(e.find(f"{ATOM}category").get("term") == "paper" for e in entries)
    awards = len(entries) - papers
    if papers > fd.MAX_PAPERS or awards > fd.MAX_AWARDS:
        _fail("feed exceeds the 30 paper / 30 award cap")

    index = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    grants = json.loads(GRANTS_JSON.read_text(encoding="utf-8"))
    fresh = fd.render_feed(index, grants)
    if fresh != fd.render_feed(index, grants):
        _fail("feed render is not deterministic")
    if fresh != FEED.read_bytes():
        _fail("site/feed.xml is stale; rerun scripts/build_feed.py")
    return {"papers": papers, "awards": awards, "bytes": len(fresh)}


def check_index_html() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")
    head, _, rest = text.partition("</head>")
    link = (
        '<link rel="alternate" type="application/atom+xml" '
        'title="New CA plastics papers and awards" href="feed.xml">'
    )
    if link not in head:
        _fail("site/index.html head lacks the Atom alternate link")
    about = rest[rest.find('id="panel-about"') :]
    if not re.search(r'<a href="feed\.xml"[^>]*>Subscribe \(Atom feed\)</a>', about):
        _fail("site/index.html About tab lacks the Subscribe (Atom feed) link")
    if 'href="status.html">run status' not in about:
        _fail("status link is missing from the About tab footer")


def check_workflow() -> None:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = doc["jobs"]["build"]["steps"]
    names = [s.get("name", "") for s in steps]
    if "Build digest feed" not in names or "Upload static site" not in names:
        _fail("build_deploy.yml lacks the digest step or the upload step")
    digest = names.index("Build digest feed")
    if digest > names.index("Upload static site"):
        _fail("digest step must run before Upload static site")
    earlier = ("Refresh open funding calls", "Build status page")
    if any(digest < names.index(name) for name in earlier):
        _fail("digest step must run after the open-calls and status steps")
    step = steps[digest]
    if step.get("continue-on-error") is not True:
        _fail("digest step must set continue-on-error: true")
    run = step.get("run", "")
    if "requirements/lock.txt" not in run or "scripts/build_feed.py" not in run:
        _fail("digest step must install with the lock file and run scripts/build_feed.py")


def main() -> int:
    feed_counts = check_feed()
    check_index_html()
    check_workflow()
    print(json.dumps({"status": "ok", **feed_counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
