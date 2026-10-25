import io

import pytest

from report_automator import InputFileError
from report_automator.loader import load_file

from .conftest import HEADER, d


def test_finds_header_below_title_rows(write_xlsx, config):
    path = write_xlsx([
        ["MY STORE"],
        ["Sales Register: July"],
        [],
        HEADER,
        [d(1), "B1", "Sugar 1kg", 1, 48, 48, "Cash"],
    ])
    lf = load_file(path, config)
    assert lf.header_row == 4
    assert lf.mapping["product"] == "Item Name"
    assert lf.rows.loc[0, "_source_row"] == 5  # matches the row number the owner sees in Excel


def test_reports_ignored_columns(write_xlsx, config):
    path = write_xlsx([HEADER + ["GST %"], [d(1), "B1", "Sugar", 1, 48, 48, "Cash", 5]])
    assert load_file(path, config).ignored_columns == ["GST %"]


def test_missing_required_column_message_lists_found_columns(write_xlsx, config):
    path = write_xlsx([["Date", "Item Name", "Qty"], [d(1), "Sugar", 1]])
    with pytest.raises(InputFileError, match="missing required column.*amount.*Columns found: Date, Item Name, Qty"):
        load_file(path, config)


def test_no_header_at_all(write_xlsx, config):
    path = write_xlsx([["foo", "bar"], [1, 2]])
    with pytest.raises(InputFileError, match="could not find the column headers"):
        load_file(path, config)


def test_custom_aliases_make_unknown_headers_work(write_xlsx):
    from report_automator import load_config

    path = write_xlsx([["Txn Dt", "SKU Name", "Bill Value"], [d(1), "Sugar", 48]])
    cfg = load_config({"column_aliases": {"date": ["Txn Dt"], "product": ["SKU Name"], "amount": ["Bill Value"]}})
    assert set(load_file(path, cfg).mapping) == {"date", "product", "amount"}


def test_old_xls_is_refused_with_instructions(tmp_path, config):
    p = tmp_path / "old.xls"
    p.write_bytes(b"whatever")
    with pytest.raises(InputFileError, match="Save As"):
        load_file(p, config)


def test_unsupported_extension(tmp_path, config):
    p = tmp_path / "sales.pdf"
    p.write_bytes(b"%PDF")
    with pytest.raises(InputFileError, match="unsupported file type"):
        load_file(p, config)


def test_empty_file(tmp_path, config):
    p = tmp_path / "empty.csv"
    p.write_text("")
    with pytest.raises(InputFileError, match="empty"):
        load_file(p, config)


def test_corrupt_excel(tmp_path, config):
    p = tmp_path / "broken.xlsx"
    p.write_bytes(b"this is not a zip file")
    with pytest.raises(InputFileError, match="could not open as an Excel workbook"):
        load_file(p, config)


def test_missing_file(tmp_path, config):
    with pytest.raises(InputFileError, match="not found"):
        load_file(tmp_path / "nope.csv", config)


def test_semicolon_csv_and_windows_encoding(write_csv, config):
    path = write_csv([["Date", "Item", "Amount"], ["01/07/2026", "Café Filter Coffee", "260"]],
                     encoding="cp1252", delimiter=";")
    lf = load_file(path, config)
    assert lf.rows.loc[0, "product"] == "Café Filter Coffee"


def test_uploaded_file_object_can_be_read_twice(config):
    buf = io.BytesIO(b"Date,Item,Amount\n01/07/2026,Sugar,48\n")
    buf.name = "upload.csv"
    first = load_file(buf, config)
    second = load_file(buf, config)  # web page re-runs read the same object again
    assert len(first.rows) == len(second.rows) == 1
    assert second.name == "upload.csv"


def test_uses_first_sheet_that_has_a_table(tmp_path, config):
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "Notes"
    wb.active.append(["Prepared by accounts"])
    data = wb.create_sheet("Data")
    data.append(["Date", "Item", "Amount"])
    data.append([d(2), "Sugar", 48])
    path = tmp_path / "multi.xlsx"
    wb.save(path)
    lf = load_file(path, config)
    assert lf.sheet == "Data" and len(lf.rows) == 1
