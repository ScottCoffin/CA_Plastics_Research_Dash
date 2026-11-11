"""Owner review sheets used by the small Streamlit review apps (atlas.csv_review)."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas.csv_review import load_sheet, set_fields


def _write(path: Path, text: str) -> Path:
    path.write_bytes(text.encode("utf-8"))
    return path


def test_round_trip_keeps_crlf_header_and_other_rows(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "s.csv",
        '﻿id,name,owner_type,notes\r\nA1,One,,\r\nA2,"Two, Inc",company,x\r\n',
    )
    sheet = load_sheet(path, key="id", required=("owner_type",))
    set_fields(sheet, "A1", {"owner_type": "UC", "notes": "ok"})
    assert path.read_bytes().decode("utf-8") == (
        'id,name,owner_type,notes\r\nA1,One,UC,ok\r\nA2,"Two, Inc",company,x\r\n'
    )


def test_missing_column_duplicate_key_and_unknown_field(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing column"):
        load_sheet(_write(tmp_path / "a.csv", "id\nA1\n"), key="id", required=("x",))
    with pytest.raises(ValueError, match="more than once"):
        load_sheet(_write(tmp_path / "b.csv", "id\nA1\nA1\n"), key="id")
    sheet = load_sheet(_write(tmp_path / "c.csv", "id,v\nA1,\n"), key="id")
    with pytest.raises(KeyError):
        set_fields(sheet, "A1", {"nope": "1"})
    with pytest.raises(KeyError):
        set_fields(sheet, "Z9", {"v": "1"})
