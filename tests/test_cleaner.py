import datetime as dt

from report_automator import load_config
from report_automator.cleaner import CHECK, FIXED, REMOVED, clean
from report_automator.loader import load_file

from .conftest import HEADER, d


def run(paths, config):
    return clean([load_file(p, config) for p in paths], config)


def messages(result, severity=None):
    return [i.message for i in result.issues if severity is None or i.severity == severity]


def test_total_rows_removed_but_product_named_total_is_kept(write_xlsx, config):
    path = write_xlsx([
        HEADER,
        [d(1), "B1", "Total Wash Detergent", 1, 110, 110, "Cash"],
        [None, None, "Day Total", None, None, 110, None],
        ["Grand Total", None, None, None, None, 110, None],
        [d(2), "B2", "Sugar 1kg", 1, 48, 48, "UPI"],
        [None, None, "Sub-Total:", None, None, 48, None],
    ])
    r = run([path], config)
    assert list(r.data["product"]) == ["Total Wash Detergent", "Sugar 1kg"]
    assert sum("Total/subtotal" in m for m in messages(r, REMOVED)) == 3


def test_blank_rows_are_skipped_and_reported_once(write_xlsx, config):
    path = write_xlsx([HEADER, [d(1), "B1", "Sugar", 1, 48, 48, "Cash"], [], [], [d(2), "B2", "Sugar", 1, 48, 48, "Cash"]])
    r = run([path], config)
    assert r.rows_read == 2 and r.rows_kept == 2
    assert "2 empty row(s) skipped" in messages(r, REMOVED)


def test_bad_and_missing_dates_are_removed_with_reason(write_xlsx, config):
    path = write_xlsx([HEADER, ["31/06/2026", "B1", "Sugar", 1, 48, 48, "Cash"],
                       [None, "B2", "Sugar", 1, 48, 48, "Cash"], [d(3), "B3", "Sugar", 1, 48, 48, "Cash"]])
    r = run([path], config)
    assert r.rows_kept == 1
    assert {"Date could not be understood", "Missing date"} <= set(messages(r, REMOVED))
    bad = next(i for i in r.issues if i.message == "Date could not be understood")
    assert bad.row == 2 and bad.original_value == "31/06/2026"


def test_missing_amount_is_recovered_from_qty_and_rate(write_xlsx, config):
    path = write_xlsx([HEADER, [d(1), "B1", "Milk", 3, 28, None, "Cash"]])
    r = run([path], config)
    assert r.data.loc[0, "amount"] == 84
    assert any(m.startswith("Amount was missing") for m in messages(r, FIXED))


def test_unrecoverable_amount_removes_row(write_xlsx, config):
    path = write_xlsx([HEADER, [d(1), "B1", "Milk", None, None, "N/A", "Cash"]])
    r = run([path], config)
    assert r.rows_kept == 0 and "Amount could not be understood" in messages(r, REMOVED)


def test_missing_quantity_is_recovered_from_amount_and_rate(write_xlsx, config):
    path = write_xlsx([HEADER, [d(1), "B1", "Milk", None, 28, 56, "Cash"]])
    r = run([path], config)
    assert r.data.loc[0, "quantity"] == 2
    assert any("calculated as amount ÷ rate = 2" in m for m in messages(r, FIXED))


def test_amount_mismatch_is_flagged_not_changed(write_xlsx, config):
    path = write_xlsx([HEADER, [d(1), "B1", "Ghee", 1, 330, 300, "Cash"]])
    r = run([path], config)
    assert r.data.loc[0, "amount"] == 300
    assert any("does not match" in m for m in messages(r, CHECK))


def test_mismatch_within_tolerance_is_not_flagged(write_xlsx, config):
    path = write_xlsx([HEADER, [d(1), "B1", "Ghee", 3, 33.33, 100, "Cash"]])
    assert messages(run([path], config), CHECK) == []


def test_negative_amount_is_kept_as_return(write_xlsx, config):
    path = write_xlsx([HEADER, [d(1), "B1", "Milk", -1, 28, -28, "Cash"]])
    r = run([path], config)
    assert r.data.loc[0, "amount"] == -28
    assert any("return" in m for m in messages(r, CHECK))


def test_exact_duplicates_with_invoice_numbers_are_removed(write_xlsx, config):
    row = [d(1), "B1", "Milk", 1, 28, 28, "Cash"]
    r = run([write_xlsx([HEADER, row, row, [d(1), "B1", "Curd", 1, 35, 35, "Cash"]])], config)
    assert r.rows_kept == 2
    assert "Exact duplicate of row 2" in messages(r, REMOVED)


def test_duplicates_across_files_are_removed(write_xlsx, write_csv, config):
    jul = write_xlsx([HEADER, [d(31), "B9", "Milk", 1, 28, 28, "Cash"]], name="jul.xlsx")
    aug = write_csv([HEADER, ["31/07/2026", "B9", "Milk", "1", "₹28.00", "28", "Cash"],
                     ["01/08/2026", "B10", "Milk", "1", "28", "28", "Cash"]], name="aug.csv")
    r = run([jul, aug], config)
    assert r.rows_kept == 2
    assert "Exact duplicate of row 2 of jul.xlsx" in messages(r, REMOVED)


def test_without_invoice_numbers_duplicates_are_only_flagged(write_xlsx, config):
    header = ["Date", "Item", "Amount"]
    r = run([write_xlsx([header, [d(1), "Milk", 28], [d(1), "Milk", 28]])], config)
    assert r.rows_kept == 2  # could be two customers buying milk
    assert any("may be a genuine repeat sale" in m for m in messages(r, CHECK))


def test_drop_duplicates_can_be_turned_off(write_xlsx):
    cfg = load_config({"drop_duplicates": False})
    row = [d(1), "B1", "Milk", 1, 28, 28, "Cash"]
    r = run([write_xlsx([HEADER, row, row])], cfg)
    assert r.rows_kept == 2


def test_product_spellings_are_merged_to_most_common(write_xlsx, config):
    path = write_xlsx([
        HEADER,
        [d(1), "B1", "Toor Dal 1kg", 1, 165, 165, "Cash"],
        [d(1), "B2", "Toor Dal 1kg", 1, 165, 165, "Cash"],
        [d(2), "B3", "toor dal 1 KG", 1, 165, 165, "Cash"],
        [d(2), "B4", "Toor  Dal (1kg)", 1, 165, 165, "Cash"],
    ])
    r = run([path], config)
    assert set(r.data["product"]) == {"Toor Dal 1kg"}
    assert any("'toor dal 1 KG' → 'Toor Dal 1kg' (1 row(s))" in m for m in messages(r, FIXED))


def test_product_aliases_fix_typos(write_xlsx):
    cfg = load_config({"product_aliases": {"Paneer 200g": ["Panner 200g"]}})
    r = run([write_xlsx([HEADER, [d(1), "B1", "Panner 200g", 1, 90, 90, "Cash"]])], cfg)
    assert r.data.loc[0, "product"] == "Paneer 200g"


def test_payment_modes_standardised(write_xlsx, config):
    path = write_xlsx([HEADER] + [[d(1), f"B{i}", "Milk", 1, 28, 28, m]
                                  for i, m in enumerate(["gpay", "PhonePe", "cash", "UPI", "Cheque"])])
    r = run([path], config)
    assert list(r.data["payment_mode"]) == ["UPI", "UPI", "Cash", "UPI", "Cheque"]


def test_numeric_invoice_ids_lose_trailing_zero(write_xlsx, config):
    r = run([write_xlsx([HEADER, [d(1), 1023.0, "Milk", 1, 28, 28, "Cash"]])], config)
    assert r.data.loc[0, "invoice_id"] == "1023"


def test_output_is_sorted_by_date(write_xlsx, config):
    r = run([write_xlsx([HEADER, [d(5), "B2", "Milk", 1, 28, 28, "Cash"], [d(1), "B1", "Milk", 1, 28, 28, "Cash"]])],
            config)
    assert list(r.data["date"].dt.date) == [dt.date(2026, 7, 1), dt.date(2026, 7, 5)]


def test_issues_frame_orders_removed_then_check_then_fixed(write_xlsx, config):
    path = write_xlsx([HEADER, [d(1), "B1", "milk", 1, 28, None, "Cash"], ["bad", "B2", "Milk", 1, 28, 28, "Cash"],
                       [d(1), "B3", "Milk", 1, 28, -28, "Cash"], [d(2), "B4", "Milk", 1, 28, 28, "Cash"]])
    frame = run([path], config).issues_frame()
    order = list(dict.fromkeys(frame["severity"]))
    assert order == [REMOVED, CHECK, FIXED]
    assert str(frame["row"].dtype) == "Int64"
