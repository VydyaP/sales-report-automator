"""Generate realistic, deliberately messy sample exports for a FICTIONAL store.

No real business or customer data is used anywhere in this project.
Run:  python scripts/make_sample_data.py
Output is deterministic (fixed random seed), so the demo numbers never change.

The three files mimic three different billing tools / habits:
  * July:      Excel register with title rows above the header, a daily
               "Day Total" line, blank spacer rows and a few typos.
  * August:    CSV with text amounts ("₹1,250.00", "Rs. 90"), mixed date
               formats, inconsistent payment labels, and a re-export of the
               last July bills (overlap duplicates).
  * September: Excel with different column names (Inv Date / Particulars /
               Nos / MRP / Net Amount), an extra GST column and a Grand
               Total row.
"""

from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

STORE = "Namma Angadi Provisions (demo)"
OUT = Path(__file__).resolve().parents[1] / "sample_data"

# product, category, price, popularity weight
PRODUCTS = [
    ("Milk 500ml", "Dairy", 28, 30), ("Curd 500g", "Dairy", 35, 14),
    ("Paneer 200g", "Dairy", 90, 6), ("Ghee 500ml", "Dairy", 330, 3), ("Butter 100g", "Dairy", 58, 4),
    ("Toor Dal 1kg", "Groceries", 165, 8), ("Moong Dal 500g", "Groceries", 72, 5),
    ("Sona Masoori Rice 5kg", "Groceries", 340, 6), ("Wheat Atta 5kg", "Groceries", 260, 5),
    ("Sugar 1kg", "Groceries", 48, 9), ("Sunflower Oil 1L", "Groceries", 155, 7),
    ("Groundnut Oil 1L", "Groceries", 210, 3), ("Idli Rava 1kg", "Groceries", 64, 5),
    ("Jaggery 1kg", "Groceries", 70, 3),
    ("Masala Peanuts 200g", "Snacks", 45, 6), ("Banana Chips 200g", "Snacks", 60, 6),
    ("Rusk 300g", "Snacks", 50, 5), ("Glucose Biscuits 250g", "Snacks", 30, 10),
    ("Filter Coffee Powder 500g", "Beverages", 260, 5), ("Tea Powder 250g", "Beverages", 140, 5),
    ("Badam Drink Mix 200g", "Beverages", 120, 2),
    ("Dishwash Bar 3pc", "Household", 45, 5), ("Detergent Powder 1kg", "Household", 110, 4),
    ("Agarbatti Pack", "Household", 35, 4),
]
PAYMENTS = [("UPI", 58), ("Cash", 30), ("Card", 8), ("Credit", 4)]

# Spelling variants a busy cashier or a different billing tool produces.
VARIANTS = {
    "Toor Dal 1kg": ["toor dal 1 kg", "TOOR DAL 1KG", "Toor Dal (1kg)"],
    "Milk 500ml": ["Milk 500 ml", "MILK 500ML"],
    "Paneer 200g": ["Panner 200g"],  # typo: fixed via product_aliases in the settings file
    "Glucose Biscuits 250g": ["glucose biscuits 250g"],
    "Sunflower Oil 1L": ["Sunflower Oil 1 L"],
}
AUG_PAYMENT_LABELS = {"UPI": ["UPI", "upi", "GPay", "PhonePe"], "Cash": ["Cash", "cash"],
                      "Card": ["Card", "card"], "Credit": ["Credit"]}


def make_bills(rng: random.Random, start: dt.date, end: dt.date, first_no: int):
    """Return a list of bills: (date, bill_no, payment, [(product, cat, qty, rate)])."""
    names = [p for p in PRODUCTS]
    weights = [p[3] for p in PRODUCTS]
    bills = []
    no = first_no
    day = start
    while day <= end:
        weekend = day.weekday() >= 5
        n_bills = rng.randint(14, 22) + (6 if weekend else 0)
        if day.day <= 5:  # salary-week bump
            n_bills += 4
        for _ in range(n_bills):
            lines = []
            chosen = set()
            for _ in range(rng.choices([1, 2, 3, 4], weights=[35, 35, 20, 10])[0]):
                prod = rng.choices(names, weights=weights)[0]
                if prod[0] in chosen:
                    continue
                chosen.add(prod[0])
                qty = rng.choices([1, 2, 3, 4], weights=[60, 25, 10, 5])[0]
                lines.append((prod[0], prod[1], qty, prod[2]))
            pay = rng.choices([p for p, _ in PAYMENTS], weights=[w for _, w in PAYMENTS])[0]
            bills.append((day, no, pay, lines))
            no += 1
        day += dt.timedelta(days=1)
    return bills


def maybe_variant(rng: random.Random, name: str, rate: float = 0.25) -> str:
    if name in VARIANTS and rng.random() < rate:
        return rng.choice(VARIANTS[name])
    return name


def write_july(rng: random.Random, bills) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sales Register"
    ws.append([STORE.upper()])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append(["Sales Register: 01-07-2026 to 31-07-2026"])
    ws.append([])
    ws.append(["Bill Date", "Bill No", "Item Name", "Group", "Qty", "Rate", "Amount", "Mode"])
    for c in ws[4]:
        c.font = Font(bold=True)

    current_day, day_total = None, 0.0
    for i, (day, no, pay, lines) in enumerate(bills):
        if current_day and day != current_day:
            ws.append([None, None, "Day Total", None, None, None, day_total, None])
            if rng.random() < 0.3:
                ws.append([])  # spacer row
            day_total = 0.0
        current_day = day
        for prod, cat, qty, price in lines:
            amount = qty * price
            day_total += amount
            ws.append([day, f"NA/{no:05d}", maybe_variant(rng, prod), cat, qty, price, amount, pay])
            ws.cell(ws.max_row, 1).number_format = "dd-mm-yyyy"
    ws.append([None, None, "Day Total", None, None, None, day_total, None])

    # Hand-made problems a real register has:
    rows = list(ws.iter_rows(min_row=5))
    data_rows = [r for r in rows if r[1].value]
    # 1. an impossible date typed by hand
    data_rows[40][0].value = "31/06/2026"
    # 2. quantity missing (can be recovered from amount / rate)
    data_rows[75][4].value = None
    # 3. amount that does not match qty x rate (discount not recorded?)
    data_rows[120][6].value = data_rows[120][6].value - 15
    # 4. a return entered as a negative line
    r = data_rows[200]
    r[4].value, r[6].value = -1, -(r[5].value)
    # 5. same bill line keyed in twice
    dup = [c.value for c in data_rows[300]]
    ws.insert_rows(data_rows[300][0].row + 1)
    for j, v in enumerate(dup, start=1):
        ws.cell(data_rows[300][0].row + 1, j, v)
        if j == 1:
            ws.cell(data_rows[300][0].row + 1, j).number_format = "dd-mm-yyyy"
    # 6. a line with the item name missing
    data_rows[500][2].value = None

    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["C"].width = 28
    wb.save(OUT / "jul_2026_sales_register.xlsx")


def write_august(rng: random.Random, bills, july_overlap) -> None:
    def fmt_date(d: dt.date) -> str:
        return rng.choices(
            [d.strftime("%d/%m/%Y"), d.strftime("%Y-%m-%d"), d.strftime("%d %b %Y"), d.strftime("%d-%m-%y")],
            weights=[60, 20, 15, 5],
        )[0]

    def fmt_money(v: float) -> str:
        return rng.choices([f"₹{v:,.2f}", f"Rs. {v:g}", f"{v:g}", f"{v:,.2f}"], weights=[40, 20, 25, 15])[0]

    rows = []
    # Export was run from 30 July, so the last July bills appear again.
    for day, no, pay, lines in july_overlap:
        for prod, cat, qty, price in lines:
            rows.append([fmt_date(day), f"NA/{no:05d}", prod, cat, qty, fmt_money(price),
                         fmt_money(qty * price), pay])
    for day, no, pay, lines in bills:
        label = rng.choice(AUG_PAYMENT_LABELS[pay])
        for prod, cat, qty, price in lines:
            rows.append([fmt_date(day), f"NA/{no:05d}", maybe_variant(rng, prod), cat, qty,
                         fmt_money(price), fmt_money(qty * price), label])

    # Problems:
    rows[60][6] = ""          # amount missing, recoverable from qty x price
    rows[150][0] = ""         # date missing
    rows[260][6] = "N/A"      # amount unreadable and no way to recover? (qty & price present -> recoverable)
    rows[261][4] = ""         # ...and next row also lacks a quantity
    rows[261][5] = ""         # ...and a price, so its amount stays as entered with qty unknown
    rows.insert(420, list(rows[419]))  # duplicated line

    with open(OUT / "aug_2026_sales.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Invoice No", "Product", "Category", "Quantity", "Price", "Total", "Payment"])
        w.writerows(rows)


def write_september(rng: random.Random, bills) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sep"
    ws.append(["Inv Date", "Inv No", "Particulars", "Category", "Nos", "MRP", "GST %", "Net Amount", "Pay Mode"])
    for c in ws[1]:
        c.font = Font(bold=True)
    total = 0.0
    gst = {"Dairy": 5, "Groceries": 5, "Snacks": 12, "Beverages": 18, "Household": 18}
    for day, no, pay, lines in bills:
        for prod, cat, qty, price in lines:
            amount = qty * price
            total += amount
            ws.append([dt.datetime.combine(day, dt.time()), no, maybe_variant(rng, prod, 0.15), cat,
                       qty, price, gst[cat], amount, pay])
            ws.cell(ws.max_row, 1).number_format = "dd/mm/yyyy"
    ws.append([])
    ws.append(["Grand Total", None, None, None, None, None, None, total, None])
    # A typo in a date
    ws.cell(30, 1).value = "15/13/2026"
    wb.save(OUT / "sep_2026_sales.xlsx")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rng = random.Random(2026)
    july = make_bills(rng, dt.date(2026, 7, 1), dt.date(2026, 7, 31), first_no=1)
    aug = make_bills(rng, dt.date(2026, 8, 1), dt.date(2026, 8, 31), first_no=july[-1][1] + 1)
    sep = make_bills(rng, dt.date(2026, 9, 1), dt.date(2026, 9, 30), first_no=aug[-1][1] + 1)
    write_july(random.Random(1), july)
    write_august(random.Random(2), aug, [b for b in july if b[0] == dt.date(2026, 7, 31)][-3:])
    write_september(random.Random(3), sep)
    for p in sorted(OUT.glob("*")):
        print(f"wrote {p.relative_to(OUT.parent)} ({p.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
