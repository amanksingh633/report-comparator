import pandas as pd
import pytest

from report_comparator import ReportError, compare_reports, render_markdown
from report_comparator.cli import main


def frame(**cols):
    return pd.DataFrame(cols)


def test_identical_reports_pass():
    df = frame(id=[1, 2], amount=[10.0, 20.0])
    result = compare_reports(df, df.copy(), ["id"])
    assert result.passed
    assert result.mismatched_cells == 0
    assert result.rows_compared == 2


def test_detects_value_mismatch_with_delta():
    a = frame(id=[1, 2], amount=[10.0, 20.0])
    b = frame(id=[1, 2], amount=[10.0, 25.5])
    result = compare_reports(a, b, ["id"])
    assert not result.passed
    assert result.mismatched_cells == 1
    row = result.mismatches.iloc[0]
    assert row["id"] == 2 and row["column"] == "amount"
    assert row["delta"] == pytest.approx(5.5)


def test_absolute_tolerance_absorbs_float_noise():
    a = frame(id=[1], amount=[100.00])
    b = frame(id=[1], amount=[100.004])
    assert not compare_reports(a, b, ["id"]).passed
    assert compare_reports(a, b, ["id"], abs_tol=0.01).passed


def test_relative_tolerance():
    a = frame(id=[1], amount=[1000.0])
    b = frame(id=[1], amount=[1000.9])
    assert compare_reports(a, b, ["id"], rel_tol=0.001).passed
    assert not compare_reports(a, b, ["id"], rel_tol=0.0001).passed


def test_missing_and_extra_rows():
    a = frame(id=[1, 2, 3], v=["a", "b", "c"])
    b = frame(id=[2, 3, 4], v=["b", "c", "d"])
    result = compare_reports(a, b, ["id"])
    assert result.missing_in_candidate["id"].tolist() == [1]
    assert result.extra_in_candidate["id"].tolist() == [4]
    assert result.rows_compared == 2
    assert not result.passed


def test_null_handling():
    a = frame(id=[1, 2, 3], v=[None, "x", None])
    b = frame(id=[1, 2, 3], v=[None, None, "y"])
    result = compare_reports(a, b, ["id"])
    assert sorted(result.mismatches["id"].tolist()) == [2, 3]


def test_whitespace_is_ignored_by_default_but_can_be_strict():
    a = frame(id=[1], name=["Acme"])
    b = frame(id=[1], name=["Acme  "])
    assert compare_reports(a, b, ["id"]).passed
    assert not compare_reports(a, b, ["id"], strip_strings=False).passed


def test_numeric_strings_compare_as_numbers():
    a = frame(id=[1], amount=[10])
    b = frame(id=[1], amount=["10.0"])
    assert compare_reports(a, b, ["id"]).passed


def test_ignore_columns():
    a = frame(id=[1], ts=["t1"], v=[1])
    b = frame(id=[1], ts=["t2"], v=[1])
    assert not compare_reports(a, b, ["id"]).passed
    assert compare_reports(a, b, ["id"], ignore_columns=["ts"]).passed


def test_schema_differences_fail_the_gate():
    a = frame(id=[1], v=[1], old=[1])
    b = frame(id=[1], v=[1], new=[1])
    result = compare_reports(a, b, ["id"])
    assert result.columns_only_in_baseline == ["old"]
    assert result.columns_only_in_candidate == ["new"]
    assert not result.passed


def test_composite_keys():
    a = frame(region=["N", "N", "S"], month=[1, 2, 1], v=[1, 2, 3])
    b = frame(region=["N", "N", "S"], month=[1, 2, 1], v=[1, 9, 3])
    result = compare_reports(a, b, ["region", "month"])
    assert result.mismatches[["region", "month"]].values.tolist() == [["N", 2]]


def test_duplicate_keys_are_rejected():
    a = frame(id=[1, 1], v=[1, 2])
    with pytest.raises(ReportError, match="duplicate keys"):
        compare_reports(a, a, ["id"])


def test_unknown_key_is_rejected():
    a = frame(id=[1], v=[1])
    with pytest.raises(ReportError, match="not found"):
        compare_reports(a, a, ["nope"])


def test_markdown_contains_verdict_and_counts():
    a = frame(id=[1, 2], amount=[1.0, 2.0])
    b = frame(id=[1, 2], amount=[1.0, 3.0])
    md = render_markdown(compare_reports(a, b, ["id"]))
    assert "FAIL" in md and "Mismatched cells" in md and "amount" in md
    assert "PASS" in render_markdown(compare_reports(a, a, ["id"]))


def test_cli_exit_codes_on_sample_data(tmp_path, capsys):
    from pathlib import Path

    data = Path(__file__).parent.parent / "sample_data"
    base, cand = str(data / "baseline.csv"), str(data / "candidate.csv")

    assert main([base, base, "-k", "invoice_id"]) == 0
    assert main([base, cand, "-k", "invoice_id"]) == 1
    assert main([base, "missing.csv", "-k", "invoice_id"]) == 2

    out = tmp_path / "report.md"
    main(
        [base, cand, "-k", "invoice_id", "-i", "generated_at", "--abs-tol", "0.01", "-o", str(out)]
    )
    text = out.read_text(encoding="utf-8")
    assert "Missing in candidate | 2" in text
    assert "Extra in candidate | 2" in text
    assert "Mismatched rows / cells | 3 / 3" in text
