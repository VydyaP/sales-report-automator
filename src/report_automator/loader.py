"""Reading Excel/CSV exports and finding the real table inside them.

Billing software often puts a title, store address or date range above the
actual column headers. Instead of assuming the header is on row 1, we scan
the first rows and pick the one that best matches the known column names.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from .config import REQUIRED_FIELDS, Config, normalise_header
from .errors import InputFileError
from .parsing import is_blank

HEADER_SCAN_ROWS = 15
SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xlsm")
MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB is far beyond a small shop's monthly export


@dataclass
class LoadedFile:
    name: str
    rows: pd.DataFrame  # canonical columns + _source_file + _source_row
    header_row: int  # 1-based row number in the original file
    mapping: dict[str, str]  # canonical field -> original header text
    ignored_columns: list[str] = field(default_factory=list)
    sheet: str | None = None


def load_file(source: str | Path | BinaryIO, config: Config, name: str | None = None) -> LoadedFile:
    """Load one CSV/Excel file from a path or an uploaded file object."""
    display_name = name or _name_of(source)
    ext = Path(display_name).suffix.lower()
    if ext == ".xls":
        raise InputFileError(
            f"{display_name}: old .xls format is not supported. "
            "Open it in Excel and use 'Save As' -> .xlsx, then try again."
        )
    if ext not in SUPPORTED_EXTENSIONS:
        raise InputFileError(
            f"{display_name}: unsupported file type '{ext or 'none'}'. "
            f"Use one of: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    data = _read_bytes(source, display_name)
    if not data.strip():
        raise InputFileError(f"{display_name}: the file is empty.")

    if ext == ".csv":
        sheets = {None: _read_csv(data, display_name)}
    else:
        sheets = _read_excel(data, display_name)

    lookup = config.alias_lookup()
    best_error: InputFileError | None = None
    for sheet_name, raw in sheets.items():
        if raw.empty:
            continue
        try:
            return _extract_table(raw, lookup, display_name, sheet_name)
        except InputFileError as exc:
            best_error = best_error or exc
    raise best_error or InputFileError(f"{display_name}: no data found in the file.")


def _name_of(source: str | Path | BinaryIO) -> str:
    if isinstance(source, (str, Path)):
        return Path(source).name
    return Path(getattr(source, "name", "uploaded_file")).name


def _read_bytes(source: str | Path | BinaryIO, display_name: str) -> bytes:
    try:
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.is_file():
                raise InputFileError(f"{display_name}: file not found at {path}.")
            if path.stat().st_size > MAX_FILE_BYTES:
                raise InputFileError(f"{display_name}: file is larger than 25 MB.")
            return path.read_bytes()
        # Web uploads may be read more than once (the page re-runs), so
        # never depend on the current read position.
        if hasattr(source, "getvalue"):
            data = source.getvalue()
        else:
            if hasattr(source, "seek"):
                source.seek(0)
            data = source.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise InputFileError(f"{display_name}: file is larger than 25 MB.")
        return data
    except OSError as exc:
        raise InputFileError(f"{display_name}: could not read the file ({exc}).") from exc


def _read_csv(data: bytes, display_name: str) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 decodes anything
        raise InputFileError(f"{display_name}: could not decode the text.")
    try:
        return pd.read_csv(
            io.StringIO(text),
            header=None,
            dtype=object,
            sep=None,
            engine="python",
            skip_blank_lines=False,
            keep_default_na=False,
        )
    except (pd.errors.ParserError, ValueError) as exc:
        raise InputFileError(f"{display_name}: this does not look like a valid CSV file ({exc}).") from exc


def _read_excel(data: bytes, display_name: str) -> dict[str | None, pd.DataFrame]:
    try:
        return pd.read_excel(
            io.BytesIO(data), sheet_name=None, header=None, dtype=object, engine="openpyxl",
            keep_default_na=False,  # keep "N/A", "NA" etc. as typed so the issue log shows them
        )
    except Exception as exc:  # openpyxl raises a variety of types for corrupt files
        raise InputFileError(
            f"{display_name}: could not open as an Excel workbook. "
            "It may be corrupted or password-protected."
        ) from exc


def _extract_table(
    raw: pd.DataFrame, lookup: dict[str, str], display_name: str, sheet: str | None
) -> LoadedFile:
    header_idx, mapping_by_col = _find_header(raw, lookup)
    if header_idx is None:
        found = [str(v) for v in raw.iloc[0].tolist() if not is_blank(v)]
        raise InputFileError(
            f"{display_name}: could not find the column headers. "
            f"Expected columns like Date, Product and Amount; first row has: {', '.join(found[:8]) or 'nothing'}. "
            "If your columns use different names, add them to the settings file under column_aliases."
        )

    mapped_fields = set(mapping_by_col.values())
    missing = [f for f in REQUIRED_FIELDS if f not in mapped_fields]
    if missing:
        header_text = [str(v) for v in raw.iloc[header_idx].tolist() if not is_blank(v)]
        raise InputFileError(
            f"{display_name}: missing required column(s): {', '.join(missing)}. "
            f"Columns found: {', '.join(header_text)}. "
            "Add the matching names to column_aliases in the settings file."
        )

    body = raw.iloc[header_idx + 1 :]
    rows = pd.DataFrame(index=body.index)
    original_headers = raw.iloc[header_idx]
    mapping: dict[str, str] = {}
    for col, canonical in mapping_by_col.items():
        rows[canonical] = body[col]
        mapping[canonical] = str(original_headers[col]).strip()
    rows["_source_file"] = display_name
    rows["_source_row"] = [int(i) + 1 for i in body.index]  # 1-based, matches Excel row numbers

    ignored = [
        str(original_headers[c]).strip()
        for c in raw.columns
        if c not in mapping_by_col and not is_blank(original_headers[c])
    ]
    return LoadedFile(
        name=display_name,
        rows=rows.reset_index(drop=True),
        header_row=header_idx + 1,
        mapping=mapping,
        ignored_columns=ignored,
        sheet=str(sheet) if sheet is not None else None,
    )


def _find_header(raw: pd.DataFrame, lookup: dict[str, str]) -> tuple[int | None, dict[int, str]]:
    """Return (row index, {column index: canonical field}) of the best header row."""
    best_idx, best_map = None, {}
    for idx in range(min(HEADER_SCAN_ROWS, len(raw))):
        row_map: dict[int, str] = {}
        for col, value in raw.iloc[idx].items():
            if is_blank(value):
                continue
            canonical = lookup.get(normalise_header(value))
            # First column wins if two columns map to the same field.
            if canonical and canonical not in row_map.values():
                row_map[col] = canonical
        if len(row_map) >= 2 and len(row_map) > len(best_map):
            best_idx, best_map = idx, row_map
    return best_idx, best_map
