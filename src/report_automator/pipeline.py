"""One entry point used by both the command line and the web page:
files in -> clean data, summary, Excel bytes and PDF bytes out."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Union

from .cleaner import CleanResult, clean
from .config import Config
from .errors import InputFileError
from .excel_writer import build_workbook
from .loader import load_file
from .pdf_writer import build_pdf
from .summarize import Summary, summarise

# A source is a path, or (display name, file-like object) for uploads.
Source = Union[str, Path, tuple[str, BinaryIO]]


@dataclass
class ReportResult:
    cleaned: CleanResult
    summary: Summary
    excel_bytes: bytes
    pdf_bytes: bytes
    excel_path: Path | None = None
    pdf_path: Path | None = None

    @property
    def base_name(self) -> str:
        return report_base_name(self.summary)


def run_report(sources: Iterable[Source], config: Config, out_dir: str | Path | None = None) -> ReportResult:
    sources = list(sources)
    if not sources:
        raise InputFileError("No input files were given.")

    loaded = []
    seen_names: set[str] = set()
    for src in sources:
        if isinstance(src, tuple):
            name, fileobj = src
            lf = load_file(fileobj, config, name=name)
        else:
            lf = load_file(src, config)
        if lf.name in seen_names:
            raise InputFileError(f"{lf.name}: the same file name was given twice.")
        seen_names.add(lf.name)
        loaded.append(lf)

    cleaned = clean(loaded, config)
    summary = summarise(cleaned, config)

    buf = io.BytesIO()
    build_workbook(cleaned, summary).save(buf)
    result = ReportResult(cleaned, summary, buf.getvalue(), build_pdf(cleaned, summary))

    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        result.excel_path = out / f"{result.base_name}.xlsx"
        result.pdf_path = out / f"{result.base_name}.pdf"
        result.excel_path.write_bytes(result.excel_bytes)
        result.pdf_path.write_bytes(result.pdf_bytes)
    return result


def report_base_name(summary: Summary) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", summary.business_name.lower()).strip("-") or "sales"
    start = summary.period_start.strftime("%Y-%m-%d")
    end = summary.period_end.strftime("%Y-%m-%d")
    return f"{slug}_sales-report_{start}_to_{end}"
