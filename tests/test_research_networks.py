"""Research networks registry and public JSON (NET-1). Synthetic mutations of the real registry."""

from __future__ import annotations

import copy
import json
import sys
from datetime import date
from pathlib import Path

import pytest

from atlas import networks

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
REGISTRY = REPO / "config" / "research_networks.yml"
COMMITTED = REPO / "site" / "data" / "research_networks.json"
PUBLIC_NETWORK_KEYS = [
    "id",
    "name",
    "url",
    "steward",
    "steward_source",
    "description",
    "description_source",
    "focus_areas",
    "related_links",
    "host_institution_ids",
    "member_institution_ids",
    "listed_contributor_count",
    "roster_as_of",
    "atlas_contributors",
    "logo",
    "disclosure",
]
PRIVATE_VALUES = (
    "name_variants",
    "url_status",
    "source_url",
    "treatment",
    "terms",
    "permission",
    "to_confirm",
    "Copyright",
    "Land to Sea Microplastic Consortium",
)


@pytest.fixture(scope="module")
def build_script():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import build_research_networks_json

        return build_research_networks_json
    finally:
        sys.path.remove(str(SCRIPTS))


def _registry() -> dict:
    return networks.load_registry(REGISTRY)


def _net(data: dict) -> dict:
    return data["networks"][0]


def _mutated(mutate) -> list[str]:
    data = copy.deepcopy(_registry())
    mutate(data)
    return networks.validate_registry(data)


def _set(key, value):
    def mutate(data):
        _net(data)[key] = value

    return mutate


def _set_logo(key, value):
    def mutate(data):
        _net(data)["logo"][key] = value

    return mutate


def _add_key(key, value):
    def mutate(data):
        _net(data)[key] = value

    return mutate


def _duplicate(data):
    data["networks"].append(copy.deepcopy(_net(data)))


def _overlap(data):
    member = _net(data)["member_institution_ids"]
    member.append(_net(data)["host_institution_ids"][0])


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (_set("url", "http://marinescience.ucdavis.edu/x"), "url must be an https URL"),
        (_set("steward_source", "http://x.example/"), "steward_source must be an https URL"),
        (_set("related_links", [{"label": "x", "url": "http://x.example/"}]), "https URL"),
        (
            _set_logo("source_url", "http://x.example/a.png"),
            "logo.source_url must be an https URL",
        ),
        (_set_logo("path", "assets/networks/missing.png"), "logo file not found"),
        (_set_logo("path", "../config/x.png"), "must not contain '..'"),
        (_set_logo("path", "/abs/x.png"), "must be relative"),
        (_set("listed_contributor_count", "14"), "listed_contributor_count must be"),
        (_set("listed_contributor_count", 3), "below the number of atlas_contributors"),
        (_set("host_institution_ids", "I84218800"), "host_institution_ids must be a list"),
        (_set("member_institution_ids", ["bad id"]), "member_institution_ids must be a list"),
        (_overlap, "both host and member"),
        (_add_key("discolsure", "typo"), "unknown key discolsure"),
        (_set("atlas_contributors", [{"author_id": "5081541713", "name": "X"}]), "author_id"),
        (_set("roster_as_of", date(2026, 10, 29)), "roster_as_of must be a YYYY-MM-DD string"),
        (_set("disclosure", "   "), "disclosure must be a non-empty string"),
        (_set("focus_areas", []), "focus_areas must be a non-empty list"),
        (lambda d: d.update(schema_version=2), "schema_version must be 1"),
        (lambda d: _net(d).pop("disclosure"), "missing key disclosure"),
        (_duplicate, "duplicate id NET-1"),
        (_set("id", "NET-x"), "id must match NET-<number>"),
    ],
)
def test_validation_rejects_bad_registry(mutate, expected):
    errors = _mutated(mutate)
    assert errors, "expected a validation error"
    assert any(expected in error for error in errors), errors


def test_real_registry_is_valid():
    assert networks.validate_registry(_registry()) == []


def test_public_payload_has_exact_shape_and_omits_private_fields():
    payload = networks.public_payload(_registry())
    assert list(payload) == ["schema_version", "source", "networks"]
    assert payload["schema_version"] == "net1.v1"
    assert payload["source"] == "config/research_networks.yml"
    assert payload["networks"], "expected at least one network"
    for network in payload["networks"]:
        assert list(network) == PUBLIC_NETWORK_KEYS
        assert list(network["logo"]) == ["path", "alt"]
        assert all(list(item) == ["author_id", "name"] for item in network["atlas_contributors"])
        assert all(list(item) == ["label", "url"] for item in network["related_links"])
    text = json.dumps(payload, ensure_ascii=False)
    for value in PRIVATE_VALUES:
        assert value not in text, value


def test_public_payload_raises_on_invalid_registry():
    data = _registry()
    _net(data)["url"] = "http://x.example/"
    with pytest.raises(ValueError, match="invalid research networks registry"):
        networks.public_payload(data)


def test_load_registry_rejects_non_mapping(tmp_path):
    path = tmp_path / "research_networks.yml"
    path.write_text("- just a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="top level must be a mapping"):
        networks.load_registry(path)


def test_committed_json_matches_fresh_build(build_script):
    fresh = build_script.render(build_script.build_payload())
    assert COMMITTED.read_bytes() == fresh.encode("utf-8"), (
        "site/data/research_networks.json is stale; run scripts/build_research_networks_json.py"
    )


def test_committed_json_shape_and_line_endings():
    raw = COMMITTED.read_bytes()
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    assert json.loads(raw.decode("utf-8")) == networks.public_payload(_registry())


def test_check_flag_detects_stale_output(build_script, tmp_path, capsys):
    stale = tmp_path / "research_networks.json"
    stale.write_text("{}\n", encoding="utf-8")
    assert build_script.main(["--check", "--output", str(stale)]) == 1
    assert "stale" in capsys.readouterr().err
    assert build_script.main(["--output", str(stale)]) == 0
    assert build_script.main(["--check", "--output", str(stale)]) == 0
    assert build_script.main(["--check", "--output", str(tmp_path / "missing.json")]) == 1
