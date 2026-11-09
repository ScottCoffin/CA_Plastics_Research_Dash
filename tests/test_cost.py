import json
from pathlib import Path

import pytest

from atlas.util.cost import ApiCostLogger, OpenAlexUsageMetadataError, redact_url


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_redact_url_removes_credentials() -> None:
    redacted = redact_url(
        "https://api.openalex.org/works?filter=type:article&api_key=secret&token=also-secret"
    )
    assert "secret" not in redacted
    assert "filter=type%3Aarticle" in redacted
    assert redacted.count("%5BREDACTED%5D") == 2


def test_logger_writes_request_and_run_totals(tmp_path: Path) -> None:
    path = tmp_path / "api_usage.jsonl"
    logger = ApiCostLogger("test-run", path)
    logger.record_openalex_response(
        method="GET",
        url="https://api.openalex.org/works?api_key=secret",
        status_code=200,
        headers={"x-ratelimit-credits-used": "1"},
        body={"meta": {"cost_usd": 0.0001}},
    )
    logger.record(
        source="ror",
        method="get",
        url="https://api.ror.org/v2/organizations/01an7q238",
        status_code=200,
    )
    summary = logger.close()
    assert logger.close() == summary

    records = read_jsonl(path)
    assert len(records) == 3
    assert records[0]["credits"] == 1.0
    assert records[0]["cost_usd"] == 0.0001
    assert "secret" not in str(records[0])
    assert records[1]["credits"] == 0.0
    assert records[2] == summary
    assert summary["request_count"] == 2
    assert summary["credits_total"] == 1.0
    assert summary["cost_usd_total"] == 0.0001


def test_logger_rejects_records_after_summary(tmp_path: Path) -> None:
    logger = ApiCostLogger("test-run", tmp_path / "usage.jsonl")
    logger.close()
    with pytest.raises(RuntimeError, match="after the run summary"):
        logger.record(
            source="ror",
            method="GET",
            url="https://api.ror.org/v2/organizations",
            status_code=200,
        )


def test_success_response_missing_credit_is_marked_unknown_and_fails_closed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing_credit.jsonl"
    with pytest.raises(OpenAlexUsageMetadataError, match="credit usage"):
        with ApiCostLogger("missing-credit", path) as logger:
            logger.record_openalex_response(
                method="GET",
                url="https://api.openalex.org/works",
                status_code=200,
                headers={},
                body={"meta": {"cost_usd": 0}},
            )
    rows = read_jsonl(path)
    assert rows[0]["credits"] == 0
    assert rows[0]["credits_known"] is False
    assert rows[0]["cost_known"] is True


def test_missing_cost_is_explicit_and_credits_remain_available(tmp_path: Path) -> None:
    path = tmp_path / "missing_cost.jsonl"
    with ApiCostLogger("missing-cost", path) as logger:
        logger.record_openalex_response(
            method="GET",
            url="https://api.openalex.org/works",
            status_code=200,
            headers={"X-RateLimit-Credits-Used": "1"},
            body={"meta": {}},
        )
    row = read_jsonl(path)[0]
    assert row["credits"] == 1
    assert row["credits_known"] is True
    assert row["cost_known"] is False
