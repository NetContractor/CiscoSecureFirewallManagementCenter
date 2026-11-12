import pytest

from fmc_setup.client import SetupError
from fmc_setup.objects import resolve
from fmc_setup.workbook import SetupWorkbook, cell, data_rows, split_names


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("", None), ("   ", None), (" Zone_Inside ", "Zone_Inside"), (3.0, "3"), (26, "26"), (1.5, "1.5")],
)
def test_cell(value, expected):
    assert cell(value) == expected


def test_split_names_strips_and_skips_empty():
    assert split_names(" A, B ,,C ") == ["A", "B", "C"]


def test_data_rows_skips_rows_without_key(workbook):
    rows = list(data_rows(workbook.sheet("ACP"), 13, key_column=1))
    assert [row[3] for row in rows] == ["DC-DC", "CLIENTS-TO-DC", "CLIENTS-TO-WEB", "PING-PRINTERS"]


def test_missing_sheet_raises(workbook):
    with pytest.raises(SetupError, match="does not exist"):
        workbook.sheet("NoSuchSheet")


def test_missing_workbook_raises(tmp_path):
    with pytest.raises(SetupError, match="does not exist"):
        SetupWorkbook(tmp_path / "missing.xlsx").sheet("ACP")


def test_resolve_uses_lookups_in_order_and_deduplicates():
    first = {"A": {"type": "Host", "id": "1", "name": "A"}}
    second = {"A": {"type": "NetworkGroup", "id": "2", "name": "A"}, "B": {"type": "Network", "id": "3", "name": "B"}}
    objects, missing = resolve(["A", "B", "A", "C"], first, second)
    assert [o["id"] for o in objects] == ["1", "3"]
    assert missing == ["C"]
