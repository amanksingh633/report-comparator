"""Generate the synthetic before/after invoice reports used by the demo and tests.

All data is randomly generated. Nothing here comes from a real company or customer.
Run:  python sample_data/generate.py
"""

import csv
import random
from pathlib import Path

HERE = Path(__file__).parent
FIELDS = ["invoice_id", "vendor", "trips", "base_amount", "tax", "total", "status", "generated_at"]
VENDORS = [
    "Northwind Fleet",
    "Blue Harbor Cabs",
    "Summit Rides",
    "Greenline Transport",
    "Orbit Mobility",
]


def build_baseline(n: int = 200) -> list[dict]:
    rng = random.Random(42)
    rows = []
    for i in range(1, n + 1):
        trips = rng.randint(20, 900)
        base = round(trips * rng.uniform(80, 140), 2)
        tax = round(base * 0.05, 2)
        rows.append(
            {
                "invoice_id": f"INV-{i:04d}",
                "vendor": rng.choice(VENDORS),
                "trips": trips,
                "base_amount": base,
                "tax": tax,
                "total": round(base + tax, 2),
                "status": "APPROVED",
                "generated_at": "2026-10-01 09:00:00",
            }
        )
    return rows


def build_candidate(baseline: list[dict]) -> list[dict]:
    rows = [dict(r, generated_at="2026-10-02 09:00:00") for r in baseline]

    # Float noise inside a 0.01 tolerance: should be ignored with --abs-tol 0.01
    for idx in (3, 17, 40):
        rows[idx]["total"] = round(rows[idx]["total"] + 0.004, 3)

    # Real regressions
    rows[10]["total"] = round(rows[10]["total"] + 125.50, 2)
    rows[55]["tax"] = round(rows[55]["tax"] * 1.1, 2)
    rows[90]["status"] = "PENDING"

    # Whitespace-only differences: ignored by default
    for idx in (5, 6):
        rows[idx]["vendor"] = rows[idx]["vendor"] + "  "

    # Two rows dropped, two rows added
    rows = [r for i, r in enumerate(rows) if i not in (120, 121)]
    for n in (201, 202):
        rows.append(
            {
                "invoice_id": f"INV-{n:04d}",
                "vendor": "Orbit Mobility",
                "trips": 100,
                "base_amount": 10000.0,
                "tax": 500.0,
                "total": 10500.0,
                "status": "APPROVED",
                "generated_at": "2026-10-02 09:00:00",
            }
        )
    return rows


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    base = build_baseline()
    write(HERE / "baseline.csv", base)
    write(HERE / "candidate.csv", build_candidate(base))
    print("wrote baseline.csv and candidate.csv")
