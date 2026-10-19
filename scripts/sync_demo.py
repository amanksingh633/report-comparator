"""Copy the package and sample data into docs/ so the GitHub Pages demo ships the real code.

Run after changing anything in src/ or sample_data/:  python scripts/sync_demo.py
tests/test_demo.py fails if docs/ drifts out of sync.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_FILES = ["__init__.py", "compare.py", "render.py"]  # the CLI is not needed in the browser


def main() -> None:
    pkg_dst = ROOT / "docs" / "py" / "report_comparator"
    pkg_dst.mkdir(parents=True, exist_ok=True)
    for name in PACKAGE_FILES:
        shutil.copyfile(ROOT / "src" / "report_comparator" / name, pkg_dst / name)

    sample_dst = ROOT / "docs" / "sample"
    sample_dst.mkdir(parents=True, exist_ok=True)
    for name in ("baseline.csv", "candidate.csv"):
        shutil.copyfile(ROOT / "sample_data" / name, sample_dst / name)
    print("docs/ synced")


if __name__ == "__main__":
    main()
