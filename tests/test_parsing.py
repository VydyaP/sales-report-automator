import datetime as dt

import pytest

from report_automator.parsing import format_inr, is_blank, parse_date, parse_number


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-07-05", dt.date(2026, 7, 5)),  # ISO must never be read as 7 May
        ("05/07/2026", dt.date(2026, 7, 5)),  # Indian day-first
        ("5-7-2026", dt.date(2026, 7, 5)),
        ("05.07.2026", dt.date(2026, 7, 5)),
        ("05/07/26", dt.date(2026, 7, 5)),
        ("5 Jul 2026", dt.date(2026, 7, 5)),
        ("5 Jul. 2026", dt.date(2026, 7, 5)),
        ("05-JUL-2026", dt.date(2026, 7, 5)),
        ("5 July 2026", dt.date(2026, 7, 5)),
        ("  05/07/2026  ", dt.date(2026, 7, 5)),
        ("05/07/2026 14:30", dt.date(2026, 7, 5)),
        (dt.datetime(2026, 7, 5, 18, 0), dt.date(2026, 7, 5)),
        (dt.date(2026, 7, 5), dt.date(2026, 7, 5)),
        (46208, dt.date(2026, 7, 5)),  # Excel serial number
    ],
)
def test_parse_date_valid(value, expected):
    assert parse_date(value) == expected


@pytest.mark.parametrize("value", ["31/06/2026", "15/13/2026", "yesterday", "", None, "1899-01-01", 12, True])
def test_parse_date_invalid(value):
    assert parse_date(value) is None


@pytest.mark.parametrize(
    "value, expected",
    [
        (1200, 1200.0),
        (99.5, 99.5),
        ("1,200", 1200.0),
        ("₹1,200.50", 1200.5),
        ("₹ 12,34,567.00", 1234567.0),
        ("Rs. 90", 90.0),
        ("Rs.90/-", 90.0),
        ("INR 45", 45.0),
        ("(250)", -250.0),
        ("-35", -35.0),
        ("35-", -35.0),
    ],
)
def test_parse_number_valid(value, expected):
    assert parse_number(value) == expected


@pytest.mark.parametrize("value", ["N/A", "", "-", "abc", "1.2.3", None, float("nan"), float("inf"), True])
def test_parse_number_invalid(value):
    assert parse_number(value) is None


@pytest.mark.parametrize(
    "amount, expected",
    [
        (0, "₹0.00"),
        (999, "₹999.00"),
        (1000, "₹1,000.00"),
        (100000, "₹1,00,000.00"),
        (1234567.5, "₹12,34,567.50"),
        (123456789, "₹12,34,56,789.00"),
        (-1500.25, "-₹1,500.25"),
    ],
)
def test_format_inr(amount, expected):
    assert format_inr(amount) == expected


def test_format_inr_rounding_carries_into_whole_number():
    assert format_inr(999.999) == "₹1,000.00"


def test_is_blank():
    assert is_blank(None) and is_blank("  ") and is_blank(float("nan")) and is_blank("-")
    assert not is_blank(0) and not is_blank("0")
