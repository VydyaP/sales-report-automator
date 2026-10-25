"""Errors shown to the person using the tool. Messages are written in plain
language because they appear directly in the web page and the terminal."""


class ReportError(Exception):
    """Base class for problems the user can fix."""


class ConfigError(ReportError):
    """The settings file is invalid."""


class InputFileError(ReportError):
    """An input file could not be read or understood."""


class NoValidRowsError(ReportError):
    """Every row was rejected, so there is nothing to report on."""
