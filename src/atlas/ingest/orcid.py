"""ORCID public API enrichment for the expert list (S2.5c, feeding S9.5).

ORCID public data is CC0. This module never keeps email addresses: the ``emails``
section of ``/person`` is removed before anything is cached or returned.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

API_BASE = "https://pub.orcid.org/v3.0"
USER_AGENT = (
    "CA-Plastics-Research-Atlas/1.0 "
    "(+https://github.com/ScottCoffin/CA_Plastics_Research_Dash; academic research)"
)
BIO_MAX = 1200
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
CA_REGIONS = {"ca", "california"}
ORCID_RE = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")

SENSITIVE_PERSON_KEYS = ("emails",)


# --------------------------------------------------------------------------- helpers


def normalize_orcid(value: str | None) -> str:
    """Return the bare ORCID iD (0000-0000-0000-0000) or an empty string."""
    match = ORCID_RE.search(value or "")
    return match.group(0) if match else ""


def normalize_doi(value: str | None) -> str:
    """Lowercase DOI without any resolver prefix; empty when it is not a DOI."""
    text = (value or "").strip().lower()
    text = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text).strip()
    return text if text.startswith("10.") and "/" in text else ""


def normalize_ror(value: str | None) -> str:
    """Bare ROR id (e.g. 05rrcem69) from a URL or id; empty when absent."""
    text = (value or "").strip().lower()
    text = re.sub(r"^(?:https?://)?ror\.org/", "", text)
    return text if re.fullmatch(r"0[0-9a-z]{8}", text) else ""


def _get(obj: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(obj, Mapping):
            return None
        obj = obj.get(key)
    return obj


def _year(date_obj: Any) -> int | None:
    value = _get(date_obj, "year", "value")
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def strip_sensitive(person: Mapping[str, Any]) -> dict[str, Any]:
    """Copy of a ``/person`` payload without contact sections."""
    return {k: v for k, v in person.items() if k not in SENSITIVE_PERSON_KEYS}


# --------------------------------------------------------------------------- parsers


def parse_biography(person: Mapping[str, Any]) -> str:
    text = _get(person, "biography", "content")
    if not isinstance(text, str):
        return ""
    # Biographies are free text: redact contact details as the site export does.
    text = EMAIL_RE.sub("[email removed]", " ".join(text.split()))
    if len(text) > BIO_MAX:
        text = text[: BIO_MAX - 1].rstrip() + "…"
    return text


def parse_keywords(person: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for item in _get(person, "keywords", "keyword") or []:
        content = (item or {}).get("content")
        if isinstance(content, str) and content.strip() and content.strip() not in out:
            out.append(content.strip())
    return out


def parse_researcher_urls(person: Mapping[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in _get(person, "researcher-urls", "researcher-url") or []:
        url = str(_get(item, "url", "value") or "").strip()
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            continue
        out.append({"name": str((item or {}).get("url-name") or "").strip(), "url": url})
    return out


def parse_employments(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for group in payload.get("affiliation-group") or []:
        for summary in group.get("summaries") or []:
            emp = (summary or {}).get("employment-summary") or {}
            org = emp.get("organization") or {}
            dis = org.get("disambiguated-organization") or {}
            ror = ""
            if str(dis.get("disambiguation-source") or "").upper() == "ROR":
                ror = normalize_ror(dis.get("disambiguated-organization-identifier"))
            addr = org.get("address") or {}
            out.append(
                {
                    "org": str(org.get("name") or "").strip(),
                    "ror": ror,
                    "city": str(addr.get("city") or "").strip(),
                    "region": str(addr.get("region") or "").strip(),
                    "country": str(addr.get("country") or "").strip(),
                    "start_year": _year(emp.get("start-date")),
                    "end_year": _year(emp.get("end-date")),
                    "role": str(emp.get("role-title") or "").strip(),
                }
            )
    return out


def parse_work_dois(payload: Mapping[str, Any]) -> list[tuple[str, int | None]]:
    """(doi, publication year) pairs from a ``/works`` payload, de-duplicated."""
    seen: dict[str, int | None] = {}
    for group in payload.get("group") or []:
        year = None
        for ws in group.get("work-summary") or []:
            year = year or _year(ws.get("publication-date"))
        for ext in _get(group, "external-ids", "external-id") or []:
            if str(ext.get("external-id-type") or "").lower() != "doi":
                continue
            doi = normalize_doi(ext.get("external-id-value"))
            if doi and doi not in seen:
                seen[doi] = year
    return list(seen.items())


# --------------------------------------------------------------------------- California logic


def is_ca_employment(emp: Mapping[str, Any], ca_rors: set[str] | frozenset[str]) -> bool:
    region = str(emp.get("region") or "").strip().lower().rstrip(".")
    country = str(emp.get("country") or "").strip().upper()
    if country in {"US", "USA"} and region in CA_REGIONS:
        return True
    ror = normalize_ror(emp.get("ror"))
    return bool(ror and ror in ca_rors)


def ca_employment_years(
    employments: Sequence[Mapping[str, Any]], ca_rors: set[str] | frozenset[str]
) -> list[list[int | None]]:
    """[start, end] for dated California employments (open ends stay None).

    Employments with neither a start nor an end year carry no timing evidence and
    are left out.
    """
    out: list[list[int | None]] = []
    for emp in employments:
        if not is_ca_employment(emp, ca_rors):
            continue
        start, end = emp.get("start_year"), emp.get("end_year")
        if start is None and end is None:
            continue
        out.append([start, end])
    return out


def has_dated_employment(employments: Sequence[Mapping[str, Any]]) -> bool:
    return any(
        e.get("start_year") is not None or e.get("end_year") is not None for e in employments
    )


def classify_carry_forward(
    work_year: int | None,
    employments: Sequence[Mapping[str, Any]],
    ca_years: Sequence[Sequence[int | None]],
    slack: int = 1,
) -> str:
    """confirmed / contradicted / no_evidence for one author_carry_forward authorship."""
    if work_year is None or not has_dated_employment(employments):
        return "no_evidence"
    for start, end in ca_years:
        lo = -(10**6) if start is None else start - slack
        hi = 10**6 if end is None else end + slack
        if lo <= work_year <= hi:
            return "confirmed"
    return "contradicted"


# --------------------------------------------------------------------------- client


class BudgetExhausted(RuntimeError):
    pass


class OrcidClient:
    """Polite urllib client: rate limited, retrying, capped, thread safe."""

    def __init__(self, max_requests: int, rps: float = 8.0, retries: int = 4) -> None:
        self.max_requests = max_requests
        self.interval = 1.0 / rps
        self.retries = retries
        self.requests = 0
        self._lock = threading.Lock()
        self._next = 0.0

    def _reserve(self) -> None:
        with self._lock:
            if self.requests >= self.max_requests:
                raise BudgetExhausted(f"request cap {self.max_requests} reached")
            self.requests += 1
            now = time.monotonic()
            wait = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.interval
        if wait:
            time.sleep(wait)

    def get_json(self, path_or_url: str) -> tuple[int, dict[str, Any]]:
        url = path_or_url if path_or_url.startswith("http") else f"{API_BASE}/{path_or_url}"
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
        )
        for attempt in range(self.retries + 1):
            self._reserve()
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.status, json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code != 429 and exc.code < 500:
                    return exc.code, {}
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
                pass
            if attempt == self.retries:
                break
            time.sleep(min(30.0, 2.0 ** (attempt + 1)))
        return 0, {}


# --------------------------------------------------------------------------- cache


def cache_path(root: Path, orcid: str, endpoint: str) -> Path:
    return root / orcid / f"{endpoint}.json"


def cache_fresh(path: Path, refresh_days: float, now: float | None = None) -> bool:
    if not path.exists():
        return False
    age = (now if now is not None else time.time()) - path.stat().st_mtime
    return age < refresh_days * 86400


def write_cache(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def read_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def fetch_endpoint(
    client: OrcidClient, root: Path, orcid: str, endpoint: str, refresh_days: float
) -> int | None:
    """Fetch one endpoint into the cache. Returns the status, or None when cached."""
    path = cache_path(root, orcid, endpoint)
    if cache_fresh(path, refresh_days):
        return None
    code, payload = client.get_json(f"{orcid}/{endpoint}")
    if code == 0:
        return 0  # transient failure: leave uncached so a rerun retries
    if code != 200:
        payload = {"_status": code}
    elif endpoint == "person":
        payload = strip_sensitive(payload)
    write_cache(path, payload)
    return code


def fetch_expert(client: OrcidClient, root: Path, orcid: str, refresh_days: float) -> list[int]:
    """Fetch person, employments and works for one ORCID; returns statuses fetched."""
    codes: list[int] = []
    for endpoint in ("person", "employments", "works"):
        code = fetch_endpoint(client, root, orcid, endpoint, refresh_days)
        if code is not None:
            codes.append(code)
        if code in (404, 409, 410, 401, 403):
            break  # locked or deactivated record: skip the other endpoints
    return codes


def parse_ror_search(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    out = []
    for item in payload.get("expanded-result") or []:
        orcid = normalize_orcid(item.get("orcid-id"))
        if not orcid:
            continue
        insts = item.get("institution-name") or []
        out.append(
            {
                "orcid": orcid,
                "given_names": str(item.get("given-names") or ""),
                "family_names": str(item.get("family-names") or ""),
                "institution": "; ".join(str(x) for x in insts[:3]),
            }
        )
    return out


def ror_search_url(ror: str, rows: int = 200) -> str:
    q = urllib.parse.quote(f'ror-org-id:"https://ror.org/{ror}"', safe="")
    return f"{API_BASE}/expanded-search/?q={q}&start=0&rows={rows}"


def strip_search_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Drop the ``email`` field from every expanded-search result before caching."""
    out = dict(payload)
    out["expanded-result"] = [
        {k: v for k, v in item.items() if k != "email"}
        for item in payload.get("expanded-result") or []
    ]
    return out
