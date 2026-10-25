import pytest

from report_automator import NoValidRowsError
from report_automator.cleaner import clean
from report_automator.loader import load_file
from report_automator.summarize import summarise

from .conftest import HEADER, d

# 2026-07-04 is a Saturday, 2026-07-06 a Monday.
ROWS = [
    HEADER,
    [d(4), "B1", "Rice 5kg", 1, 340, 340, "UPI"],
    [d(4), "B1", "Milk", 2, 28, 56, "UPI"],
    [d(4), "B2", "Rice 5kg", 1, 340, 340, "Cash"],
    [d(6), "B3", "Milk", 1, 28, 28, "Cash"],
    [d(6), "B4", "Sugar", 1, 48, 48, "UPI"],
    [d(6), "B5", "Milk", -1, 28, -28, "Cash"],
]


@pytest.fixture
def summary(write_xlsx, config):
    result = clean([load_file(write_xlsx(ROWS), config)], config)
    return summarise(result, config)


def test_headline_numbers(summary):
    assert summary.gross_sales == 812
    assert summary.returns == 28
    assert summary.net_revenue == 784
    assert summary.bill_count == 5
    assert summary.avg_bill_value == pytest.approx(784 / 5)
    assert summary.units_sold == 5  # 1 + 2 + 1 + 1 + 1 - 1


def test_best_day_and_period(summary):
    assert summary.best_day[0].day == 4 and summary.best_day[1] == 736
    assert summary.period_label == "04 Jul 2026 to 06 Jul 2026"


def test_by_product_sorted_with_share(summary):
    top = summary.by_product.iloc[0]
    assert top["product"] == "Rice 5kg" and top["revenue"] == 680
    assert top["share"] == pytest.approx(680 / 784)
    assert summary.by_product["revenue"].sum() == pytest.approx(784)


def test_by_day_counts_bills(summary):
    sat = summary.by_day.iloc[0]
    assert sat["weekday"] == "Saturday" and sat["bills"] == 2


def test_payment_mix(summary):
    mix = summary.by_payment_mode.set_index("payment_mode")["revenue"]
    assert mix["UPI"] == 444 and mix["Cash"] == 340


def test_insights_are_plain_language(summary):
    text = " ".join(summary.insights)
    assert "Saturday is the busiest day" in text
    assert "UPI is the most common payment method (57% of sales)" in text
    assert "Returns/refunds totalled ₹28.00" in text


def test_summary_without_optional_columns(write_xlsx, config):
    path = write_xlsx([["Date", "Item", "Amount"], [d(1), "Milk", 28], [d(2), "Curd", 35]])
    s = summarise(clean([load_file(path, config)], config), config)
    assert s.bill_count is None and s.units_sold is None and s.by_payment_mode is None
    assert "units" not in s.by_product.columns
    assert [k for k, _ in s.kpis()][:3] == ["Net sales", "Gross sales", "Returns / refunds"]


def test_month_on_month_insight_marks_incomplete_month(write_xlsx, config):
    path = write_xlsx([["Date", "Item", "Amount"], [d(10, 6), "Milk", 100], [d(10, 7), "Milk", 150]])
    s = summarise(clean([load_file(path, config)], config), config)
    assert any("July sales were up 50% on June" in i and "may be incomplete" in i for i in s.insights)


def test_no_valid_rows(write_xlsx, config):
    path = write_xlsx([["Date", "Item", "Amount"], ["not a date", "Milk", 28]])
    with pytest.raises(NoValidRowsError):
        summarise(clean([load_file(path, config)], config), config)
