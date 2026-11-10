"""Add-on A2 Need Ledger quote regression against owner-local source PDFs (EM-1, A2 sections 9, 12).

The PDFs are never committed. Callers inject the page-text extractor, so tests run offline with
fake pages. The report carries statuses, page numbers and fuzzy ratios only, never quote or page
text.
"""

from __future__ import annotations

import csv
import difflib
import io
import json
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from atlas.evidence.need_ledger import SOURCE_DOCS

PageExtractor = Callable[[Path, frozenset[int] | None], dict[int, str]]

MATCH_ON_PAGE = "match_on_page"
MATCH_NEARBY = "match_nearby"
MATCH_ELSEWHERE = "match_elsewhere"
NOT_FOUND = "not_found"
MISSING_PDF = "missing_pdf"
NOT_PDF = "not_pdf"
BAD_PAGE = "bad_page"
STATUSES: tuple[str, ...] = (
    MATCH_ON_PAGE,
    MATCH_NEARBY,
    MATCH_ELSEWHERE,
    NOT_FOUND,
    MISSING_PDF,
    NOT_PDF,
    BAD_PAGE,
)
FAILING_STATUSES: frozenset[str] = frozenset({NOT_FOUND, MATCH_ELSEWHERE, BAD_PAGE})
WEB_SOURCE_DOCS: frozenset[str] = frozenset({"DTSC_LIST", "DTSC_RES"})
PDF_SOURCE_DOCS: tuple[str, ...] = tuple(doc for doc in SOURCE_DOCS if doc not in WEB_SOURCE_DOCS)
NEARBY_RADIUS = 2
REQUIRED_COLUMNS: tuple[str, ...] = ("need_id", "source_doc", "pdf_page", "quote")

_HYPHEN_BREAK = re.compile(r"-[ \t]*\r?\n\s*")
_WHITESPACE = re.compile(r"\s+")
_TEXT_MAP = str.maketrans(
    {
        "‘": "'",  # left single quotation mark
        "’": "'",  # right single quotation mark
        "‚": "'",
        "‛": "'",
        "“": '"',  # left double quotation mark
        "”": '"',  # right double quotation mark
        "„": '"',
        "‟": '"',
        "‐": "-",  # hyphen
        "‑": "-",  # non-breaking hyphen
        "‒": "-",  # figure dash
        "–": "-",  # en dash
        "—": "-",  # em dash
        "―": "-",  # horizontal bar
        "−": "-",  # minus sign
        "­": None,  # soft hyphen
    }
)
_RANGE = re.compile(r"^(\d+)(?:\s*-\s*(\d+))?$")


def normalize_text(text: str) -> str:
    """Return the comparison form: NFKC, joined hyphen breaks, ASCII quotes, lowercase."""
    text = unicodedata.normalize("NFKC", text)
    text = _HYPHEN_BREAK.sub("", text)
    text = text.translate(_TEXT_MAP)
    return _WHITESPACE.sub(" ", text.lower()).strip()


def parse_pdf_pages(value: str) -> tuple[int, ...]:
    """Parse a ledger pdf_page cell such as ``28``, ``151-152`` or ``6; 10`` into 1-based pages.

    Raises ValueError when the cell has no usable page, a page is below 1, or a range is reversed.
    """
    if not isinstance(value, str):
        raise ValueError("pdf_page must be text")
    pages: set[int] = set()
    for part in value.translate(_TEXT_MAP).split(";"):
        token = part.strip()
        if not token:
            continue
        match = _RANGE.fullmatch(token)
        if match is None:
            raise ValueError(f"unparseable page token: {token!r}")
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) is not None else start
        if start < 1 or end < start:
            raise ValueError(f"invalid page or range: {token!r}")
        pages.update(range(start, end + 1))
    if not pages:
        raise ValueError("no page numbers in pdf_page")
    return tuple(sorted(pages))


def best_fuzzy_ratio(quote: str, text: str) -> float:
    """Best difflib ratio of ``quote`` against any window of ``text`` of the quote's length.

    Windows slide in steps of about a tenth of the quote length, so this is approximate.
    """
    if not quote or not text:
        return 0.0
    qlen = len(quote)
    matcher = difflib.SequenceMatcher(None, quote, autojunk=False)
    if len(text) <= qlen:
        matcher.set_seq2(text)
        return round(matcher.ratio(), 3)
    last_start = len(text) - qlen
    starts = list(range(0, last_start + 1, max(1, qlen // 10)))
    if starts[-1] != last_start:
        starts.append(last_start)
    best = 0.0
    for start in starts:
        matcher.set_seq2(text[start : start + qlen])
        if matcher.real_quick_ratio() <= best or matcher.quick_ratio() <= best:
            continue
        best = max(best, matcher.ratio())
        if best >= 1.0:
            break
    return round(best, 3)


def pdfminer_page_extractor(path: Path, pages: frozenset[int] | None) -> dict[int, str]:
    """Return raw text for the requested 1-based pages (None means all pages), using pdfminer.six.

    Pages past the end of the document are simply absent from the result.
    """
    from pdfminer.converter import TextConverter
    from pdfminer.layout import LAParams
    from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
    from pdfminer.pdfpage import PDFPage

    if pages is not None and not pages:
        return {}
    last = max(pages) if pages is not None else None
    buffer = io.StringIO()
    manager = PDFResourceManager()
    device = TextConverter(manager, buffer, laparams=LAParams())
    interpreter = PDFPageInterpreter(manager, device)
    out: dict[int, str] = {}
    try:
        with path.open("rb") as handle:
            for index, page in enumerate(PDFPage.get_pages(handle), start=1):
                if last is not None and index > last:
                    break
                if pages is not None and index not in pages:
                    continue
                buffer.seek(0)
                buffer.truncate()
                interpreter.process_page(page)
                out[index] = buffer.getvalue()
    finally:
        device.close()
    return out


class PageText:
    """Lazily extracts and caches normalized page text for one PDF."""

    def __init__(self, path: Path, extractor: PageExtractor) -> None:
        self._path = path
        self._extractor = extractor
        self._pages: dict[int, str] = {}
        self._requested: set[int] = set()
        self._complete = False

    def get(self, wanted: Iterable[int]) -> dict[int, str]:
        """Return normalized text for the wanted pages that exist in the PDF."""
        wanted_set = set(wanted)
        need = wanted_set - self._requested
        if need and not self._complete:
            self._requested |= need
            raw = self._extractor(self._path, frozenset(need))
            self._pages.update({page: normalize_text(text) for page, text in raw.items()})
        return {page: self._pages[page] for page in wanted_set if page in self._pages}

    def all_pages(self) -> dict[int, str]:
        """Return normalized text for every page, extracting the whole document once."""
        if not self._complete:
            raw = self._extractor(self._path, None)
            self._pages.update({page: normalize_text(text) for page, text in raw.items()})
            self._complete = True
        return dict(self._pages)


MAX_SEGMENT_GAP = 400  # characters allowed between consecutive quote segments
MIN_SPLIT_CHARS = 20  # each half of a once-interrupted quote must be at least this long


def _segments_in_order(segments: Sequence[str], text: str) -> bool:
    """True when every segment occurs in order, each starting within the gap limit."""
    first, rest = segments[0], segments[1:]
    start = text.find(first)
    while start != -1:
        end = start + len(first)
        for segment in rest:
            nxt = text.find(segment, end)
            if nxt == -1 or nxt - end > MAX_SEGMENT_GAP:
                break
            end = nxt + len(segment)
        else:
            return True
        start = text.find(first, start + 1)
    return False


def _contains(quote: str, text: str) -> bool:
    """Match a normalized quote, honouring elisions and one layout interruption.

    An elided quote (``...``; NFKC also maps ``…`` to it) matches when its segments
    occur in order. An unelided quote may be interrupted once, for example by a
    running header, footer or photo caption at a page break, with each half at
    least ``MIN_SPLIT_CHARS`` long and the gap at most ``MAX_SEGMENT_GAP``.
    """
    if quote in text:
        return True
    segments = [part.strip(" ,;") for part in quote.split("...")]
    segments = [part for part in segments if part]
    if not segments:
        return False
    if len(segments) > 1 and _segments_in_order(segments, text):
        return True
    for position, segment in enumerate(segments):
        words = segment.split(" ")
        for index in range(1, len(words)):
            head, tail = " ".join(words[:index]), " ".join(words[index:])
            if len(head) >= MIN_SPLIT_CHARS and len(tail) >= MIN_SPLIT_CHARS:
                candidate = [*segments[:position], head, tail, *segments[position + 1 :]]
                if _segments_in_order(candidate, text):
                    return True
    return False


def _find_quote(quote: str, page_texts: Mapping[int, str]) -> tuple[int, ...] | None:
    """Return the page(s) containing the quote: a single page, else an adjacent pair."""
    ordered = sorted(page_texts)
    for page in ordered:
        if _contains(quote, page_texts[page]):
            return (page,)
    for first, second in zip(ordered, ordered[1:]):
        if second == first + 1 and _contains(quote, f"{page_texts[first]} {page_texts[second]}"):
            return (first, second)
    return None


def check_quote(
    quote: str, doc: PageText, listed: tuple[int, ...]
) -> tuple[str, tuple[int, ...], float | None]:
    """Classify one quote against its listed pages. Returns (status, matched pages, ratio)."""
    needle = normalize_text(quote)
    if not needle:
        return NOT_FOUND, (), 0.0
    listed_text = doc.get(listed)
    if not listed_text:
        return BAD_PAGE, (), None
    hit = _find_quote(needle, listed_text)
    if hit is not None:
        return MATCH_ON_PAGE, hit, None
    window = {page + delta for page in listed for delta in range(-NEARBY_RADIUS, NEARBY_RADIUS + 1)}
    nearby_text = doc.get(window)
    nearby_text.update(listed_text)
    hit = _find_quote(needle, nearby_text)
    if hit is not None:
        return MATCH_NEARBY, hit, None
    hit = _find_quote(needle, doc.all_pages())
    if hit is not None:
        return MATCH_ELSEWHERE, hit, None
    combined = " ".join(listed_text[page] for page in sorted(listed_text))
    return NOT_FOUND, (), best_fuzzy_ratio(needle, combined)


def check_rows(
    rows: Sequence[Mapping[str, str]],
    pdf_paths: Mapping[str, Path],
    extractor: PageExtractor = pdfminer_page_extractor,
) -> list[dict[str, Any]]:
    """Check every ledger row and return per-row results without quote or page text."""
    documents: dict[Path, PageText] = {}
    results: list[dict[str, Any]] = []
    for row in rows:
        need_id = row["need_id"]
        source_doc = row["source_doc"]
        base: dict[str, Any] = {"need_id": need_id, "source_doc": source_doc}
        if source_doc in WEB_SOURCE_DOCS:
            results.append(
                {**base, "status": NOT_PDF, "pages": [], "matched_pages": [], "ratio": None}
            )
            continue
        try:
            listed = parse_pdf_pages(row["pdf_page"])
        except ValueError:
            results.append(
                {**base, "status": BAD_PAGE, "pages": [], "matched_pages": [], "ratio": None}
            )
            continue
        path = pdf_paths.get(source_doc)
        if path is None or not path.is_file():
            results.append(
                {
                    **base,
                    "status": MISSING_PDF,
                    "pages": list(listed),
                    "matched_pages": [],
                    "ratio": None,
                }
            )
            continue
        doc = documents.setdefault(path, PageText(path, extractor))
        status, matched, ratio = check_quote(row["quote"], doc, listed)
        results.append(
            {
                **base,
                "status": status,
                "pages": list(listed),
                "matched_pages": list(matched),
                "ratio": ratio,
            }
        )
    return results


def summarize(results: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in STATUSES}
    for result in results:
        counts[result["status"]] += 1
    return counts


def build_report(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the JSON-serialisable report. It holds no quote text and no page text."""
    return {
        "schema": "need_ledger_quote_check/1",
        "counts": summarize(results),
        "rows": [dict(result) for result in results],
    }


def write_report(report: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def format_summary(counts: Mapping[str, int]) -> str:
    lines = [f"{'status':<16}{'count':>6}"]
    lines += [f"{status:<16}{counts.get(status, 0):>6}" for status in STATUSES]
    lines.append(f"{'total':<16}{sum(counts.values()):>6}")
    return "\n".join(lines)


def load_ledger_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"ledger CSV is missing columns: {', '.join(missing)}")
        return [dict(row) for row in reader]


def load_source_map(path: Path) -> dict[str, str]:
    """Load a JSON or YAML mapping of source_doc to PDF file name."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        import yaml

        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("source map must be a mapping of source_doc to file name")
    mapping: dict[str, str] = {}
    for key, value in data.items():
        if key not in PDF_SOURCE_DOCS:
            raise ValueError(f"source map key is not a PDF source_doc: {key!r}")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"source map value for {key} must be a file name")
        mapping[key] = value.strip()
    return mapping


def build_pdf_paths(mapping: Mapping[str, str], pdf_dir: Path) -> dict[str, Path]:
    """Resolve mapped file names inside pdf_dir. Names that escape the directory are rejected."""
    root = pdf_dir.resolve()
    paths: dict[str, Path] = {}
    for source_doc, name in mapping.items():
        candidate = (root / name).resolve()
        if candidate.parent != root:
            raise ValueError(
                f"file name for {source_doc} must sit directly inside the PDF directory"
            )
        paths[source_doc] = candidate
    return paths


def map_template_json() -> str:
    template = {doc: "REPLACE_WITH_FILE_NAME.pdf" for doc in PDF_SOURCE_DOCS}
    return json.dumps(template, indent=2) + "\n"
