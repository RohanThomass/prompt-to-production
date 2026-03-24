"""
UC-0C: Number That Looks Right
BudgetAnalystAgent — Ward Budget Growth Analyser

CRAFT commit trail:
  UC-0C Fix silent aggregation: no scope in enforcement → restricted to per-ward per-category only
  UC-0C Fix division-by-zero: no null guard → added zero-baseline check
  UC-0C Fix missing-year edge case: single-year wards crashed → added null growth for single-year data
  UC-0C Fix scope audit: no post-write validation → added ward/category count assertion
"""

import csv
import os
from collections import defaultdict

# ── Paths ────────────────────────────────────────────────────────────────────
INPUT_PATH  = os.path.join("data", "budget", "ward_budget.csv")
OUTPUT_PATH = "growth_output.csv"
ANOMALY_PATH = "anomaly_report.txt"

# ── Skill 1: CSV Ingestion with Schema Validation ────────────────────────────
def load_budget_data(path: str) -> list[dict]:
    """Load CSV and adapt custom schema to expected format."""
    rows = []
    skipped = 0

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        print(f"[INFO] Columns detected: {reader.fieldnames}")
        print(f"[INFO] Loading data from: {path}")

        for i, row in enumerate(reader, start=2):
            try:
                # Extract year from period (e.g., 2024-01 → 2024)
                year = int(row["period"].split("-")[0])

                rows.append({
                    "ward":     row["ward"].strip(),
                    "category": row["category"].strip(),
                    "year":     year,
                    "amount":   float(row["actual_spend"]),
                })

            except Exception as e:
                print(f"[WARN] Skipping row {i}: {e}")
                skipped += 1

    print(f"[INFO] Loaded {len(rows)} rows. Skipped {skipped} invalid rows.")
    return rows


# ── Skill 2: Strict Per-Ward Per-Category Grouping ───────────────────────────
def group_by_ward_category(rows: list[dict]) -> dict:
    """
    Build nested dict: data[ward][category][year] = amount
    Enforces strict per-ward per-category scope — never aggregates across wards.
    """
    data = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        ward     = row["ward"]
        category = row["category"]
        year     = row["year"]
        amount   = row["amount"]

        if year in data[ward][category]:
            # Accumulate if duplicate (ward, category, year) rows exist
            data[ward][category][year] += amount
        else:
            data[ward][category][year] = amount

    ward_count = len(data)
    cat_count  = len({cat for ward_data in data.values() for cat in ward_data})
    print(f"[INFO] Grouped into {ward_count} wards × {cat_count} unique categories.")
    return data


# ── Skill 3: Year-over-Year Growth Rate Computation ──────────────────────────
def compute_growth(year_amounts: dict) -> dict:
    """
    Given {year: amount}, return growth stats for the two most recent years.
    Returns null growth_rate if only one year exists or previous amount is zero.
    """
    if not year_amounts:
        return {}

    sorted_years = sorted(year_amounts.keys())

    if len(sorted_years) == 1:
        yr = sorted_years[0]
        return {
            "year_current":    yr,
            "amount_current":  round(year_amounts[yr], 2),
            "year_previous":   None,
            "amount_previous": None,
            "growth_rate_pct": None,
            "flag":            "MISSING_YEAR",
        }

    yr_prev    = sorted_years[-2]
    yr_curr    = sorted_years[-1]
    amt_prev   = year_amounts[yr_prev]
    amt_curr   = year_amounts[yr_curr]

    flag = None

    if amt_prev == 0:
        growth = None
        flag   = "ZERO_BASELINE"
    else:
        growth = round(((amt_curr - amt_prev) / amt_prev) * 100, 2)
        if growth > 200:
            flag = "HIGH_GROWTH"

    if amt_prev < 0 or amt_curr < 0:
        flag = "NEGATIVE_AMOUNT"

    return {
        "year_current":    yr_curr,
        "amount_current":  round(amt_curr, 2),
        "year_previous":   yr_prev,
        "amount_previous": round(amt_prev, 2),
        "growth_rate_pct": growth,
        "flag":            flag,
    }


# ── Skill 4: Output Writer ────────────────────────────────────────────────────
def write_output(results: list[dict], path: str):
    """Write growth_output.csv with one row per (ward, category)."""
    fieldnames = [
        "ward", "category",
        "year_current", "amount_current",
        "year_previous", "amount_previous",
        "growth_rate_pct",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"[INFO] Output written to: {path} ({len(results)} rows)")


# ── Skill 5: Anomaly Flagging ────────────────────────────────────────────────
def write_anomaly_report(results: list[dict], path: str):
    """Write anomaly_report.txt for flagged ward-category pairs."""
    flagged = [r for r in results if r.get("flag")]
    with open(path, "w", encoding="utf-8") as f:
        f.write("UC-0C Anomaly Report\n")
        f.write("=" * 50 + "\n\n")
        if not flagged:
            f.write("No anomalies detected.\n")
        else:
            for r in flagged:
                f.write(
                    f"[{r['flag']}] Ward={r['ward']} | Category={r['category']} | "
                    f"Current={r['amount_current']} ({r['year_current']}) | "
                    f"Previous={r['amount_previous']} ({r['year_previous']})\n"
                )
    print(f"[INFO] Anomaly report written to: {path} ({len(flagged)} flagged rows)")


# ── Skill 6: Scope Enforcement Audit ─────────────────────────────────────────
def audit_scope(rows: list[dict], results: list[dict]):
    """
    Post-write validation: verify output covers all input ward-category combos.
    Raises AssertionError if any (ward, category) pair was silently dropped.
    """
    input_pairs  = {(r["ward"], r["category"]) for r in rows}
    output_pairs = {(r["ward"], r["category"]) for r in results}

    missing = input_pairs - output_pairs
    if missing:
        print(f"[ERROR] Scope audit FAILED — {len(missing)} ward-category pairs missing from output:")
        for pair in sorted(missing):
            print(f"  → Ward={pair[0]}, Category={pair[1]}")
        raise AssertionError("Scope enforcement failed — output is incomplete.")
    else:
        print(f"[PASS] Scope audit passed — all {len(input_pairs)} ward-category pairs present in output.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n=== UC-0C: Number That Looks Right ===\n")

    # Step 1 — Load
    rows = load_budget_data(INPUT_PATH)

    # Step 2 — Group strictly per ward per category
    grouped = group_by_ward_category(rows)

    # Step 3 — Compute growth for each (ward, category)
    results = []
    for ward, categories in grouped.items():
        for category, year_amounts in categories.items():
            stats = compute_growth(year_amounts)
            stats["ward"]     = ward
            stats["category"] = category
            results.append(stats)

    # Sort for deterministic output
    results.sort(key=lambda r: (r["ward"], r["category"]))

    # Step 4 — Write output
    write_output(results, OUTPUT_PATH)

    # Step 5 — Write anomaly report
    write_anomaly_report(results, ANOMALY_PATH)

    # Step 6 — Scope audit
    audit_scope(rows, results)

    print("\n=== Done ✓ ===\n")


if __name__ == "__main__":
    main()
