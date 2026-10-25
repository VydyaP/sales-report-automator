"""Business numbers an owner actually asks for: how much did we sell,
what sold best, which days are busiest, how do customers pay."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .cleaner import CleanResult
from .config import Config
from .errors import NoValidRowsError
from .parsing import format_inr

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class Summary:
    business_name: str
    currency: str
    period_start: pd.Timestamp
    period_end: pd.Timestamp
    net_revenue: float
    gross_sales: float
    returns: float
    line_count: int
    bill_count: int | None
    units_sold: float | None
    avg_bill_value: float | None
    best_day: tuple[pd.Timestamp, float]
    by_product: pd.DataFrame
    by_day: pd.DataFrame
    by_week: pd.DataFrame
    by_month: pd.DataFrame
    by_weekday: pd.DataFrame
    by_category: pd.DataFrame | None = None
    by_payment_mode: pd.DataFrame | None = None
    insights: list[str] = field(default_factory=list)

    def money(self, value: float) -> str:
        return format_inr(value, self.currency)

    @property
    def period_label(self) -> str:
        start, end = self.period_start, self.period_end
        if start == end:
            return start.strftime("%d %b %Y")
        return f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}"

    def kpis(self) -> list[tuple[str, str]]:
        rows = [
            ("Net sales", self.money(self.net_revenue)),
            ("Gross sales", self.money(self.gross_sales)),
            ("Returns / refunds", self.money(self.returns)),
        ]
        if self.bill_count is not None:
            rows.append(("Number of bills", f"{self.bill_count:,}"))
        if self.avg_bill_value is not None:
            rows.append(("Average bill value", self.money(self.avg_bill_value)))
        if self.units_sold is not None:
            rows.append(("Units sold", f"{self.units_sold:,.0f}"))
        rows.append(("Sale lines", f"{self.line_count:,}"))
        rows.append(("Best day", f"{self.best_day[0].strftime('%a %d %b %Y')} ({self.money(self.best_day[1])})"))
        return rows


def summarise(result: CleanResult, config: Config) -> Summary:
    df = result.data
    if df.empty:
        raise NoValidRowsError(
            "No usable sales rows were found after cleaning. "
            "Check the Issues list to see why rows were removed."
        )

    net = float(df["amount"].sum())
    gross = float(df.loc[df["amount"] > 0, "amount"].sum())
    returns = float(-df.loc[df["amount"] < 0, "amount"].sum())

    bills = None
    if result.has_invoice_ids:
        bills = int(df.dropna(subset=["invoice_id"]).groupby(["date", "invoice_id"]).ngroups)
    units = float(df["quantity"].sum()) if result.has_quantity else None
    avg_bill = net / bills if bills else None

    by_day = _by_day(df, result.has_invoice_ids)
    best = by_day.loc[by_day["revenue"].idxmax()]

    by_product = (
        df.groupby("product", as_index=False)
        .agg(units=("quantity", "sum"), revenue=("amount", "sum"), lines=("amount", "size"))
        .sort_values(["revenue", "product"], ascending=[False, True], kind="stable")
        .reset_index(drop=True)
    )
    by_product["share"] = by_product["revenue"] / net if net else 0.0
    if result.has_category:
        cat = df.dropna(subset=["category"]).groupby("product")["category"].agg(lambda s: s.mode().iat[0])
        by_product.insert(1, "category", by_product["product"].map(cat))
    if not result.has_quantity:
        by_product = by_product.drop(columns="units")

    summary = Summary(
        business_name=config.business_name,
        currency=config.currency_symbol,
        period_start=df["date"].min(),
        period_end=df["date"].max(),
        net_revenue=net,
        gross_sales=gross,
        returns=returns,
        line_count=len(df),
        bill_count=bills,
        units_sold=units,
        avg_bill_value=avg_bill,
        best_day=(best["date"], float(best["revenue"])),
        by_product=by_product,
        by_day=by_day,
        by_week=_by_period(df, "W-SUN", "week_starting", lambda p: p.start_time),
        by_month=_by_period(df, "M", "month", lambda p: p.start_time),
        by_weekday=_by_weekday(by_day),
        by_category=_share_table(df, "category", net) if result.has_category else None,
        by_payment_mode=_share_table(df, "payment_mode", net) if result.has_payment_mode else None,
    )
    summary.insights = _insights(summary)
    return summary


def _by_day(df: pd.DataFrame, has_invoices: bool) -> pd.DataFrame:
    agg = {"revenue": ("amount", "sum"), "lines": ("amount", "size")}
    out = df.groupby("date", as_index=False).agg(**agg)
    if has_invoices:
        bills = df.dropna(subset=["invoice_id"]).groupby("date")["invoice_id"].nunique()
        out["bills"] = out["date"].map(bills).fillna(0).astype(int)
    out.insert(1, "weekday", out["date"].dt.day_name())
    return out


def _by_period(df: pd.DataFrame, freq: str, label: str, to_start) -> pd.DataFrame:
    periods = df["date"].dt.to_period(freq)
    out = df.groupby(periods).agg(revenue=("amount", "sum"), lines=("amount", "size")).reset_index()
    out[label] = out["date"].map(to_start)
    return out[[label, "revenue", "lines"]]


def _by_weekday(by_day: pd.DataFrame) -> pd.DataFrame:
    out = by_day.groupby("weekday").agg(days=("revenue", "size"), avg_revenue=("revenue", "mean")).reset_index()
    out["order"] = out["weekday"].map({d: i for i, d in enumerate(WEEKDAYS)})
    return out.sort_values("order").drop(columns="order").reset_index(drop=True)


def _share_table(df: pd.DataFrame, col: str, net: float) -> pd.DataFrame:
    out = (
        df.assign(**{col: df[col].fillna("(not recorded)")})
        .groupby(col, as_index=False)
        .agg(revenue=("amount", "sum"), lines=("amount", "size"))
        .sort_values("revenue", ascending=False)
        .reset_index(drop=True)
    )
    out["share"] = out["revenue"] / net if net else 0.0
    return out


def _insights(s: Summary) -> list[str]:
    """Plain-language findings for the owner. Only facts computed above."""
    lines: list[str] = []
    top = s.by_product.head(3)
    if len(s.by_product) >= 3 and s.net_revenue > 0:
        share = top["revenue"].sum() / s.net_revenue
        lines.append(
            f"Your top 3 products ({', '.join(top['product'])}) brought in "
            f"{share:.0%} of sales."
        )
    elif not top.empty:
        lines.append(f"Best-selling product: {top.iloc[0]['product']} ({s.money(top.iloc[0]['revenue'])}).")

    wk = s.by_weekday
    if len(wk) >= 2:
        best = wk.loc[wk["avg_revenue"].idxmax()]
        worst = wk.loc[wk["avg_revenue"].idxmin()]
        lines.append(
            f"{best['weekday']} is the busiest day on average ({s.money(best['avg_revenue'])}); "
            f"{worst['weekday']} is the quietest ({s.money(worst['avg_revenue'])})."
        )

    if s.by_payment_mode is not None and not s.by_payment_mode.empty:
        lead = s.by_payment_mode.iloc[0]
        lines.append(f"{lead['payment_mode']} is the most common payment method ({lead['share']:.0%} of sales).")

    if len(s.by_month) >= 2:
        last, prev = s.by_month.iloc[-1], s.by_month.iloc[-2]
        if prev["revenue"]:
            change = (last["revenue"] - prev["revenue"]) / prev["revenue"]
            direction = "up" if change >= 0 else "down"
            lines.append(
                f"{last['month'].strftime('%B')} sales were {direction} {abs(change):.0%} "
                f"on {prev['month'].strftime('%B')}."
            )
            if last["month"].to_period("M") == s.period_end.to_period("M") and s.period_end.day < 28:
                lines[-1] += " (The latest month may be incomplete.)"

    if s.returns > 0:
        lines.append(f"Returns/refunds totalled {s.money(s.returns)}.")
    return lines
