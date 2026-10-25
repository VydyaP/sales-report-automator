"""Per-client settings.

Every business exports sales with its own column names ("Bill Date",
"Inv Date", "Date" ...). Instead of changing code for each client, the
differences live in a small YAML file. This module loads and validates it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError

# The fields the tool understands. "required" ones must be present in the
# input file; the rest make the report richer when available.
CANONICAL_FIELDS = (
    "date",
    "invoice_id",
    "product",
    "category",
    "quantity",
    "unit_price",
    "amount",
    "payment_mode",
)
REQUIRED_FIELDS = ("date", "product", "amount")

DEFAULT_COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["date", "bill date", "invoice date", "inv date", "sale date", "txn date"],
    "invoice_id": ["invoice no", "invoice number", "invoice id", "inv no", "bill no",
                   "bill number", "receipt no", "voucher no"],
    "product": ["product", "product name", "item", "item name", "item description",
                "particulars", "description"],
    "category": ["category", "group", "item group", "department"],
    "quantity": ["qty", "quantity", "units", "nos"],
    "unit_price": ["rate", "price", "unit price", "mrp", "selling price"],
    "amount": ["amount", "total", "net amount", "line total", "value", "bill amount"],
    "payment_mode": ["payment mode", "payment", "mode", "pay mode", "payment type"],
}


@dataclass
class Config:
    business_name: str = "My Business"
    currency_symbol: str = "₹"
    column_aliases: dict[str, list[str]] = field(
        default_factory=lambda: {k: list(v) for k, v in DEFAULT_COLUMN_ALIASES.items()}
    )
    # Map of official product name -> spellings seen in exports.
    product_aliases: dict[str, list[str]] = field(default_factory=dict)
    drop_duplicates: bool = True
    # If |amount - qty*rate| is larger than this (in currency units), flag it.
    amount_tolerance: float = 1.0
    top_n_products: int = 10

    def alias_lookup(self) -> dict[str, str]:
        """normalised header text -> canonical field name."""
        lookup: dict[str, str] = {}
        for canonical, aliases in self.column_aliases.items():
            for alias in [canonical, *aliases]:
                lookup[normalise_header(alias)] = canonical
        return lookup

    def product_lookup(self) -> dict[str, str]:
        """normalised product spelling -> official product name."""
        lookup: dict[str, str] = {}
        for official, spellings in self.product_aliases.items():
            for s in [official, *spellings]:
                lookup[normalise_key(s)] = official
        return lookup


def normalise_header(text: Any) -> str:
    """'  Bill_Date. ' -> 'bill date'"""
    s = str(text).strip().lower()
    for ch in "_.:-/()":
        s = s.replace(ch, " ")
    return " ".join(s.split())


def normalise_key(text: Any) -> str:
    """Case/spacing-insensitive key used to match product spellings."""
    s = str(text).lower()
    for ch in "()[]-_,.":
        s = s.replace(ch, " ")
    # "1 kg" and "1kg" should match
    s = "".join(s.split())
    return s


def load_config(source: str | Path | dict | None = None) -> Config:
    """Load a Config from a YAML path, a YAML string, a dict, or defaults."""
    if source is None:
        return Config()

    if isinstance(source, dict):
        raw = source
    else:
        text = Path(source).read_text(encoding="utf-8") if _looks_like_path(source) else str(source)
        try:
            raw = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"Settings file is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Settings file must contain key: value pairs at the top level.")

    unknown = set(raw) - set(Config.__dataclass_fields__)
    if unknown:
        raise ConfigError(f"Unknown setting(s): {', '.join(sorted(unknown))}")

    cfg = Config()
    if "business_name" in raw:
        cfg.business_name = _require_str(raw, "business_name")
    if "currency_symbol" in raw:
        cfg.currency_symbol = _require_str(raw, "currency_symbol")
    if "column_aliases" in raw:
        aliases = _require_mapping_of_lists(raw, "column_aliases")
        bad = set(aliases) - set(CANONICAL_FIELDS)
        if bad:
            raise ConfigError(
                f"column_aliases has unknown field(s): {', '.join(sorted(bad))}. "
                f"Allowed: {', '.join(CANONICAL_FIELDS)}"
            )
        # Client aliases extend the defaults rather than replacing them.
        for key, values in aliases.items():
            cfg.column_aliases[key] = list(dict.fromkeys([*values, *cfg.column_aliases[key]]))
    if "product_aliases" in raw:
        cfg.product_aliases = _require_mapping_of_lists(raw, "product_aliases")
    if "drop_duplicates" in raw:
        if not isinstance(raw["drop_duplicates"], bool):
            raise ConfigError("drop_duplicates must be true or false.")
        cfg.drop_duplicates = raw["drop_duplicates"]
    if "amount_tolerance" in raw:
        val = raw["amount_tolerance"]
        if not isinstance(val, (int, float)) or isinstance(val, bool) or val < 0:
            raise ConfigError("amount_tolerance must be a number >= 0.")
        cfg.amount_tolerance = float(val)
    if "top_n_products" in raw:
        val = raw["top_n_products"]
        if not isinstance(val, int) or isinstance(val, bool) or not 1 <= val <= 50:
            raise ConfigError("top_n_products must be a whole number between 1 and 50.")
        cfg.top_n_products = val
    return cfg


def _looks_like_path(source: str | Path) -> bool:
    if isinstance(source, Path):
        return True
    return "\n" not in source and source.strip().lower().endswith((".yaml", ".yml"))


def _require_str(raw: dict, key: str) -> str:
    val = raw[key]
    if not isinstance(val, str) or not val.strip():
        raise ConfigError(f"{key} must be non-empty text.")
    return val.strip()


def _require_mapping_of_lists(raw: dict, key: str) -> dict[str, list[str]]:
    val = raw[key] or {}
    if not isinstance(val, dict):
        raise ConfigError(f"{key} must be a mapping of name -> list of spellings.")
    out: dict[str, list[str]] = {}
    for k, v in val.items():
        if isinstance(v, str):
            v = [v]
        if not isinstance(v, list) or not all(isinstance(x, (str, int, float)) for x in v):
            raise ConfigError(f"{key}.{k} must be a list of text values.")
        out[str(k)] = [str(x) for x in v]
    return out
