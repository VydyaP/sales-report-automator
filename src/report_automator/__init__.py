"""Sales Report Automator: messy sales exports in, clean report out."""

from .config import Config, load_config
from .errors import ConfigError, InputFileError, NoValidRowsError, ReportError
from .pipeline import ReportResult, run_report

__all__ = [
    "Config",
    "ConfigError",
    "InputFileError",
    "NoValidRowsError",
    "ReportError",
    "ReportResult",
    "load_config",
    "run_report",
]

__version__ = "1.0.0"
