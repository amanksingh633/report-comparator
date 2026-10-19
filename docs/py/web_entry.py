"""Browser entry point for the live demo (runs in Pyodide, also unit-tested with plain Python).

The page passes raw CSV text in and gets one JSON string back, so all comparison logic lives in
the real ``report_comparator`` package rather than being re-implemented in JavaScript.
"""

from __future__ import annotations

import io
import json

import pandas as pd

from report_comparator import compare_reports, render_markdown

MAX_ROWS = 500  # rows sent back to the page per table


def _split(text: str) -> list[str]:
    return [part.strip() for part in (text or "").split(",") if part.strip()]


def _records(df: pd.DataFrame) -> tuple[list[dict], bool]:
    shown = df.head(MAX_ROWS)
    return json.loads(shown.to_json(orient="records")), len(df) > MAX_ROWS


def run_comparison(
    baseline_csv: str,
    candidate_csv: str,
    keys: str,
    abs_tol: float = 0.0,
    rel_tol: float = 0.0,
    ignore: str = "",
) -> str:
    """Compare two CSV texts. Returns JSON with either ``error`` or the full result."""
    try:
        baseline = pd.read_csv(io.StringIO(baseline_csv))
        candidate = pd.read_csv(io.StringIO(candidate_csv))
        result = compare_reports(
            baseline,
            candidate,
            _split(keys),
            abs_tol=float(abs_tol or 0),
            rel_tol=float(rel_tol or 0),
            ignore_columns=_split(ignore),
        )
    except ValueError as exc:  # includes ReportError, parser and empty-input errors
        return json.dumps({"error": str(exc)})

    mismatches, m_cut = _records(result.mismatches)
    missing, miss_cut = _records(result.missing_in_candidate)
    extra, extra_cut = _records(result.extra_in_candidate)
    return json.dumps(
        {
            "summary": result.summary(),
            "keys": result.keys,
            "by_column": {str(k): int(v) for k, v in result.column_mismatch_counts().items()},
            "mismatches": mismatches,
            "missing": missing,
            "extra": extra,
            "truncated": m_cut or miss_cut or extra_cut,
            "markdown": render_markdown(result, max_rows=50),
        }
    )
