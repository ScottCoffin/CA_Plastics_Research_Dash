#!/usr/bin/env python3
"""Build suggestions.json (cg-suggestions-v1): Wikidata identity suggestions for roster groups.

GRP-ENRICH slice 1 (ADR-GRP-ENRICH-2026-11-26). Facts here are suggestions only: an ambassador
confirms each one with evidence, and nothing is tagged automatically. Source: Wikidata (CC0).

Usage:
  py -3.14 scripts/build_group_suggestions.py             # query Wikidata (cached) and write
  py -3.14 scripts/build_group_suggestions.py --offline   # use only the raw response cache
  py -3.14 scripts/build_group_suggestions.py --check     # validate; rebuild offline if cached
  py -3.14 scripts/build_group_suggestions.py --limit 50  # first N roster records; not written

Matching, in order: (1) the registrable domain of the roster URL equals that of a Wikidata P856
website; (2) an English label or alias equals the roster name (or an alternate name), the item has
the roster country (P17, ISO P297), and it is an organisation (P31/P279* Q43229). A roster country
of AF or none counts as unknown, so label matches are not made. Ambiguous matches and items that
match two groups are dropped. Exit codes: 0 ok, 1 invalid or differs from the rebuild, 2 network
error, rate limit or cache miss.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.groups import admission  # noqa: E402
from atlas.groups.build import to_bytes  # noqa: E402

GROUPS_DIR = ROOT / "site" / "data" / "global" / "groups"
ROSTER_PATH = GROUPS_DIR / "roster.json"
OUTPUT_PATH = GROUPS_DIR / "suggestions.json"
CACHE_DIR = ROOT / "data" / "interim" / "group_enrichment"

SCHEMA = "cg-suggestions-v1"
SOURCE = "Wikidata (CC0)"
SPARQL_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "PlastiverseLive/1.0 (https://plastiverse.live)"
MIN_INTERVAL = 1.0
RETRY_AFTER_429 = 60
TIMEOUT = 60
DOMAIN_BATCH = 50  # roster hosts per query (8 URL variants each)
LABEL_BATCH = 25  # literal names per query
ITEM_BATCH = 50  # item ids per query
ORGANISATION = "Q43229"
# Label matches only (website matches are not filtered): the subclass walk admits places and
# vessels through government and other classes, so the item's English type labels must name an
# organisation and none may name a place, vessel, election or local government.
ORG_TYPE_WORDS = re.compile(
    r"organi[sz]ation|association|foundation|charit|coalition|network|cooperative|co-operative|"
    r"society|club|institute|university|college|school|think tank|advocacy|movement|trust|"
    r"alliance|federation|collective|campaign|nonprofit|non-profit",
    re.IGNORECASE,
)
NOT_ORG_TYPE_WORDS = re.compile(
    r"municipality|county|city|town|village|parish|province|district|ship|caravel|vessel|"
    r"electoral|election|painting|song|album|film|human settlement|river|island",
    re.IGNORECASE,
)


def label_types_ok(labels: Iterable[str]) -> bool:
    """True when the type labels name an organisation and nothing that is clearly not one."""
    labels = [label for label in labels if label]
    if any(NOT_ORG_TYPE_WORDS.search(label) for label in labels):
        return False
    return any(ORG_TYPE_WORDS.search(label) for label in labels)


UNKNOWN_COUNTRY = "AF"
MATCH_METHODS = ("website", "label")
MIN_YEAR = 1800
QID_RE = re.compile(r"^Q\d+$")
HOST_RE = re.compile(r"^[a-z0-9.-]+$")
ENTITY_PREFIX = "http://www.wikidata.org/entity/"


class WikidataError(Exception):
    """Network failure, unexpected HTTP status or invalid response."""


class RateLimited(WikidataError):
    """HTTP 429 twice in a row: stop and re-run later (cached queries are kept)."""


class CacheMiss(WikidataError):
    """Offline run needs a query that is not in the cache."""


def _post_sparql(query: str) -> dict[str, Any]:
    data = urllib.parse.urlencode({"query": query, "format": "json"}).encode("ascii")
    req = urllib.request.Request(
        SPARQL_URL,
        data=data,
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


class WikidataClient:
    """Batched SPARQL access with a raw-response cache, 1 request/second and one 429 retry."""

    def __init__(
        self,
        cache_dir: Path = CACHE_DIR,
        offline: bool = False,
        post: Callable[[str], dict[str, Any]] = _post_sparql,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache_dir = cache_dir
        self.offline = offline
        self._post = post
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None

    def sparql(self, query: str) -> list[dict[str, Any]]:
        key = hashlib.sha256(query.encode("utf-8")).hexdigest()
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            body = json.loads(path.read_text(encoding="utf-8"))
        elif self.offline:
            raise CacheMiss(f"query {key[:12]} is not cached; run without --offline")
        else:
            body = self._fetch(query)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(body), encoding="utf-8")
            os.replace(tmp, path)
        return body["results"]["bindings"]

    def _throttle(self) -> None:
        if self._last is not None:
            wait = MIN_INTERVAL - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)

    def _fetch(self, query: str) -> dict[str, Any]:
        for attempt in (1, 2):
            self._throttle()
            try:
                body = self._post(query)
            except urllib.error.HTTPError as exc:
                self._last = self._clock()
                if exc.code != 429:
                    raise WikidataError(f"HTTP {exc.code} from query.wikidata.org") from exc
                if attempt == 2:
                    raise RateLimited(
                        "HTTP 429 twice; stopped. Re-run later (cached queries kept)."
                    )
                self._sleep(RETRY_AFTER_429)
                continue
            except (urllib.error.URLError, OSError, ValueError) as exc:
                raise WikidataError(f"query.wikidata.org request failed: {exc}") from exc
            self._last = self._clock()
            return body
        raise WikidataError("unreachable")  # pragma: no cover

    def domain_rows(self, hosts: Iterable[str]) -> list[tuple[str, str]]:
        """(item QID, P856 value) for items whose website is one of the hosts' URL variants."""
        rows: list[tuple[str, str]] = []
        for chunk in _batches(sorted(hosts), DOMAIN_BATCH):
            values = " ".join(f"<{url}>" for host in chunk for url in _host_variants(host))
            query = (
                "SELECT DISTINCT ?item ?web WHERE { VALUES ?web { "
                + values
                + " } ?item wdt:P856 ?web . }"
            )
            rows += [(_qid(b["item"]["value"]), b["web"]["value"]) for b in self.sparql(query)]
        return rows

    def label_rows(self, literals: Iterable[str]) -> list[tuple[str, str]]:
        """(item QID, English label or alias) for items with an exact English label or alias."""
        rows: list[tuple[str, str]] = []
        for chunk in _batches(sorted(literals), LABEL_BATCH):
            values = " ".join(_sparql_str(text) + "@en" for text in chunk)
            query = (
                "SELECT DISTINCT ?item ?lab WHERE { VALUES ?lab { "
                + values
                + " } { ?item rdfs:label ?lab } UNION { ?item skos:altLabel ?lab } }"
            )
            rows += [(_qid(b["item"]["value"]), b["lab"]["value"]) for b in self.sparql(query)]
        return rows

    def values(self, prop: str, qids: Iterable[str]) -> dict[str, list[str]]:
        """Raw values of a direct claim (wdt:PNNN) for each item; entity values are URIs."""
        out: dict[str, list[str]] = defaultdict(list)
        for chunk in _batches(sorted(qids), ITEM_BATCH):
            query = (
                "SELECT DISTINCT ?item ?v WHERE { VALUES ?item { "
                + " ".join(f"wd:{q}" for q in chunk)
                + " } ?item wdt:"
                + prop
                + " ?v . }"
            )
            for b in self.sparql(query):
                out[_qid(b["item"]["value"])].append(b["v"]["value"])
        return out

    def organisation_types(self, qids: Iterable[str]) -> set[str]:
        """The QIDs among qids that are organisation (Q43229) or a subclass of it (P279*).

        Walks direct P279 parents upward in batches (the endpoint is slow on P279* over many
        items), then marks every node whose parents reach Q43229 by a fixed-point pass.
        """
        parents: dict[str, set[str]] = defaultdict(set)
        seen = set(qids)
        frontier = set(qids)
        while frontier:
            for chunk in _batches(sorted(frontier), ITEM_BATCH):
                query = (
                    "SELECT DISTINCT ?t ?p WHERE { VALUES ?t { "
                    + " ".join(f"wd:{q}" for q in chunk)
                    + " } ?t wdt:P279 ?p . }"
                )
                for b in self.sparql(query):
                    parents[_qid(b["t"]["value"])].add(_qid(b["p"]["value"]))
            frontier = {p for ps in parents.values() for p in ps} - seen
            seen |= frontier
        is_org = {ORGANISATION}
        changed = True
        while changed:
            changed = False
            for node, ps in parents.items():
                if node not in is_org and ps & is_org:
                    is_org.add(node)
                    changed = True
        return {q for q in qids if q in is_org}

    def english_labels(self, qids: Iterable[str]) -> dict[str, str]:
        labels: dict[str, str] = {}
        for chunk in _batches(sorted(qids), ITEM_BATCH):
            query = (
                "SELECT DISTINCT ?item ?lab WHERE { VALUES ?item { "
                + " ".join(f"wd:{q}" for q in chunk)
                + ' } ?item rdfs:label ?lab . FILTER(LANG(?lab) = "en") }'
            )
            for b in self.sparql(query):
                labels[_qid(b["item"]["value"])] = b["lab"]["value"]
        return labels


def _batches(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _qid(uri: str) -> str:
    return uri.removeprefix(ENTITY_PREFIX)


def _sparql_str(text: str) -> str:
    clean = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ")
    return '"' + clean + '"'


def _host_variants(host: str) -> list[str]:
    urls = []
    for scheme in ("https", "http"):
        for prefix in ("", "www."):
            for slash in ("/", ""):
                urls.append(f"{scheme}://{prefix}{host}{slash}")
    return urls


def _host(url: str) -> str | None:
    """Lower-case host without a leading www., or None."""
    if "://" not in url:
        url = "https://" + url
    try:
        host = urllib.parse.urlsplit(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower().rstrip(".")
    return host.removeprefix("www.")


def norm(text: str) -> str:
    """Accent-, case-, punctuation- and leading-'the'-insensitive key (as in the spike)."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[\W_]+", " ", text).strip()
    return re.sub(r"^the ", "", text)


def _eligible_host(url: str | None) -> tuple[str, str] | None:
    """(registrable domain, host) for a roster URL that may be used as a website key."""
    if not url or admission.excluded_host(url):
        return None
    reg = admission.registrable_domain(url)
    host = _host(url)
    if not reg or not host or not HOST_RE.match(host) or reg in admission.SOCIAL_HOSTS:
        return None
    return reg, host


def _country_ok(record: Mapping[str, Any]) -> bool:
    country = record.get("country")
    return bool(country) and country != UNKNOWN_COUNTRY


def _year(values: Iterable[str], today_year: int) -> int | None:
    years = []
    for value in values:
        m = re.match(r"^\+?(\d{1,4})-", value)
        if m and MIN_YEAR <= int(m.group(1)) <= today_year:
            years.append(int(m.group(1)))
    return min(years) if years else None


def _first_web(values: Iterable[str]) -> str | None:
    webs = sorted(v for v in values if v.startswith(("https://", "http://")))
    webs.sort(key=lambda u: not u.startswith("https://"))
    return webs[0] if webs else None


def build_groups(
    records: Sequence[Mapping[str, Any]], client: WikidataClient, today_year: int
) -> tuple[dict[str, dict[str, Any]], Counter]:
    """Return ({group_id: suggestion}, counts). Pure function of the roster and the client."""
    stats: Counter = Counter()
    eligible: dict[str, tuple[str, str]] = {}
    for rec in records:
        key = _eligible_host(rec.get("url"))
        if key:
            eligible[rec["group_id"]] = key
    host_gids: dict[str, list[str]] = defaultdict(list)
    for gid, (_, host) in eligible.items():
        host_gids[host].append(gid)

    # Method 1: website. Rows are exact-host hits, so the registrable domains are equal.
    web_hits: dict[str, set[str]] = defaultdict(set)
    for qid, web in client.domain_rows(host_gids):
        for gid in host_gids.get(_host(web) or "", []):
            web_hits[gid].add(qid)

    # Method 2: English label or alias, only for groups with no website hit and a usable country.
    label_recs = [
        r
        for r in records
        if r["group_id"] not in web_hits and _country_ok(r) and norm(r.get("name", ""))
    ]
    literal_gids: dict[str, set[str]] = defaultdict(set)
    for rec in label_recs:
        for name in [rec["name"]] + list(rec.get("name_alt", []))[:2]:
            if norm(name):
                literal_gids[name].add(rec["group_id"])
    label_hits: dict[str, set[str]] = defaultdict(set)
    for qid, lab in client.label_rows(literal_gids):
        for gid in literal_gids.get(lab, ()):
            label_hits[gid].add(qid)

    candidates: set[str] = set()
    for qids in list(web_hits.values()) + list(label_hits.values()):
        candidates |= qids
    countries = client.values("P17", candidates)
    country_qids = {_qid(v) for vs in countries.values() for v in vs}
    country_iso = {q: set(vs) for q, vs in client.values("P297", country_qids).items()}

    def item_isos(qid: str) -> set[str]:
        return {iso for c in countries.get(qid, []) for iso in country_iso.get(_qid(c), set())}

    websites = client.values("P856", candidates)
    inceptions = client.values("P571", candidates)
    types = {
        q: sorted({_qid(v) for v in vs if v.startswith(ENTITY_PREFIX)})
        for q, vs in client.values("P31", candidates).items()
    }
    type_labels = client.english_labels({t for ts in types.values() for t in ts})
    org_types = client.organisation_types({t for ts in types.values() for t in ts})
    orgs = {
        q
        for q, ts in types.items()
        if org_types.intersection(ts) and label_types_ok([type_labels.get(t, "") for t in ts])
    }

    chosen: dict[str, tuple[str, str]] = {}
    for rec in records:
        gid = rec["group_id"]
        if gid in web_hits:
            if len(web_hits[gid]) == 1:
                chosen[gid] = (next(iter(web_hits[gid])), "website")
            else:
                stats["ambiguous_website"] += 1
            continue
        if gid not in label_hits:
            continue
        ok = {q for q in label_hits[gid] if q in orgs and rec.get("country") in item_isos(q)}
        if len(ok) == 1:
            chosen[gid] = (next(iter(ok)), "label")
        elif ok:
            stats["ambiguous_label"] += 1

    owners: dict[str, list[str]] = defaultdict(list)
    for gid, (qid, _) in chosen.items():
        owners[qid].append(gid)
    for qid, gids in owners.items():
        if len(gids) > 1:
            stats["shared_item_dropped"] += len(gids)
            for gid in gids:
                del chosen[gid]

    groups: dict[str, dict[str, Any]] = {}
    for gid in sorted(chosen):
        qid, method = chosen[gid]
        ptypes = types.get(qid, [])
        groups[gid] = {
            "qid": qid,
            "match": method,
            "website": _first_web(websites.get(qid, [])),
            "inception_year": _year(inceptions.get(qid, []), today_year),
            "types": ptypes,
            "type_labels": [type_labels.get(t, t) for t in ptypes],
        }
        stats[method] += 1
    return groups, stats


def validate(doc: Mapping[str, Any], group_ids: set[str], today_year: int) -> list[str]:
    """Structure checks shared by the build and --check. Returns error strings (empty if valid)."""
    errors: list[str] = []
    if doc.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if doc.get("source") != SOURCE:
        errors.append(f"source must be {SOURCE}")
    try:
        dt.date.fromisoformat(str(doc.get("retrieved_at")))
    except ValueError:
        errors.append("retrieved_at must be YYYY-MM-DD")
    groups = doc.get("groups")
    if not isinstance(groups, dict):
        return errors + ["groups must be an object"]
    for gid, item in sorted(groups.items()):
        where = f"groups[{gid}]"
        if gid not in group_ids:
            errors.append(f"{where}: not a roster group_id")
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        if not isinstance(item.get("qid"), str) or not QID_RE.match(item["qid"]):
            errors.append(f"{where}: qid must match ^Q\\d+$")
        if item.get("match") not in MATCH_METHODS:
            errors.append(f"{where}: match must be website or label")
        site = item.get("website")
        if site is not None and not (
            isinstance(site, str) and site.startswith(("http://", "https://"))
        ):
            errors.append(f"{where}: website must be http(s) or null")
        year = item.get("inception_year")
        if year is not None and not (isinstance(year, int) and MIN_YEAR <= year <= today_year):
            errors.append(f"{where}: inception_year out of range")
        types = item.get("types")
        labels = item.get("type_labels")
        if not isinstance(types, list) or not all(
            isinstance(t, str) and QID_RE.match(t) for t in types
        ):
            errors.append(f"{where}: types must be a list of QIDs")
        if (
            not isinstance(labels, list)
            or not all(isinstance(t, str) for t in labels)
            or (isinstance(types, list) and len(labels) != len(types))
        ):
            errors.append(f"{where}: type_labels must align with types")
    return errors


def render(
    records: Sequence[Mapping[str, Any]],
    client: WikidataClient,
    committed: Mapping[str, Any] | None,
    today: str,
) -> tuple[dict[str, Any], Counter]:
    """Build the document. retrieved_at keeps the committed date when the groups are unchanged."""
    today_year = dt.date.fromisoformat(today).year
    groups, stats = build_groups(records, client, today_year)
    retrieved = today
    if committed and committed.get("groups") == groups and committed.get("retrieved_at"):
        retrieved = committed["retrieved_at"]
    doc = {"schema": SCHEMA, "source": SOURCE, "retrieved_at": retrieved, "groups": groups}
    return doc, stats


def load_roster(path: Path = ROSTER_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["records"]


def _read_committed(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _cache_populated(cache_dir: Path) -> bool:
    return cache_dir.is_dir() and any(cache_dir.glob("*.json"))


def _summary(stats: Counter, groups: Mapping[str, Any]) -> str:
    return (
        f"groups={len(groups)} website={stats['website']} label={stats['label']} "
        f"ambiguous_website={stats['ambiguous_website']} "
        f"ambiguous_label={stats['ambiguous_label']} "
        f"shared_dropped={stats['shared_item_dropped']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="validate the committed file")
    parser.add_argument("--offline", action="store_true", help="use only the raw response cache")
    parser.add_argument(
        "--limit", type=int, default=None, help="first N roster records (not written)"
    )
    args = parser.parse_args(argv)

    today = dt.date.today().isoformat()
    roster = load_roster(ROSTER_PATH)
    group_ids = {r["group_id"] for r in roster}
    committed = _read_committed(OUTPUT_PATH)

    if args.check:
        if committed is None:
            print(f"{OUTPUT_PATH.name} is missing; run scripts/build_group_suggestions.py")
            return 1
        errors = validate(committed, group_ids, dt.date.today().year)
        if errors:
            print("\n".join(errors[:20]))
            return 1
        print(f"{OUTPUT_PATH.name} structure is valid ({len(committed['groups'])} groups)")
        if not _cache_populated(CACHE_DIR):
            print("no response cache; structure checked only")
            return 0
        try:
            doc, _ = render(
                roster, WikidataClient(cache_dir=CACHE_DIR, offline=True), committed, today
            )
        except WikidataError as exc:
            print(f"cache does not cover this roster: {exc}")
            return 1
        if to_bytes(doc) != OUTPUT_PATH.read_bytes():
            print(f"{OUTPUT_PATH.name} differs from the offline rebuild; run the builder")
            return 1
        print(f"{OUTPUT_PATH.name} matches the offline rebuild from the cache")
        return 0

    records = roster[: args.limit] if args.limit is not None else roster
    try:
        client = WikidataClient(cache_dir=CACHE_DIR, offline=args.offline)
        doc, stats = render(records, client, committed, today)
    except WikidataError as exc:
        print(f"stopped: {exc}")
        return 2
    print(_summary(stats, doc["groups"]))
    if args.limit is not None:
        print("limit run: output not written")
        return 0
    errors = validate(doc, group_ids, dt.date.today().year)
    if errors:
        print("\n".join(errors[:20]))
        return 1
    OUTPUT_PATH.write_bytes(to_bytes(doc))
    print(f"wrote {OUTPUT_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
