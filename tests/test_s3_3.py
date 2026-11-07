import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_experts_workflow_has_filter_drawer_and_virtualization_hooks() -> None:
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    for marker in (
        'id="institution-type-filter"',
        'id="institution-filter"',
        'id="ca-basis-filter"',
        "renderVirtualRows",
        'id="researcher-drawer"',
        "Report an error",
    ):
        assert marker in html
    assert 'style="transform:translateY(' in html


def test_every_fixture_author_has_detail_payload() -> None:
    data = ROOT / "site" / "data"
    index = json.loads((data / "index.json").read_text(encoding="utf-8"))
    for author in index["authors"]:
        detail = json.loads(
            (data / "authors" / f"{author['author_id']}.json").read_text(encoding="utf-8")
        )
        assert detail["author"]["author_id"] == author["author_id"]
        assert isinstance(detail["works"], list)
