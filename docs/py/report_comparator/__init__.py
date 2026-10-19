"""Compare two tabular reports and explain exactly where they differ."""

from .compare import ComparisonResult, ReportError, compare_reports, load_report
from .render import render_markdown

__all__ = [
    "ComparisonResult",
    "ReportError",
    "compare_reports",
    "load_report",
    "render_markdown",
]
__version__ = "0.1.0"
