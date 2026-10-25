from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import pytest
from openpyxl import Workbook

from report_automator import Config

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "sample_data"
DEMO_CONFIG = ROOT / "configs" / "demo_store.yaml"


@pytest.fixture
def config() -> Config:
    return Config(business_name="Test Store")


@pytest.fixture
def write_xlsx(tmp_path):
    """write_xlsx(rows, name) -> path. rows is a list of lists (header included)."""

    def _write(rows: list[list], name: str = "sales.xlsx") -> Path:
        wb = Workbook()
        ws = wb.active
        for r in rows:
            ws.append(r)
        path = tmp_path / name
        wb.save(path)
        return path

    return _write


@pytest.fixture
def write_csv(tmp_path):
    def _write(rows: list[list], name: str = "sales.csv", encoding: str = "utf-8", delimiter: str = ",") -> Path:
        path = tmp_path / name
        with open(path, "w", newline="", encoding=encoding) as f:
            csv.writer(f, delimiter=delimiter).writerows(rows)
        return path

    return _write


HEADER = ["Date", "Bill No", "Item Name", "Qty", "Rate", "Amount", "Mode"]


def d(day: int, month: int = 7) -> dt.datetime:
    return dt.datetime(2026, month, day)
