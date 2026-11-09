"""Check the offline AT-1 query transcription and human-audit gate."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    spec = (ROOT / "docs/add_on_spec.md").read_bytes()
    appendix_start = spec.rfind(b"Appendix A ")
    expression_start = spec.find(b"\n", appendix_start) + 1
    syntax_start = spec.find(b"Syntax ", expression_start)
    expression_end = spec.rfind(b"\n", expression_start, syntax_start)
    expected = spec[expression_start:expression_end].rstrip(b"\r\n")
    observed = (ROOT / "config/query_v2.txt").read_bytes().rstrip(b"\r\n")
    if observed != expected:
        raise SystemExit("config/query_v2.txt differs from the Appendix A query bytes")

    audit = (ROOT / "docs/QUERY_AUDIT.md").read_text(encoding="utf-8")
    if "0/500" not in audit or 'query_mode="audit"' not in audit:
        raise SystemExit("audit must report human-label status and explicit audit mode")
    print("AT-1 offline transcription and human-audit gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
