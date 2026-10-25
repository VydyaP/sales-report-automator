"""Turning messy cell values into clean numbers and dates.

Each parser returns None when a value cannot be understood, so the caller
decides whether that row is fixed, flagged or rejected.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from typing import Any

# Day-first formats (Indian convention) plus unambiguous ISO year-first.
# ISO is tried first and only matches 4-digit-year-first strings, so
# "2026-07-05" is always 5 July, never 7 May.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d.%m.%y",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d %B %Y",
    "%d-%b-%y",
    "%d %b %y",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
)
_EXCEL_EPOCH = dt.date(1899, 12, 30)
_MIN_YEAR, _MAX_YEAR = 2000, 2100

_CURRENCY_TOKENS = re.compile(r"(₹|rs\.?|inr|/-)", re.IGNORECASE)


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() in {"", "-", "--", "nan", "NaN", "None"}:
        return True
    # pandas NaT / NA
    try:
        import pandas as pd

        if value is pd.NaT or value is pd.NA:
            return True
    except ImportError:  # pragma: no cover
        pass
    return False


def parse_date(value: Any) -> dt.date | None:
    """Return a date, or None if the value is not a recognisable date."""
    if is_blank(value):
        return None

    result: dt.date | None = None
    if isinstance(value, dt.datetime):
        result = value.date()
    elif isinstance(value, dt.date):
        result = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        # Excel stores dates as days since 1899-12-30.
        if 20000 <= value <= 80000:
            result = _EXCEL_EPOCH + dt.timedelta(days=int(value))
    else:
        text = " ".join(str(value).strip().split())
        # "5 Jul. 2026" -> "5 Jul 2026"
        text = re.sub(r"(?<=[A-Za-z])\.", "", text)
        for fmt in _DATE_FORMATS:
            try:
                result = dt.datetime.strptime(text, fmt).date()
                break
            except ValueError:
                continue
        if result is None:
            # strptime is case-sensitive for %b with some locales; retry titled.
            titled = text.title()
            for fmt in ("%d %b %Y", "%d-%b-%Y", "%d %B %Y", "%d-%b-%y", "%d %b %y"):
                try:
                    result = dt.datetime.strptime(titled, fmt).date()
                    break
                except ValueError:
                    continue

    if result is None or not (_MIN_YEAR <= result.year <= _MAX_YEAR):
        return None
    return result


def parse_number(value: Any) -> float | None:
    """'₹1,200.50' -> 1200.5, '(250)' -> -250.0, 'Rs. 99/-' -> 99.0"""
    if is_blank(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None

    text = _CURRENCY_TOKENS.sub("", str(value)).replace(",", "").replace(" ", "").strip()
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1]
    if text.endswith("-") and text[:-1].replace(".", "", 1).isdigit():
        negative, text = True, text[:-1]
    if not re.fullmatch(r"[+-]?\d+(\.\d+)?", text):
        return None
    number = float(text)
    return -number if negative else number


def format_inr(amount: float, symbol: str = "₹", decimals: int = 2) -> str:
    """Indian digit grouping: 1234567.5 -> '₹12,34,567.50'."""
    sign = "-" if amount < 0 else ""
    amount = abs(round(amount, decimals))
    whole = int(amount)
    frac = f"{amount - whole:.{decimals}f}"[1:] if decimals else ""
    digits = str(whole)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    return f"{sign}{symbol}{digits}{frac}"
