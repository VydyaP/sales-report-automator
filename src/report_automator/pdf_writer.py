"""One-page PDF summary, sized to be shared on WhatsApp or printed."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import BinaryIO

import matplotlib

matplotlib.use("Agg")  # no display needed; must be set before pyplot import
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from fpdf import FPDF  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from .cleaner import CHECK, FIXED, CleanResult  # noqa: E402
from .summarize import Summary  # noqa: E402

BRAND = (31, 78, 95)
BRAND_HEX = "#1F4E5F"
ACCENT_HEX = "#3A8FA6"
TEXT = (40, 40, 40)
MUTED = (110, 110, 110)
FONT_DIR = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
plt.rcParams["font.family"] = "DejaVu Sans"  # has the ₹ glyph


def build_pdf(result: CleanResult, summary: Summary) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(12, 12, 12)
    # DejaVu ships with matplotlib and includes the ₹ glyph.
    pdf.add_font("DejaVu", "", os.path.join(FONT_DIR, "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"))
    pdf.set_title(f"{summary.business_name} sales report")
    pdf.set_creator("Sales Report Automator")
    pdf.add_page()

    width = pdf.w - pdf.l_margin - pdf.r_margin

    # Header band
    pdf.set_fill_color(*BRAND)
    pdf.rect(0, 0, pdf.w, 30, style="F")
    pdf.set_xy(12, 7)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("DejaVu", "B", 17)
    pdf.cell(width, 8, _fit(summary.business_name, 48))
    pdf.set_xy(12, 17)
    pdf.set_font("DejaVu", "", 10.5)
    pdf.cell(width, 6, f"Sales report  |  {summary.period_label}")

    # KPI tiles
    tiles = [("Net sales", summary.money(summary.net_revenue))]
    if summary.bill_count is not None:
        tiles.append(("Bills", f"{summary.bill_count:,}"))
    if summary.avg_bill_value is not None:
        tiles.append(("Avg bill", summary.money(summary.avg_bill_value)))
    if summary.units_sold is not None:
        tiles.append(("Units sold", f"{summary.units_sold:,.0f}"))
    if len(tiles) < 4:
        tiles.append(("Returns", summary.money(summary.returns)))
    tiles = tiles[:4]
    gap = 4
    tile_w = (width - gap * (len(tiles) - 1)) / len(tiles)
    y = 36
    for i, (label, value) in enumerate(tiles):
        x = 12 + i * (tile_w + gap)
        pdf.set_fill_color(232, 241, 243)
        pdf.rect(x, y, tile_w, 20, style="F")
        pdf.set_xy(x + 3, y + 3)
        pdf.set_text_color(*MUTED)
        pdf.set_font("DejaVu", "", 8.5)
        pdf.cell(tile_w - 6, 4, label.upper())
        pdf.set_xy(x + 3, y + 9)
        pdf.set_text_color(*BRAND)
        pdf.set_font("DejaVu", "B", 13 if len(value) <= 13 else 11)
        pdf.cell(tile_w - 6, 8, value)

    # Insights
    y = 62
    pdf.set_xy(12, y)
    pdf.set_text_color(*BRAND)
    pdf.set_font("DejaVu", "B", 11.5)
    pdf.cell(width, 6, "What stands out")
    pdf.set_text_color(*TEXT)
    pdf.set_font("DejaVu", "", 9.5)
    pdf.set_y(y + 8)
    for line in summary.insights[:5]:
        pdf.set_x(14)
        pdf.multi_cell(width - 4, 5, f"•  {line}")
        pdf.ln(0.8)

    # Charts
    chart_top = max(pdf.get_y() + 3, 100)
    available = 297 - 12 - 18 - chart_top  # leave room for footer
    chart_h = min(80, (available - 4) / 2)
    pdf.image(_products_chart(summary), x=12, y=chart_top, w=width, h=chart_h)
    pdf.image(_daily_chart(summary), x=12, y=chart_top + chart_h + 4, w=width, h=chart_h)

    # Footer: data quality, so the reader knows the numbers are traceable.
    pdf.set_draw_color(208, 215, 218)
    pdf.line(12, 297 - 26, pdf.w - 12, 297 - 26)
    pdf.set_xy(12, 297 - 24)
    pdf.set_text_color(*MUTED)
    pdf.set_font("DejaVu", "", 8.5)
    pdf.multi_cell(
        width, 4.2,
        f"Data quality: {result.rows_read:,} rows read, {result.rows_kept:,} used, "
        f"{result.rows_removed:,} removed (total lines, duplicates or unreadable), "
        f"{result.count(FIXED):,} automatic corrections, {result.count(CHECK):,} items flagged for review. "
        "Full row-by-row details are in the Excel report's Issues sheet.",
    )
    return bytes(pdf.output())


def save_pdf(data: bytes, target: str | Path | BinaryIO) -> None:
    if isinstance(target, (str, Path)):
        Path(target).write_bytes(data)
    else:
        target.write(data)


def _fit(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _money_axis(symbol: str) -> FuncFormatter:
    def fmt(x, _pos):
        if abs(x) >= 1e7:
            return f"{symbol}{x / 1e7:.1f}Cr"
        if abs(x) >= 1e5:
            return f"{symbol}{x / 1e5:.1f}L"
        if abs(x) >= 1e3:
            return f"{symbol}{x / 1e3:.0f}k"
        return f"{symbol}{x:.0f}"

    return FuncFormatter(fmt)


def _style(ax, title: str) -> None:
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=BRAND_HEX)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#BBBBBB")
    ax.spines["bottom"].set_color("#BBBBBB")
    ax.tick_params(colors="#444444", labelsize=8)


def _products_chart(s: Summary) -> io.BytesIO:
    top = s.by_product.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=200)
    labels = [p if len(p) <= 28 else p[:27] + "…" for p in top["product"]]
    ax.barh(labels, top["revenue"], color=ACCENT_HEX)
    ax.xaxis.set_major_formatter(_money_axis(s.currency))
    _style(ax, f"Top {len(top)} products by sales")
    ax.grid(axis="x", color="#EEEEEE")
    ax.set_axisbelow(True)
    return _to_png(fig)


def _daily_chart(s: Summary) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=200)
    ax.plot(s.by_day["date"], s.by_day["revenue"], color=ACCENT_HEX, linewidth=1.4)
    ax.fill_between(s.by_day["date"], s.by_day["revenue"], color=ACCENT_HEX, alpha=0.12)
    ax.yaxis.set_major_formatter(_money_axis(s.currency))
    _style(ax, "Daily sales")
    ax.grid(axis="y", color="#EEEEEE")
    ax.set_axisbelow(True)
    fig.autofmt_xdate(rotation=0, ha="center")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    return _to_png(fig)


def _to_png(fig) -> io.BytesIO:
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf
