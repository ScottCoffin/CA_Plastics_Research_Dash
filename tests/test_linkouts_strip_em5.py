import json
import sys
from pathlib import Path

import pytest

from atlas import linkouts

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
COMMITTED = REPO / "site" / "data" / "linkouts.json"
MANIFEST = REPO / "site" / "data" / "bundle" / "manifest.json"
PUBLIC_FIELDS = {
    "id",
    "name",
    "steward",
    "steward_source",
    "description",
    "relation",
    "root_url",
    "topics",
    "default",
    "description_source",
    "update_model",
    "terms_status",
    "terms",
    "url_status",
}


@pytest.fixture(scope="module")
def build_script():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import build_linkouts_json

        return build_linkouts_json
    finally:
        sys.path.remove(str(SCRIPTS))


def _registry() -> dict:
    return linkouts.load_registry(REPO / "config" / "linkouts.yml")


def test_parse_trigger_rules_topics_default_and_ignored():
    rules = [
        "topic=risk_assessment",
        "default",
        "weekly HTTP status check only",
        "topic=air",
        "topic=air",
        "topic=",
    ]
    assert linkouts.parse_trigger_rules(rules) == {
        "topics": ["air", "risk_assessment"],
        "default": True,
    }


def test_parse_trigger_rules_empty_and_ignored_only():
    assert linkouts.parse_trigger_rules([]) == {"topics": [], "default": False}
    assert linkouts.parse_trigger_rules(["weekly HTTP status check only"]) == {
        "topics": [],
        "default": False,
    }


def test_strip_entries_field_set_and_order():
    data = _registry()
    stripped = linkouts.strip_entries(data)
    assert [entry["id"] for entry in stripped] == [e["id"] for e in data["entries"]]
    for entry in stripped:
        assert set(entry) == PUBLIC_FIELDS
        assert set(entry["topics"]) <= {
            rule[len("topic=") :]
            for source in data["entries"]
            for rule in source["trigger_rules"]
            if rule.startswith("topic=")
        }
        assert isinstance(entry["default"], bool)
        assert entry["description_source"].startswith("https://")
        assert entry["terms"] is None or isinstance(entry["terms"], str)
        assert (entry["terms"] is not None) == (entry["terms_status"] == "recorded")


def test_strip_entries_rejects_invalid_registry():
    data = _registry()
    data["entries"] = [e for e in data["entries"] if e["id"] != "LO-5"]
    with pytest.raises(ValueError, match="missing id LO-5"):
        linkouts.strip_entries(data)


def test_committed_json_matches_fresh_build(build_script):
    fresh = build_script.render(build_script.build_payload())
    assert COMMITTED.read_bytes() == fresh.encode("utf-8"), (
        "site/data/linkouts.json is stale; run scripts/build_linkouts_json.py"
    )


def test_committed_json_shape_and_line_endings():
    raw = COMMITTED.read_bytes()
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    payload = json.loads(raw.decode("utf-8"))
    assert payload["schema_version"] == "em5.v1"
    assert payload["source"] == "config/linkouts.yml"
    assert [e["id"] for e in payload["entries"]] == [e["id"] for e in _registry()["entries"]]


def test_every_entry_has_topics_or_default():
    payload = json.loads(COMMITTED.read_text(encoding="utf-8"))
    for entry in payload["entries"]:
        assert entry["topics"] or entry["default"], entry["id"]


def test_no_minderoo_mention_in_entries_or_public_json():
    # The YAML header comment states the map is intentionally absent, so only the
    # registry entries (parsed, no comments) and the public JSON are checked.
    entries_text = json.dumps(_registry()["entries"], ensure_ascii=False)
    assert "minderoo" not in entries_text.lower()
    assert "minderoo" not in COMMITTED.read_text(encoding="utf-8").lower()


def test_rule_topics_exist_in_bundle_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    known = set(manifest["facet_label_counts"]["topic"])
    used = {
        tag
        for entry in _registry()["entries"]
        for tag in linkouts.parse_trigger_rules(entry["trigger_rules"])["topics"]
    }
    assert used, "expected at least one topic rule"
    assert used <= known, sorted(used - known)


def test_check_flag_detects_stale_output(build_script, tmp_path, capsys):
    stale = tmp_path / "linkouts.json"
    stale.write_text("{}\n", encoding="utf-8")
    assert build_script.main(["--check", "--output", str(stale)]) == 1
    assert "stale" in capsys.readouterr().err
    assert build_script.main(["--output", str(stale)]) == 0
    assert build_script.main(["--check", "--output", str(stale)]) == 0
    assert build_script.main(["--check", "--output", str(tmp_path / "missing.json")]) == 1
