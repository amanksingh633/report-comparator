"""Render a ComparisonResult as a Markdown summary suitable for a PR or release note."""

from __future__ import annotations

import pandas as pd

from .compare import ComparisonResult


def _table(df: pd.DataFrame, max_rows: int) -> str:
    shown = df.head(max_rows)
    header = "| " + " | ".join(str(c) for c in shown.columns) + " |"
    divider = "|" + "|".join("---" for _ in shown.columns) + "|"
    rows = [
        "| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |"
        for row in shown.itertuples(index=False, name=None)
    ]
    lines = [header, divider, *rows]
    if len(df) > max_rows:
        lines.append(f"\n_Showing {max_rows} of {len(df)} rows._")
    return "\n".join(lines)


def render_markdown(result: ComparisonResult, max_rows: int = 20) -> str:
    s = result.summary()
    verdict = "PASS: reports match" if result.passed else "FAIL: reports differ"
    out = [
        f"# Report comparison: {verdict}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Key columns | {', '.join(result.keys)} |",
        f"| Rows in baseline / candidate | {s['rows_baseline']} / {s['rows_candidate']} |",
        f"| Rows compared | {s['rows_compared']} |",
        f"| Missing in candidate | {s['missing_in_candidate']} |",
        f"| Extra in candidate | {s['extra_in_candidate']} |",
        f"| Mismatched rows / cells | {s['mismatched_rows']} / {s['mismatched_cells']} |",
    ]

    if result.columns_only_in_baseline or result.columns_only_in_candidate:
        out += ["", "## Schema differences"]
        if result.columns_only_in_baseline:
            out.append(f"- Only in baseline: {', '.join(result.columns_only_in_baseline)}")
        if result.columns_only_in_candidate:
            out.append(f"- Only in candidate: {', '.join(result.columns_only_in_candidate)}")

    counts = result.column_mismatch_counts()
    if not counts.empty:
        out += ["", "## Mismatches by column", "", "| Column | Cells |", "|---|---|"]
        out += [f"| {col} | {n} |" for col, n in counts.items()]
        out += ["", "## Mismatched cells", "", _table(result.mismatches, max_rows)]

    if not result.missing_in_candidate.empty:
        out += ["", "## Missing in candidate", "", _table(result.missing_in_candidate, max_rows)]
    if not result.extra_in_candidate.empty:
        out += ["", "## Extra in candidate", "", _table(result.extra_in_candidate, max_rows)]

    return "\n".join(out) + "\n"
