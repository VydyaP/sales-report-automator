import pytest

from report_automator import ConfigError, load_config
from report_automator.config import normalise_header, normalise_key

from .conftest import DEMO_CONFIG


def test_defaults():
    cfg = load_config()
    assert cfg.currency_symbol == "₹"
    assert cfg.alias_lookup()["bill date"] == "date"
    assert cfg.alias_lookup()["particulars"] == "product"


def test_demo_config_loads():
    cfg = load_config(DEMO_CONFIG)
    assert cfg.business_name == "Namma Angadi Provisions (demo)"
    assert cfg.product_lookup()[normalise_key("panner 200g")] == "Paneer 200g"


def test_client_aliases_extend_defaults():
    cfg = load_config({"column_aliases": {"amount": ["Bill Value (Rs)"]}})
    lookup = cfg.alias_lookup()
    assert lookup[normalise_header("Bill Value (Rs)")] == "amount"
    assert lookup["net amount"] == "amount"  # default still there


def test_yaml_text_is_accepted():
    cfg = load_config("business_name: Kirana One\ntop_n_products: 5\n")
    assert cfg.business_name == "Kirana One" and cfg.top_n_products == 5


@pytest.mark.parametrize(
    "raw, fragment",
    [
        ({"colour": "blue"}, "Unknown setting"),
        ({"column_aliases": {"price_per_kg": ["x"]}}, "unknown field"),
        ({"drop_duplicates": "yes"}, "true or false"),
        ({"amount_tolerance": -1}, ">= 0"),
        ({"top_n_products": 0}, "between 1 and 50"),
        ({"business_name": "  "}, "non-empty"),
        ({"product_aliases": ["a", "b"]}, "mapping"),
    ],
)
def test_invalid_settings_raise_clear_errors(raw, fragment):
    with pytest.raises(ConfigError, match=fragment):
        load_config(raw)


def test_invalid_yaml():
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_config("business_name: [unclosed\n")


def test_normalisers():
    assert normalise_header("  Bill_Date. ") == "bill date"
    assert normalise_key("Toor Dal (1 KG)") == normalise_key("toor dal 1kg")
