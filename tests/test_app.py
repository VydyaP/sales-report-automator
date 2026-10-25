"""Smoke test of the web page using Streamlit's headless test runner."""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from .conftest import ROOT  # noqa: E402

APP = str(ROOT / "app.py")


def test_page_loads_and_waits_for_files():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value == "Sales Report Automator"
    assert len(at.success) == 0  # nothing processed yet


def test_demo_button_builds_report():
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.button[0].click().run()
    assert not at.exception
    assert "Report ready" in at.success[0].value
    labels = {m.label: m.value for m in at.metric}
    assert labels["Net sales"] == "₹5,18,322"
    assert labels["Bills"] == "1,840"
    assert labels["Best day (₹10,707)"] == "Sun 23 Aug"
    assert labels["Rows read"] == "3,612"


def test_business_name_override():
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.text_input[0].input("Sri Ganesh Stores")
    at.button[0].click().run()
    assert "Sri Ganesh Stores" in at.success[0].value
