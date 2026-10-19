"""Core comparison logic: diff two tabular reports keyed on one or more columns."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


class ReportError(ValueError):
    """Raised when the inputs cannot be compared (bad keys, duplicate keys, ...)."""


@dataclass
class ComparisonResult:
    """Everything a reviewer needs to decide whether two report runs agree."""

    keys: list[str]
    rows_baseline: int
    rows_candidate: int
    rows_compared: int
    missing_in_candidate: pd.DataFrame
    extra_in_candidate: pd.DataFrame
    mismatches: pd.DataFrame
    columns_compared: list[str]
    columns_only_in_baseline: list[str] = field(default_factory=list)
    columns_only_in_candidate: list[str] = field(default_factory=list)

    @property
    def mismatched_cells(self) -> int:
        return len(self.mismatches)

    @property
    def mismatched_rows(self) -> int:
        if self.mismatches.empty:
            return 0
        return len(self.mismatches[self.keys].drop_duplicates())

    @property
    def passed(self) -> bool:
        """True only when the two reports are equivalent under the chosen tolerances."""
        return (
            self.missing_in_candidate.empty
            and self.extra_in_candidate.empty
            and self.mismatches.empty
            and not self.columns_only_in_baseline
            and not self.columns_only_in_candidate
        )

    def column_mismatch_counts(self) -> pd.Series:
        """Mismatched cell count per column, largest first."""
        if self.mismatches.empty:
            return pd.Series(dtype="int64", name="mismatches")
        counts = self.mismatches["column"].value_counts()
        counts.name = "mismatches"
        return counts

    def summary(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "rows_baseline": self.rows_baseline,
            "rows_candidate": self.rows_candidate,
            "rows_compared": self.rows_compared,
            "missing_in_candidate": len(self.missing_in_candidate),
            "extra_in_candidate": len(self.extra_in_candidate),
            "mismatched_rows": self.mismatched_rows,
            "mismatched_cells": self.mismatched_cells,
            "columns_compared": len(self.columns_compared),
            "columns_only_in_baseline": list(self.columns_only_in_baseline),
            "columns_only_in_candidate": list(self.columns_only_in_candidate),
        }


def load_report(path: str | Path, sheet: str | int = 0) -> pd.DataFrame:
    """Load a CSV or Excel report into a DataFrame."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet)
    raise ReportError(f"Unsupported file type '{suffix}' (use .csv or .xlsx)")


def compare_reports(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    keys: Sequence[str],
    *,
    abs_tol: float = 0.0,
    rel_tol: float = 0.0,
    ignore_columns: Iterable[str] = (),
    strip_strings: bool = True,
) -> ComparisonResult:
    """Compare ``candidate`` against ``baseline`` row by row, matched on ``keys``.

    Numeric cells match when ``|a - b| <= max(abs_tol, rel_tol * |a|)``. Two nulls
    match each other; a null against a value is a mismatch. Everything else is
    compared as text, after stripping surrounding whitespace if ``strip_strings``.
    """
    keys = list(keys)
    if not keys:
        raise ReportError("At least one key column is required")
    if abs_tol < 0 or rel_tol < 0:
        raise ReportError("Tolerances must be non-negative")

    ignore = set(ignore_columns)
    base = _prepare(baseline, keys, "baseline", strip_strings)
    cand = _prepare(candidate, keys, "candidate", strip_strings)

    shared = [c for c in base.columns if c in cand.columns and c not in ignore]
    only_base = [c for c in base.columns if c not in cand.columns and c not in ignore]
    only_cand = [c for c in cand.columns if c not in base.columns and c not in ignore]

    missing_idx = base.index.difference(cand.index)
    extra_idx = cand.index.difference(base.index)
    common = base.index.intersection(cand.index)

    left = base.loc[common, shared]
    right = cand.loc[common, shared]

    frames = []
    for col in shared:
        mask = _differs(left[col], right[col], abs_tol, rel_tol)
        if not mask.any():
            continue
        frame = pd.DataFrame(
            {"baseline": left[col][mask], "candidate": right[col][mask]}
        ).reset_index()
        frame.insert(len(keys), "column", col)
        frame["delta"] = _delta(frame["baseline"], frame["candidate"])
        frames.append(frame)

    if frames:
        mismatches = pd.concat(frames, ignore_index=True).sort_values(keys + ["column"])
        mismatches = mismatches.reset_index(drop=True)
    else:
        mismatches = pd.DataFrame(columns=keys + ["column", "baseline", "candidate", "delta"])

    return ComparisonResult(
        keys=keys,
        rows_baseline=len(base),
        rows_candidate=len(cand),
        rows_compared=len(common),
        missing_in_candidate=missing_idx.to_frame(index=False),
        extra_in_candidate=extra_idx.to_frame(index=False),
        mismatches=mismatches,
        columns_compared=shared,
        columns_only_in_baseline=only_base,
        columns_only_in_candidate=only_cand,
    )


def _prepare(df: pd.DataFrame, keys: list[str], label: str, strip: bool) -> pd.DataFrame:
    absent = [k for k in keys if k not in df.columns]
    if absent:
        raise ReportError(f"Key column(s) {absent} not found in {label} report")

    out = df.copy()
    if strip:
        for col in out.columns:
            if out[col].dtype == object or pd.api.types.is_string_dtype(out[col]):
                out[col] = out[col].map(lambda v: v.strip() if isinstance(v, str) else v)

    dupes = out.duplicated(subset=keys, keep=False)
    if dupes.any():
        example = out.loc[dupes, keys].iloc[0].to_dict()
        raise ReportError(
            f"{label} report has {int(dupes.sum())} rows with duplicate keys, e.g. {example}"
        )
    return out.set_index(keys)


def _as_numeric(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series] | None:
    """Return numeric versions of both series, or None if they are not both numeric."""
    if pd.api.types.is_bool_dtype(a) or pd.api.types.is_bool_dtype(b):
        return None
    if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
        return a, b
    na, nb = pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")
    if na.isna().sum() == a.isna().sum() and nb.isna().sum() == b.isna().sum():
        return na, nb
    return None


def _differs(a: pd.Series, b: pd.Series, abs_tol: float, rel_tol: float) -> pd.Series:
    both_null = a.isna() & b.isna()
    one_null = a.isna() ^ b.isna()

    numeric = _as_numeric(a, b)
    if numeric is not None:
        na, nb = numeric
        limit = (na.abs() * rel_tol).clip(lower=abs_tol)
        unequal = (na - nb).abs() > limit
    else:
        unequal = a.astype(str) != b.astype(str)

    return (unequal & ~both_null & ~one_null) | one_null


def _delta(baseline: pd.Series, candidate: pd.Series) -> pd.Series:
    numeric = _as_numeric(baseline, candidate)
    if numeric is None:
        return pd.Series(float("nan"), index=baseline.index, dtype="float64")
    na, nb = numeric
    return (nb - na).round(6)
