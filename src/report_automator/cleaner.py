"""Cleaning rules.

Principle: nothing is changed or dropped silently. Every removal, fix and
doubt is written to the issue log, which becomes the "Issues" sheet in the
report so the business owner can see exactly what happened to their data.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field

import pandas as pd

from .config import Config, normalise_key
from .loader import LoadedFile
from .parsing import format_inr, is_blank, parse_date, parse_number

REMOVED, FIXED, CHECK = "Removed", "Fixed", "Check"

# Whole-cell match only, so a product like "Total Wash Detergent" is kept.
_TOTAL_ROW = re.compile(
    r"\s*(grand|sub|day|daily|net|month|monthly)?\s*-?\s*totals?"
    r"(\s+(sales|amount|value))?(\s+for\b.*)?\s*:?\s*",
    re.I,
)
_PAYMENT_MODES = {
    "upi": "UPI", "gpay": "UPI", "google pay": "UPI", "phonepe": "UPI", "phone pe": "UPI",
    "paytm": "UPI", "bhim": "UPI", "cash": "Cash", "card": "Card", "credit card": "Card",
    "debit card": "Card", "credit": "Credit", "on credit": "Credit", "udhaar": "Credit",
    "net banking": "Net Banking", "neft": "Net Banking", "imps": "Net Banking",
}

CLEAN_COLUMNS = [
    "date", "invoice_id", "product", "category", "quantity", "unit_price",
    "amount", "payment_mode", "source_file", "source_row",
]


@dataclass
class Issue:
    severity: str  # Removed / Fixed / Check
    file: str
    row: int | None  # row number in the original file; None for grouped issues
    field: str
    message: str
    original_value: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class CleanResult:
    data: pd.DataFrame
    issues: list[Issue]
    rows_read: int
    files: list[LoadedFile] = field(default_factory=list)
    has_invoice_ids: bool = False
    has_quantity: bool = False
    has_category: bool = False
    has_payment_mode: bool = False

    @property
    def rows_kept(self) -> int:
        return len(self.data)

    @property
    def rows_removed(self) -> int:
        return self.rows_read - self.rows_kept

    def count(self, severity: str) -> int:
        return sum(1 for i in self.issues if i.severity == severity)

    def issues_frame(self) -> pd.DataFrame:
        cols = ["severity", "file", "row", "field", "message", "original_value"]
        if not self.issues:
            return pd.DataFrame(columns=cols)
        order = {REMOVED: 0, CHECK: 1, FIXED: 2}
        frame = pd.DataFrame([i.as_dict() for i in self.issues], columns=cols)
        frame["_o"] = frame["severity"].map(order)
        frame["row"] = frame["row"].astype("Int64")  # whole numbers, blank when grouped
        frame = frame.sort_values(["_o", "file", "row"], na_position="last", kind="stable")
        return frame.drop(columns="_o").reset_index(drop=True)


def clean(files: list[LoadedFile], config: Config) -> CleanResult:
    issues: list[Issue] = []
    records: list[dict] = []
    rows_read = 0
    mapped = set().union(*(f.mapping.keys() for f in files)) if files else set()

    for loaded in files:
        blank_count = 0
        for raw in loaded.rows.to_dict("records"):
            fname, rownum = raw["_source_file"], raw["_source_row"]
            values = {k: v for k, v in raw.items() if not k.startswith("_")}
            if all(is_blank(v) for v in values.values()):
                blank_count += 1  # trailing/spacer rows: not counted as data
                continue
            rows_read += 1
            rec = _clean_row(values, fname, rownum, config, issues)
            if rec is not None:
                records.append(rec)
        if blank_count:
            issues.append(Issue(REMOVED, loaded.name, None, "(row)",
                                f"{blank_count} empty row(s) skipped"))

    data = pd.DataFrame(records, columns=CLEAN_COLUMNS)
    _standardise_text(data, "product", config.product_lookup(), issues)
    _standardise_payment_modes(data, issues)
    data = _handle_duplicates(data, config, issues, has_invoice="invoice_id" in mapped)

    data["date"] = pd.to_datetime(data["date"])
    for col in ("quantity", "unit_price", "amount"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.sort_values(["date", "source_file", "source_row"], kind="stable").reset_index(drop=True)

    return CleanResult(
        data=data,
        issues=issues,
        rows_read=rows_read,
        files=files,
        has_invoice_ids="invoice_id" in mapped and data["invoice_id"].notna().any(),
        has_quantity="quantity" in mapped and data["quantity"].notna().any(),
        has_category="category" in mapped and data["category"].notna().any(),
        has_payment_mode="payment_mode" in mapped and data["payment_mode"].notna().any(),
    )


def _clean_row(values: dict, fname: str, rownum: int, config: Config, issues: list[Issue]) -> dict | None:
    def log(sev: str, fld: str, msg: str, orig=None):
        issues.append(Issue(sev, fname, rownum, fld, msg, "" if is_blank(orig) else str(orig)))

    product_raw = values.get("product")
    # Subtotal / total lines would double-count sales.
    for key in ("product", "invoice_id", "date"):
        v = values.get(key)
        if not is_blank(v) and isinstance(v, str) and _TOTAL_ROW.fullmatch(v):
            log(REMOVED, key, "Total/subtotal line (would double-count sales)", v)
            return None

    raw_date = values.get("date")
    date = parse_date(raw_date)
    if date is None:
        msg = "Missing date" if is_blank(raw_date) else "Date could not be understood"
        log(REMOVED, "date", msg, raw_date)
        return None

    if is_blank(product_raw):
        log(REMOVED, "product", "Missing product name", product_raw)
        return None
    product = " ".join(str(product_raw).split())

    qty_raw, price_raw, amount_raw = values.get("quantity"), values.get("unit_price"), values.get("amount")
    qty, price, amount = parse_number(qty_raw), parse_number(price_raw), parse_number(amount_raw)
    for name, raw_v, parsed in (("quantity", qty_raw, qty), ("unit_price", price_raw, price)):
        if parsed is None and not is_blank(raw_v):
            log(CHECK, name, "Value is not a number; ignored", raw_v)

    if amount is None:
        if qty is not None and price is not None:
            amount = round(qty * price, 2)
            log(FIXED, "amount", f"Amount was {'unreadable' if not is_blank(amount_raw) else 'missing'}; "
                                 f"calculated as quantity × rate = {format_inr(amount, config.currency_symbol)}",
                amount_raw)
        else:
            msg = "Missing amount" if is_blank(amount_raw) else "Amount could not be understood"
            log(REMOVED, "amount", msg, amount_raw)
            return None

    if qty is None and "quantity" in values:
        if price not in (None, 0):
            qty = round(amount / price, 3)
            log(FIXED, "quantity", f"Quantity missing; calculated as amount ÷ rate = {qty:g}", qty_raw)
        else:
            log(CHECK, "quantity", "Quantity missing; row counts toward revenue but not units sold", qty_raw)

    if qty is not None and price is not None:
        expected = qty * price
        if abs(expected - amount) > config.amount_tolerance:
            log(CHECK, "amount",
                f"Amount {format_inr(amount, config.currency_symbol)} does not match "
                f"{qty:g} × {format_inr(price, config.currency_symbol)} = "
                f"{format_inr(expected, config.currency_symbol)}; kept amount as entered",
                amount_raw)

    if amount < 0:
        log(CHECK, "amount", "Negative amount; treated as a return/refund", amount_raw)
    elif amount == 0:
        log(CHECK, "amount", "Zero amount", amount_raw)

    return {
        "date": date,
        "invoice_id": _clean_id(values.get("invoice_id")),
        "product": product,
        "category": None if is_blank(values.get("category")) else " ".join(str(values["category"]).split()),
        "quantity": qty,
        "unit_price": price,
        "amount": round(amount, 2),
        "payment_mode": None if is_blank(values.get("payment_mode")) else " ".join(str(values["payment_mode"]).split()),
        "source_file": fname,
        "source_row": rownum,
    }


def _clean_id(value) -> str | None:
    if is_blank(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text[:-2] if re.fullmatch(r"\d+\.0", text) else text


def _standardise_text(data: pd.DataFrame, col: str, official: dict[str, str], issues: list[Issue]) -> None:
    """Merge spelling variants ("toor dal 1 KG", "Toor Dal 1kg") into one name.

    Configured aliases win; otherwise the most common spelling of each
    variant group becomes the standard name.
    """
    if data.empty:
        return
    groups: dict[str, Counter] = defaultdict(Counter)
    for value in data[col]:
        groups[normalise_key(value)][value] += 1

    chosen: dict[str, str] = {}
    for key, counter in groups.items():
        if key in official:
            chosen[key] = official[key]
        else:
            # most common; ties broken by first appearance (Counter keeps insertion order)
            chosen[key] = max(counter.items(), key=lambda kv: kv[1])[0]

    changes: Counter = Counter()
    new_values = []
    for value, fname in zip(data[col], data["source_file"]):
        target = chosen[normalise_key(value)]
        if target != value:
            changes[(value, target, fname)] += 1
        new_values.append(target)
    data[col] = new_values
    for (old, new, fname), n in changes.items():
        issues.append(Issue(FIXED, fname, None, col, f"Standardised '{old}' → '{new}' ({n} row(s))", old))


def _standardise_payment_modes(data: pd.DataFrame, issues: list[Issue]) -> None:
    if data.empty or data["payment_mode"].isna().all():
        return
    changes: Counter = Counter()
    out = []
    for value, fname in zip(data["payment_mode"], data["source_file"]):
        if value is None:
            out.append(None)
            continue
        target = _PAYMENT_MODES.get(value.strip().lower(), value.strip())
        if target != value:
            changes[(value, target, fname)] += 1
        out.append(target)
    data["payment_mode"] = out
    for (old, new, fname), n in changes.items():
        issues.append(Issue(FIXED, fname, None, "payment_mode",
                            f"Standardised '{old}' → '{new}' ({n} row(s))", old))


def _handle_duplicates(data: pd.DataFrame, config: Config, issues: list[Issue], has_invoice: bool) -> pd.DataFrame:
    """Exact repeats of the same invoice line are removed (common when an
    export is run twice or months overlap). Without invoice numbers we
    cannot tell a repeat from a genuine second sale, so we only flag."""
    if data.empty:
        return data
    key_cols = ["date", "invoice_id", "product", "quantity", "unit_price", "amount"]
    keys = ["|".join("" if is_blank(v) else str(v) for v in row)
            for row in data[key_cols].itertuples(index=False, name=None)]
    first_seen: dict[str, tuple[str, int]] = {}
    drop_idx = []
    for idx, key, fname, row, inv in zip(data.index, keys, data["source_file"], data["source_row"], data["invoice_id"]):
        if key in first_seen:
            orig_file, orig_row = first_seen[key]
            where = f"row {orig_row}" + ("" if orig_file == fname else f" of {orig_file}")
            if has_invoice and inv is not None and config.drop_duplicates:
                issues.append(Issue(REMOVED, fname, row, "(row)", f"Exact duplicate of {where}"))
                drop_idx.append(idx)
            else:
                issues.append(Issue(CHECK, fname, row, "(row)",
                                    f"Looks identical to {where}; kept because it may be a genuine repeat sale"))
        else:
            first_seen[key] = (fname, row)
    return data.drop(index=drop_idx)
