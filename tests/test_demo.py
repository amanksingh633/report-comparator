"""The GitHub Pages demo ships copies of the package; keep them honest."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"


def _load_web_entry():
    """Load docs/py/web_entry.py by path so the shipped package copy never shadows src/."""
    spec = importlib.util.spec_from_file_location("web_entry", DOCS / "py" / "web_entry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


web_entry = _load_web_entry()


def test_demo_package_matches_source():
    for name in ("__init__.py", "compare.py", "render.py"):
        shipped = (DOCS / "py" / "report_comparator" / name).read_text(encoding="utf-8")
        source = (ROOT / "src" / "report_comparator" / name).read_text(encoding="utf-8")
        assert shipped == source, (
            f"docs/py/report_comparator/{name} is stale: run scripts/sync_demo.py"
        )


def test_demo_sample_data_matches_source():
    for name in ("baseline.csv", "candidate.csv"):
        shipped = (DOCS / "sample" / name).read_bytes()
        source = (ROOT / "sample_data" / name).read_bytes()
        assert shipped == source, f"docs/sample/{name} is stale: run scripts/sync_demo.py"


def _run(**overrides):
    args = {
        "baseline_csv": (DOCS / "sample" / "baseline.csv").read_text(encoding="utf-8"),
        "candidate_csv": (DOCS / "sample" / "candidate.csv").read_text(encoding="utf-8"),
        "keys": "invoice_id",
        "abs_tol": 0.01,
        "rel_tol": 0,
        "ignore": "generated_at",
    }
    args.update(overrides)
    return json.loads(web_entry.run_comparison(**args))


def test_web_entry_reports_the_planted_differences():
    out = _run()
    s = out["summary"]
    assert s["passed"] is False
    assert (s["missing_in_candidate"], s["extra_in_candidate"]) == (2, 2)
    assert (s["mismatched_rows"], s["mismatched_cells"]) == (3, 3)
    assert out["by_column"] == {"status": 1, "tax": 1, "total": 1}
    assert {m["column"] for m in out["mismatches"]} == {"total", "tax", "status"}
    assert "FAIL" in out["markdown"]


def test_web_entry_passes_identical_input():
    text = "id,v\n1,a\n2,b\n"
    out = _run(baseline_csv=text, candidate_csv=text, keys="id", ignore="")
    assert out["summary"]["passed"] is True
    assert out["mismatches"] == []


def test_web_entry_turns_bad_input_into_an_error_message():
    assert "not found" in _run(keys="nope")["error"]
    assert "error" in _run(baseline_csv="")
    dup = "id,v\n1,a\n1,b\n"
    assert "duplicate" in _run(baseline_csv=dup, candidate_csv=dup, keys="id", ignore="")["error"]
