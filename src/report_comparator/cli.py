"""Command line entry point. Exit code 0 = reports match, 1 = they differ, 2 = bad input.

That makes it usable as a release gate: run it in CI and fail the build on a diff.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compare import ReportError, compare_reports, load_report
from .render import render_markdown


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="report-comparator",
        description="Compare two CSV/Excel reports and list every difference.",
    )
    p.add_argument("baseline", type=Path, help="Known-good report (before the change)")
    p.add_argument("candidate", type=Path, help="Report to validate (after the change)")
    p.add_argument("-k", "--key", action="append", required=True, help="Key column (repeatable)")
    p.add_argument("--abs-tol", type=float, default=0.0, help="Absolute numeric tolerance")
    p.add_argument("--rel-tol", type=float, default=0.0, help="Relative numeric tolerance")
    p.add_argument(
        "-i", "--ignore", action="append", default=[], help="Column to ignore (repeatable)"
    )
    p.add_argument("--sheet", default=0, help="Excel sheet name or index (default: first)")
    p.add_argument("--max-rows", type=int, default=20, help="Rows shown per section")
    p.add_argument("-o", "--out", type=Path, help="Also write the Markdown report to this file")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        sheet = int(args.sheet) if str(args.sheet).isdigit() else args.sheet
        result = compare_reports(
            load_report(args.baseline, sheet),
            load_report(args.candidate, sheet),
            args.key,
            abs_tol=args.abs_tol,
            rel_tol=args.rel_tol,
            ignore_columns=args.ignore,
        )
    except (ReportError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = render_markdown(result, max_rows=args.max_rows)
    print(report)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
