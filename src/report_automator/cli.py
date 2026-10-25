"""Command line:

    sales-report sample_data/*.xlsx sample_data/*.csv --config configs/demo_store.yaml --out output/

Exit codes: 0 success, 1 nothing to report, 2 bad input or settings.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .cleaner import CHECK, FIXED
from .config import load_config
from .errors import ConfigError, InputFileError, NoValidRowsError
from .pipeline import run_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sales-report",
        description="Clean messy sales exports (Excel/CSV) and produce an Excel + PDF sales report.",
    )
    p.add_argument("files", nargs="+", type=Path, help="One or more .xlsx or .csv sales files")
    p.add_argument("-c", "--config", type=Path, help="Settings file (YAML). Optional.")
    p.add_argument("-o", "--out", type=Path, default=Path("output"), help="Folder for the reports (default: output)")
    p.add_argument("-q", "--quiet", action="store_true", help="Only print the output file paths")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config) if args.config else load_config()
        result = run_report(args.files, config, out_dir=args.out)
    except (ConfigError, InputFileError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except NoValidRowsError as exc:
        print(f"Nothing to report: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:  # e.g. missing settings file
        print(f"Error: file not found: {exc.filename}", file=sys.stderr)
        return 2

    if not args.quiet:
        c, s = result.cleaned, result.summary
        print(f"\n{s.business_name}  |  {s.period_label}\n")
        for label, value in s.kpis():
            print(f"  {label:<22} {value}")
        print("\nWhat stands out:")
        for line in s.insights:
            print(f"  - {line}")
        print(
            f"\nData quality: {c.rows_read:,} rows read, {c.rows_kept:,} used, {c.rows_removed:,} removed, "
            f"{c.count(FIXED):,} automatic corrections, {c.count(CHECK):,} to double-check."
        )
        print("\nReports written:")
    print(f"  {result.excel_path}")
    print(f"  {result.pdf_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
